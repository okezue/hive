import json, os, shutil, subprocess, sys, textwrap, time, tomllib
from pathlib import Path

import pytest

from hive import Hive
from hive.cfg import locate
from hive.cli import main
from hive.err import Bad
from hive.harness import doctor, install, installed, uninstall
from hive.hook import main as hookMain
from hive.reg import alive, mine, nearest, reg
from hive.run import Runner
from hive.srv import claim

VENV = sys.executable
JOIN = textwrap.dedent('''
    import asyncio, json, os, sys
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters

    async def main():
        async with Client(StdioServerParameters(command=sys.argv[1], args=['-m', 'hive', 'mcp'], env=dict(os.environ), cwd=sys.argv[2])) as c:
            r = await c.call_tool('join', {'name': sys.argv[3], 'role': 'implementer'})
            assert not r.is_error, r.content[0].text

    asyncio.run(main())
''')


@pytest.fixture
def home(tmp_path, monkeypatch):
    (h := tmp_path/'userhome').mkdir()
    monkeypatch.setenv('HOME', str(h))
    for k in ('HIVE_DB', 'HIVE_ROOT', 'HIVE_AGENT', 'HIVE_AGENT_TOKEN', 'HIVE_SESSION'): monkeypatch.delenv(k, raising=False)
    return h


def proj(tmp_path, n):
    (d := tmp_path/n).mkdir()
    (d/'.git').mkdir()
    return d


