import json, sys, textwrap, threading, time

import pytest

from hive import Hive
from hive.reg import alive
from hive.run import Runner
from hive.srv import INFO

WORK = textwrap.dedent('''
    import os, sys
    from hive import Hive
    h = Hive.open(os.environ['HIVE_DB'], os.environ['HIVE_ROOT'])
    x = h.sess(os.environ['HIVE_AGENT_TOKEN'])
    t = os.environ['HIVE_TASK']
    x.take(t)
    x.done(t, result=f"{x.name} ran as its own process")
''')


@pytest.fixture
def lead(hive):
    x = hive.join('lead', 'coordinator')
    with hive.db.tx() as c: hive.agents.set(c, x.id, harness='grok')
    return x


def testTopLevelSessionsGetAPromptAndSubagentsGetTheRunner(hive, lead):
    r = lead.spawn('map the parser', 'researcher')
    assert r['launch'] == 'host' and 'prompt' in r and 'right away' not in r['hint'] and 'now' in r['hint']
    kid = hive.sess(r['token'])
    assert 'You run as a subagent' in r['prompt']
    g = kid.spawn('dig into the lexer', budget=0)
    assert g['launch'] == 'runner' and g['harness'] == 'grok' and 'prompt' not in g and 'subagents cannot start subagents' in g['hint']
    assert 'automatic runners are off' in g['hint']
    kid2 = kid.spawn('explicit host is impossible here', launch='host', budget=0)
    assert kid2['launch'] == 'runner'
    r2 = lead.spawn('long job', 'researcher', launch='runner', budget=0)
    assert r2['launch'] == 'runner' and 'subagents cannot' not in r2['hint'] and r2['harness'] == 'grok'
    assert 'You run as a subagent' not in hive.tree.prompt(hive.agents.named(r2['agent']))


def testDispatchHandsTasksToTheRunnerForSubagentCoordinators(hive, lead):
    [a, b] = lead.plan([{'title': 'alpha'}, {'title': 'beta'}])['created']
    d = lead.dispatch(a['id'])
    assert 'prompt' in d and 'You run as a subagent' in d['prompt']
    sub = hive.sess(lead.spawn('coordinate beta', 'coordinator', budget=2)['token'])
    h = sub.dispatch(b['id'])
    assert h['launch'] == 'runner' and 'token' not in h and 'subagents cannot' in h['hint']
    assert hive.tasks.get(int(b['id'][1:])).run == 1 and hive.tasks.get(int(a['id'][1:])).run == 0
    [c] = lead.plan([{'title': 'gamma'}])['created']
    assert lead.dispatch(c['id'], launch='runner')['launch'] == 'runner'


def testHandedRunnerStartsOnlyWhatWasHandedAndStopsWhenIdle(hive, lead, tmp_path):
    (w := tmp_path/'work.py').write_text(WORK)
    [a, b] = lead.plan([{'title': 'handed'}, {'title': 'kept for my own subagent'}])['created']
    lead.dispatch(a['id'], launch='runner')
    kid = hive.sess(lead.spawn('runner child', 'implementer', launch='runner', budget=0)['token'])
    said, t = [], time.time()
    r = Runner(hive, {'default': [sys.executable, str(w)]}, poll=.1, handed=True, watch=True, linger=1.5, say=said.append).run(120)
    assert hive.tasks.get(int(a['id'][1:])).state == 'done' and hive.tasks.get(int(b['id'][1:])).state == 'ready'
    assert hive.tasks.get(kid.agent.deleg).state == 'done' and r['stuck'] == {'ready': 1}
    assert any('nothing to do' in x for x in said) and time.time()-t < 60


