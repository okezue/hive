import io, json

from hive.hook import Ev, handle, main, who

from .conftest import nums


def run(kind, raw, hive, x, fmt='claude'):
    out = handle(kind, raw, hive, x, fmt)
    return json.loads(out) if out and fmt == 'claude' else out


def testPaths():
    e = Ev('post', {'tool_name': 'apply_patch', 'tool_input': {'patch': '*** Update File: a.py\n+x\n*** Add File: b.py\n'}})
    assert e.paths() == ['a.py', 'b.py'] and e.edit
    e = Ev('post', {'toolName': 'search_replace', 'toolInput': {'file_path': 'c.py'}})
    assert e.paths() == ['c.py'] and e.edit and not Ev('post', {'tool_name': 'Bash'}).edit
    assert Ev('post', {'tool_name': 'mcp__hive__read'}).hive and Ev('post', {'tool_name': 'hive__read'}).hive


def testPostLogsActivityAndDeliversInterrupts(hive, team):
    a, b = team['alice'], team['bob']
    b.send('alice', 'stop touching main.py', 'interrupt')
    r = run('post', {'tool_name': 'Bash', 'tool_input': {'command': 'pytest -q'}}, hive, a)
    assert r['decision'] == 'block' and 'INTERRUPT' in r['reason'] and 'stop touching' in r['reason']
    assert any('Bash: pytest -q' in e for e in team['coord'].watch('alice')['events'])
    a.ack()
    assert run('post', {'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}, hive, a) is None
    b.send('alice', 'fyi', 'steer')
    r = run('post', {'tool_name': 'Read', 'tool_input': {'file_path': 'x'}}, hive, a)
    assert 'decision' not in r and 'fyi' in r['hookSpecificOutput']['additionalContext']


def testEditToolsAreSyncedAndMerged(hive, team, root):
    f = root/'m.py'
    f.write_text(nums(12))
    a, b = team['alice'], team['bob']
    raw = {'tool_name': 'Edit', 'tool_input': {'file_path': str(f)}, 'cwd': str(root)}
    assert run('pre', raw, hive, a) is None
    b.read('m.py')
    b.edit('m.py', [{'old': 'line 2\n', 'new': 'B\n'}])
    ctx = run('pre', raw, hive, a)['hookSpecificOutput']['additionalContext']
    assert 'changed since you last looked' in ctx and 'bob' in ctx
    f.write_text(nums(12, l11='A'))
    r = run('post', raw, hive, a)
    assert 'merged with changes by bob' in r['hookSpecificOutput']['additionalContext']
    assert f.read_text() == nums(12, l2='B', l11='A')
    assert any('m.py' in u for u in b.notices()['updates'])


def testConflictingEditIsBlockedUntilSettled(hive, team, root):
    f = root/'m.py'
    f.write_text(nums(5))
    a, b = team['alice'], team['bob']
    raw = {'tool_name': 'Write', 'tool_input': {'file_path': 'm.py'}, 'cwd': str(root)}
    run('pre', raw, hive, a)
    b.read('m.py')
    b.edit('m.py', [{'old': 'line 3\n', 'new': 'B\n'}])
    f.write_text(nums(5, l3='A'))
    r = run('post', raw, hive, a)
    assert r['decision'] == 'block' and 'overlaps a newer change by bob' in r['reason'] and f.read_text() == nums(5, l3='B')
    d = run('pre', raw, hive, a)['hookSpecificOutput']
    assert d['permissionDecision'] == 'deny' and 'mr1' in d['permissionDecisionReason']
    s = run('stop', {'reason': 'end_turn'}, hive, a)
    assert s['decision'] == 'block' and 'mr1' in s['reason']


def testStopMarksIdleWhenClear(hive, team):
    a = team['alice']
    assert run('stop', {}, hive, a) is None and a.agent.state == 'idle'
    team['bob'].send('alice', 'urgent', 'interrupt')
    assert 'm1' in run('stop', {}, hive, a)['reason']
    assert run('stop', {'reason': 'channel_closed'}, hive, a) is None


def testSubagentAndUnknownAreIgnored(hive, team):
    team['bob'].send('alice', 'x', 'interrupt')
    assert run('post', {'tool_name': 'Bash', 'subagentType': 'explore'}, hive, team['alice']) is None
    assert run('post', {'tool_name': 'Bash'}, hive, None) is None


def testStartAndEnd(hive, team):
    a = team['alice']
    assert 'You are alice' in run('start', {}, hive, a)['hookSpecificOutput']['additionalContext']
    assert run('start', {}, hive, a, 'text').startswith('You are alice')
    run('end', {}, hive, a)
    assert a.agent.state == 'left'


def testMainNeverFails(hive, monkeypatch, capsys):
    monkeypatch.setenv('HIVE_AGENT', 'hooky')
    monkeypatch.setattr('sys.stdin', io.StringIO('not json'))
    assert main('post', hive=hive) == 0 and 'hive hook post' in capsys.readouterr().err
    assert who(hive).name == 'hooky'
    monkeypatch.setattr('sys.stdin', io.StringIO(json.dumps({'tool_name': 'Bash', 'tool_input': {'command': 'make'}})))
    assert main('post', hive=hive) == 0
    assert any('make' in e for e in hive.join('peek', 'observer').watch('hooky')['events'])
