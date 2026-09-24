import asyncio, json, os, subprocess, sys, textwrap, tomllib

import pytest
from mcp.client import Client

from hive import Hive
from hive.cli import main
from hive.err import Err
from hive.harness import GE, doctor, install, installed, servers, uninstall
from hive.hook import handle
from hive.reg import WRAP, chain, host, mine, reg
from hive.run import Runner
from hive.srv import build

STRIP = textwrap.dedent('''
    import asyncio, json, os, subprocess, sys
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters

    env = {k: v for k, v in os.environ.items() if not k.startswith('HIVE_') or k in ('HIVE_HOME', 'HIVE_GLOBAL')}

    async def main():
        async with Client(StdioServerParameters(command=sys.executable, args=['-m', 'hive', 'mcp'], env=env, cwd=os.getcwd())) as c:
            async def call(n, **a):
                r = await c.call_tool(n, a)
                if r.is_error: raise SystemExit(f'{n}: {r.content[0].text}')
                return json.loads(r.content[0].text.split('\\n-----')[0])
            me = await call('me')
            if len(sys.argv) > 1 and sys.argv[1] == 'task':
                t = await call('take')
                await call('done', id=t['task']['id'], result=f"{me['name']} finished without any HIVE_ variables")
                return
            await call('note', text=f"{me['name']} saw a prompt ending in {sys.argv[-1][-5:]!r}")
            open('x.txt', 'a').write(f"line from {me['name']}\\n")
            p = subprocess.run([sys.executable, '-m', 'hive', 'hook', 'post'], text=True, capture_output=True, env=env,
                               input=json.dumps({'tool_name': 'Write', 'tool_input': {'file_path': 'x.txt'}, 'cwd': os.getcwd()}))
            print(json.dumps({'me': me['name'], 'hook': p.stderr}))

    asyncio.run(main())
''')

LAZY = textwrap.dedent('''
    import asyncio, json, os, sys
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters

    async def main():
        async with Client(StdioServerParameters(command=sys.executable, args=['-m', 'hive', 'mcp'], env=dict(os.environ), cwd=sys.argv[1])) as c:
            assert 'mount' in [t.name for t in (await c.list_tools()).tools] and not os.path.exists(os.path.join(sys.argv[2], '.hive'))
            r = await c.call_tool('join', {'name': 'solo', 'role': 'implementer'})
            assert not r.is_error, r.content[0].text
            print((await c.call_tool('me', {})).content[0].text.replace('\\n', ' '))

    asyncio.run(main())
''')

CALC = textwrap.dedent('''
    from mcp.server.mcpserver import MCPServer
    s, n = MCPServer('calc'), [0]

    @s.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @s.tool()
    def count() -> str:
        """Count calls on this connection."""
        n[0] += 1
        return f'call {n[0]}'

    @s.tool()
    def boom() -> str:
        """Always fails."""
        raise ValueError('boom')

    s.run('stdio')
''')


@pytest.fixture
def home(tmp_path, monkeypatch):
    (h := tmp_path/'userhome').mkdir()
    monkeypatch.setenv('HOME', str(h))
    for k in ('HIVE_DB', 'HIVE_ROOT', 'HIVE_AGENT', 'HIVE_AGENT_TOKEN', 'HIVE_SESSION'): monkeypatch.delenv(k, raising=False)
    return h


def parsed(n, p): return tomllib.loads(p.read_text()) if p.suffix == '.toml' else json.loads(p.read_text())


