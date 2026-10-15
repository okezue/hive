import json

import pytest

import hive.build as build
from hive.err import Clash, Denied
import os, subprocess

from hive.harness import GATE, H, hooked, putHooks
from hive.hook import handle


@pytest.fixture(autouse=True)
def roomy(monkeypatch): monkeypatch.setattr(build, 'free', lambda: 80.)


def grok(h, x, kind, sid, **kw): return handle(kind, {'sessionId': sid, 'subagentType': 'general-purpose'} | kw, h, x)


def first(h, co, title='Fix it'):
    co.plan([{'title': title}])
    st = co.host()['start'][0]
    return st, h.agents.named(st['agent'])


def testHostRunsPlannedTasksWithinItsCap(hive, team):
    co = team['coord']
    co.plan([{'title': f'T{i}'} for i in range(3)])
    r = co.host(cap=2)
    assert [x['description'] for x in r['start']] == ['hive implementer-t1', 'hive implementer-t2'] and r['hosting']['waiting'] == 1
    p = r['start'][0]['prompt']
    assert 'Your Hive token is' in p and "take('t1')" in p and 'fellow subagents' in p
    assert co.host()['start'] == [] and hive.autorun() == 'host'
    x = hive.sess(hive.agents.named('implementer-t1').token)
    x.take('t1')
    x.done('t1', 'ok')
    r = co.host()
    assert [s['agent'] for s in r['start']] == ['implementer-t3'] and r['hosting']['running'] == 2


def testHelpersAndHandedTasksOfSubagentsQueueForTheHost(hive, team):
    co = team['coord']
    st, k = first(hive, co, 'Parent work')
    x = hive.sess(k.token)
    x.take('t1')
    s = x.spawn('write the docs', deliver='a README section')
    assert s['launch'] == 'host' and 'prompt' not in s and 'hosts this hive' in s['hint']
    with pytest.raises(Denied): x.host()
    n = co.notices()
    assert 'can start now' in n['host'] and any('call host()' in m['body'] for m in n.get('messages', []))
    r = co.host()
    assert r['start'][0]['agent'] == s['agent'] and 'Why you exist' in r['start'][0]['prompt']
    lead = co.spawn('coordinate the tests', role='coordinator')
    assert 'prompt' in lead and hive.agents.named(lead['agent']).handed
    y = hive.sess(lead['token'])
    y.plan([{'title': 'Run the suite'}])
    d = y.dispatch('t4')
    assert d['launch'] == 'host' and hive.db.one('SELECT run FROM tasks WHERE id=4').run == 1
    assert [z['agent'] for z in co.host()['start']] == ['implementer-t4']


def testGrokHooksBindInjectDeliverGateAndRestart(hive, team):
    co, al = team['coord'], team['alice']
    st, k = first(hive, co)
    assert grok(hive, co, 'substart', 'parent', subagentId='s1', description=st['description']) is None
    assert hive.db.one('SELECT agent FROM runs WHERE key=?', ('s1',)).agent == k.id
    out = json.loads(grok(hive, co, 'pre', 's1', toolName='hive__take', toolInput={'tool_name': 'hive__take', 'tool_input': {'id': 't1'}}))
    assert out['hookSpecificOutput']['updatedInput'] == {'tool_name': 'hive__take', 'tool_input': {'id': 't1', 'agent': k.token}}
    same = {'tool_name': 'hive__take', 'tool_input': {'id': 't1', 'agent': k.token}}
    assert grok(hive, co, 'pre', 's1', toolName='hive__take', toolInput=same) is None
    x = hive.sess(k.token)
    x.take('t1')
    al.send(k.name, 'stop touching main.py', 'interrupt')
    out = json.loads(grok(hive, co, 'post', 's1', toolName='read_file', toolInput={'target_file': 'a.txt'}))
    assert out['decision'] == 'block' and 'INTERRUPT' in out['reason'] and 'main.py' in out['reason']
    assert hive.db.one("SELECT 1 FROM events WHERE agent=? AND kind='activity'", (k.id,))
    out = json.loads(grok(hive, co, 'substop', 's1', subagentId='s1', stopHookActive=False, lastAssistantMessage='done?'))
    assert out['decision'] == 'block' and "done('t1'" in out['reason']
    assert grok(hive, co, 'substop', 's1', subagentId='s1', stopHookActive=True, lastAssistantMessage='I ran out of turns') is None
    k2 = hive.agents.get(k.id)
    assert k2.state == 'pending' and k2.handed is None and any('stopped before finishing' in m.body for m in hive.mail.unread(co.id))
    r = co.host()
    assert r['start'][0]['agent'] == k.name and 'Hive restarted this task' in r['start'][0]['prompt'] and 'I ran out of turns' in r['start'][0]['prompt']
    grok(hive, co, 'prompt', 's2', prompt=r['start'][0]['prompt'])
    assert hive.db.one('SELECT agent,state FROM runs WHERE key=?', ('s2',)) == {'agent': k.id, 'state': 'running'}
    assert hive.db.one('SELECT state FROM runs WHERE key=?', ('s1',)).state == 'ended'
    x.done('t1', 'fixed')
    assert grok(hive, co, 'substop', 's2', subagentId='s2', stopHookActive=False) is None and hive.agents.get(k.id).state == 'left'
    assert grok(hive, co, 'end', 'other', subagentType='explore', reason='shutdown') is None and co.agent.state != 'left'
    assert grok(hive, co, 'post', 'other', toolName='read_file', toolInput={}) is None


