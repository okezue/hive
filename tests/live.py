import asyncio, io, json, os, shutil, subprocess, sys, time
from pathlib import Path

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

import hive
import hive.build as build
import hive.harness as harness
import hive.hook as hook
import hive.live as live
from hive.cfg import NOLIMIT
from hive.run import Job, Runner
from hive.srv import build as server


def body(r): return json.loads(r.content[0].text.split('\n-----')[0])


def pids(home): return [int(p.stem) for p in (home/'live').glob('*.json') if p.stem.isdigit()]


async def testServerSwapsInNewHiveInPlaceAndKeepsTheSession(root, tmp_path):
    pkg, home = tmp_path/'pkg', Path(os.environ['HIVE_HOME'])
    shutil.copytree(Path(hive.__file__).parent, pkg/'hive', ignore=shutil.ignore_patterns('__pycache__'))
    p = StdioServerParameters(command=sys.executable, args=['-m', 'hive', '--db', str(root/'.hive'/'hive.db'), '--root', str(root), 'mcp'],
                              env={**os.environ, 'PYTHONPATH': str(pkg)}, cwd=str(tmp_path))
    async with Client(p) as c:
        names = {t.name for t in (await c.list_tools()).tools}
        assert 'hello' not in names and 'call' in names
        me = body(await c.call_tool('join', {'name': 'ann', 'role': 'coordinator'}))
        [pid] = pids(home)
        assert json.loads((home/'live'/f'{pid}.json').read_text())['resumed'] is False
        for f, a, b in (('util.py', "'core': 'me progress", "'core': 'hello me progress"),
                        ('srv.py', "\nPRIV = ", "\nDOCS['hello'] = 'Say hello'\nPRIV = "),
                        ('sess.py', '\n    def me(s):', "\n    def hello(s): return {'hello': s._me().name}\n\n    def me(s):")):
            (pkg/'hive'/f).write_text((pkg/'hive'/f).read_text().replace(a, b, 1))
        t0, seen = time.time(), []
        while time.time()-t0 < 90:
            r = await asyncio.gather(*[c.call_tool('me', {}) for _ in range(3)])
            assert not any(x.is_error for x in r), r[0].content[0].text
            seen += [json.loads(x.content[0].text.split('\n-----')[0]) for x in r]
            if json.loads((home/'live'/f'{pid}.json').read_text())['resumed']: break
            await asyncio.sleep(.05)
        assert pids(home) == [pid], 'the new version runs in the same process'
        r = body(await c.call_tool('me', {}))
        assert r['name'] == 'ann' and r['token'] == me['token'], 'the session kept its identity without joining again'
        got = body(await c.call_tool('call', {'name': 'hive.hello', 'args': {}}))
        assert got['hello'] == 'ann'
        told = [x['notices']['hiveUpdated'] for x in seen + [r, got] if 'hiveUpdated' in x.get('notices', {})]
        assert len(told) == 1 and 'lacks these Hive tools: hello' in told[0], 'the agent hears once which new tools its list lacks'
        bad = await c.call_tool('call', {'name': 'hive.hello', 'args': {'nope': 1}})
        assert bad.is_error and 'arguments do not match hive.hello' in bad.content[0].text
    assert all(x.get('name') == 'ann' for x in seen)


async def testCallReachesHiveToolsAndToolsListsThem(hive):
    async with Client(server(hive)) as c:
        tok = body(await c.call_tool('join', {'name': 'cal', 'role': 'coordinator'}))['token']
        call = lambda **k: c.call_tool('call', k | {'agent': tok})
        assert body(await call(name='hive.me'))['name'] == 'cal'
        assert body(await call(name='overview'))
        cat = body(await c.call_tool('tools', {'query': 'hive', 'agent': tok}))
        assert {'hive.host', 'hive.pulse', 'hive.call'} <= {x['name'] for x in cat['hive']}
        one = body(await c.call_tool('tools', {'query': 'hive.host', 'agent': tok}))['hive']
        assert one[0]['name'] == 'hive.host' and 'ended' in one[0]['args'] and 'cap' in one[0]['args']
        direct = body(await c.call_tool('pulse', {'agent': tok}))
        assert body(await call(name='pulse')).keys() == direct.keys()
        bob = body(await c.call_tool('join', {'name': 'bob', 'role': 'implementer'}))['token']
        await c.call_tool('offer', {'name': 'pulse', 'about': 'a shared tool that shadows a Hive tool name', 'agent': bob})
        assert body(await call(name='pulse', args={}, wait=0)).keys() != direct.keys(), 'a bare name that a shared tool uses stays the shared tool'
        assert body(await call(name='hive.pulse', args={})).keys() == direct.keys()
        assert (await call(name='hive.nothing')).is_error


