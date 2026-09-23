import sys, textwrap, threading, time

import pytest

from hive.err import Bad, Clash, Denied, Missing
from hive.run import Runner


@pytest.fixture
def lead(hive):
    c = hive.join('lead', 'coordinator')
    [t] = c.plan([{'title': 'ship the feature'}])['created']
    c.take(t['id'])
    return c


def testSpawnHandsDownTaskBudgetAndPrompt(hive, lead):
    r = lead.spawn('write the parser', 'implementer', deliver='src/parse.py with tests', paths=['src/*'])
    kid = hive.sess(r['token'])
    assert r['agent'] == 'lead.impl1' and r['depth'] == 1 and r['budget'] == 15 and lead.agent.budget == 16
    assert kid.agent.state == 'pending' and r['path'] == 'lead/lead.impl1'
    t = lead.task(r['task'])['task']
    assert t['owner'] == 'lead.impl1' and t['parent'] == 't1' and t['deliver'] == 'src/parse.py with tests' and t['paths'] == ['src/*']
    for s in ('lead (coordinator)', 'Deliver: src/parse.py with tests', r['token'], "take('t2')", 'budget 15'): assert s in r['prompt']
    kid.take(r['task'])
    assert kid.agent.state == 'active'


def testRecursionDepthAndLimits(hive, lead):
    hive.cfg.depth = 2
    a = hive.sess(lead.spawn('part A', 'implementer')['token'])
    a.take()
    b = hive.sess(a.spawn('part A.1')['token'])
    assert b.agent.depth == 2 and hive.tree.path(b.id) == 'lead/lead.impl1/lead.impl1.impl1'
    b.take()
    with pytest.raises(Clash, match='depth 2'): b.spawn('too deep')
    hive.cfg.fanout = 1
    with pytest.raises(Clash, match='live children'): a.spawn('second child')


def testBudgetIsConservedAndReturned(hive, lead):
    before = lead.agent.budget
    r = lead.spawn('x', budget=5)
    assert lead.agent.budget == before-6
    with pytest.raises(Clash, match='budget'): lead.spawn('y', budget=1000)
    kid = hive.sess(r['token'])
    kid.take()
    kid.spawn('z', budget=2)
    assert kid.agent.budget == 2
    kid.leave()
    assert lead.agent.budget == before-2 and hive.db.one('SELECT SUM(budget) n FROM agents').n == before-2


def testCapabilitiesNarrowDownTheTree(hive, root):
    (root/'a.py').write_text('a\n')
    v = hive.join('vic', 'verifier')
    r = v.spawn('look around', 'implementer')
    assert 'write' in r['narrowed']
    kid = hive.sess(r['token'])
    kid.read('a.py')
    with pytest.raises(Denied, match='narrowed'): kid.edit('a.py', [{'old': 'a', 'new': 'b'}])
    with pytest.raises(Denied): v.spawn('x', 'implementer', grants=['write'])
    with pytest.raises(Denied): hive.join('obs', 'observer').spawn('x')


def testParentCannotFinishBeforeChildrenSettle(hive, lead):
    kid = hive.sess(lead.spawn('sub job')['token'])
    with pytest.raises(Clash, match='unsettled subtasks'): lead.done('t1', 'all done')
    kid.take()
    kid.done('t2', 'sub result')
    assert lead.done('t1', 'all done')['task']['state'] == 'done'


def testCancellationCascades(hive, lead):
    a = hive.sess(lead.spawn('a')['token'])
    a.take()
    b = hive.sess(a.spawn('b')['token'])
    b.take()
    lead.cancel('t1', 'scrapped')
    states = {t['id']: t['state'] for t in lead.tasks()['tasks']}
    assert states == {'t1': 'cancelled', 't2': 'cancelled', 't3': 'cancelled'}
    assert 'parent task' in b.notices()['interrupts'][0]['body']


def testGather(hive, lead):
    kids = [hive.sess(lead.spawn(f'piece {i}')['token']) for i in range(2)]

    def work(k, d):
        time.sleep(d)
        k.take()
        k.done(k.agent.deleg, f'{k.name} finished')

    for k, d in zip(kids, (.1, .6)): threading.Thread(target=work, args=(k, d)).start()
    first = lead.gather(any=True, secs=5)
    assert len(first['settled']) >= 1 and first['settled'][0]['result'].endswith('finished')
    r = lead.gather(secs=5)
    assert r['done'] and {x['agent'] for x in r['settled']} == {k.name for k in kids}
    assert lead.gather([kids[0].name], secs=0)['done'] and lead.agent.state == 'active'
    assert hive.join('solo').gather()['note'] == 'you have no delegated children'


