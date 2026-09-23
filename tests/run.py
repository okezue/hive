import sys, textwrap, time

import pytest

from hive.run import Runner, fill

AGENT = textwrap.dedent('''
    import os, sys, time
    from hive import Hive
    h = Hive.open(os.environ['HIVE_DB'], os.environ['HIVE_ROOT'])
    me, t = h.sess(os.environ['HIVE_AGENT_TOKEN']), os.environ['HIVE_TASK']
    task = me.task(t)['task']
    with open(os.path.join(os.environ['HIVE_ROOT'], 'order.log'), 'a') as f: f.write(f"start {task['title']} {time.time()}\\n")
    if task['title'] == 'crash': sys.exit(1)
    me.take(t)
    time.sleep(float(os.environ.get('NAP', '0')))
    if task['kind'] == 'verify': me.verify(t, True, 'checked by fake verifier')
    else: me.done(t, f"{task['title']} finished; saw {[d['id'] for d in me.task(t).get('dependencies', [])]}")
    with open(os.path.join(os.environ['HIVE_ROOT'], 'order.log'), 'a') as f: f.write(f"end {task['title']} {time.time()}\\n")
''')


@pytest.fixture
def agent(tmp_path):
    (p := tmp_path/'agent.py').write_text(AGENT)
    return [sys.executable, str(p)]


def events(root):
    out = []
    for x in (root/'order.log').read_text().splitlines():
        k, rest = x.split(' ', 1)
        n, t = rest.rsplit(' ', 1)
        out.append((k, n, float(t)))
    return out


def testDependenciesAndConcurrency(hive, root, agent):
    op = hive.op()
    op.plan([{'key': 'a', 'title': 'a'}, {'key': 'b', 'title': 'b'}, {'key': 'c', 'title': 'c', 'after': ['a', 'b'], 'verify': True}])
    lines = []
    r = Runner(hive, {'default': agent}, cap=2, poll=.05, say=lines.append, env={'NAP': '.4'}).run(60)
    assert r['stuck'] == {} and r['counts'] == {'done': 4}
    ev = {(k, n): t for k, n, t in events(root)}
    assert ev['start', 'b'] < ev['end', 'a'] and ev['start', 'a'] < ev['end', 'b']
    assert ev['start', 'c'] > max(ev['end', 'a'], ev['end', 'b'])
    assert "saw ['t1', 't2']" in hive.tasks.get(3).result
    assert any('started verifier-t4' in x for x in lines)


def testCrashRetriesThenFails(hive, root, agent):
    op = hive.op()
    op.plan([{'key': 'x', 'title': 'crash'}, {'title': 'after', 'after': ['x']}])
    r = Runner(hive, {'default': agent}, cap=1, poll=.05).run(60)
    assert r['counts'] == {'failed': 1, 'blocked': 1}
    assert len([e for e in events(root) if e[0] == 'start']) == 2
    assert 'exited with code 1' in hive.tasks.get(1).notes[-1]['failed']


def testOnlyRolesWithCommandsRun(hive, root, agent):
    hive.op().plan([{'title': 'impl', 'role': 'implementer'}, {'title': 'res', 'role': 'researcher'}])
    r = Runner(hive, {'implementer': agent}, poll=.05).run(60)
    assert r['counts'] == {'done': 1, 'ready': 1} and r['stuck'] == {'ready': 1}


def testTimeoutStopsAgents(hive, root, agent):
    hive.op().plan([{'title': 'slow'}])
    t = time.monotonic()
    r = Runner(hive, {'default': agent}, poll=.05, env={'NAP': '30'}).run(1)
    assert time.monotonic()-t < 15 and r['counts'] in ({'ready': 1}, {'running': 1})


def testFill():
    v = {k: k.upper() for k in ('prompt', 'promptFile', 'task', 'agent', 'token', 'role', 'db', 'root', 'mcp')}
    assert fill('--x={task} {mcp}/{nope}', v) == '--x=TASK MCP/{nope}'