def joined(tmp_path, d, name, via='join'):
    (s := tmp_path/f'{via}.py').write_text(JOIN)
    r = subprocess.run([VENV, str(s), VENV, str(d), name], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr


def testJoinBindsOnlyARealHarnessAndOnlyForItsProject(home, tmp_path):
    a, b = proj(tmp_path, 'a'), proj(tmp_path, 'b')
    joined(tmp_path, a, 'term')
    assert not reg().db.q('SELECT * FROM binds'), 'a plain parent process (a terminal or shell) must never be bound'
    joined(tmp_path, a, 'gk', via='grok')
    assert [r.harness for r in reg().db.q('SELECT * FROM binds')] == ['grok'] and Hive.open(a/'.hive'/'hive.db', a).agents.named('gk').harness == 'grok'
    Hive.open(b/'.hive'/'hive.db', b).close()
    r = reg()
    r.bind(os.getpid(), a/'.hive'/'hive.db', a, 'me', 'me.tok', 'grok')
    assert locate(cwd=b).db == b/'.hive'/'hive.db' and locate(cwd=a/'src').db == a/'.hive'/'hive.db'
    assert mine(cwd=b) is None and mine(cwd=a).agent == 'me'


def testOneHarnessKeepsItsFirstLiveAgent(hive, monkeypatch):
    monkeypatch.setattr('hive.srv.host', lambda: (os.getpid(), 'grok'))
    x1, x2 = hive.join('s1', 'implementer'), hive.join('s2', 'implementer')
    claim(hive, x1)
    claim(hive, x2)
    assert reg().holder(os.getpid()).agent == 's1'
    x1.leave()
    claim(hive, x2)
    assert reg().holder(os.getpid()).agent == 's2'


def testSessionEndAndDeletedHivesDropTheBinding(hive, root, capsys, monkeypatch):
    x = hive.join('cl', 'implementer')
    reg().bind(os.getpid(), hive.cfg.db, root, 'cl', x.token, 'claude')
    monkeypatch.setattr('sys.stdin', type('I', (), {'read': lambda s: '{}'})())
    hookMain('end')
    assert hive.agents.named('cl').state == 'left' and not reg().db.q('SELECT * FROM binds')
    hookMain('start', 'gemini')
    assert capsys.readouterr().out == ''
    (d := root.parent/'gone').mkdir()
    Hive.open(d/'.hive'/'hive.db', d).close()
    reg().bind(os.getpid(), d/'.hive'/'hive.db', d, 'z', 'z.tok', 'claude')
    shutil.rmtree(d)
    assert mine() is None
    hookMain('prompt')
    assert not d.exists() and capsys.readouterr() == ('', '')


def testDeadBindingsDoNotCostAProcessScan(home, monkeypatch):
    reg().bind(999999, '/nope/hive.db', '/nope', 'x', 'x.tok', 'claude', 'y')
    monkeypatch.setattr('hive.reg.chain', lambda *a: pytest.fail('scanned processes for a dead binding'))
    assert nearest(reg().db.q('SELECT * FROM binds')) is None


def testTomlWriterKeepsLookalikeTablesAndComments(home, root):
    (home/'.codex').mkdir()
    (c := home/'.codex'/'config.toml').write_text('[mcp_servers."hive.dev"]\ncommand = "dev"\n\n[mcp_servers.hive]\ncommand = "old"\n\n'
                                                   '[mcp_servers.hive.env]\nA = "1"\n\n# my github server, keep this comment\n[mcp_servers.github]\ncommand = "gh"\n')
    install('codex', 'user', root)
    uninstall('codex', 'user', root)
    t = c.read_text()
    assert tomllib.loads(t)['mcp_servers'] == {'hive.dev': {'command': 'dev'}, 'github': {'command': 'gh'}} and '# my github server' in t


def testWritersFollowSymlinksAndOddJson(home, root, tmp_path):
    (dot := tmp_path/'dotfiles').mkdir()
    (dot/'codex.toml').write_text('model = "o"\n')
    (home/'.codex').mkdir()
    (home/'.codex'/'config.toml').symlink_to(dot/'codex.toml')
    install('codex', 'user', root)
    assert (home/'.codex'/'config.toml').is_symlink() and 'hive' in tomllib.loads((dot/'codex.toml').read_text())['mcp_servers']
    (home/'.claude.json').write_text('{"mcpServers": null, "theme": "dark"}')
    install('claude', 'user', root, hooks=False)
    assert json.loads((home/'.claude.json').read_text())['theme'] == 'dark' and installed('claude', root) == 'user'
    (home/'.gemini').mkdir()
    (home/'.gemini'/'settings.json').write_text('{"theme": "x"}')
    install('gemini', 'user', root)
    baks = list((home/'.gemini').glob('settings.json.bak-*'))
    assert len(baks) == 1 and json.loads(baks[0].read_text()) == {'theme': 'x'}


def testHookCleanupSparesSimilarCommandsAndCarriesHiveHome(home, root):
    (root/'.claude').mkdir()
    (root/'.claude'/'settings.json').write_text(json.dumps({'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': '~/bin/beehive hook stop --notify'}]}]}}))
    install('claude', 'project', root)
    stop = json.loads((root/'.claude'/'settings.json').read_text())['hooks']['Stop']
    assert f"exec env HIVE_HOME={os.environ['HIVE_HOME']} " in stop[1]['hooks'][0]['command']
    assert json.loads((root/'.mcp.json').read_text())['mcpServers']['hive']['env'] == {'HIVE_HOME': os.environ['HIVE_HOME']}
    uninstall('claude', 'project', root)
    assert json.loads((root/'.claude'/'settings.json').read_text())['hooks']['Stop'][0]['hooks'][0]['command'] == '~/bin/beehive hook stop --notify'


def testPlansAndRunnersRejectHarnessesWithoutAHeadlessCommand(hive, root):
    (root/'.hive'/'config.toml').write_text('[harness.mine]\nchat = ["mine"]\n')
    h = Hive.open(root/'.hive'/'hive.db', root)
    with pytest.raises(Bad, match='no headless'): h.op().plan([{'title': 'x', 'harness': 'mine'}])
    with h.db.tx() as c: c.execute("INSERT INTO tasks(title,state,harness,ts) VALUES('sneaky','ready','mine',0)")
    said = []
    r = Runner(h, {'default': ['true']}, poll=.05, say=said.append).run(3)
    assert r['stuck'] == {'ready': 1} and any('cannot run t1 in mine' in x for x in said)