def testClaudeCodeShapesBindOnFirstHiveCallAndStopImpersonation(hive, team):
    co = team['coord']
    st, k = first(hive, co)

    def cc(kind, **kw): return handle(kind, {'session_id': 'parent', 'agent_type': 'general-purpose'} | kw, hive, co)
    assert cc('substart', agent_id='a1') is None and not hive.db.one("SELECT 1 FROM runs WHERE key='a1'")
    cc('post', agent_id='a1', tool_name='mcp__hive__take', tool_input={'id': 't1', 'agent': k.token}, tool_response='{}')
    assert hive.db.one("SELECT agent FROM runs WHERE key='a1'").agent == k.id
    out = json.loads(cc('pre', agent_id='a1', tool_name='mcp__hive__progress', tool_input={'text': 'x', 'agent': co.token}))
    assert out['hookSpecificOutput']['updatedInput'] == {'text': 'x', 'agent': k.token}
    out = json.loads(cc('substop', agent_id='a1', stop_hook_active=False, last_assistant_message='hm'))
    assert out['decision'] == 'block'


def testRestartsAreCappedThenTheTaskFails(hive, team):
    co = team['coord']
    st, k = first(hive, co)
    hive.sess(k.token).take('t1')
    for i in range(hive.host.cfg['restarts']+1):
        grok(hive, co, 'substart', 'parent', subagentId=f's{i}', description=st['description'])
        grok(hive, co, 'substop', f's{i}', subagentId=f's{i}', stopHookActive=True)
        if i < hive.host.cfg['restarts']: assert co.host()['start'][0]['agent'] == k.name
    assert hive.tasks.get(1).state == 'failed' and hive.agents.get(k.id).state == 'left'


def testHostingIsExclusiveReleasableAndHoldsBackOnLowMemory(hive, team, monkeypatch):
    co, al = team['coord'], team['alice']
    co.plan([{'title': 'A'}])
    co.host(tasks=False)
    with pytest.raises(Clash): al.host()
    monkeypatch.setattr(build, 'free', lambda: 5.)
    r = co.host()
    assert r['start'] == [] and 'free memory is 5%' in r['held']
    assert co.host(stop=True)['hosting'] is False and hive.host.live() is None and hive.autorun() == 'off'
    assert al.host()['hosting']['max'] == 'no limit'


def testInstallAddsSubagentHooksAndDoctorSeesGaps(root):
    for n in ('grok', 'claude'):
        putHooks(n, 'project', root)
        p = root/H[n]['hooks'][0]
        d = json.loads(p.read_text())
        assert {'SubagentStart', 'SubagentStop'} <= set(d['hooks']) and 'hive__' in d['hooks']['PreToolUse'][0]['matcher']
        assert hooked(n, root, True) == ('project', [])
        del d['hooks']['SubagentStop']
        p.write_text(json.dumps(d))
        assert hooked(n, root, True) == ('project', ['SubagentStop'])


def testGateSkipsTopLevelHiveCallsButNotSubagentsOrEdits(tmp_path):
    got, g = tmp_path/'got', tmp_path/'gate'
    g.write_text(GATE % {'marks': str(tmp_path/'bound'), 'hosting': str(tmp_path/'hosting'), 'up': str(tmp_path/'upgrade'), 'run': f"sh -c 'cat >> {got}; echo \\| >> {got}' --"})
    g.chmod(0o755)

    def run(ev, d):
        got.write_text('')
        subprocess.run([str(g), ev], input=json.dumps(d), text=True, env=dict(os.environ, HIVE_AGENT='x'), check=True)
        return got.read_text()
    assert run('pre', {'toolName': 'hive__take', 'toolInput': {}}) == ''
    assert run('pre', {'toolName': 'hive__take', 'subagentType': 'general-purpose'}) == ''
    (tmp_path/'hosting').mkdir()
    (tmp_path/'hosting'/str(os.getpid())).touch()
    assert 'hive__take' in run('pre', {'toolName': 'hive__take', 'subagentType': 'general-purpose'})
    assert 'mcp__hive__take' in run('pre', {'tool_name': 'mcp__hive__take', 'agent_id': 'a1'})
    assert 'search_replace' in run('pre', {'toolName': 'search_replace', 'toolInput': {'new': 'hive__x'}})
    assert 'read_file' in run('post', {'toolName': 'read_file'})
