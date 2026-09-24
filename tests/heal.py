import json, os, signal, subprocess, sys, textwrap, threading, time

import httpx
import pytest

from hive.cli import main
from hive.err import Err
from hive.fault import alive, backoff, classify, hint, label, same, span, stamp
from hive.run import Runner
from hive.summ import Fail, Llm
from hive.util import dumps, now

AGENT = textwrap.dedent('''
    import json, os, sys, time
    from hive import Hive
    root, t = os.environ['HIVE_ROOT'], os.environ['HIVE_TASK']
    me = Hive.open(os.environ['HIVE_DB'], root).sess(os.environ['HIVE_AGENT_TOKEN'])
    steps = json.load(open(os.path.join(root, 'steps.json')))[t]
    runs = os.path.join(root, t + '.runs')
    n = len(open(runs).read().splitlines()) if os.path.exists(runs) else 0
    open(runs, 'a').write(f"{os.environ['HIVE_AGENT']} {sys.argv[2]} {time.time()} {os.getpid()}\\n")
    kind, _, arg = steps[min(n, len(steps)-1)].partition(':')
    try: prompt = open(sys.argv[1]).read()
    except OSError: prompt = sys.argv[1]
    if kind == 'echo': sys.exit(print(prompt) or print('Error: sandbox setup failed') or 1)
    if kind == 'nul': sys.exit(sys.stdout.write('binary junk \\x00\\x01 from a tool\\nValueError: boom\\n') and 1)
    if kind == 'rate': sys.exit(print(arg or 'Error: 429 Too Many Requests') or 1)
    if kind == 'auth': sys.exit(print('Error: 401 Unauthorized: invalid API key') or 1)
    if kind == 'crash': sys.exit(print('Traceback (most recent call last):\\nValueError: boom') or 1)
    me.take(t)
    if kind == 'turns':
        me.write(t + '.part1', 'first half\\n')
        me.progress('wrote the first half; the second half is next')
        sys.exit(print('Error: max turns reached') or 1)
    if kind == 'hang': time.sleep(60)
    if kind == 'slow':
        for _ in range(600):
            me.progress('still going')
            time.sleep(.1)
    if kind == 'flag':
        while not os.path.exists(os.path.join(root, 'go')): time.sleep(.1)
    if kind == 'quit': sys.exit(0)
    if kind == 'failhard': sys.exit(me.fail(t, 'cannot do this') and 0)
    if kind == 'idlewait':
        me.spawn('never started', launch='host')
        while True: me.gather(secs=30)
    if kind == 'failretry': sys.exit(me.fail(t, 'someone else should try', retry=True) and 0)
    if kind == 'verify': sys.exit(me.verify(me.task(t)['task']['checks'], True, 'looks right') and 0)
    if kind == 'parent':
        me.spawn('count to twenty-five slowly', launch='runner')
        me.done(t, 'kid said: ' + me.gather(secs=60)['settled'][0]['result'])
        sys.exit(0)
    if kind == 'tick':
        for i in range(int(arg)):
            me.progress(f'tick {i}')
            time.sleep(.1)
    if kind == 'tickrate':
        for i in range(int(arg)):
            me.progress(f'tick {i}')
            time.sleep(.1)
        sys.exit(print('Error: 429 Too Many Requests') or 1)
    brief = 'this is attempt' in prompt
    me.done(t, 'finished' + (' after reading the brief' if brief else '') + (' with the first half kept' if brief and t + '.part1' in prompt
                                                                            and 'wrote the first half' in prompt else ''))
''')


@pytest.fixture
def run(hive, tmp_path):
    (p := tmp_path/'agent.py').write_text(AGENT)
    main_, backup = [sys.executable, str(p), '{promptFile}', 'main'], [sys.executable, str(p), '{promptFile}', 'backup']
    out = {'lines': []}
    (hive.cfg.dir/'config.toml').write_text('[insights]\nauto = false\n')
    hive.know.auto = False

    def go(steps, cmds=None, secs=60, plan=None, **kw):
        (hive.root/'steps.json').write_text(json.dumps(steps))
        if plan is not False and not hive.db.q('SELECT 1 FROM tasks'):
            hive.op().plan(plan or [{'key': k, 'title': k} for k in steps])
        kw = {'poll': .05, 'backoff': (.05, .1), 'idle': 0, 'timeout': 0} | kw
        r = Runner(hive, cmds or {'default': main_}, say=out['lines'].append, **kw)
        out['runner'] = r
        return r.run(secs) if secs else r
    go.main, go.backup, go.out = main_, backup, out
    return go