def testHookRestartsAnOldServerOnceAndTellsTheModel(monkeypatch, capsys, tmp_path):
    (tmp_path/'hive').write_text('import time; time.sleep(120)')
    fake = subprocess.Popen([sys.executable, str(tmp_path/'hive'), 'mcp'])
    talk = subprocess.Popen(['sh', '-c', 'sleep 120', 'grep', '-m', 'hive', 'mcp'])
    try:
        time.sleep(.3)
        rows = {p: (pp, new) for p, pp, new in live.servers()}
        assert rows[fake.pid] == (os.getpid(), False) and talk.pid not in rows, 'only Python running Hive counts as a server'
        (u := live.home()/'upgrade').mkdir(parents=True)
        (u/str(os.getpid())).touch()
        monkeypatch.setattr(hook.os, 'getppid', os.getpid)
        monkeypatch.setattr(sys, 'stdin', io.StringIO('{"toolName":"run_terminal_command"}'))
        assert hook.main('post') == 0
        out = json.loads(capsys.readouterr().out)
        assert 'Transport closed' in out['hookSpecificOutput']['additionalContext']
        assert fake.wait(10) is not None and not (u/str(os.getpid())).exists()
        monkeypatch.setattr(sys, 'stdin', io.StringIO('{}'))
        assert hook.main('post') == 0 and capsys.readouterr().out == '', 'only once'
        assert talk.poll() is None, 'a process that only mentions hive mcp is left alone'
    finally:
        fake.kill()
        talk.kill()


def testGateLetsAMarkedSessionThrough(tmp_path):
    t = harness.GATE % {'marks': str(tmp_path/'bound'), 'hosting': str(tmp_path/'hosting'), 'up': str(tmp_path/'upgrade'),
                        'run': "sh -c 'echo ran' --"}
    (g := tmp_path/'gate').write_text(t)
    g.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith('HIVE_AGENT')}
    run = lambda: subprocess.run([str(g), 'post'], input='{}', capture_output=True, text=True, env=env).stdout
    assert run() == ''
    (tmp_path/'upgrade').mkdir()
    (tmp_path/'upgrade'/str(os.getpid())).touch()
    assert run() == 'ran\n'


def testNoAgentCountLimitsByDefault(hive):
    lead = hive.join('lead', 'coordinator')
    assert hive.cfg.fanout == 0 and lead.agent.budget == NOLIMIT
    [t] = lead.plan([{'title': 'big job'}])['created']
    lead.take(t['id'])
    kids = [lead.spawn(f'part {i}') for i in range(40)]
    assert len(kids) == 40 and 'no budget limit' in kids[-1]['prompt'] and hive.sess(kids[-1]['token']).agent.budget == NOLIMIT
    assert lead.agent.budget == NOLIMIT, 'an unlimited parent is not charged'


def testHostingIsPacedByMemoryAndTheHarnessLimit(hive, monkeypatch):
    co = hive.join('co', 'coordinator')
    co.plan([{'title': f'T{i}'} for i in range(9)])
    monkeypatch.setattr(build, 'total', lambda: 1000.)
    monkeypatch.setattr(build, 'free', lambda: 80.)
    r = co.host()
    assert len(r['start']) == 4 and r['hosting']['max'] == 'no limit', 'memory for four more: (80% - 20%) of 1000 MB at 150 MB each'
    assert co.host()['start'] == [] and 'free memory' in co.host()['held'], 'the four just handed out still count while they warm up'
    co.host(stop=True)
    monkeypatch.setattr(build, 'total', lambda: 10**6)
    monkeypatch.setattr(harness, 'subagents', lambda n, root='.': 6)
    assert len(co.host()['start']) == 2, "Grok's own subagent limit caps the total at six"


def testHarnessSubagentLimitComesFromGrokConfig(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    assert harness.subagents('grok', tmp_path) == 32 and harness.subagents('claude', tmp_path) is None
    (tmp_path/'.grok').mkdir()
    (tmp_path/'.grok'/'config.toml').write_text('[subagents]\nmax_concurrent = 72\n')
    assert harness.subagents('grok', tmp_path/'elsewhere') == 72


def testHostEndedRestartsAStoppedAgentWithoutHooks(hive, monkeypatch):
    monkeypatch.setattr(build, 'free', lambda: 80.)
    co = hive.join('co', 'coordinator')
    co.plan([{'title': 'A'}, {'title': 'B'}])
    a, b = co.host()['start']
    sa, sb = hive.sess(hive.agents.named(a['agent']).token), hive.sess(hive.agents.named(b['agent']).token)
    sa.take(sa.agent.deleg)
    sb.take(sb.agent.deleg)
    sb.done(sb.agent.deleg, result='did B')
    r = co.host(ended=[a['description'], b['agent'], 'nobody'])
    assert [x['agent'] for x in r['start']] == [a['agent']] and 'stopped before finishing' in r['start'][0]['prompt'] + json.dumps(hive.faults.show())
    assert hive.agents.named(b['agent']).state == 'left'


def testRunnerHoldsNewAgentsWhenMemoryIsShort(hive, monkeypatch):
    r, said = Runner(hive, {'default': ['true']}), []
    r.say = said.append
    assert r.cap == float('inf')
    monkeypatch.setattr(build, 'free', lambda: 80.)
    assert not r.full()
    r.jobs = {i: Job('x', i, 1, None, None, None, time.time()) for i in range(10**4)}
    assert r.full() and len(said) == 1, 'running agents still warming up count against free memory'
    r.jobs = {i: Job('x', i, 1, None, None, None, time.time()-61) for i in range(10)}
    assert not r.full(), 'agents past their first minute already show in free memory'
    r.jobs = {}
    assert not r.full()
    monkeypatch.setattr(build, 'free', lambda: 20.5)
    assert r.full() and r.full() and len(said) == 2 and 'free memory is 2' in said[1], 'it says so once each time it starts holding'
