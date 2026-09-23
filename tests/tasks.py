import threading

import pytest

from hive.err import Bad, Clash, Denied


def ids(r): return {x['key']: x['id'] for x in r['created']}


def testDagReadiness(team):
    c = team['coord']
    r = c.plan([{'key': 'a', 'title': 'A'}, {'key': 'b', 'title': 'B'}, {'key': 'c', 'title': 'C', 'after': ['a', 'b']}])
    st = {x['key']: x['state'] for x in r['created']}
    assert st == {'a': 'ready', 'b': 'ready', 'c': 'pending'}
    t = ids(r)
    a, b = team['alice'], team['bob']
    assert a.take()['task']['id'] == t['a'] and b.take()['task']['id'] == t['b']
    assert a.done(t['a'], 'A done')['unblocked'] == []
    assert b.done(t['b'], 'B done')['unblocked'] == [t['c']]
    got = a.take()
    assert got['task']['id'] == t['c'] and [d['result'] for d in got['dependencies']] == ['A done', 'B done']


def testChainAndCycles(team):
    c = team['coord']
    r = c.plan([{'title': 'one'}, {'title': 'two'}, {'title': 'three'}], chain=True)
    assert [x['after'] for x in r['created']] == [[], [r['created'][0]['id']], [r['created'][1]['id']]]
    with pytest.raises(Bad, match='cycle'): c.plan([{'key': 'x', 'title': 'x', 'after': ['y']}, {'key': 'y', 'title': 'y', 'after': ['x']}])
    with pytest.raises(Bad): c.plan([{'title': ''}])
    with pytest.raises(Bad): c.plan([{'key': 'k', 'title': 'a'}, {'key': 'k', 'title': 'b'}])


def testDependsOnExistingTask(team):
    c = team['coord']
    [first] = c.plan([{'title': 'base'}])['created']
    [later] = c.plan([{'title': 'later', 'after': [first['id']]}])['created']
    assert later['state'] == 'pending' and later['after'] == [first['id']]


def testRoleMatchingAndOneTaskAtATime(team):
    c, a, v = team['coord'], team['alice'], team['vera']
    t = ids(c.plan([{'key': 'i', 'title': 'impl', 'role': 'implementer'}, {'key': 'j', 'title': 'impl2', 'role': 'implementer'}]))
    assert v.take()['task'] is None
    with pytest.raises(Clash, match='needs an implementer'): v.take(t['i'])
    a.take(t['i'])
    with pytest.raises(Clash, match='still on'): a.take(t['j'])
    assert a.take(t['i'])['note'] == 'already yours'


def testVerificationFlow(team):
    c, a, v = team['coord'], team['alice'], team['vera']
    t = ids(c.plan([{'key': 'w', 'title': 'work', 'verify': True}, {'key': 'd', 'title': 'docs', 'after': ['w']}]))
    a.take(t['w'])
    r = a.done(t['w'], 'implemented')
    vt = r['verification']
    assert r['task']['state'] == 'in_review' and 'verify' in v.notices()['messages'][0]['body']
    v.take(vt)
    with pytest.raises(Bad): v.verify(t['w'], False, '')
    r = v.verify(t['w'], False, 'test_x fails')
    assert r['task']['state'] == 'running' and 'test_x fails' in a.notices()['interrupts'][0]['body']
    assert a.me()['task'] == t['w']
    vt2 = a.done(t['w'], 'fixed')['verification']
    assert vt2 != vt
    r = v.verify(vt2, True, 'all green')
    assert r['verdict'] == 'approved' and r['unblocked'] == [t['d']]
    assert [n['verdict'] for n in c.task(t['w'])['task']['notes']] == ['rejected', 'approved']


def testCannotVerifyOwnWork(hive, team):
    c = team['coord']
    both = hive.join('dual', 'coordinator')
    [w] = c.plan([{'title': 'w', 'verify': True}])['created']
    both.take(w['id'])
    both.done(w['id'], 'did it')
    with pytest.raises(Denied, match='own work'): both.verify(w['id'], True, 'looks fine')
    with pytest.raises(Denied): team['alice'].verify(w['id'], True, 'x')


