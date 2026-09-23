import threading, time

import pytest

from hive.err import Bad, Clash, Denied, Missing


def testQueueSteerInterrupt(team):
    a, b = team['alice'], team['bob']
    a.send('bob', 'later', 'queue')
    a.send('bob', 'soon', 'steer')
    a.send('bob', 'now', 'interrupt')
    n = b.notices()
    assert [m['body'] for m in n['interrupts']] == ['now'] and [m['body'] for m in n['messages']] == ['soon']
    assert n['queued'].startswith('1 queued')
    n = b.notices()
    assert 'messages' not in n and n['interrupts'][0]['reminder'] == 'still unacknowledged'
    assert [m['body'] for m in b.inbox()['messages']] == ['later']
    assert b.ack()['acked'] == 1 and 'interrupts' not in b.notices() and 'queued' not in b.notices()


def testInboxOrdersByUrgency(team):
    a, b = team['alice'], team['bob']
    for mode in ('queue', 'steer', 'interrupt'): a.send('bob', mode, mode)
    assert [m['mode'] for m in b.inbox()['messages']] == ['interrupt', 'steer', 'queue']
    assert b.inbox()['messages'] == [] and len(b.inbox(all=True)['messages']) == 3


def testAckSpecificAndForeign(team):
    a, b = team['alice'], team['bob']
    [i] = a.send('bob', 'x', 'interrupt')['sent']
    with pytest.raises(Missing): a.ack([i])
    assert b.ack([i])['acked'] == 1 and b.inbox()['unacked'] == []


def testRecipients(hive, team):
    c, a = team['coord'], team['alice']
    assert set(c.send('role:implementer', 'hi')['to']) == {'alice', 'bob'}
    assert set(c.send('*', 'all')['to']) == {'alice', 'bob', 'vera'}
    with pytest.raises(Denied): a.send('*', 'nope')
    w = hive.join('wally', 'implementer', 'alpha', parent='coord')
    assert c.send('workflow:alpha', 'wf')['to'] == ['wally'] and c.send('children', 'kids')['to'] == ['wally']
    assert w.send('parent', 'up')['to'] == ['coord']
    with pytest.raises(Missing): a.send('ghost', 'x')
    with pytest.raises(Bad): a.send('bob', 'x', 'shout')
    with pytest.raises(Bad): a.send('bob', '   ')


def testLeftAgentsAreSkipped(team):
    team['bob'].leave()
    with pytest.raises(Clash): team['alice'].send('bob', 'x')
    assert team['coord'].send('role:implementer', 'x')['to'] == ['alice']


def testThreadsAndReplies(hive, team):
    a, b = team['alice'], team['bob']
    [i] = a.send('bob', 'question?')['sent']
    b.send('alice', 'answer', re=i)
    [m] = a.inbox()['messages']
    assert m['re'] == i and m['thread'] == i
    assert [x.body for x in hive.mail.thread(i)] == ['question?', 'answer']


def testAskWaitsForReply(team):
    a, b = team['alice'], team['bob']

    def answer():
        for _ in range(100):
            if ms := b.inbox()['messages']:
                b.send('alice', 'forty-two', re=ms[0]['id'])
                return
            time.sleep(.02)

    threading.Thread(target=answer).start()
    r = a.ask('bob', 'meaning?', wait=5)
    assert r['reply']['body'] == 'forty-two'
    assert a.ask('bob', 'again?', wait=.1)['reply'] is None


def testWaitWakesOnMessage(team):
    a, b = team['alice'], team['bob']
    threading.Timer(.2, lambda: a.send('bob', 'wake up')).start()
    t = time.monotonic()
    r = b.wait(5)
    assert r['woke'] and r['messages'][0]['body'] == 'wake up' and time.monotonic()-t < 4
    assert b.wait(.1)['woke'] is False


def testWaitWakesOnFollowedUpdate(team, root):
    (root/'f.txt').write_text('a\nb\n')
    a, b = team['alice'], team['bob']
    b.read('f.txt')
    threading.Timer(.2, lambda: a.edit('f.txt', [{'old': 'a', 'new': 'A'}])).start()
    assert b.wait(5)['woke'] and 'f.txt' in b.notices()['updates'][0]


def testShare(team, root):
    (root/'m.py').write_text('one\ntwo\nthree\n')
    a, b = team['alice'], team['bob']
    a.put('plan', {'step': 1})
    assert a.share('bob', 'see', key='plan')['shared'] == 'context entry plan'
    a.share('bob', path='m.py', lines='2-3')
    a.share('bob', text='fyi')
    ms = b.notices()['messages']
    assert ms[0]['data']['context']['value'] == {'step': 1}
    assert ms[1]['data']['content'] == 'two\nthree\n' and ms[1]['data']['version'] == 1
    assert ms[2]['data'] == {'text': 'fyi'}
    [i] = team['vera'].send('bob', 'private')['sent']
    with pytest.raises(Denied): a.share('bob', msg=i)
    with pytest.raises(Bad): a.share('bob')


def testHandoff(team, root):
    (root/'x.py').write_text('x\n')
    a = team['alice']
    a.read('x.py')
    a.progress('halfway through x.py')
    r = a.handoff('bob', 'finish x.py please')
    p = team['bob'].notices()['messages'][0]['data']
    assert p['from'] == 'alice' and p['files'] == [{'path': 'x.py', 'version': 1}] and 'halfway' in p['activity'] and r['to'] == ['bob']
    with pytest.raises(Bad): a.handoff('bob', ' ')


def testFollowAgent(team):
    a, b = team['alice'], team['bob']
    b.follow(['agent:alice'])
    a.progress('did a thing')
    assert any('did a thing' in u for u in b.notices()['updates'])
    b.follow(['agent:alice'], stop=True)
    a.progress('another')
    assert 'updates' not in b.notices()
    with pytest.raises(Bad): b.follow(['nonsense'])
