import contextlib, os, re, signal, subprocess, sys, threading, time
from collections import Counter
from dataclasses import dataclass
from typing import IO

from .err import Err
from .fault import ENV, FIX, FREE, HARD, RESUME, SAY, alive, backoff, clean, classify, dur, label, same, stamp, tag, tail
from .prompt import mcp
from .tasks import SETTLED
from .util import J, clip, dumps, now, sha

try: import fcntl
except ImportError: fcntl = None

KEYS = ('prompt', 'promptFile', 'task', 'agent', 'token', 'role', 'db', 'root', 'mcp')
PH = re.compile(r'\{(' + '|'.join(KEYS) + r')\}')
SEP = '\n--- hive: attempt '
POL = {'timeout': 7200., 'idle': 1800., 'resumes': 3, 'waits': 12, 'patience': 21600., 'probe': 1800., 'backoff': (5., 600.)}
GATE = {'until': 0., 'strikes': 0, 'since': 0., 'paused': '', 'hard': False, 'probe': 0., 'why': '', 'last': '', 'hits': 0, 'at': 0., 'ok': 0.,
        'by': 0, 'grow': 0.}


@dataclass
class Job:
    agent: str
    aid: int
    task: int
    proc: object
    log: IO[str] | None
    path: object
    at: float
    key: str = ''
    kind: str = ''
    why: str = ''
    skip: frozenset = frozenset()
    idle: float = 0.
    tick: float = 0.


class Adopt:
    def __init__(s, pid): s.pid, s.returncode = pid, None

    def poll(s):
        if s.returncode is None:
            # a zombie still answers kill(pid, 0), so reap it when it happens to be our own child
            with contextlib.suppress(OSError):
                if os.waitpid(s.pid, os.WNOHANG)[0]: s.returncode = 'unknown'
            if not alive(s.pid): s.returncode = 'unknown'
        return s.returncode

    def wait(s, secs=None):
        end = time.monotonic()+(1e9 if secs is None else secs)
        while s.poll() is None:
            if time.monotonic() > end: raise subprocess.TimeoutExpired('adopted agent', secs)
            time.sleep(.1)
        return s.returncode

    def terminate(s): os.kill(s.pid, signal.SIGTERM)

    def kill(s): os.kill(s.pid, signal.SIGKILL)