def testCliKeepsDashDashForOtherCommands(hive, root, capsys):
    hive.join('bob', 'implementer')
    assert main(['--db', str(root/'.hive'/'hive.db'), '--root', str(root), 'send', 'bob', '--', '-1 is the answer']) == 0
    assert hive.db.one("SELECT body FROM msgs ORDER BY id DESC LIMIT 1").body == '-1 is the answer'


def testInteractiveStartLeavesCtrlCToTheHarness(home, root):
    Hive.open(root/'.hive'/'hive.db', root).close()
    code = 'import signal; print("SIGINT", signal.getsignal(signal.SIGINT))'
    (root/'.hive'/'config.toml').write_text(f'[harness.mine]\nchat = [{json.dumps(sys.executable)}, "-c", {json.dumps(code)}]\n')
    p = subprocess.run([sys.executable, '-m', 'hive', 'start', 'mine'], cwd=root, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and 'SIGINT' in p.stdout and 'SIG_IGN' not in p.stdout, p.stdout + p.stderr


SLOW = textwrap.dedent('''
    import os, sys, time
    from mcp.server.mcpserver import MCPServer
    from mcp.shared.exceptions import MCPError
    open(sys.argv[1], 'w').write(str(os.getpid()))
    s = MCPServer('slow')

    @s.tool()
    def nap() -> str:
        """Sleep a long time."""
        time.sleep(45)
        return 'awake'

    @s.tool()
    def charge(amount: int) -> str:
        """Charge once, then refuse."""
        open(sys.argv[2], 'a').write(f'charged {amount}\\n')
        raise MCPError(-32000, 'card declined')

    s.run('stdio')
''')


def gone(pid, secs=10):
    end = time.time()+secs
    while alive(pid) and time.time() < end: time.sleep(.2)
    return not alive(pid)


def testMountedErrorsRunOnceAndTimeoutsReapTheServer(hive, tmp_path):
    (srv := tmp_path/'slow.py').write_text(SLOW)
    pf, log = tmp_path/'pid', tmp_path/'charges.log'
    op = hive.op()
    op.mount('slow', sys.executable, [str(srv), str(pf), str(log)], timeout=3)
    r = op.call('slow.charge', {'amount': 100})
    assert r['state'] == 'error' and 'refused' in r['error'] and log.read_text().splitlines() == ['charged 100']
    t = time.time()
    r = op.call('slow.nap')
    assert r['state'] == 'error' and 'did not answer' in r['error'] and time.time()-t < 15
    assert gone(int(pf.read_text())), 'the timed-out server was left running'
    op.call('slow.charge', {'amount': 5})
    pid = int(pf.read_text())
    hive.close()
    assert gone(pid, 6), 'closing the hive left the mounted server running'


COUNT = textwrap.dedent('''
    import os, sys
    from mcp.server.mcpserver import MCPServer
    open(sys.argv[1], 'w').write(str(os.getpid()))
    s, n = MCPServer('count'), [0]

    @s.tool()
    def count() -> str:
        """Count calls on this connection."""
        n[0] += 1
        return f'call {n[0]}'

    s.run('stdio')
''')


def testMountReconnectsAfterTheServerDies(hive, tmp_path):
    (srv := tmp_path/'count.py').write_text(COUNT)
    op = hive.op()
    op.mount('ct', sys.executable, [str(srv), str(tmp_path/'pid')])
    assert op.call('ct.count')['result'] == 'call 1'
    os.kill(int((tmp_path/'pid').read_text()), 9)
    assert gone(int((tmp_path/'pid').read_text()))
    r = op.call('ct.count')
    if r['state'] == 'error': r = op.call('ct.count')
    assert r == r | {'state': 'done', 'result': 'call 1'}, r


def testHookUnbindsQuietlyWhenTheHiveWasReset(hive, root, capsys, monkeypatch):
    x = hive.join('cl', 'implementer')
    reg().bind(os.getpid(), hive.cfg.db, root, 'cl', 'stale.token', 'claude')
    monkeypatch.setattr('sys.stdin', type('I', (), {'read': lambda s: '{}'})())
    assert hookMain('prompt') == 0 and capsys.readouterr() == ('', '') and not reg().db.q('SELECT * FROM binds')
    assert x.agent.state != 'left'


def testTomlKeepsTrailingCommentsAfterHive(home, root):
    (home/'.grok').mkdir()
    (c := home/'.grok'/'config.toml').write_text('[mcp_servers.rlm]\ncommand = "rlm"\n\n[mcp_servers.hive]\ncommand = "old"\n\n# TODO re-enable later:\n'
                                                 '# [mcp_servers.disabled]\n')
    install('grok', 'user', root, hooks=False)
    assert '# TODO re-enable later:\n# [mcp_servers.disabled]' in c.read_text()
    uninstall('grok', 'user', root)
    assert c.read_text().rstrip().endswith('# TODO re-enable later:\n# [mcp_servers.disabled]') and 'hive' not in tomllib.loads(c.read_text())['mcp_servers']


def testHolderIgnoresReusedPidsAndRelativeHomesAreResolved(home, root, monkeypatch):
    with reg().db.tx() as c: c.execute('INSERT INTO binds VALUES(?,?,?,?,?,?,?,?)', (os.getpid(), '1.000000', str(root), str(root), 'old', 'old.t', 'grok', 0))
    assert reg().holder(os.getpid()) is None
    monkeypatch.chdir(root)
    monkeypatch.setenv('HIVE_HOME', '.hh')
    install('codex', 'user', root)
    assert tomllib.loads((home/'.codex'/'config.toml').read_text())['mcp_servers']['hive']['env'] == {'HIVE_HOME': str((root/'.hh').resolve())}


def testHarnessDetectionSkipsInterpreterFlags(monkeypatch):
    from hive import reg as r
    monkeypatch.setattr(r, 'args', lambda p: 'node --max-old-space-size=4096 --stack-size=984 "/opt/my tools/gemini" --yolo')
    assert r.script(1) == 'gemini'
    monkeypatch.setattr(r, 'args', lambda p: 'python3 /tmp/unrelated.py grok')
    assert r.script(1) == ''


def testStaleReadersCannotClearTheBoundMarker(hive, root):
    x = hive.join('m', 'implementer')
    stale = []
    reg().bind(os.getpid(), hive.cfg.db, root, 'm', x.token, 'grok')
    assert (Path(os.environ['HIVE_HOME'])/'bound').exists()
    assert nearest(stale) is None and (Path(os.environ['HIVE_HOME'])/'bound').exists(), 'a reader with an old snapshot cleared the marker'
    reg().unbind(token=x.token)
    assert not (Path(os.environ['HIVE_HOME'])/'bound').exists()


def testHookCommandsNeverReferenceUnsetVariables(home, root):
    import re
    install('grok', 'user', root)
    cmds = [h['command'] for gs in json.loads((home/'.grok'/'hooks'/'hive.json').read_text())['hooks'].values() for g in gs for h in g['hooks']]
    assert cmds and all(not re.search(r'\$(?!\{[A-Z_]+:-\})', c) for c in cmds), 'grok skips hooks whose $VAR is unset; use ${VAR:-}'
    r = subprocess.run(['sh', '-c', cmds[0]], input='{}', text=True, capture_output=True, env={'PATH': os.environ['PATH'], 'HOME': str(home)})
    assert r.returncode == 0 and r.stdout == r.stderr == ''


def testDoctorSeesAUserInstallFromTheHomeFolder(home):
    install('grok', 'user', home)
    assert installed('grok', home) == 'user'
    d = doctor('grok', home, native=False)
    assert d['installed'] == 'user' and d['hooks'] == 'user' and 'trust' not in d and d['ok'], d