def runs(hive, t): return [x.split() for x in (hive.root/f'{t}.runs').read_text().splitlines()]


def kinds(hive): return [r.kind for r in hive.db.q('SELECT kind FROM faults ORDER BY id')]


def testClassifierReadsHarnessErrorsAndWaitHints():
    k, why, w = classify(1, 'working...\nAPI Error: 429 {"type":"rate_limit_error"}\nRetry-After: 30')
    assert (k, w) == ('rate', 30.)
    k, _, w = classify(1, f'Claude AI usage limit reached|{int(now())+3600}')
    assert k == 'rate' and 3500 < w <= 3600
    assert classify(1, "You've hit your usage limit. Try again in 2 days 3 hours.")[2] == 2*86400+3*3600
    assert span('1h30m') == 5400 and span('20s') == 20 and span('250ms') == .25
    assert classify(1, '{"text": "done"}\nError: max turns reached')[0] == 'turns'
    assert classify(1, 'Error: prompt is too long: 250000 tokens > 200000 maximum')[0] == 'context'
    assert classify(1, 'Error: 401 Unauthorized')[0] == 'auth'
    assert classify(1, 'httpx.ConnectError: [Errno 61] Connection refused')[0] == 'net'
    assert classify(127, '')[0] == 'setup'
    assert classify(1, 'Invalid API key · Please run /login')[0] == 'auth' and classify(1, 'Credit balance is too low')[0] == 'auth'
    assert classify(1, 'Your input exceeds the context window of this model. Please adjust your input and try again.')[0] == 'context'
    assert classify(1, 'API Error: 529 {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}')[0] == 'rate'
    assert classify(1, '[API Error: You exceeded your current quota, please check your plan]')[0] == 'rate'
    assert classify(1, 'stream error: exceeded retry limit, last status: 429 Too Many Requests')[0] == 'rate'
    assert classify(1, 'API Error: Request timed out.')[0] == 'net' and classify(1, 'Error: 503 Service Unavailable')[0] == 'net'
    assert classify(1, '  "text": "I fixed the 429 rate limit handling",\n}')[0] == 'crash'
    assert classify(0, 'rate limit hit once\nretried fine\nall good\nbye')[0] == 'quit'
    assert label(['grok', '-p', 'x', '-m', 'grok-4']) == 'grok grok-4' and label([sys.executable, 'a/agent.py', '{prompt}']).endswith(' agent.py')


def testRateLimitsCoolTheCommandWithoutSpendingRetries(hive, run):
    t = time.monotonic()
    r = run({'t1': ['rate:Error: 429 Too Many Requests. Retry-After: 1'] * 3 + ['done']}, cap=2)
    assert r['counts'] == {'done': 1} and kinds(hive) == ['rate'] * 3
    xs = runs(hive, 't1')
    assert len(xs) == 4 and len({x[0] for x in xs}) == 1 and all(float(b[2])-float(a[2]) >= .9 for a, b in zip(xs, xs[1:]))
    assert time.monotonic()-t < 30
    g = hive.faults.show()['commands'][0]
    assert g['state'] == 'ok' and g['concurrency'] == 2


def testFallbackTakesOverWhileTheCommandIsRateLimited(hive, run):
    t = time.monotonic()
    r = run({'t1': ['rate:429 rate limit exceeded, retry after 60s', 'done']}, {'default': [run.main, run.backup]})
    assert r['counts'] == {'done': 1} and [x[1] for x in runs(hive, 't1')] == ['main', 'backup'] and time.monotonic()-t < 15
    assert [g['state'] for g in hive.faults.show()['commands']] == ['cooling', 'ok']