class Runner:
    def __init__(s, hive, cmds, cap=3, poll=1., op=None, say=None, env=None, watch=False, budget=4, **pol):
        if not cmds: raise ValueError('the runner needs a command, by role or default')
        if bad := set(pol)-set(POL): raise TypeError(f"unknown runner settings: {', '.join(sorted(bad))}")
        s.hive, s.cap, s.poll, s.env, s.watch, s.budget = hive, max(1, cap), poll, env or {}, watch, budget
        s.cmds = {k: [list(x) for x in v] if v and isinstance(v[0], list | tuple) else [list(v)] for k, v in cmds.items()}
        s.pol = {k: pol.get(k, hive.cfg.runner.get(k, v)) for k, v in POL.items()}
        s.calm = 12*float(s.pol['backoff'][0])
        s.keys, got = {}, {}
        for cm in (x for cs in s.cmds.values() for x in cs):
            k = label(cm)
            s.keys[tuple(cm)] = k if got.setdefault(k, cm) == cm else f'{k} #{sha(dumps(cm))[:6]}'
        s.op, s.say, s.jobs, s.beaten, s.idle, s.reset, s.lock, s.hb = op or hive.op('runner'), say or (lambda t: None), {}, 0, set(), 0., None, None
        s.gs = {k: {**GATE, **g, 'cap': min(float(s.cap), g.get('cap', s.cap))} for k, g in hive.faults.gates().items()}
        db = hive.cfg.db.resolve()
        s.dir = hive.cfg.dir/('run' if db == (hive.cfg.dir/'hive.db').resolve() else f'run-{db.stem}-{sha(str(db))[:6]}')
        s.dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def fromCfg(cls, hive, **kw):
        r = hive.cfg.runner
        cmds = {k: [list(v['command']), *map(list, v.get('fallback', []))] for k, v in r.get('roles', {}).items() if v.get('command')}
        kw.setdefault('budget', int(r.get('budget', 4)))
        return cls(hive, kw.pop('cmds', None) or cmds, int(kw.pop('cap', None) or r.get('max', 3)), float(kw.pop('poll', r.get('poll', 1.))), **kw)

    def cmd(s, t): return s.cmds.get(t.role or ('verifier' if t.kind == 'verify' else 'implementer')) or s.cmds.get('default')

    def key(s, cm): return s.keys.get(tuple(cm)) or label(cm)

    def gate(s, k): return s.gs.setdefault(k, {**GATE, 'cap': float(s.cap)})

    def save(s):
        with s.hive.db.tx() as c: s.hive.faults.save(c, s.gs)

    def sync(s):
        if (r := s.hive.faults.reset()) > s.reset:
            for g in s.gs.values():
                if g['at'] <= r: g.update({**GATE, 'cap': float(s.cap), 'at': r})
            s.reset = r
            s.save()

    def ready(s):
        return [t for t in map(s.hive.tasks._d, s.hive.db.q("SELECT * FROM tasks WHERE state='ready' AND owner IS NULL ORDER BY prio DESC,id"))
                if s.cmd(t)]

    def mine(s, st):
        return s.hive.db.q(f"SELECT a.*,t.state tstate,t.owner towner FROM agents a JOIN tasks t ON t.id=a.deleg WHERE a.state IN ({','.join('?'*len(st))}) "
                           "AND (a.launch='runner' OR a.parent=?) ORDER BY a.depth DESC,a.id", (*st, s.op.id))

    def pend(s):
        return [a for a in s.mine(['pending']) if a.tstate in ('ready', 'running') and a.towner in (None, a.id) and a.id not in s.jobs
                and s.cmd(s.hive.tasks.get(a.deleg))]

    def full(s):
        # agents blocked in gather or wait hold a process but not a slot, so parents waiting on children cannot starve them
        return len([j for j in s.jobs if j not in s.idle]) >= s.cap or len(s.jobs) >= s.cap*(s.hive.cfg.depth+2)

    def busy(s, k): return sum(j.key == k and j.aid not in s.idle for j in s.jobs.values())

    def spent(s, n, k):
        got = Counter()
        for (kind, c), v in n.items():
            if c == k: got['resume' if kind in RESUME else 'hard' if kind in HARD else 'env' if kind in ENV else kind] += v
        return got['crash'] >= s.hive.cfg.tries or got['resume'] > s.pol['resumes'] or got['env'] >= s.pol['waits'] or got['hard'] >= 3 or \
            got['resume']+got['onward'] > 5*s.pol['resumes'] or got['env']+got['drift']+got['held'] > 5*s.pol['waits']

    def pick(s, t):
        t0 = now()
        if (t.wake or 0) > t0: return 'wait', None, t.wake
        n, eta = s.hive.faults.counts([t.id]).get(t.id, {}), []
        for cmd in s.cmd(t) or []:
            k = s.key(cmd)
            g = s.gate(k)
            if s.spent(n, k) or g['paused'] and g['hard']: continue
            if g['paused'] and (g['probe'] > t0 or s.busy(k)): eta.append(max(g['probe'], t0+s.poll))
            elif not g['paused'] and g['until'] > t0: eta.append(g['until'])
            elif not g['paused'] and s.busy(k) >= max(1, int(g['cap'])): eta.append(t0+s.poll)
            else: return 'go', cmd, k
        return ('wait', None, min(eta)) if eta else ('stop', None, None)

    def beat(s, on=True):
        if on and now()-s.beaten < 10: return
        s.beaten = on and now()
        with s.hive.db.tx() as c:
            if on: c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('runner', dumps({'roles': sorted(s.cmds), 'pid': os.getpid(), 'ts': now()})))
            elif (r := c.execute("SELECT val FROM meta WHERE key='runner'").fetchone()) and J(r.val).get('pid') == os.getpid():
                c.execute("DELETE FROM meta WHERE key='runner'")

    def pulse(s, stop):
        while not stop.wait(10):
            with contextlib.suppress(Exception): s.beat()

    def mend(s):
        # concurrency cut by a rate limit comes back one slot per calm period (a minute by default) once the command stops failing
        t0, hit = now(), False
        for g in s.gs.values():
            if g['cap'] < s.cap and not g['paused'] and t0-max(g['at'], g['grow']) > s.calm:
                g.update(cap=min(float(s.cap), g['cap']+1), grow=t0)
                hit = True
        if hit: s.save()

    def step(s):
        s.beat()
        s.sync()
        s.mend()
        s.watchdog()
        s.reap()
        s.sweep()
        s.idle = {r.id for r in s.hive.db.q("SELECT id FROM agents WHERE state='idle'")}
        for a in s.pend():
            if s.full(): return
            t = s.hive.tasks.get(a.deleg)
            if (p := s.pick(t))[0] == 'go': s.safe(f'start {a.name}', s.start, a, t, s.op.promptFor(s.hive.sess(a.token), t.id), a.role, p[1], p[2])
        for t in s.ready():
            if s.full(): break
            if (p := s.pick(t))[0] == 'go': s.safe(f'start t{t.id}', s.launch, t, p[1], p[2])

    def safe(s, what, f, *a):
        try: f(*a)
        except Err as e: s.say(f'could not {what}: {e}')
        except Exception as e: s.say(f'could not {what}: {type(e).__name__}: {e}')

    def launch(s, t, cmd, k):
        d = s.op.dispatch(t.id, budget=min(s.budget, s.op.agent.budget) if s.hive.roles.get(t.role or 'implementer').caps & {'fork'} else 0)
        s.start(s.hive.agents.named(d['agent']), s.hive.tasks.get(t.id), d['prompt'], d['role'], cmd, k)

    def start(s, a, t, prompt, role, cmd, k):
        n, tok, h = a.name, a.token, s.hive
        b = h.faults.brief(t, a.id)
        prompt = clean(f'{prompt}\n\n{b}' if b else prompt)
        g = s.gate(k)
        if g['paused']: g['probe'] = now()+s.pol['probe']
        pf, mf, lf = s.dir/f'{n}.prompt.md', s.dir/f'{n}.mcp.json', s.dir/f'{n}.log'
        pf.write_text(prompt)
        env = {'HIVE_DB': str(h.cfg.db), 'HIVE_ROOT': str(h.root), 'HIVE_AGENT_TOKEN': tok, 'HIVE_AGENT': n, 'HIVE_TASK': f't{t.id}'}
        mf.write_text(mcp([sys.executable, '-m', 'hive', 'mcp'], env))
        vals = {'prompt': prompt, 'promptFile': str(pf), 'task': f't{t.id}', 'agent': n, 'token': tok, 'role': role,
                'db': env['HIVE_DB'], 'root': env['HIVE_ROOT'], 'mcp': str(mf)}
        argv = [fill(x, vals) for x in cmd]
        log = open(lf, 'a')
        log.write(f"{SEP}{time.strftime('%Y-%m-%d %H:%M:%S')} ({k}) ---\n")
        log.flush()
        try: p = subprocess.Popen(argv, cwd=h.root, env={**os.environ, **s.env, **env}, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                  start_new_session=True)
        except (OSError, ValueError) as e:
            s.settle(Job(n, a.id, t.id, None, log, None, now(), k, 'setup', f'could not start {argv[0]}: {e}'), None)
            raise Err(f'could not start {argv[0]}: {e}') from None
        with h.db.tx() as c:
            if a.launch and not b: c.execute('UPDATE tasks SET tries=tries+1 WHERE id=?', (t.id,))
            h.agents.set(c, a.id, state='active', pid=p.pid, pidAt=stamp(p.pid))
        s.jobs[a.id] = Job(n, a.id, t.id, p, log, lf, now(), k, skip=frozenset(x.strip() for x in prompt.splitlines() if x.strip()))
        s.say(f'started {n} for t{t.id} with {k} (pid {p.pid}, log {lf})' + (' with a brief of the earlier attempts' if b else ''))

    def watchdog(s):
        t0, hit = now(), False
        for j in list(s.jobs.values()):
            if j.kind or j.proc.poll() is not None: continue
            a, g = s.hive.agents.get(j.aid), s.gate(j.key)
            if a.state == 'idle': j.idle += t0-(j.tick or j.at)
            j.tick = t0
            # an agent that keeps working proves the command, but only after it outlives the last failure by a calm period and never for its own task
            if (g['hits'] or g['strikes'] or g['paused'] and not g['hard']) and j.at > g['at'] and (a.seen or 0) > j.at+1 and t0-j.at > s.calm:
                s.healthy(j.key, by=j.aid)
                hit = True
            quiet, busy = t0-max(j.at, a.seen or 0, mtime(j.path)), t0-j.at-j.idle
            if s.pol['timeout'] and busy > s.pol['timeout']: s.kill(j, 'timeout', f"worked {dur(busy)}, over the {dur(s.pol['timeout'])} limit")
            elif s.pol['timeout'] and t0-j.at > 4*s.pol['timeout']: s.kill(j, 'timeout', f'ran {dur(t0-j.at)}, most of it waiting, over four times the limit')
            elif s.pol['idle'] and a.state != 'idle' and quiet > s.pol['idle']: s.kill(j, 'hang', f'no Hive calls or output for {dur(quiet)}')
        if hit: s.save()

    def signal(s, j, sig):
        try: os.killpg(j.proc.pid, sig)
        except (AttributeError, OSError):
            with contextlib.suppress(OSError): (j.proc.terminate if sig == signal.SIGTERM else j.proc.kill)()

    def kill(s, j, kind, why):
        j.kind, j.why = j.kind or kind, j.why or why
        s.say(f'stopping {j.agent}: {why}')
        s.signal(j, signal.SIGTERM)
        try: j.proc.wait(5)
        except subprocess.TimeoutExpired:
            s.signal(j, signal.SIGKILL)
            with contextlib.suppress(subprocess.TimeoutExpired): j.proc.wait(5)

    def reap(s):
        for j in list(s.jobs.values()):
            if (code := j.proc.poll()) is not None: s.safe(f'settle {j.agent}', s.settle, j, code)

    def sweep(s):
        h = s.hive
        for a in s.mine(['pending']):
            if a.tstate in SETTLED or a.towner not in (None, a.id):
                with h.db.tx() as c: h.agents.set(c, a.id, state='left')
        for a in s.mine(['active', 'idle']):
            if a.id not in s.jobs and a.tstate in ('ready', 'running') and a.towner == a.id and a.pid and s.cmd(h.tasks.get(a.deleg)) \
                    and not same(a.pid, a.pidAt):
                s.safe(f'restart {a.name}', s.lost, a, 'its process ended while the runner was not tracking it')

    def lost(s, a, why):
        t = s.hive.tasks.get(a.deleg)
        with s.hive.db.tx() as c: st = s.handle(c, Job(a.name, a.id, t.id, None, None, None, now(), s.key(s.cmd(t)[0])), a, t, 'lost', why, None, '', None)
        s.save()
        s.say(f'{a.name} was lost; t{t.id} is {st}')

    def settle(s, j, code):
        s.jobs.pop(j.aid, None)
        if j.log: j.log.close()
        h = s.hive
        text = tail(j.path).rsplit(SEP, 1)[-1].split('\n', 1)[-1] if j.path else ''
        with h.db.tx() as c:
            a, t = h.agents.get(j.aid), h.tasks.get(j.task, c)
            for r in c.execute("SELECT id FROM tasks WHERE owner=? AND state IN ('running','ready') AND id!=?", (a.id, t.id)).fetchall():
                h.tasks.release(c, r.id, f'{j.agent} exited with code {code} before finishing (log {j.path})')
            if a.state == 'left' or t.owner != a.id or t.state not in ('ready', 'running'):
                if a.state != 'left': h.agents.set(c, a.id, state='left')
                if t.state in ('done', 'in_review'): s.healthy(j.key, c, a.id)
                st = h.tasks.get(t.id, c).state
            else: st = s.handle(c, j, a, t, *((j.kind, j.why, None) if j.kind else classify(code, text, j.skip)), text, code)
        s.save()
        s.say(f'{j.agent} exited ({code}); t{j.task} is {st}')

    def handle(s, c, j, a, t, k, why, wait, text, code):
        h, g, t0, (lo, hi) = s.hive, s.gate(j.key), now(), s.pol['backoff']
        delay, lone = 0., int(k in ENV and g['ok'] > j.at and g['by'] != a.id)
        if k in ENV:
            g.update(strikes=g['strikes']+1, since=g['since'] or t0, last=k, why=why, at=t0)
            g['until'] = max(g['until'], t0+(wait or backoff(g['strikes']-1, lo, hi)))
            if k == 'rate': g['cap'] = max(1., g['cap']/2)
            if not g['paused'] and t0-g['since'] > s.pol['patience']:
                g.update(paused=why, hard=False)
                s.issue(c, t, f"{SAY[k]} for {dur(t0-g['since'])}: {why}. Its tasks stay queued and Hive tries it again every {dur(s.pol['probe'])}. "
                              f'{FIX[k]}', j.key)
            if g['paused']: g['probe'] = max(g['probe'], t0+s.pol['probe'])
        elif k in HARD:
            g.update(hits=g['hits']+1, last=k, why=why, at=t0)
            if g['hits'] >= 2 and not g['paused']:
                g.update(paused=why, hard=True)
                s.issue(c, t, f'{SAY[k]}: {why}. Its tasks stay queued until it works. {FIX[k]}', j.key)
            delay = backoff(0, lo, hi)
        elif k not in RESUME and k not in FREE:
            delay = backoff(sum(v for (x, cm), v in h.faults.counts([t.id]).get(t.id, {}).items() if x == 'crash' and cm == j.key), lo, hi)
        h.faults.add(c, t.id, a.id, j.key, k, why, clip(text.strip()[-1500:], 1500), code, now()-j.at, delay or max(0., g['until']-t0) * (k in ENV),
                     h.faults.made(c, a.id, j.at) if k not in FREE else 0, lone)
        n = h.faults.counts([t.id]).get(t.id, {})
        if not [cm for cm in s.cmd(t) or [] if not s.spent(n, s.key(cm))]: return s.giveUp(c, a, t, k, why, n)
        c.execute("UPDATE tasks SET state='ready',wake=? WHERE id=?", (t0+delay if delay else 0, t.id))
        h.agents.set(c, a.id, state='pending', task=None)
        return f'ready; {a.name} restarts' + (f' in {dur(delay)}' if delay >= 1 else f" after a {dur(g['until']-t0)} cooldown" if k in ENV else '') + \
            ' with a brief of its progress'

    def giveUp(s, c, a, t, k, why, n):
        h, tried = s.hive, Counter()
        for (x, cm), v in n.items(): tried[x, cm] += v
        how = '; '.join(f"{cm}: {', '.join(f'{SAY.get(x, x)} x{v}' for (x, c2), v in tried.items() if c2 == cm)}" for cm in dict.fromkeys(c2 for _, c2 in tried))
        diag = f"{a.name} {SAY[k]}: {why}. Out of retries ({how}). {FIX.get(k, '')} retry('t{t.id}') reopens it with a brief of every attempt."
        c.execute('UPDATE tasks SET notes=? WHERE id=?', (dumps([*t.notes, {'by': 'runner', 'failed': diag}]), t.id))
        h.tasks.finish(c, None, h.tasks.get(t.id, c), 'failed', diag)
        h.agents.set(c, a.id, state='left')
        s.issue(c, h.tasks.get(t.checks, c) if t.kind == 'verify' and t.checks else t, diag, ref=t)
        return 'failed'

    def issue(s, c, t, need, key=None, ref=None):
        h = s.hive
        if key:
            if c.execute("SELECT 1 FROM issues WHERE state='open' AND substr(need,1,?)=?", (len(tag(key)), tag(key))).fetchone(): return
            need, to = tag(key) + need, None
        else: need, to = f't{(ref or t).id} {need}', t.creator and h.agents.heir(c, t.creator)
        i = c.execute("INSERT INTO issues(src,holder,need,options,ts) VALUES(?,?,?,?,?)",
                      (s.op.id, to and to.id, need, dumps(['retry'] + ([] if key else ['cancel'])), now())).lastrowid
        h.log.add(c, s.op.id, 'issue.raised', f"i{i} to {to.name if to else 'whoever runs the hive'}: {clip(need, 160)}", 'runner')
        s.say(f'issue i{i}: {need}')

    def healthy(s, k, c=None, by=0):
        g = s.gate(k)
        g.update(strikes=0, since=0., hits=0, ok=now(), by=by, cap=min(float(s.cap), g['cap']+1))
        if g['paused'] and not g['hard']:
            g.update(paused='', probe=0., until=0., at=now())
            with contextlib.nullcontext(c) if c else s.hive.db.tx() as cc:
                cc.execute("UPDATE issues SET state='decided',choice='recovered',doneAt=? WHERE state='open' AND substr(need,1,?)=?",
                           (now(), len(tag(k)), tag(k)))
                s.hive.log.add(cc, s.op.id, 'runner.recovered', f'{k} works again; its queued tasks resume', 'runner')
            s.say(f'{k} works again')

    def recover(s):
        h, t0 = s.hive, now()
        if (r := h.db.one("SELECT val FROM meta WHERE key='runner'")) and (m := J(r.val)).get('pid') != os.getpid() and alive(m.get('pid')) \
                and t0-m.get('ts', 0) < 60:
            raise Err(f"another runner (pid {m['pid']}) is already running this session", 'stop it first, or let it finish')
        for a in s.mine(['active', 'idle']):
            if a.id in s.jobs or a.tstate not in ('ready', 'running') or a.towner != a.id or not (cs := s.cmd(t := h.tasks.get(a.deleg))): continue
            if same(a.pid, a.pidAt):
                s.jobs[a.id] = Job(a.name, a.id, t.id, Adopt(a.pid), None, s.dir/f'{a.name}.log', t0, s.key(cs[0]))
                s.say(f'adopted {a.name} (pid {a.pid}), still working on t{t.id}')
            else: s.safe(f'restart {a.name}', s.lost, a, 'its process was gone when the runner restarted')
        s.save()

    def claim(s):
        if not fcntl: return
        s.lock = open(s.dir/'runner.lock', 'w')
        try: fcntl.flock(s.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            s.lock.close()
            s.lock = None
            raise Err('another runner is already running this session', 'stop it first, or let it finish') from None

    def blocked(s): return sorted({f"{k}: {g['why']}" for k, g in s.gs.items() if g['paused'] and g['hard']})

    def stuck(s): return {k: v for k, v in s.hive.tasks.counts().items() if k in ('pending', 'ready', 'running', 'in_review')}

    def waiting(s): return any(s.pick(x)[0] != 'stop' for x in [*s.ready(), *(s.hive.tasks.get(a.deleg) for a in s.pend())])

    def run(s, timeout=None):
        end = timeout and time.monotonic()+timeout
        s.claim()
        stop = threading.Event()
        th = threading.Thread(target=s.pulse, args=(stop,), daemon=True)
        try:
            s.recover()
            th.start()
            while True:
                s.step()
                if not s.watch and not s.jobs and not s.waiting(): break
                if end and time.monotonic() > end:
                    s.say('timeout; stopping agents')
                    s.stop()
                    break
                time.sleep(s.poll)
        except KeyboardInterrupt:
            s.say('interrupted; stopping agents')
            s.stop()
        finally:
            stop.set()
            if th.is_alive(): th.join(15)
            s.beat(False)
            if s.lock: s.lock.close()
        return {'counts': s.hive.tasks.counts(), 'stuck': s.stuck()} | ({'paused': b} if (b := s.blocked()) else {})

    def stop(s):
        for j in s.jobs.values():
            j.kind, j.why = j.kind or 'stopped', j.why or 'the runner stopped'
            s.signal(j, signal.SIGTERM)
        end = time.monotonic()+10
        for j in s.jobs.values():
            try: j.proc.wait(max(.1, end-time.monotonic()))
            except subprocess.TimeoutExpired:
                s.signal(j, signal.SIGKILL)
                with contextlib.suppress(subprocess.TimeoutExpired): j.proc.wait(5)
        s.reap()


def mtime(p):
    try: return os.path.getmtime(p)
    except (OSError, TypeError): return 0.


def fill(t, vals): return PH.sub(lambda m: vals[m[1]], t)