def testAutorunStartsOneRunnerWhenNeeded(hive, lead, tmp_path, monkeypatch):
    (w := tmp_path/'work.py').write_text(WORK)
    (hive.cfg.dir/'config.toml').write_text(f'[runner]\nlinger = 3\n\n[runner.roles.default]\ncommand = [{json.dumps(sys.executable)}, {json.dumps(str(w))}]\n')
    h = Hive.open(hive.cfg.db, hive.root)
    assert h.autorun() == 'off'
    monkeypatch.setenv('HIVE_AUTORUN', '1')
    x = h.sess(lead.token)
    r = x.spawn('as its own process', 'implementer', launch='runner', budget=0)
    assert 'started a runner (pid' in r['hint']
    pid = int(r['hint'].split('pid ')[1].split(')')[0])
    got = []
    ts = [threading.Thread(target=lambda: got.append(Hive.open(hive.cfg.db, hive.root).autorun())) for _ in range(3)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert got == ['running']*3 and h.autorun() == 'running'
    end = time.time()+90
    while h.tasks.get(h.agents.named(r['agent']).deleg).state != 'done' and time.time() < end: time.sleep(.3)
    assert h.tasks.get(h.agents.named(r['agent']).deleg).state == 'done', (h.cfg.dir/'run'/'runner.log').read_text()
    end = time.time()+60
    while alive(pid) and time.time() < end: time.sleep(.3)
    assert not alive(pid), 'the automatic runner did not stop after lingering'
    assert 'stopping' in (h.cfg.dir/'run'/'runner.log').read_text()


def testUnstartedAndQuietHelpersAreFlaggedToTheirCreator(hive, lead):
    kid = lead.spawn('never started', 'researcher', budget=0)
    busy = hive.sess(lead.spawn('went quiet', 'researcher', budget=0)['token'])
    busy.take(busy.agent.deleg and f't{busy.agent.deleg}')
    with hive.db.tx() as c:
        c.execute('UPDATE agents SET joined=joined-700 WHERE name=?', (kid['agent'],))
        c.execute('UPDATE agents SET seen=seen-1000 WHERE id=?', (busy.id,))
    assert {a['name']: a['state'] for a in lead.overview()['agents']}[kid['agent']] == 'not started'
    n = lead.notices()
    msgs = ' '.join(n['helpersNeedYou'])
    assert kid['agent'] in msgs and 'never started' in msgs and busy.name in msgs and 'progress' in msgs
    assert 'helpersNeedYou' not in lead.notices(), 'reminders repeat at most every ten minutes'


def testMessagesToQuietSubagentsSayWhenTheyWillSeeThem(hive, lead):
    kid = lead.spawn('slow worker', 'researcher', budget=0)
    r = lead.send(kid['agent'], 'stop and rerun the tests', 'interrupt')
    assert 'no Hive call yet' in r['note'] and 'next call Hive' in r['note']
    top = hive.join('peer', 'implementer')
    assert 'note' not in lead.send('peer', 'hello')
    assert top


def testEveryAgentIsToldHowToStayReachableAndHowToSplitWork(hive, lead):
    b = lead.welcome()['brief']
    assert 'Post `progress` every few steps' in b and 'launch="runner"' in b and 'cannot start subagents' in b
    assert 'post progress every few steps' in INFO and 'Subagents cannot start subagents' in INFO
    from hive.srv import DOCS
    assert "launch 'auto'" in DOCS['spawn'] and 'launch="runner"' in DOCS['dispatch'] and 'unstarted' in DOCS['dispatch']


def testConcurrentSpawnsStartOneRunner(hive, lead, tmp_path, monkeypatch):
    (w := tmp_path/'work.py').write_text(WORK)
    (hive.cfg.dir/'config.toml').write_text(f'[runner]\nlinger = 2\n\n[runner.roles.default]\ncommand = [{json.dumps(sys.executable)}, {json.dumps(str(w))}]\n')
    monkeypatch.setenv('HIVE_AUTORUN', '1')
    got, go = [], threading.Barrier(4)

    def one():
        h = Hive.open(hive.cfg.db, hive.root)
        go.wait()
        got.append(h.autorun())

    ts = [threading.Thread(target=one) for _ in range(4)]
    for t in ts: t.start()
    for t in ts: t.join()
    started = [x for x in got if x.startswith('started')]
    assert len(started) == 1 and got.count('running') == 3, got
    pid = int(started[0].split('pid ')[1].rstrip(')'))
    end = time.time()+60
    while alive(pid) and time.time() < end: time.sleep(.3)
    assert not alive(pid)