def testInstallWritesEveryHarnessAndKeepsTheRest(home, root):
    (home/'.grok').mkdir()
    (home/'.grok'/'config.toml').write_text('# mine\nmodel = "x"\n\n[mcp_servers.rlm]\ncommand = "rlm"\n\n[mcp_servers.rlm.env]\nK = "v"\n\n'
                                           '[mcp_servers.hive]\ncommand = "old"\n\n[mcp_servers.hive.env]\nHIVE_DB = "/old"\n\n[ui]\ntheme = "night"\n')
    (root/'.claude').mkdir()
    (root/'.mcp.json').write_text(json.dumps({'mcpServers': {'db': {'command': 'dbmcp'}}}))
    (root/'.claude'/'settings.json').write_text(json.dumps({'hooks': {'PostToolUse': [{'hooks': [{'type': 'command', 'command': 'lint'}]},
                                                                                     {'hooks': [{'type': 'command', 'command': '/x/bin/hive hook post'}]}]}}))
    for n, sc in (('grok', 'user'), ('claude', 'project'), ('codex', 'user'), ('gemini', 'user'), ('cursor', 'project'), ('opencode', 'user')):
        ch = install(n, sc, root)
        assert ch and installed(n, root) == sc and servers(n, root, sc)['hive']['args'][-3 if sc == 'project' else -1:][0] == 'mcp', n
        assert install(n, sc, root) == [], f'{n} install is not idempotent'
    g = tomllib.loads((home/'.grok'/'config.toml').read_text())
    assert g['model'] == 'x' and g['mcp_servers']['rlm'] == {'command': 'rlm', 'env': {'K': 'v'}} and g['ui']['theme'] == 'night'
    assert g['mcp_servers']['hive']['args'][-1] == 'mcp' and g['mcp_servers']['hive']['env'] == {'HIVE_HOME': os.environ['HIVE_HOME']}
    assert (home/'.grok'/'config.toml').read_text().startswith('# mine') and list((home/'.grok').glob('config.toml.bak-*'))
    hooks = json.loads((home/'.grok'/'hooks'/'hive.json').read_text())['hooks']
    assert set(hooks) == {'SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'Stop', 'SessionEnd'} and 'matcher' not in hooks['Stop'][0]
    c = json.loads((root/'.claude'/'settings.json').read_text())['hooks']['PostToolUse']
    assert [h['command'] for g2 in c for h in g2['hooks']] == ['lint', c[1]['hooks'][0]['command']] and c[1]['hooks'][0]['command'].endswith('hook post')
    assert json.loads((root/'.mcp.json').read_text())['mcpServers']['db'] == {'command': 'dbmcp'}
    assert json.loads((root/'.claude'/'settings.local.json').read_text())['enabledMcpjsonServers'] == ['hive']
    assert tomllib.loads((home/'.codex'/'config.toml').read_text())['mcp_servers']['hive']['tool_timeout_sec'] == 1000
    assert 'SessionEnd' not in json.loads((home/'.codex'/'hooks.json').read_text())['hooks']
    gm = json.loads((home/'.gemini'/'settings.json').read_text())
    assert set(gm['hooks']) == {e for e, _, _ in GE} and gm['hooks']['AfterTool'][0]['hooks'][0]['command'].endswith('--format gemini')
    assert gm['hooks']['AfterTool'][0]['hooks'][0]['timeout'] == 30000 and gm['mcpServers']['hive']['timeout'] == 1000000
    assert json.loads((home/'.config'/'opencode'/'opencode.json').read_text())['mcp']['hive']['command'][-1] == 'mcp'
    assert json.loads((root/'.cursor'/'mcp.json').read_text())['mcpServers']['hive']['args'][-2:] == ['--dir', str(root)]
    for n, sc in (('grok', 'user'), ('claude', 'project'), ('codex', 'user'), ('gemini', 'user')):
        uninstall(n, sc, root)
        assert not installed(n, root), n
    g = tomllib.loads((home/'.grok'/'config.toml').read_text())
    assert 'hive' not in g['mcp_servers'] and g['mcp_servers']['rlm']['env'] == {'K': 'v'} and not (home/'.grok'/'hooks'/'hive.json').exists()
    c = json.loads((root/'.claude'/'settings.json').read_text())['hooks']['PostToolUse']
    assert [h['command'] for g2 in c for h in g2['hooks']] == ['lint'] and 'hooks' not in json.loads((home/'.gemini'/'settings.json').read_text())


def testInstallRefusesToClobberBrokenConfigs(home, root):
    (home/'.gemini').mkdir()
    (home/'.gemini'/'settings.json').write_text('{"mcpServers": {,}')
    with pytest.raises(Err, match='not plain JSON'): install('gemini', 'user', root)
    assert (home/'.gemini'/'settings.json').read_text() == '{"mcpServers": {,}'
    (home/'.codex').mkdir()
    (home/'.codex'/'config.toml').write_text('[mcp_servers]\nhive = { command = "x" }\n')
    with pytest.raises(Err, match='safely'): install('codex', 'user', root)
    assert (home/'.codex'/'config.toml').read_text() == '[mcp_servers]\nhive = { command = "x" }\n'


def testDoctorHandshakesWithTheConfiguredServer(home, root):
    install('grok', 'project', root)
    d = doctor('grok', root, native=False)
    assert d['server'].startswith('answers with') and 'trust' in d and not d['ok'] and not (root/'.hive').exists()
    install('codex', 'user', root)
    d = doctor('codex', root, native=False)
    assert d['ok'] and d['installed'] == 'user' and d['hooks'] == 'user', d


def testRegistryFindsTheHarnessThroughProcessAncestry(home, root):
    Hive.open(root/'.hive'/'hive.db', root).close()
    r = reg()
    r.bind(os.getpid(), root/'.hive'/'hive.db', root, 'alice', 'alice.tok', 'grok')
    code = 'from hive.reg import mine; b = mine(); print(b.agent, b.harness)'
    out = subprocess.run([sys.executable, '-c', f'import subprocess, sys; subprocess.run([sys.executable, "-c", {code!r}])'], capture_output=True, text=True)
    assert out.stdout.split() == ['alice', 'grok'], out.stderr
    with r.db.tx() as c: c.execute("UPDATE binds SET at='Thu Jan  1 00:00:00 1970'")
    assert mine() is None
    up = chain()
    assert up[0][0] == os.getpid() and host()[0] in [q for q, _ in up[1:]] and host()[1] not in WRAP


def testMcpFindsItsProjectLazilyAndBindsTheHarness(home, tmp_path):
    (proj := tmp_path/'proj').mkdir()
    (proj/'.git').mkdir()
    (sub := proj/'src'/'deep').mkdir(parents=True)

    (g := tmp_path/'grok.py').write_text(LAZY)
    r = subprocess.run([sys.executable, str(g), str(sub), str(proj)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    me, b = json.loads(r.stdout.splitlines()[-1]), reg().db.q('SELECT * FROM binds')
    assert me['name'] == 'solo' and (proj/'.hive'/'hive.db').exists() and (proj/'.hive'/'.gitignore').read_text().startswith('*')
    assert [(x.agent, x.harness, x.root) for x in b] == [('solo', 'grok', str(proj))]
    ls = subprocess.run([sys.executable, '-m', 'hive', 'ls', '--json'], capture_output=True, text=True)
    got = json.loads(ls.stdout)
    assert [h['name'] for h in got] == ['proj'] and got[0]['agents'][0]['name'] == 'solo', ls.stderr
    assert subprocess.run([sys.executable, '-m', 'hive', '-H', 'proj', 'status'], capture_output=True, text=True).stdout.startswith(str(proj))


def testStartRunsAnyHarnessInTheSharedHive(home, root, tmp_path):
    (f := tmp_path/'fake.py').write_text(STRIP)
    Hive.open(root/'.hive'/'hive.db', root).close()
    (root/'.hive'/'config.toml').write_text(f'[harness.fake]\nrun = [{json.dumps(sys.executable)}, {json.dumps(str(f))}, "{{prompt}}"]\n')
    p = subprocess.run([sys.executable, '-m', 'hive', 'start', 'fake', 'please', 'wave', '-p'], cwd=root, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout.strip().splitlines()[-1])
    h = Hive.open(root/'.hive'/'hive.db', root)
    a = h.agents.named('fake')
    assert out['me'] == 'fake' and a.harness == 'fake' and a.state == 'left' and not out['hook']
    assert 'wave' in h.db.one('SELECT text FROM findings WHERE agent=?', (a.id,)).text
    assert h.db.one("SELECT agent,origin FROM vers WHERE path='x.txt' ORDER BY v DESC") == {'agent': a.id, 'origin': 'sync'}
    assert not reg().db.q('SELECT * FROM binds')
    p = subprocess.run([sys.executable, '-m', 'hive', 'start', 'fake', '-p'], cwd=root, capture_output=True, text=True)
    assert p.returncode == 2 and 'needs a prompt' in p.stderr


def testRunnerStartsTasksInTheirHarness(home, root, tmp_path):
    (f := tmp_path/'fake.py').write_text(STRIP)
    Hive.open(root/'.hive'/'hive.db', root).close()
    (root/'.hive'/'config.toml').write_text(f'[harness.fake]\nrun = [{json.dumps(sys.executable)}, {json.dumps(str(f))}, "task"]\n')
    h = Hive.open(root/'.hive'/'hive.db', root)
    h.op().plan([{'title': 'tell me you ran', 'harness': 'fake'}])
    with pytest.raises(Err, match='unknown harness'): h.op().plan([{'title': 'x', 'harness': 'nope'}])
    r = Runner(h, {'default': ['false']}, poll=.1).run(90)
    t, a = h.tasks.get(1), h.agents.named('implementer-t1')
    logs = '\n'.join(p.read_text() for p in (h.cfg.dir/'run').glob('*.log'))
    assert r['counts'].get('done') == 1 and 'without any HIVE_' in t.result and a.harness == 'fake', logs


def testMountSharesAnMcpServerWithEveryone(home, root, tmp_path, hive):
    (calc := tmp_path/'calc.py').write_text(CALC)
    op, bob = hive.op(), hive.join('bob', 'implementer')
    with pytest.raises(Err, match='exec'): bob.mount('calc', sys.executable, [str(calc)])
    r = op.mount('calc', sys.executable, [str(calc)])
    assert sorted(r['tools']) == ['calc.add', 'calc.boom', 'calc.count']
    assert bob.call('calc.add', {'a': 2, 'b': 40})['result'] == '42'
    assert [bob.call('calc.count')['result'] for _ in range(2)] == ['call 1', 'call 2']
    e = bob.call('calc.boom')
    assert e['state'] == 'error' and 'boom' in e['error']
    assert bob.tools('add')['tools'][0]['kind'] == 'mcp' and bob.tools()['mounts'][0]['tools'] == 3
    hive.tools.pool.forget()
    assert bob.call('calc.count')['result'] == 'call 1'

    async def viaMcp():
        async with Client(build(hive)) as c:
            await c.call_tool('join', {'name': 'carol', 'role': 'researcher'})
            return json.loads((await c.call_tool('call', {'name': 'calc.add', 'args': {'a': 1, 'b': 1}})).content[0].text)

    assert asyncio.run(viaMcp())['result'] == '2'
    op.unmount('calc')
    with pytest.raises(Err, match='no shared tool'): bob.call('calc.add', {'a': 1, 'b': 1})
    with pytest.raises(Err, match='could not reach'): op.mount('ghost', sys.executable, ['-c', 'import sys; sys.exit(3)'], timeout=20)


def testMountFromAHarnessConfig(home, root, tmp_path, capsys):
    (calc := tmp_path/'calc.py').write_text(CALC)
    (home/'.grok').mkdir()
    (home/'.grok'/'config.toml').write_text(f'[mcp_servers.calc]\ncommand = {json.dumps(sys.executable)}\nargs = [{json.dumps(str(calc))}]\n'
                                           f'env = {{ TOKEN = "${{CALC_TOKEN}}" }}\n\n[mcp_servers.off]\ncommand = "x"\nenabled = false\n')
    install('grok', 'user', root)
    assert set(servers('grok', root)) == {'calc', 'hive'} and servers('grok', root)['calc']['env'] == {'TOKEN': '${CALC_TOKEN}'}
    base = ['--db', str(root/'.hive'/'hive.db'), '--root', str(root)]
    assert main([*base, 'mount', '--from', 'grok']) == 0 and 'calc: 3 tools' in capsys.readouterr().out
    assert main([*base, 'mount']) == 0 and 'calc' in capsys.readouterr().out
    h = Hive.open(root/'.hive'/'hive.db', root)
    assert json.loads(h.db.one("SELECT spec FROM mounts WHERE name='calc'").spec)['env'] == {'TOKEN': '${CALC_TOKEN}'}
    assert main([*base, 'mount', 'x', '--', sys.executable, str(calc)]) == 0 and '"x.add"' in capsys.readouterr().out
    assert main([*base, 'unmount', 'x']) == 0


def testHooksSpeakGeminiAndFindHiveToolsByServer(hive, root):
    x = hive.join('gem', 'implementer')
    hive.op().send('gem', 'stop and check the tests', 'interrupt')
    out = json.loads(handle('post', {'tool_name': 'run_shell_command', 'tool_input': {'command': 'ls'}}, hive, x, 'gemini'))
    assert out['hookSpecificOutput']['hookEventName'] == 'AfterTool' and 'INTERRUPT' in out['hookSpecificOutput']['additionalContext']
    assert 'decision' not in out
    stop = json.loads(handle('stop', {}, hive, x, 'gemini'))
    assert stop['decision'] == 'block' and 'interrupts' in stop['reason']
    n = hive.log.count(x.id)
    handle('post', {'tool_name': 'mcp_hive_me', 'mcp_context': {'server_name': 'hive'}, 'tool_input': {}}, hive, x, 'gemini')
    assert hive.log.count(x.id) == n