def testCustodyMovesButLineageStays(hive, lead):
    a = hive.sess(lead.spawn('a', 'coordinator')['token'])
    a.take()
    a.put('style', 'tabs', 'node')
    b = hive.sess(a.spawn('b', 'implementer')['token'])
    a.leave('crashed')
    assert b.node('me')['keeper'] == 'lead' and b.path()['path'] == 'lead/lead.coor1/lead.coor1.impl1'
    assert b.get('style')['value'] == 'tabs' and b.get('style')['inherited']
    assert 'keeper is now lead' in b.notices()['messages'][0]['body'] and 'you now keep' in lead.notices()['messages'][-1]['body']


def testEscalateDecideAndPassUp(hive, lead):
    a = hive.sess(lead.spawn('a', 'coordinator', budget=4)['token'])
    a.take()
    b = hive.sess(a.spawn('b', budget=0)['token'])
    r = b.escalate('need more helpers', ['yes', 'no'], fund=2)
    assert r['holder'] == 'lead.coor1' and a.notices()['issuesWaitingOnYou'] == [r['issue']] and a.blockers()
    assert a.decide(r['issue'], 'up', 'my budget is small')['holder'] == 'lead'
    a.ack()
    with pytest.raises(Denied): hive.join('stranger').decide(r['issue'], 'no')
    out = lead.decide(r['issue'], 'yes', 'go ahead')
    assert out['funded'] == 2 and b.agent.budget == 2 and 'decided' in b.notices()['interrupts'][0]['body']
    assert b.issues()['issues'] == [] and not a.blockers()


def testNavigation(hive, lead):
    kids = [hive.sess(lead.spawn(f'goal {i}', 'implementer' if i else 'researcher', budget=1)['token']) for i in range(3)]
    kids[1].take()
    hive.sess(kids[1].spawn('deep dive into caching')['token'])
    t = lead.tree('me', depth=2, limit=2)['tree']
    assert t.splitlines()[0].startswith('lead · coordinator') and '└─ +1 more' in t and 'deep dive' in t
    n = lead.node('me')
    assert n['rollup']['below'] == 4 and n['rollup']['agents']['pending'] == 3 and len(n['children']) == 3
    assert lead.walk('down')['name'] == kids[0].name
    assert lead.walk('next')['name'] == kids[1].name
    assert lead.walk('down')['name'] == 'lead.impl1.impl1'
    assert lead.walk('up')['name'] == kids[1].name and lead.walk('prev')['name'] == kids[0].name
    assert lead.walk('root')['name'] == 'lead' and lead.node()['name'] == 'lead'
    with pytest.raises(Clash): lead.walk('up')
    p = lead.path('lead.impl1.impl1')
    assert [x['name'] for x in p['chain']] == ['lead', 'lead.impl1', 'lead.impl1.impl1'] and p['chain'][-1]['goal'] == 'deep dive into caching'
    assert [f['path'] for f in lead.find('caching')['found']] == ['lead/lead.impl1/lead.impl1.impl1']
    assert len(lead.find(role='implementer', within='lead')['found']) == 3
    assert lead.me()['name'] == 'lead'


def testNodePointsAtTrouble(hive, lead):
    a = hive.sess(lead.spawn('a')['token'])
    a.take()
    a.fail(a.agent.task, 'tests broke')
    n = lead.node('me')
    assert f'{a.name} needs attention (failed task)' in n['look']
    b = lead.brief('me', 300)
    assert any('tests broke' in x for x in b['blockers']) and a.name in b['summary']


def testLexicalContext(hive, lead):
    a, b = (hive.sess(lead.spawn(g)['token']) for g in ('a', 'b'))
    lead.put('rules', 'no globals', 'node')
    a.put('scratch', 'mine', 'node')
    a.put('plan', 'shared by the team', 'team')
    assert a.get('rules')['inherited'] and b.get('rules')['value'] == 'no globals'
    assert b.get('plan')['value'] == 'shared by the team'
    with pytest.raises(Missing): b.get('scratch')
    b.put('rules', 'b override', 'node')
    assert b.get('rules')['value'] == 'b override' and a.get('rules')['value'] == 'no globals'
    assert [k['scope'] for k in b.keys()['keys'] if k['key'] == 'rules'] == [f'node {b.name}']
    with pytest.raises(Bad): lead.put('x', 1, 'team')


def testFundAndAdopt(hive, lead):
    a = hive.sess(lead.spawn('a', budget=0)['token'])
    lead.fund(a.name, 3)
    assert a.agent.budget == 3
    with pytest.raises(Denied): a.fund('lead', 1)
    other = hive.join('other', 'implementer')
    with pytest.raises(Denied): other.adopt(a.name)
    assert lead.adopt(a.name)['keeper'] == 'lead'


