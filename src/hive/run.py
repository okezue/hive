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
    def __init__(s, hive, cmds, cap=3, poll=1., op=None, say=None, env=None):
        if not cmds: raise ValueError('the runner needs a command, by role or default')
        s.hive, s.cmds, s.cap, s.poll, s.env = hive, cmds, max(1, cap), poll, env or {}
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

    def step(s):
        s.reap()
        for t in s.ready():
            if len(s.jobs) >= s.cap: break
            try: s.launch(t)
            except Err as e: s.say(f'could not start t{t.id}: {e}')

    def launch(s, t):
        d = s.op.dispatch(t.id)
        n, tok, h = d['agent'], d['token'], s.hive
        a = h.agents.named(n)
        pf, mf, lf = s.dir/f'{n}.prompt.md', s.dir/f'{n}.mcp.json', s.dir/f'{n}.log'
        pf.write_text(d['prompt'])
        env = {'HIVE_DB': str(h.cfg.db), 'HIVE_ROOT': str(h.root), 'HIVE_AGENT_TOKEN': tok, 'HIVE_AGENT': n, 'HIVE_TASK': f't{t.id}'}
        mf.write_text(mcp([sys.executable, '-m', 'hive', 'mcp'], env))
        vals = {'prompt': d['prompt'], 'promptFile': str(pf), 'task': f't{t.id}', 'agent': n, 'token': tok, 'role': d['role'],
                'db': env['HIVE_DB'], 'root': env['HIVE_ROOT'], 'mcp': str(mf)}
        argv = [fill(x, vals) for x in s.cmd(t)]
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
            with h.db.tx() as c:
                for r in c.execute("SELECT id FROM tasks WHERE owner=? AND state IN ('running','ready')", (aid,)).fetchall():
                    h.tasks.release(c, r.id, f'{j.agent} exited with code {code} before finishing (log {j.path})')
                h.agents.set(c, aid, state='left')
                st = h.tasks.get(j.task, c).state
            s.say(f'{j.agent} exited ({code}); t{j.task} is {st}')

    def stuck(s): return {k: v for k, v in s.hive.tasks.counts().items() if k in ('pending', 'ready', 'running', 'in_review')}

    def run(s, timeout=None):
        end = timeout and time.monotonic()+timeout
        try:
            while True:
                s.step()
                if not s.jobs and not s.ready(): break
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
