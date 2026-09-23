import sys, threading, time

import pytest

from hive.err import Bad, Clash, Denied, Missing


def serve(x, stop, fn):
    while not stop.is_set():
        for m in x.inbox()['messages'] + x.notices().get('messages', []):
            if m.get('kind') == 'call': x.answer(m['data']['call'], fn(m['data']['args']))
        time.sleep(.02)


def testAgentServedRoundTrip(team):
    a, b = team['alice'], team['bob']
    a.offer('square', 'squares n', {'type': 'object', 'properties': {'n': {'type': 'integer'}}, 'required': ['n']})
    stop = threading.Event()
    threading.Thread(target=serve, args=(a, stop, lambda g: g['n']**2), daemon=True).start()
    try: assert b.call('square', {'n': 7}, wait=5)['result'] == 49
    finally: stop.set()
    with pytest.raises(Bad, match='schema'): b.call('square', {'n': 'x'})
    assert [t['name'] for t in b.tools()['tools']] == ['square']


def testLateAnswerArrivesAsMessage(team):
    a, b = team['alice'], team['bob']
    a.offer('slow', 'slow thing')
    r = b.call('slow', {}, wait=0)
    assert r['state'] == 'pending'
    call = a.notices()['messages'][0]['data']['call']
    a.answer(call, {'ok': True})
    assert b.result(r['call'])['result'] == {'ok': True}
    assert 'result of slow' in b.notices()['messages'][0]['body']
    with pytest.raises(Clash): a.answer(call, 1)
    with pytest.raises(Denied): b.answer(call, 1)


def testCommandTool(team):
    c, a = team['coord'], team['alice']
    with pytest.raises(Denied): a.offer('echo', 'x', kind='command', argv=['cat'])
    c.offer('echo', 'echoes args', kind='command', argv=[sys.executable, '-c', 'import sys; print(sys.stdin.read())'])
    assert a.call('echo', {'x': 1})['result'].strip() == '{"x": 1}'
    c.offer('boom', 'fails', kind='command', argv=[sys.executable, '-c', 'import sys; sys.exit(3)'])
    assert a.call('boom')['error'].startswith('exit 3')


def testOwnershipAndLeaving(team):
    a, b = team['alice'], team['bob']
    a.offer('mine', 'x')
    with pytest.raises(Clash): b.offer('mine', 'y')
    with pytest.raises(Bad): a.call('mine')
    with pytest.raises(Denied): b.withdraw('mine')
    a.leave()
    with pytest.raises(Clash, match='left'): b.call('mine')
    team['coord'].withdraw('mine')
    with pytest.raises(Missing): b.call('mine')
    with pytest.raises(Bad): b.offer('Bad Name', 'x')
