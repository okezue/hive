import io, json, sys

import pytest
from mcp.client import Client

from hive.err import Anon, Bad, Clash
from hive.hook import handle, main
from hive.run import Runner, fill
from hive.srv import Who, build

from .conftest import nums


@pytest.fixture
def app(root):
    (root/'app.py').write_text(nums(20))
    return root/'app.py'


def testClaimDoesNotHideConcurrentChanges(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 3\n', 'new': 'B3\n'}])
    a.claim('app.py', 10, 12, 'mine')
    assert a.write('app.py', nums(20, l11='A11'))['status'] == 'merged' and app.read_text() == nums(20, l3='B3', l11='A11')


def testSyncOverlapWithUnseenChangeOpensRequest(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 3\nline 4\n', 'new': 'A\nB\n'}])
    app.write_text(nums(20, l3='A', l4='b2'))
    assert a.sync('app.py')['status'] == 'conflict' and app.read_text() == nums(20, l3='A', l4='B')


def testReadThroughHarnessMarksFileSeen(hive, team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 3\n', 'new': 'B3\n'}])
    handle('post', {'tool_name': 'Read', 'tool_input': {'file_path': str(app)}}, hive, a)
    app.write_text(nums(20, l3='C3'))
    assert a.sync('app.py')['status'] == 'committed'


def testPendingHarnessEditIsAttributedToItsAuthor(hive, team, app):
    a, b, c = team['alice'], team['bob'], team['coord']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 3\n', 'new': 'B3\n'}])
    handle('pre', {'tool_name': 'Write', 'tool_input': {'file_path': str(app)}}, hive, a)
    app.write_text(nums(20, l3='A3'))
    c.read('app.py')
    assert app.read_text() == nums(20, l3='B3') and hive.files.mrs.opened()[0].src == a.id


def testVerifierEditDeniedBeforeItHappens(hive, team, app):
    r = json.loads(handle('pre', {'tool_name': 'Edit', 'tool_input': {'file_path': str(app)}}, hive, team['vera']))
    assert r['hookSpecificOutput']['permissionDecision'] == 'deny'


def testStaleDiskIsRewritten(team, app):
    a = team['alice']
    a.read('app.py')
    a.edit('app.py', [{'old': 'line 3\n', 'new': 'x\n'}])
    app.write_text(nums(20))
    assert team['bob'].read('app.py')['version'] == 2 and app.read_text() == nums(20, l3='x')


def testHiveDirGuardIgnoresCase(team):
    with pytest.raises(Bad): team['alice'].write('.HIVE/config.toml', 'x')


def testPutAfterDrop(team):
    a = team['alice']
    a.put('k', 1)
    a.drop('k')
    assert a.put('k', 2)['version'] == 3 and a.get('k')['value'] == 2


def testRejectKeepsCurrentTaskPointer(team):
    c, a, v = team['coord'], team['alice'], team['vera']
    t1, t2 = (x['id'] for x in c.plan([{'title': 'one', 'verify': True}, {'title': 'two'}])['created'])
    a.take(t1)
    a.done(t1, 'r1')
    a.take(t2)
    v.take()
    v.verify(t1, False, 'broken')
    assert a.me()['task'] == t2
    a.done(t1, 'fixed')
    with pytest.raises(Clash, match='still on'): a.take()
    assert a.leave()[t2] == 'ready'


def testRejectAfterAuthorLeftFreesTask(team):
    c, a, v = team['coord'], team['alice'], team['vera']
    [t] = [x['id'] for x in c.plan([{'title': 'w', 'verify': True}])['created']]
    a.take(t)
    a.done(t, 'r')
    a.leave()
    v.take()
    assert v.verify(t, False, 'nope')['task']['state'] == 'ready'


def testVerificationLifecycle(team):
    c, a, v = team['coord'], team['alice'], team['vera']
    t, d = (x['id'] for x in c.plan([{'key': 'w', 'title': 'w', 'verify': True}, {'title': 'd', 'after': ['w']}])['created'])
    a.take(t)
    vt = a.done(t, 'r')['verification']
    v.take(vt)
    v.fail(vt, 'cannot run tests')
    states = {x['id']: x['state'] for x in c.tasks()['tasks']}
    assert states[t] == 'failed' and states[d] == 'blocked'
    [u] = [x['id'] for x in c.plan([{'title': 'u', 'verify': True}])['created']]
    a.take(u)
    vu = a.done(u, 'r')['verification']
    c.cancel(u, 'dropped')
    assert c.task(vu)['task']['state'] == 'cancelled'
    with pytest.raises(Clash): v.verify(vu, True, 'late')


def testDefaultKeysDoNotShadowTaskIds(team):
    c = team['coord']
    c.plan([{'title': 'a'}, {'title': 'b'}, {'title': 'c'}])
    [x] = c.plan([{'title': 'after t2', 'after': ['2']}])['created']
    assert x['after'] == ['t2']


def testProgressState(team):
    with pytest.raises(Bad): team['alice'].progress('bye', 'left')


def testFollowedUpdateFoundPastManyEvents(team, app):
    a, b = team['alice'], team['bob']
    b.read('app.py')
    for i in range(600): team['coord'].progress(f'noise {i}')
    a.read('app.py')
    a.edit('app.py', [{'old': 'line 1\n', 'new': 'one\n'}])
    assert b.hive.notice.pending(b.agent) and any('app.py' in u for u in b.notices()['updates'])


def testDigestPerScope(hive, team):
    w = hive.join('w', 'coordinator', 'alpha')
    w.digest()
    w.digest('session')
    team['alice'].progress('session news')
    w.digest()
    assert 'session news' in w.digest('session')['digest']


def testStrictIdentity(hive):
    who = Who(hive, strict=True)
    x = hive.join('alice')
    who.bind(x)
    with pytest.raises(Anon): who(None)
    with pytest.raises(Anon): who('alice')
    assert who(x.token).id == x.id


async def testHttpJoinNeedsKeyForPrivilegedRoles(hive, monkeypatch):
    monkeypatch.setenv('HIVE_KEY', 'sesame')
    async with Client(build(hive, strict=True)) as c:
        r = await c.call_tool('join', {'name': 'mallory', 'role': 'coordinator'})
        assert r.is_error and 'admin key' in r.content[0].text
        assert not (await c.call_tool('join', {'name': 'boss', 'role': 'coordinator', 'key': 'sesame'})).is_error
        assert not (await c.call_tool('join', {'name': 'dev'})).is_error
        assert (await c.call_tool('me', {})).is_error


def testEnvIdentityRetriesAfterFailure(hive, monkeypatch):
    hive.join('taken')
    monkeypatch.setenv('HIVE_AGENT_TOKEN', 'bogus')
    who = Who(hive)
    with pytest.raises(Anon): who(None)
    monkeypatch.setenv('HIVE_AGENT_TOKEN', hive.agents.named('taken').token)
    assert who(None).name == 'taken'


async def testStateDescriptions(hive):
    async with Client(build(hive)) as c:
        ts = {t.name: t.input_schema for t in (await c.list_tools()).tools}
    assert 'active' in ts['progress']['properties']['state']['description']
    assert 'abandoned' in ts['merges']['properties']['state']['description']
    assert 'in_review' in ts['tasks']['properties']['state']['description']


def testHookWithoutIdentityTouchesNothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for k in ('HIVE_AGENT', 'HIVE_AGENT_TOKEN', 'HIVE_DB'): monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr('sys.stdin', io.StringIO('{}'))
    assert main('post') == 0 and not (tmp_path/'.hive').exists()


def testFillIsSinglePass():
    v = dict.fromkeys(('promptFile', 'task', 'token', 'role', 'db', 'root', 'mcp'), 'x') | {'prompt': 'use {token}', 'agent': 'a'}
    assert fill('{prompt} {agent}', v) == 'use {token} a'


def testRunnerReleasesEveryTaskItsAgentHeld(hive, tmp_path):
    (p := tmp_path/'greedy.py').write_text(
        "import os\nfrom hive import Hive\nh = Hive.open(os.environ['HIVE_DB'], os.environ['HIVE_ROOT'])\n"
        "me, t = h.sess(os.environ['HIVE_AGENT_TOKEN']), os.environ['HIVE_TASK']\nme.take(t)\nme.done(t, 'ok')\nme.take()\n")
    hive.op().plan([{'title': 'first'}, {'title': 'second'}])
    r = Runner(hive, {'default': [sys.executable, str(p)]}, cap=1, poll=.05).run(60)
    assert r['counts'] == {'done': 2} and 'exited with code 0' in hive.tasks.get(2).notes[0]['failed']
