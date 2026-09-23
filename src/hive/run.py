import os, re, subprocess, sys, time
from dataclasses import dataclass
from typing import IO

from .err import Err
from .prompt import mcp
from .util import now

KEYS = ('prompt', 'promptFile', 'task', 'agent', 'token', 'role', 'db', 'root', 'mcp')
PH = re.compile(r'\{(' + '|'.join(KEYS) + r')\}')


@dataclass
class Job:
    agent: str
    aid: int
    task: int
    proc: subprocess.Popen
    log: IO[str]
    path: object
    at: float


class Runner:
    def __init__(s, hive, cmds, cap=3, poll=1., op=None, say=None, env=None, watch=False):
        if not cmds: raise ValueError('the runner needs a command, by role or default')
        s.hive, s.cmds, s.cap, s.poll, s.env, s.watch = hive, cmds, max(1, cap), poll, env or {}, watch
        s.op, s.say, s.jobs = op or hive.op('runner'), say or (lambda t: None), {}
        s.dir = hive.cfg.dir/'run'
        s.dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def fromCfg(cls, hive, **kw):
        r = hive.cfg.runner
        cmds = {k: list(v['command']) for k, v in r.get('roles', {}).items() if v.get('command')}
        return cls(hive, kw.pop('cmds', None) or cmds, int(kw.pop('cap', None) or r.get('max', 3)), float(kw.pop('poll', r.get('poll', 1.))), **kw)

    def cmd(s, t): return s.cmds.get(t.role or ('verifier' if t.kind == 'verify' else 'implementer')) or s.cmds.get('default')

    def ready(s):
        return [t for t in map(s.hive.tasks._d, s.hive.db.q("SELECT * FROM tasks WHERE state='ready' AND owner IS NULL ORDER BY prio DESC,id"))
                if s.cmd(t)]

    def pend(s):
        rows = s.hive.db.q("SELECT a.* FROM agents a JOIN tasks t ON t.id=a.deleg WHERE a.state='pending' AND a.launch='runner' "
                           "AND t.state IN ('ready','running') ORDER BY a.depth DESC,a.id")
        return [a for a in rows if a.id not in s.jobs and s.cmd(s.hive.tasks.get(a.deleg))]

    def full(s):
        # agents blocked in gather or wait hold a process but not a slot, so parents waiting on children cannot starve them
        idle = {r.id for r in s.hive.db.q("SELECT id FROM agents WHERE state='idle'")}
        return len([j for j in s.jobs if j not in idle]) >= s.cap or len(s.jobs) >= s.cap*(s.hive.cfg.depth+2)

    def step(s):
        s.reap()
        for a in s.pend():
            if s.full(): return
            t = s.hive.tasks.get(a.deleg)
            try: s.start(a, t, s.hive.tree.prompt(a), a.role, s.cmd(t))
            except Err as e: s.say(f'could not start {a.name}: {e}')
        for t in s.ready():
            if s.full(): break
            try: s.launch(t)
            except Err as e: s.say(f'could not start t{t.id}: {e}')

    def launch(s, t):
        d = s.op.dispatch(t.id, budget=min(4, s.op.agent.budget) if t.kind == 'compose' else 0)
        s.start(s.hive.agents.named(d['agent']), t, d['prompt'], d['role'], s.cmd(t))

    def start(s, a, t, prompt, role, cmd):
        n, tok, h = a.name, a.token, s.hive
        if a.launch:
            with h.db.tx() as c: c.execute('UPDATE tasks SET tries=tries+1 WHERE id=?', (t.id,))
        pf, mf, lf = s.dir/f'{n}.prompt.md', s.dir/f'{n}.mcp.json', s.dir/f'{n}.log'
        pf.write_text(prompt)
        env = {'HIVE_DB': str(h.cfg.db), 'HIVE_ROOT': str(h.root), 'HIVE_AGENT_TOKEN': tok, 'HIVE_AGENT': n, 'HIVE_TASK': f't{t.id}'}
        mf.write_text(mcp([sys.executable, '-m', 'hive', 'mcp'], env))
        vals = {'prompt': prompt, 'promptFile': str(pf), 'task': f't{t.id}', 'agent': n, 'token': tok, 'role': role,
                'db': env['HIVE_DB'], 'root': env['HIVE_ROOT'], 'mcp': str(mf)}
        argv = [fill(x, vals) for x in cmd]
        log = open(lf, 'w')
        try: p = subprocess.Popen(argv, cwd=h.root, env={**os.environ, **s.env, **env}, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        except OSError as e:
            log.close()
            with h.db.tx() as c:
                h.tasks.release(c, t.id, f'could not start {argv[0]}: {e}')
                h.agents.set(c, a.id, state='left')
            raise Err(f'could not start {argv[0]}: {e}') from None
        s.jobs[a.id] = Job(n, a.id, t.id, p, log, lf, now())
        s.say(f'started {n} for t{t.id} (pid {p.pid}, log {lf})')

    def reap(s):
        for aid, j in list(s.jobs.items()):
            if (code := j.proc.poll()) is None: continue
            j.log.close()
            del s.jobs[aid]
            h = s.hive
            why = f'{j.agent} exited with code {code} before finishing (log {j.path})'
            with h.db.tx() as c:
                a, t = h.agents.get(aid), h.tasks.get(j.task, c)
                again = a.state != 'left' and a.launch == 'runner' and a.deleg == t.id and t.state in ('running', 'ready') and t.owner == aid \
                    and t.tries < h.cfg.tries
                for r in c.execute("SELECT id FROM tasks WHERE owner=? AND state IN ('running','ready') AND id!=?", (aid, t.id if again else -1)).fetchall():
                    h.tasks.release(c, r.id, why)
                if again:
                    c.execute("UPDATE tasks SET state='ready' WHERE id=?", (t.id,))
                    h.agents.set(c, aid, state='pending', task=None)
                else: h.agents.set(c, aid, state='left')
                st = 'relaunching' if again else h.tasks.get(j.task, c).state
            s.say(f'{j.agent} exited ({code}); t{j.task} is {st}')

    def stuck(s): return {k: v for k, v in s.hive.tasks.counts().items() if k in ('pending', 'ready', 'running', 'in_review')}

    def run(s, timeout=None):
        end = timeout and time.monotonic()+timeout
        try:
            while True:
                s.step()
                if not s.watch and not s.jobs and not s.ready() and not s.pend(): break
                if end and time.monotonic() > end:
                    s.say('timeout; stopping agents')
                    s.stop()
                    break
                time.sleep(s.poll)
        except KeyboardInterrupt:
            s.say('interrupted; stopping agents')
            s.stop()
        return {'counts': s.hive.tasks.counts(), 'stuck': s.stuck()}

    def stop(s):
        for j in s.jobs.values():
            if j.proc.poll() is None: j.proc.terminate()
        for j in s.jobs.values():
            try: j.proc.wait(10)
            except subprocess.TimeoutExpired: j.proc.kill()
        s.reap()


def fill(t, vals): return PH.sub(lambda m: vals[m[1]], t)