AGENT = textwrap.dedent('''
    import os
    from hive import Hive
    h = Hive.open(os.environ['HIVE_DB'], os.environ['HIVE_ROOT'])
    me = h.sess(os.environ['HIVE_AGENT_TOKEN'])
    t = me.agent.deleg
    me.take(t)
    if me.agent.depth < 3:
        for part in ('first', 'second'): me.spawn(f'{part} half', launch='runner', budget=2 if me.agent.depth == 1 else 0)
        me.done(t, ' + '.join(x['result'] for x in me.gather(secs=80)['settled']))
    else: me.done(t, f'leaf {me.name}')
''')


def testRunnerGivesRealDepth(hive, tmp_path):
    (p := tmp_path/'agent.py').write_text(AGENT)
    top = hive.join('top', 'coordinator')
    top.spawn('the whole job', 'implementer', launch='runner', budget=10)
    r = Runner(hive, {'default': [sys.executable, str(p)]}, cap=2, poll=.05).run(120)
    assert r['stuck'] == {} and top.gather(secs=0)['settled'][0]['result'].count('leaf') == 4
    assert sorted(a.depth for a in hive.agents.all(gone=True) if a.name.startswith('top.')) == [1, 2, 2, 3, 3, 3, 3]


def testLeavingChildFailsItsDelegationAndTellsParent(hive, lead):
    kid = hive.sess(lead.spawn('a job')['token'])
    kid.take()
    kid.leave('giving up')
    assert lead.task('t2')['task']['state'] == 'failed' and 'failed' in lead.notices()['interrupts'][0]['body']
    assert lead.done('t1', 'handled without it')['task']['state'] == 'done'


def testRunnerRelaunchesSameIdentityThenFails(hive, tmp_path):
    (p := tmp_path/'crash.py').write_text("import os\nopen(os.environ['HIVE_ROOT']+'/runs', 'a').write(os.environ['HIVE_AGENT']+'\\n')\nraise SystemExit(3)\n")
    top = hive.join('top', 'coordinator')
    r = top.spawn('doomed', launch='runner', budget=0)
    Runner(hive, {'default': [sys.executable, str(p)]}, poll=.05).run(60)
    assert (hive.root/'runs').read_text().split() == [r['agent'], r['agent']]
    assert top.task(r['task'])['task']['state'] == 'failed' and 'failed' in top.notices()['interrupts'][0]['body']


def testDispatchedAgentsSitInTheTree(hive, lead):
    [t] = lead.plan([{'title': 'side quest', 'role': 'researcher'}])['created']
    d = lead.dispatch(t['id'])
    kid = hive.sess(d['token'])
    assert kid.agent.budget == 0 and kid.node('me')['task']['id'] == t['id']
    assert d['agent'] in lead.tree('me')['tree']


async def testTreeToolsOverMcp(hive):
    import json

    from mcp.client import Client

    from hive.srv import build
    async with Client(build(hive)) as c:
        assert {'spawn', 'gather', 'tree', 'node', 'walk', 'path', 'find', 'brief', 'escalate', 'decide'} <= {t.name for t in (await c.list_tools()).tools}
        tok = json.loads((await c.call_tool('join', {'name': 'boss', 'role': 'coordinator'})).content[0].text)['token']
        r = json.loads((await c.call_tool('spawn', {'goal': 'explore', 'role': 'researcher', 'agent': tok})).content[0].text)
        assert r['agent'] == 'boss.rese1' and 'Why you exist' in r['prompt']
        t = json.loads((await c.call_tool('tree', {'of': 'me', 'agent': tok})).content[0].text)['tree']
        assert 'boss.rese1' in t


def testOldDatabaseMigrates(root):
    import sqlite3

    from hive import Hive
    db = root/'.hive'/'hive.db'
    db.parent.mkdir()
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE agents(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,role TEXT NOT NULL,token TEXT UNIQUE NOT NULL,wf INTEGER,"
              "parent INTEGER,about TEXT DEFAULT '',state TEXT DEFAULT 'active',status TEXT DEFAULT '',task INTEGER,calls INTEGER DEFAULT 0,joined REAL,seen REAL)")
    c.execute("CREATE TABLE roles(name TEXT PRIMARY KEY,charter TEXT NOT NULL,caps TEXT NOT NULL,builtin INTEGER DEFAULT 0)")
    c.execute("INSERT INTO roles VALUES('coordinator','old','[\"read\"]',1)")
    c.execute("INSERT INTO agents(name,role,token,joined,seen) VALUES('old','coordinator','old.tok',0,1e12)")
    c.commit()
    c.close()
    h = Hive.open(db, root)
    o = h.sess('old.tok')
    assert o.agent.budget == h.cfg.budget and 'fork' in h.roles.get('coordinator').caps
    assert o.spawn('works after migration')['budget'] == 15
    h.close()
    assert Hive.open(db, root).sess('old.tok').agent.budget == 16