def testTurnLimitRestartsTheSameAgentWithItsProgress(hive, run):
    r = run({'t1': ['turns', 'done']})
    assert r['counts'] == {'done': 1} and kinds(hive) == ['turns']
    assert hive.tasks.get(1).result == 'finished after reading the brief with the first half kept'
    assert len({x[0] for x in runs(hive, 't1')}) == 1 and (hive.root/'t1.part1').read_text() == 'first half\n'
    assert 'Hive restarted this task; this is attempt 2' in (hive.cfg.dir/'run'/'implementer-t1.prompt.md').read_text()


def testRestartsThatSaveProgressAreFreeWithinACap(hive, run):
    assert run({'t1': ['turns'] * 4 + ['done']}, resumes=1)['counts'] == {'done': 1} and kinds(hive) == ['turns'] * 4
    assert hive.db.one("SELECT MIN(made) n FROM faults").n > 0
    hive.op().plan([{'title': 'endless'}])
    assert run({'t1': ['done'], 't2': ['turns'] * 20}, resumes=1, plan=False)['counts'] == {'done': 1, 'failed': 1}
    assert kinds(hive).count('turns') == 4 + 6


def testHungAndOverdueAgentsAreStoppedAndRestarted(hive, run):
    t = time.monotonic()
    r = run({'t1': ['hang', 'done'], 't2': ['slow', 'done']}, idle=3, timeout=6, cap=2)
    assert r['counts'] == {'done': 2} and sorted(kinds(hive)) == ['hang', 'timeout'] and time.monotonic()-t < 30
    assert not any(alive(int(x[3])) for t_ in ('t1', 't2') for x in runs(hive, t_))
    assert 'no Hive calls or output' in hive.db.one("SELECT why FROM faults WHERE kind='hang'").why


def testAuthFailuresPauseTheCommandUntilRetried(hive, run):
    r = run({'t1': ['auth', 'auth', 'done']})
    assert r['counts'] == {'ready': 1} and r['paused'] and kinds(hive) == ['auth', 'auth']
    [i] = hive.db.q("SELECT * FROM issues WHERE state='open'")
    assert i.need.startswith('runner [python') and 'hive retry' in i.need
    assert hive.faults.show()['commands'][0]['state'] == 'paused'
    assert hive.op().retry(note='rotated the key')['issuesClosed'] == 1
    assert run({'t1': ['auth', 'auth', 'done']}, plan=False)['counts'] == {'done': 1}


def testExhaustedTaskFailsWithADiagnosisAndRetryResumesIt(hive, run, capsys):
    r = run({'t1': ['crash', 'crash', 'done'], 't2': ['done']}, plan=[{'key': 'a', 'title': 'a'}, {'title': 'b', 'after': ['a']}])
    assert r['counts'] == {'failed': 1, 'blocked': 1}
    t = hive.tasks.get(1)
    assert 'crashed' in t.result and "retry('t1')" in t.result and 'ValueError: boom' in t.result
    op = hive.op()
    assert any('failed' in m['body'] for m in op.notices()['interrupts'])
    [i] = hive.db.q("SELECT * FROM issues WHERE state='open'")
    assert i.need.startswith('t1 ') and i.holder == op.id
    assert main(['--db', str(hive.cfg.db), '--root', str(hive.root), 'retry', 't1', '--note', 'fixed the env']) == 0
    assert json.loads(capsys.readouterr().out)['issuesClosed'] == 1 and hive.tasks.get(2).state == 'pending'
    assert run({'t1': ['crash', 'crash', 'done'], 't2': ['done']}, plan=False)['counts'] == {'done': 2}
    assert len({x[0] for x in runs(hive, 't1')}) == 1 and len(runs(hive, 't1')) == 3
    assert hive.tasks.get(1).result == 'finished after reading the brief'
    main(['--db', str(hive.cfg.db), '--root', str(hive.root), 'faults', '--json'])
    assert any('crashed' in x for x in json.loads(capsys.readouterr().out)['faults'])


