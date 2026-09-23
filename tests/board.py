import pytest

from hive.err import Bad, Clash, Missing


def testVersionsAndCompareAndSwap(team):
    a, b = team['alice'], team['bob']
    assert a.put('plan', ['step 1'])['version'] == 1
    b.put('plan', ['step 1', 'step 2'], expect=1)
    with pytest.raises(Clash, match='version 2'): a.put('plan', ['mine'], expect=1)
    g = a.get('plan', history=5)
    assert g['value'] == ['step 1', 'step 2'] and g['author'] == 'bob' and [h['version'] for h in g['history']] == [1]


def testScopes(hive, team):
    w = hive.join('wf1', 'implementer', 'alpha')
    w.put('k', 'workflow value')
    w.put('k', 'session value', 'session')
    assert w.get('k')['value'] == 'workflow value' and team['alice'].get('k')['value'] == 'session value'
    w.put('only', 1, 'session')
    assert w.get('only')['scope'] == 'session'
    with pytest.raises(Bad): team['alice'].put('x', 1, 'workflow')
    assert {k['key'] for k in w.keys()['keys']} == {'k', 'only'}


def testKeysFilterAndDrop(team):
    a = team['alice']
    a.put('find/a', 1, tags=['x'])
    a.put('find/b', 2)
    a.put('other', 3)
    assert [k['key'] for k in a.keys('find/')['keys']] == ['find/a', 'find/b']
    assert [k['key'] for k in a.keys(tag='x')['keys']] == ['find/a']
    a.drop('other')
    with pytest.raises(Missing): a.get('other')
    with pytest.raises(Missing): a.drop('other')


def testFollowersHearOfChanges(team):
    a, b = team['alice'], team['bob']
    b.follow(['context:plan*'])
    a.put('plan', 'v1')
    assert 'context.set' in b.notices()['updates'][0]
