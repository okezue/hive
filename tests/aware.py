import threading

import pytest

from hive.err import Bad


def testOverview(team, root):
    (root/'a.py').write_text('a\n')
    c, a = team['coord'], team['alice']
    a.read('a.py')
    a.progress('reading a.py')
    c.plan([{'title': 'x'}])
    a.take()
    o = c.overview()
    me = next(x for x in o['agents'] if x['name'] == 'coord')
    al = next(x for x in o['agents'] if x['name'] == 'alice')
    assert me['you'] and al['status'] == 'reading a.py' and al['files'] == ['a.py'] and al['task'].startswith('t1 x')
    assert o['tasks']['counts'] == {'running': 1} and any('progress' in e for e in o['recent'])
    with pytest.raises(Bad): c.overview('galaxy')


def testWorkflowScope(hive, team):
    w = hive.join('w1', 'coordinator', 'alpha')
    w.plan([{'title': 'wf task'}])
    team['coord'].plan([{'title': 'session task'}])
    assert [t['title'] for t in w.tasks()['tasks']] == ['wf task']
    assert len(w.tasks(scope='session')['tasks']) == 2
    assert [x['name'] for x in w.overview()['agents']] == ['w1']


def testLiveCursor(team):
    c, a = team['coord'], team['alice']
    a.progress('one')
    first = c.watch('alice')
    assert any('one' in e for e in first['events'])
    assert c.watch('alice')['events'] == []
    a.progress('two')
    assert [e.split(': ', 1)[1] for e in c.watch('alice')['events']] == ['two']


def testLiveWaitBlocksUntilActivity(team):
    c, a = team['coord'], team['alice']
    c.watch('alice')
    threading.Timer(.2, lambda: a.progress('later')).start()
    assert any('later' in e for e in c.watch('alice', wait=5)['events'])


def testWindowSlidesBack(team):
    c, a = team['coord'], team['alice']
    for i in range(25): a.progress(f'step {i}')
    w1 = c.watch('alice', 'window', limit=10)
    assert w1['events'][-1].endswith('step 24') and w1['older']
    w2 = c.watch('alice', 'window', before=w1['older'], limit=10)
    assert w2['events'][-1].endswith('step 14')
    w3 = c.watch('alice', 'window', before=w2['older'], limit=10)
    assert w3['older'] is None and w3['total'] == 26


def testSummaryIsBudgeted(team):
    c, a = team['coord'], team['alice']
    for i in range(300): a.progress(f'step {i}: did something detailed and specific to part {i}')
    s = c.watch('alice', 'summary', budget=120)
    assert s['events'] == 301 and s['levels'] >= 1 and len(s['summary']) <= 120*4
    assert c.watch('bob', 'summary')['events'] == 1
    with pytest.raises(Bad): c.watch('alice', 'telepathy')


def testDigestAdvances(team):
    c, a, b = team['coord'], team['alice'], team['bob']
    c.digest()
    a.progress('alpha')
    b.progress('beta')
    d = c.digest()
    assert d['events'] == 2 and 'alpha' in d['digest'] and 'beta' in d['digest']
    assert c.digest()['events'] == 0