def testStoppedAndLostAgentsResumeUnderANewRunner(hive, run):
    r = run({'t1': ['hang', 'hang', 'done']}, secs=1)
    assert r['counts'] == {'ready': 1} and kinds(hive) == ['stopped']
    r1 = run({'t1': ['hang', 'hang', 'done']}, secs=0, plan=False)
    r1.recover()
    r1.step()
    [j] = r1.jobs.values()
    while len(runs(hive, 't1')) < 2: time.sleep(.05)
    os.killpg(j.proc.pid, signal.SIGKILL)
    j.proc.wait()
    assert run({'t1': ['hang', 'hang', 'done']}, plan=False)['counts'] == {'done': 1}
    assert kinds(hive) == ['stopped', 'lost'] and len({x[0] for x in runs(hive, 't1')}) == 1
    assert 'was lost when the runner stopped' in (hive.cfg.dir/'run'/'implementer-t1.prompt.md').read_text()


def testANewRunnerAdoptsAgentsThatAreStillWorking(hive, run):
    r1 = run({'t1': ['flag']}, secs=0)
    r1.recover()
    r1.step()
    threading.Timer(1.5, (hive.root/'go').touch).start()
    r = run({'t1': ['flag']}, plan=False)
    assert r['counts'] == {'done': 1} and kinds(hive) == [] and len(runs(hive, 't1')) == 1
    assert any('adopted implementer-t1' in x for x in run.out['lines'])


def testOnlyOneRunnerDrivesASession(hive, run):
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        with hive.db.tx() as c: c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('runner', dumps({'roles': ['default'], 'pid': p.pid, 'ts': now()})))
        with pytest.raises(Err, match='another runner'): run({'t1': ['done']})
    finally:
        p.kill()
        p.wait()


def testEarlyExitIsResumedWithinItsBudget(hive, run):
    r = run({'t1': ['quit'] * 5}, resumes=2)
    assert r['counts'] == {'failed': 1} and kinds(hive) == ['quit'] * 3
    assert 'exited without finishing' in hive.tasks.get(1).result and 'Make the goal' in hive.tasks.get(1).result


