import pytest

from hive.err import Anon, Bad, Clash, Denied, Missing


def testDeniedRestatesCharter(team, root):
    (root/'a.txt').write_text('a\n')
    v = team['vera']
    v.read('a.txt')
    with pytest.raises(Denied) as e: v.edit('a.txt', [{'old': 'a', 'new': 'b'}])
    assert 'verifier' in str(e.value) and 'charter' in str(e.value)
    with pytest.raises(Denied): v.plan([{'title': 'x'}])
    with pytest.raises(Denied): team['alice'].dispatch('t1')


def testObserverReadsOnly(hive, root):
    (root/'a.txt').write_text('a\n')
    o = hive.join('olly', 'observer')
    assert o.read('a.txt')['version'] == 1
    for f in (lambda: o.put('k', 1), lambda: o.take(), lambda: o.call('x', {})):
        with pytest.raises(Denied): f()


def testDefineAndAssign(team):
    c, a = team['coord'], team['alice']
    r = c.define('scribe', 'Keep the notes.', ['read', 'send', 'post'])
    assert r['caps'] == ['post', 'read', 'send']
    with pytest.raises(Bad): c.define('bad', 'x', ['fly'])
    with pytest.raises(Bad): c.define('verifier', 'x', ['read'])
    with pytest.raises(Denied): a.define('mine', 'x', ['read'])
    c.assign('alice', 'scribe')
    assert a.me()['role'] == 'scribe' and 'Keep the notes' in a.notices()['interrupts'][0]['body']
    with pytest.raises(Missing): c.assign('alice', 'nope')


def testReminderEveryN(hive):
    hive.notice.every = 3
    a = hive.join('ann')
    seen = [('roleReminder' in a.notices()) for _ in range(6) if a.me()]
    assert seen == [False, False, True, False, False, True]


def testJoinRules(hive):
    old = hive.join('ann').token
    with pytest.raises(Clash): hive.join('ann')
    b = hive.join('ann', takeover=True)
    assert b.token != old
    with pytest.raises(Anon): hive.sess(old)
    b.leave()
    with pytest.raises(Anon): b.me()
    assert hive.join('ann', 'verifier').agent.role == 'verifier'
    with pytest.raises(Bad): hive.join('bad name')
    with pytest.raises(Missing): hive.join('zed', 'wizard')


def testStaleNameCanBeReused(hive):
    hive.agents.stale = 0
    hive.join('ann')
    assert hive.join('ann').agent.state == 'active'
