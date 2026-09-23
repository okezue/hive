import sys, threading, time

import pytest

from hive.err import Bad, Clash, Denied, Missing
from hive.run import Runner


@pytest.fixture
def lead(hive):
    c = hive.join('lead', 'coordinator')
    [t] = c.plan([{'title': 'ship'}])['created']
    c.take(t['id'])
    return c


def total(hive): return hive.db.one('SELECT SUM(budget) n FROM agents').n


def testDispatchIsChargedAndConserves(hive, lead):
    start = total(hive)
    for i in range(3):
        [t] = lead.plan([{'title': f'job {i}'}])['created']
        hive.sess(lead.dispatch(t['id'], budget=2)['token']).leave()
    assert total(hive) == start
    [t] = lead.plan([{'title': 'free'}])['created']
    assert hive.sess(lead.dispatch(t['id'])['token']).agent.budget == 0
    with pytest.raises(Clash): lead.dispatch(lead.plan([{'title': 'x'}])['created'][0]['id'], budget=10**6)


def testNoNegativeFunds(hive, lead):
    kid = hive.sess(lead.spawn('k', budget=2)['token'])
    with pytest.raises(Bad): kid.escalate('give me less', fund=-7)
    i = kid.escalate('need a call')['issue']
    with pytest.raises(Bad): lead.decide(i, 'ok', fund=-3)
    lead.decide(i, 'ok')
    assert kid.agent.budget == 2


def testNarrowingSurvivesDispatchAssignAndRejoin(hive, lead):
    sub = hive.sess(lead.spawn('manage a slice', 'coordinator', grants=['fork', 'read', 'send', 'spawn', 'plan'])['token'])
    assert sorted(sub.me()['caps']) == ['fork', 'plan', 'read', 'send', 'spawn']
    [t] = lead.plan([{'title': 'needs a coordinator', 'role': 'coordinator'}])['created']
    got = hive.sess(sub.dispatch(t['id'])['token'])
    assert not hive.roles.can(got.agent, 'manage') and not hive.roles.can(got.agent, 'exec')
    v = hive.join('vic', 'verifier')
    n = v.spawn('look', 'implementer')['agent']
    lead.assign(n, 'implementer')
    assert not hive.roles.can(hive.agents.named(n), 'write')
    lead.assign(n, 'observer')
    assert hive.roles.caps(hive.agents.named(n)) <= {'read', 'send'}
    hive.join(n, 'implementer', takeover=True)
    assert not hive.roles.can(hive.agents.named(n), 'write')


def testSettledChildReturnsBudgetAndSlot(hive, lead):
    hive.cfg.fanout = 2
    before = lead.agent.budget
    for i in range(2):
        k = hive.sess(lead.spawn(f'k{i}', budget=3)['token'])
        k.take()
        k.done(k.agent.deleg, 'ok')
    assert lead.agent.budget == before-2 and lead.spawn('third', budget=1)['agent']


def testCascadeCancelsReviewsAndBlocksDependents(hive, lead):
    a = hive.sess(lead.spawn('a', verify=True)['token'])
    a.take()
    a.done(a.agent.deleg, 'for review')
    [d] = lead.plan([{'title': 'after a', 'after': [f't{a.agent.deleg}']}])['created']
    lead.cancel('t1', 'scrap')
    st = {t['id']: t['state'] for t in lead.tasks()['tasks']}
    assert st[d['id']] == 'blocked' and all(v in ('cancelled', 'blocked') for v in st.values())


def testLeavingBeforeTakeFailsDelegation(hive, lead):
    kid = hive.sess(lead.spawn('never started')['token'])
    kid.leave()
    assert lead.gather(secs=0)['done'] and lead.done('t1', 'fine')['task']['state'] == 'done'


def testRejectAfterSpawnedAuthorLeftFails(hive, lead):
    kid = hive.sess(lead.spawn('k', verify=True)['token'])
    kid.take()
    kid.done(kid.agent.deleg, 'r')
    kid.leave()
    v = hive.join('ver', 'verifier')
    v.take()
    assert v.verify(f't{kid.agent.deleg}', False, 'no')['task']['state'] == 'failed'


def testBlockedSubtasksDoNotTrapTheParent(hive):
    al = hive.join('al')
    [e, x, y] = al.plan([{'key': 'e', 'title': 'epic'}, {'key': 'x', 'title': 'x'}, {'title': 'y', 'after': ['x'], 'parent': 't1'}])['created']
    al.take(e['id'])
    al.cancel(x['id'], 'no')
    assert al.done(e['id'], 'done anyway')['task']['state'] == 'done'


def testRunnerDoesNotWaitOnChildrenItCannotStart(hive, lead, tmp_path):
    lead.spawn('research', 'researcher', launch='runner')
    t = time.monotonic()
    Runner(hive, {'implementer': [sys.executable, '-c', 'pass']}, poll=.05).run(20)
    assert time.monotonic()-t < 5


def testCustodyAndAuthorityStayInTheirLineage(hive, lead):
    a = hive.sess(lead.spawn('a', 'coordinator')['token'])
    with pytest.raises(Denied): a.adopt('lead')
    with pytest.raises(Denied): a.adopt(a.name)
    b = hive.sess(lead.spawn('b', 'coordinator')['token'])
    k = hive.sess(a.spawn('k')['token'])
    b.adopt(k.name)
    b.leave()
    assert k.node('me').get('keeper', a.name) == a.name
    i = k.escalate('help')['issue']
    cousin = hive.sess(lead.spawn('c', 'coordinator')['token'])
    with pytest.raises(Denied): cousin.decide(i, 'no')
    k.leave()
    assert lead.issues(all=True)['issues'] == []
    with pytest.raises(Clash): lead.fund(k.name, 1)


def testAutoPutWritesWhereGetReads(hive, lead):
    kid = hive.sess(lead.spawn('k')['token'])
    lead.put('plan', 'v1', 'node')
    got = kid.get('plan')
    kid.put('plan', 'v2', expect=got['version'])
    assert lead.get('plan')['value'] == 'v2' and kid.get('plan')['scope'] == 'node lead'


def testNavigationEdges(hive, lead):
    hive.sess(lead.spawn('alpha')['token'])
    with pytest.raises(Missing): lead.walk('downstream')
    with pytest.raises(Missing): lead.node('nobody/lead')
    assert lead.node('lead', limit=0)['children'] == ['+1 more']
    assert lead.tree('me', limit=0)['tree'].endswith('+1 more')


def testGatherAnyWaitsForTheNextOne(hive, lead):
    a, b = (hive.sess(lead.spawn(n)['token']) for n in ('a', 'b'))
    a.take()
    a.done(a.agent.deleg, 'first')

    def later():
        time.sleep(.4)
        b.take()
        b.done(b.agent.deleg, 'second')

    threading.Thread(target=later).start()
    t = time.monotonic()
    r = lead.gather(any=True, secs=5)
    assert time.monotonic()-t > .3 and r['done']


async def testMcpJoinCannotPickAParent(hive):
    from mcp.client import Client

    from hive.srv import build
    async with Client(build(hive)) as c:
        tool = next(t for t in (await c.list_tools()).tools if t.name == 'join')
    assert 'parent' not in tool.input_schema['properties']