def testSummarizerRetriesRateLimitsThenFallsBack(monkeypatch):
    got = []

    def post(url, **kw):
        got.append(url)
        if len(got) == 1: return httpx.Response(429, headers={'retry-after': '0'}, request=httpx.Request('POST', url))
        return httpx.Response(200, json={'choices': [{'message': {'content': 'short'}}]}, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', post)
    monkeypatch.setattr('hive.summ.time.sleep', lambda s: None)
    assert Llm('http://x', 'k', 'm')('long text', 'focus', 50) == 'short' and len(got) == 2
    monkeypatch.setattr(httpx, 'post', lambda url, **kw: httpx.Response(503, request=httpx.Request('POST', url)))
    with pytest.raises(Fail): Llm('http://x', 'k', 'm')('long text', 'focus', 50)


def testClassifierIgnoresToolOutputProseAndEchoedPrompts(hive, run):
    tb = 'Traceback (most recent call last):\n  File "/app/agent.py", line 429, in main\n    run()\nKeyError: x'
    assert classify(1, tb)[0] == 'crash' and classify(1, tb.replace('429', '401'))[0] == 'crash'
    assert classify(1, 'FAILED tests/test_authentication.py::test_login - AssertionError\n1 failed')[0] == 'crash'
    assert classify(1, 'Error: test_rate_limiter failed: expected 3 calls, got 2')[0] == 'crash'
    for x in ('Done. I added rate limiting to the API client.', 'Unauthorized users now get a 401 instead of a 500.', 'Retries now back off on timeouts.'):
        assert classify(0, x)[0] == 'quit'
    assert classify(1, 'the rate limit hit\nError: sandbox setup failed', {'the rate limit hit'})[0] == 'crash'
    assert classify(1, '5-hour limit reached ∙ resets 3pm')[0] == 'rate'
    assert classify(1, "Codex ran out of room in the model's context window. Start a new thread.")[0] == 'context'
    assert classify(1, "This model's maximum context length is 128000 tokens.")[0] == 'context'
    assert classify(53, 'Reached max session turns for this session.')[0] == 'turns'
    assert classify(1, 'When using Gemini API, you must specify the GEMINI_API_KEY environment variable.')[0] == 'setup'
    assert classify(1, '[API Error: You exceeded your current quota, please check your plan and billing details. Please retry in 30.5s.]')[:3:2] == ('rate', 30.5)
    assert backoff(1100) <= 600 and stamp(os.getpid())
    r = run({'t1': ['echo', 'echo', 'done']})
    assert r['counts'] == {'failed': 1} and kinds(hive) == ['crash', 'crash']


def testControlCharactersNeverReachAPrompt(hive, run):
    r = run({'t1': ['nul', 'done']}, {'default': [sys.executable, run.main[1], '{prompt}', 'main']})
    assert r['counts'] == {'done': 1} and '\x00' not in hive.db.one('SELECT tail FROM faults').tail


def testRetryReachesARunnerThatIsAlreadyRunning(hive, run):
    r = run({'t1': ['auth', 'auth', 'auth', 'auth', 'done']}, secs=0, watch=True)
    th = threading.Thread(target=r.run, args=(15,))
    th.start()
    while th.is_alive() and [g['state'] for g in hive.faults.show()['commands']] != ['paused']: time.sleep(.05)
    hive.op().retry(note='fixed the key')
    while th.is_alive() and len(kinds(hive)) < 4: time.sleep(.05)
    hive.op().retry(note='really fixed it')
    while hive.tasks.get(1).state != 'done' and th.is_alive(): time.sleep(.05)
    assert hive.tasks.get(1).state == 'done' and kinds(hive) == ['auth'] * 4
    r.watch = False
    th.join()


def testAReusedPidIsNeverAdopted(hive, run):
    victim = subprocess.Popen(['sleep', '60'], start_new_session=True)
    try:
        r = run({'t1': ['done']}, secs=0)
        d = r.op.dispatch('t1')
        with hive.db.tx() as c: c.execute("UPDATE agents SET pid=?,pidAt='Mon Jan  1 00:00:00 2001' WHERE name=?", (victim.pid, d['agent']))
        assert r.run(20)['counts'] == {'done': 1} and kinds(hive) == ['lost'] and victim.poll() is None
    finally:
        victim.kill()
        victim.wait()


def testTheRunnerLockKeepsASecondRunnerOut(hive, run):
    r1 = run({'t1': ['done']}, secs=0)
    r1.claim()
    try:
        with pytest.raises(Err, match='another runner'): run({'t1': ['done']}, plan=False)
    finally: r1.lock.close()
    assert run({'t1': ['done']}, plan=False)['counts'] == {'done': 1}


def testRetryingAFailedVerificationRestoresTheReview(hive, run):
    r = run({'t1': ['done'], 't2': ['crash', 'crash', 'verify']}, plan=[{'title': 'x', 'verify': True}])
    assert r['counts'] == {'failed': 2}
    op = hive.op()
    [i] = hive.db.q("SELECT * FROM issues WHERE state='open'")
    assert i.need.startswith('t2 ') and i.holder == op.id
    got = op.retry('t1')
    assert got['task']['id'] == 't2' and got['issuesClosed'] == 1 and hive.tasks.get(1).state == 'in_review' and hive.tasks.get(1).result
    assert run({'t1': ['done'], 't2': ['crash', 'crash', 'verify']}, plan=False)['counts'] == {'done': 2}


def testRetryUnblocksEveryDependentPath(hive):
    op = hive.op()
    op.plan([{'key': 'a', 'title': 'a'}, {'key': 'b', 'title': 'b', 'after': ['a']}, {'key': 'c', 'title': 'c', 'after': ['a']},
             {'key': 'd', 'title': 'd', 'after': ['c']}, {'title': 'e', 'after': ['b', 'd']}])
    op.cancel('t1', 'oops')
    op.retry('t1')
    assert [hive.tasks.get(i).state for i in range(1, 6)] == ['ready', 'pending', 'pending', 'pending', 'pending']


def testTimeLimitsCountWorkNotWaitingOnChildren(hive, run):
    r = run({'t1': ['parent'], 't2': ['tick:40', 'done']}, timeout=2.5, plan=[{'title': 'parent'}])
    assert r['counts'] == {'done': 2} and [(f.task, f.kind) for f in hive.db.q('SELECT task,kind FROM faults')] == [(2, 'timeout')]
    assert hive.tasks.get(1).result.startswith('kid said: finished')


def testRetryGivesADelegationBackItsBudget(hive, run):
    top = hive.join('top', 'coordinator')
    kid = top.spawn('doomed', launch='runner', budget=4)
    run({kid['task']: ['crash', 'crash', 'done']}, plan=False)
    assert hive.tasks.get(1).state == 'failed' and hive.agents.named(kid['agent']).budget == 0
    top.retry(kid['task'])
    assert hive.agents.named(kid['agent']).budget == 4 and run({kid['task']: ['crash', 'crash', 'done']}, plan=False)['counts'] == {'done': 1}


def testAgentsWaitingOnAnEndedTaskRetire(hive, run):
    r = run({'t1': ['crash', 'done']}, secs=0, backoff=(30, 60))
    while not kinds(hive):
        r.step()
        time.sleep(.05)
    hive.op().cancel('t1', 'not needed')
    r.step()
    assert hive.agents.named('implementer-t1').state == 'left'


def testRestartsDoNotUseUpAgentFailRetries(hive, run):
    assert run({'t1': ['rate', 'failretry', 'done']})['counts'] == {'done': 1}
    assert [x[0] for x in runs(hive, 't1')] == ['implementer-t1', 'implementer-t1', 'implementer-t1-2']


def testRetryingAHostDelegationLeavesItFreeToTake(hive, run):
    top = hive.join('top', 'coordinator')
    kid = hive.sess(top.spawn('side job', launch='host')['token'])
    kid.take()
    kid.fail(kid.agent.deleg, 'stuck')
    got = top.retry('t1')
    assert got['agent'] is None and got['task']['owner'] is None
    assert run({'t1': ['done']}, plan=False)['counts'] == {'done': 1}


def testProductiveWorkResetsThePatienceClock(hive, run):
    r = run({'t1': ['rate', 'tickrate:30', 'done']}, patience=2, secs=30)
    assert r['counts'] == {'done': 1} and kinds(hive) == ['rate', 'rate'] and not hive.db.q("SELECT 1 FROM issues")


def testEachCommandGetsItsOwnIssue(hive, run):
    alt = run.main + ['--model', 'alt']
    r = run({'t1': ['auth'] * 4 + ['done']}, {'default': [run.main, alt]})
    assert r['counts'] == {'ready': 1} and len(r['paused']) == 2
    assert sorted(i.need.split('] ')[0] for i in hive.db.q("SELECT need FROM issues WHERE state='open'")) == sorted(f'runner [{label(x)}' for x in (run.main, alt))


def testBackoffKeepsGrowingWhileOtherAgentsWork(hive, run):
    r = run({'t1': ['tick:120', 'done'], 't2': ['rate'] * 5 + ['done']}, cap=32, backoff=(.2, 5))
    assert r['counts'] == {'done': 2}
    ts = [float(x[2]) for x in runs(hive, 't2')]
    gaps = [b-a for a, b in zip(ts, ts[1:])]
    assert len(gaps) == 5 and gaps[3] > 2*gaps[0] and ts[4] < float(runs(hive, 't1')[0][2])+12


def testLongOutagesNeverFailALoneTask(hive, run):
    assert 0 < hint(['5-hour limit reached ∙ resets 3pm']) <= 86400 and 0 < hint(['Weekly limit reached ∙ resets Oct 9, 10am (Europe/Paris)'])
    assert run({'t1': ['rate'] * 15 + ['done']}, waits=3)['counts'] == {'done': 1} and kinds(hive) == ['rate'] * 15
    r = run({'t1': ['done']}, secs=0, plan=False, waits=3)
    with hive.db.tx() as c:
        for _ in range(3): hive.faults.add(c, 1, None, 'x', 'rate', lone=1)
    assert r.spent(hive.faults.counts([1])[1], 'x')


def testProcessStampsIgnoreTimezoneAndMissingTools(hive, monkeypatch):
    monkeypatch.setenv('TZ', 'Asia/Tokyo')
    a = stamp(os.getpid())
    monkeypatch.setenv('TZ', 'UTC')
    assert a and stamp(os.getpid()) == a and same(os.getpid(), a) and same(os.getpid(), '') and not same(os.getpid(), 'Mon Jan  1 00:00:00 2001')


def testMoreEdgesFromTheSecondReview(hive, run, tmp_path):
    assert classify(1, 'I fixed the login flow; unauthorized users now get a 401 instead of a 500.')[0] == 'crash'
    assert classify(1, 'Error: Unauthorized')[0] == 'auth' and classify(1, 'Forbidden: this key cannot use the model')[0] == 'auth'
    top = hive.join('top', 'coordinator')
    kid = top.spawn('research', 'researcher', launch='runner')
    with hive.db.tx() as c: c.execute("UPDATE agents SET state='active',pid=999999 WHERE name=?", (kid['agent'],))
    r = run({kid['task']: ['done']}, {'implementer': run.main}, secs=0, plan=False)
    r.step()
    assert not [x for x in run.out['lines'] if 'could not' in x]
    other = type(hive).open(hive.root/'.hive'/'sessions'/'hive.db', hive.root)
    assert Runner(other, {'default': run.main}).dir != r.dir
    other.close()


def testWaitingForeverIsBoundedByTheWallClock(hive, run):
    r = run({'t1': ['idlewait']}, timeout=2, resumes=0)
    assert r['counts'] == {'failed': 1, 'cancelled': 1} and kinds(hive) == ['timeout']
    assert 'over four times the limit' in hive.db.one('SELECT why FROM faults').why


def testBudgetComesBackEvenWhenTheAgentFailedItself(hive, run):
    top = hive.join('top', 'coordinator')
    kid = top.spawn('doomed', launch='runner', budget=4)
    run({kid['task']: ['failhard', 'done']}, plan=False)
    assert hive.agents.named(kid['agent']).budget == 0
    top.retry(kid['task'])
    assert hive.agents.named(kid['agent']).budget == 4 and run({kid['task']: ['failhard', 'done']}, plan=False)['counts'] == {'done': 1}


def testOwnHiveCallsNeverCountAsTheCommandWorking(hive, run):
    r = run({'t1': ['tickrate:3'] * 8 + ['done']}, waits=2, backoff=(.2, 5))
    assert r['counts'] == {'done': 1} and not hive.db.q('SELECT 1 FROM faults WHERE lone=1')
    ts = [float(x[2]) for x in runs(hive, 't1')]
    assert ts[5]-ts[4] > ts[1]-ts[0]


def testClockHintsHandlePassedTimesAndDates(monkeypatch):
    import datetime as dt
    from hive import fault
    real = dt.datetime

    class Fixed(real):
        @classmethod
        def now(cls, tz=None): return real(2026, 9, 23, 15, 5, tzinfo=tz) if tz else real(2026, 9, 23, 15, 5)

    monkeypatch.setattr(fault.datetime, 'datetime', Fixed)
    monkeypatch.setattr(fault, 'now', lambda: Fixed.now().timestamp())
    h = lambda x: fault.hint([x])
    assert h('limit reached, resets 3pm') == 60 and h('limit reached, resets Sep 23, 3pm') == 60
    assert h('limit reached, resets 4pm') == 3300 and h('limit reached, resets 3am') == 11*3600+55*60
    assert h('limit reached, resets Jan 5, 10am') == 7*86400 and h('limit reached, resets Sep 24, 3:05pm') == 86400


def testLoginProseStaysACrash():
    for x in ('Added a redirect to /login for expired sessions.', 'Unauthorized requests now return 401 with a JSON body.',
              'Fixed: invalid API key error message now names the env var.', 'Forbidden paths are now rejected with a clear message.',
              'Error: tests/test_api.py::test_upload timed out after 30s'):
        assert classify(1, x + '\nError: write EPIPE')[0] == 'crash', x
    assert classify(1, 'Invalid API key · Please run /login')[0] == 'auth' and classify(1, 'Error: request timed out')[0] == 'net'
    assert classify(1, 'Forbidden')[0] == 'auth' and classify(1, 'Error: Invalid API key provided')[0] == 'auth'


def testHeldRetriesEndEventually(hive, run):
    r = run({'t1': ['rate'] * 30}, waits=2)
    assert r['counts'] == {'failed': 1} and len(kinds(hive)) == 11


def testDispatchedAgentsGetTheirBudgetBackOnRetry(hive, run):
    run({'t1': ['crash', 'crash', 'done']}, plan=[{'title': 'x', 'role': 'implementer'}], budget=4)
    assert hive.agents.named('implementer-t1').budget == 0
    hive.op().retry('t1')
    assert hive.agents.named('implementer-t1').budget == 4