def testFailBlocksDownstreamAndRetryReleases(team):
    c, a, b = team['coord'], team['alice'], team['bob']
    t = ids(c.plan([{'key': 'a', 'title': 'a'}, {'key': 'b', 'title': 'b', 'after': ['a']}, {'key': 'c', 'title': 'c', 'after': ['b']}]))
    a.take(t['a'])
    r = a.fail(t['a'], 'flaky env', retry=True)
    assert r['task']['state'] == 'ready' and r['task']['owner'] is None
    b.take(t['a'])
    with pytest.raises(Denied): a.fail(t['a'], 'not mine')
    b.fail(t['a'], 'truly broken')
    states = {x['id']: x['state'] for x in c.tasks()['tasks']}
    assert states == {t['a']: 'failed', t['b']: 'blocked', t['c']: 'blocked'}
    assert 'failed' in c.notices()['interrupts'][0]['body']


def testCancel(team):
    c, a = team['coord'], team['alice']
    [x] = a.plan([{'title': 'mine'}])['created']
    [y] = c.plan([{'title': 'theirs'}])['created']
    with pytest.raises(Denied): a.cancel(y['id'], 'no')
    a.take(y['id'])
    c.cancel(y['id'], 'change of plan')
    assert 'cancelled' in a.notices()['interrupts'][0]['body'] and a.me()['task'] is None
    assert a.cancel(x['id'], 'dup')['task']['state'] == 'cancelled'
    with pytest.raises(Clash): a.cancel(x['id'], 'again')


def testConcurrentTakeIsAtomic(hive):
    c = hive.join('c', 'coordinator')
    c.plan([{'title': f't{i}'} for i in range(10)])
    agents = [hive.join(f'w{i}') for i in range(10)]
    got, lock = [], threading.Lock()

    def grab(x):
        r = x.take()['task']
        with lock: got.append(r and r['id'])

    ts = [threading.Thread(target=grab, args=(x,)) for x in agents]
    for t in ts: t.start()
    for t in ts: t.join()
    assert sorted(got) == sorted({*got}) and len(got) == 10


def testDispatchGivesPromptAndReserves(team):
    c = team['coord']
    t = ids(c.plan([{'key': 'a', 'title': 'A', 'about': 'write it', 'paths': ['src/*']}, {'key': 'b', 'title': 'B', 'after': ['a']}]))
    d = c.dispatch(t['a'])
    assert d['agent'] == 'implementer-' + t['a'] and d['token'] in d['prompt'] and 'write it' in d['prompt'] and 'src/*' in d['prompt']
    with pytest.raises(Clash): c.dispatch(t['a'])
    with pytest.raises(Clash): team['alice'].take(t['a'])
    kid = c.hive.sess(d['token'])
    kid.take(t['a'])
    kid.done(t['a'], 'A result')
    d2 = c.dispatch(t['b'])
    assert 'A result' in d2['prompt']


def testReservedOwnerCanFinishWithoutTaking(team):
    c = team['coord']
    [x] = c.plan([{'title': 'x', 'assignee': 'alice'}])['created']
    assert 'assigned to you' in team['alice'].notices()['messages'][0]['body']
    assert team['bob'].take()['task'] is None
    assert team['alice'].done(x['id'], 'did it')['task']['state'] == 'done'


def testLongDependencyResultsAreSummarized(team):
    c, a = team['coord'], team['alice']
    t = ids(c.plan([{'key': 'a', 'title': 'a'}, {'key': 'b', 'title': 'b', 'after': ['a']}]))
    a.take(t['a'])
    a.done(t['a'], '\n'.join(f'finding {i}: ' + 'detail ' * 20 for i in range(200)))
    d = a.task(t['b'], budget=300)['dependencies'][0]
    assert 'summary' in d and len(d['summary']) < 2000


def testLeaveReleasesTask(team):
    c, a = team['coord'], team['alice']
    [x] = c.plan([{'title': 'x'}])['created']
    a.take(x['id'])
    assert a.leave('bye')[x['id']] == 'ready'


def testVerifierCannotTakeReviewOfOwnWork(hive, team):
    c, v = team['coord'], team['vera']
    [w] = c.plan([{'title': 'anyone', 'verify': True}])['created']
    v.take(w['id'])
    vt = v.done(w['id'], 'did it')['verification']
    with pytest.raises(Clash, match='did the work'): v.take(vt)
    assert hive.join('val', 'verifier').take()['task']['id'] == vt
