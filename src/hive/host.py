import re

from .err import Clash, Denied, Missing
from .util import J, ago, dumps, line, now

DEF = {'max': 0, 'free': 20, 'per': 150, 'start': 600, 'restarts': 3, 'lease': 3600}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS runs(key TEXT PRIMARY KEY,agent INTEGER,host INTEGER,state TEXT DEFAULT 'running',since REAL,ended REAL,why TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS runAgent ON runs(agent,state)'''
TOKEN, DESC = re.compile(r'Your Hive token is "([^"]+)"'), re.compile(r'^hive (\S+)$')
DONE = ('done', 'failed', 'cancelled', 'blocked')
HOSTED = "(a.launch='host' OR (a.launch IS NULL AND a.deleg IS NOT NULL AND a.pid IS NULL))"
HOW = ('Start each one now as your own subagent, in the background, with the description and prompt exactly as given (Grok: spawn_subagent; '
       'Claude Code: the Agent tool), and leave their work to them. Call host again whenever a subagent finishes (pass the hive names of the '
       'subagents that finished as ended) or Hive says hive agents are waiting: it hands out {lim} and holds back while memory is low. Follow the '
       'work with tree, overview and gather.')


def lim(m):
    caps = [x for x in (m['max'], m.get('limit')) if x]
    return f'at most {min(caps)} at once' if caps else 'as many as memory allows'


def args(inp):
    if not isinstance(inp, dict): return None, None
    return (inp['tool_input'], True) if isinstance(inp.get('tool_input'), dict) else (inp, False)


class Host:
    def __init__(s, h):
        s.h, s.db, s.cfg = h, h.db, DEF | (getattr(h.cfg, 'host', None) or {})
        with s.db.tx() as c:
            for q in SCHEMA.split(';'): c.execute(q)
        h.notice.more.append(s.notes)

    def get(s, c=None):
        r = (c or s.db.conn()).execute("SELECT val FROM meta WHERE key='host'").fetchone()
        return J(r.val) if r else None

    def live(s, c=None):
        if not (m := s.get(c)): return None
        a = (c or s.db.conn()).execute('SELECT state,seen FROM agents WHERE id=?', (m['agent'],)).fetchone()
        if not a or a.state == 'left': return None
        if m.get('pid'):
            from .reg import same
            return m if same(m['pid'], m.get('at')) else None
        return m if now()-a.seen < s.cfg['lease'] else None

    def take(s, a, cap=None):
        if s.h.agents.hosted(a): raise Denied('a subagent cannot start subagents, so only a top-level session can host the hive',
                                              'ask the session you run in to call host')
        from .reg import host as harness, hosting, stamp
        p, n = harness()
        hosting(p)
        with s.db.tx() as c:
            m = s.live(c)
            if m and m['agent'] != a.id:
                raise Clash(f"{s.h.agents.get(m['agent']).name} already hosts this hive", 'ask it to release hosting, or wait until its session ends')
            from .harness import subagents
            h = n or a.harness or ''
            new = {'agent': a.id, 'max': max(0, int(cap if cap is not None else (m or {}).get('max', s.cfg['max']))), 'since': (m or {}).get('since') or now(),
                   'pid': p, 'at': p and stamp(p), 'harness': h, 'limit': subagents(h, s.h.root)}
            c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('host', dumps(new)))
            if not m: s.h.log.add(c, a.id, 'host.started', f"{a.name} hosts the hive in {new['harness'] or 'its harness'} ({lim(new)})", f'agent:{a.name}')
        return new

    def release(s, a):
        with s.db.tx() as c:
            if (m := s.get(c)) and (m['agent'] == a.id or s.h.roles.can(a, 'manage')):
                from .reg import hosting
                hosting(m.get('pid'), False)
                c.execute("DELETE FROM meta WHERE key='host'")
                s.h.log.add(c, a.id, 'host.stopped', f'{a.name} stopped hosting the hive', f'agent:{a.name}')
        return {'hosting': False, 'hint': 'queued agents wait until a session hosts again or a runner starts'}

    def running(s, c):
        return c.execute(f"SELECT a.* FROM agents a JOIN tasks t ON t.id=a.deleg WHERE {HOSTED} AND a.handed IS NOT NULL AND a.state!='left' "
                         f"AND t.state NOT IN ({','.join('?'*len(DONE))}) ORDER BY a.handed", DONE).fetchall()

    def queued(s, c):
        return c.execute(f"SELECT a.* FROM agents a JOIN tasks t ON t.id=a.deleg WHERE {HOSTED} AND a.handed IS NULL AND a.state='pending' "
                         "AND t.state IN ('ready','running') AND (t.owner IS NULL OR t.owner=a.id) ORDER BY a.depth DESC,a.id").fetchall()

    def ready(s, c, every=True):
        return c.execute("SELECT * FROM tasks WHERE state='ready' AND owner IS NULL" + ('' if every else ' AND run=1') + ' ORDER BY run DESC,prio DESC,id').fetchall()

    def room(s, c, m):
        from .build import fits, free
        run = s.running(c)
        # agents handed out in the last minute are still growing, so their expected memory counts against what is free
        if not (n := fits(s.cfg['free'], s.cfg['per'], sum(now()-r.handed < 60 for r in run))):
            return 0, f"free memory is {free():.0f}%; Hive keeps {s.cfg['free']}% free and hands out more once memory frees up"
        caps = [x for x in (m['max'], m.get('limit')) if x]
        return max(0, min(n, min(caps)-len(run)) if caps else n), None

    def reap(s, c):
        for a in c.execute(f"SELECT a.* FROM agents a WHERE {HOSTED} AND a.handed<? AND a.state='pending' AND a.calls=0", (now()-s.cfg['start'],)).fetchall():
            c.execute('UPDATE agents SET handed=NULL WHERE id=?', (a.id,))
            s.h.log.add(c, None, 'host.requeued', f'{a.name} was handed to the host but never started; it waits again', f'agent:{a.name}')

    def prompt(s, k):
        from .sess import Sess
        x = Sess(s.h, k.id)
        p, b = x.promptFor(x, k.deleg, True), s.h.faults.brief(s.h.tasks.get(k.deleg), k.id)
        return f'{p}\n\n{b}' if b else p

    def call(s, a, cap=None, stop=False, tasks=True, ended=None):
        if stop: return s.release(a)
        m = s.take(a, cap)
        for x in ended or []: s.ended(x)
        with s.db.tx() as c:
            s.reap(c)
            n, why = s.room(c, m)
            picks = s.queued(c)[:n]
            for k in picks: c.execute('UPDATE agents SET handed=? WHERE id=?', (now(), k.id))
            todo = s.ready(c, tasks)[:n-len(picks)]
        if todo:
            from .sess import Sess
            boss = Sess(s.h, a.id) if s.h.roles.can(a, 'spawn') else s.h.op()
            for t in todo:
                fork = 'fork' in s.h.roles.get(t.role or ('verifier' if t.kind == 'verify' else 'implementer')).caps
                d = boss._dispatch(t.id, None, min(int(s.h.cfg.runner.get('budget', 4)), boss.agent.budget) if fork else 0, True)
                picks.append(s.h.agents.named(d['agent']))
        start = [{'agent': k.name, 'role': k.role, 'description': f'hive {k.name}', 'prompt': s.prompt(k)} for k in picks]
        with s.db.tx() as c:
            run, wait = s.running(c), len(s.queued(c)) + len(s.ready(c, tasks))
        out = {'hosting': {'max': m['max'] or 'no limit', 'running': len(run), 'waiting': wait}, 'start': start,
               'running': [{'agent': r.name, 'task': f't{r.deleg}', 'state': r.state, 'last': ago(r.seen) if r.calls else 'not started'} |
                           ({'status': line(r.status, 100)} if r.status else {}) for r in run]}
        if why: out['held'] = why
        out['hint'] = HOW.format(lim=lim(m)) if start else ('nothing to start now; ' + ('call host again when a subagent finishes' if run or wait else
                                                                                          'every hive agent is done. Plan more work, or host(stop=true) to stop hosting'))
        return out

    def waiting(s, a, c=None):
        c = c or s.db.conn()
        if not (m := s.live(c)) or m['agent'] != a.id: return 0
        n, _ = s.room(c, m)
        return min(n, len(s.queued(c)) + len(s.ready(c)))

    def notes(s, a, eat=True):
        if (n := s.waiting(a)) <= 0: return {}
        return {'host': f'{n} hive agent(s) can start now as your subagents: call host() and start them'}

    def key(s, raw):
        return raw.get('agent_id') or raw.get('subagentId') or ((raw.get('sessionId') or raw.get('session_id')) if raw.get('subagentType') or
                                                                 raw.get('subagent_type') else None)

    def bind(s, raw, kind, hive):
        if not (k := s.key(raw)): return None
        if r := s.db.one('SELECT agent FROM runs WHERE key=?', (k,)): return s.h.agents.get(r.agent)
        a, tok, inp = None, None, args(raw.get('tool_input') or raw.get('toolInput'))[0]
        if kind == 'substart' and (d := DESC.match((raw.get('description') or '').strip())): a = s.h.db.one('SELECT * FROM agents WHERE name=?', (d[1],))
        elif m := TOKEN.search(raw.get('prompt') or ''): tok = m[1]
        elif hive and inp and isinstance(inp.get('agent'), str): tok = inp['agent']
        if tok: a = s.h.db.one('SELECT * FROM agents WHERE token=?', (tok,))
        if not a or a.state == 'left' or not s.h.agents.hosted(a): return None
        with s.db.tx() as c:
            c.execute('UPDATE runs SET state=?,ended=?,why=? WHERE agent=? AND state=?', ('ended', now(), 'replaced by a new subagent', a.id, 'running'))
            c.execute('INSERT OR REPLACE INTO runs(key,agent,host,since) VALUES(?,?,?,?)', (k, a.id, (s.get(c) or {}).get('agent'), now()))
            c.execute('UPDATE agents SET handed=COALESCE(handed,?) WHERE id=?', (now(), a.id))
            s.h.log.add(c, a.id, 'host.bound', f'{a.name} runs as subagent {k}', f'agent:{a.name}')
        return a

    def token(s, raw, a):
        inp = raw.get('tool_input') or raw.get('toolInput')
        x, nested = args(inp)
        if x is None or x.get('agent') == a.token: return None
        return dict(inp, tool_input=dict(x, agent=a.token)) if nested else dict(x, agent=a.token)

    def stopping(s, raw, a, final=False):
        t = a.deleg and s.h.tasks.get(a.deleg)
        open = bool(t) and t.state not in DONE and a.state != 'left'
        if open and not final and not (raw.get('stopHookActive') or raw.get('stop_hook_active')):
            from .sess import Sess
            bs = Sess(s.h, a.id).blockers()
            return (f"Hive: you are {a.name}, and t{t.id} is still {t.state}. Before you stop, finish it with done('t{t.id}', result=...) "
                    f"or fail('t{t.id}', reason=...)" + (f"; also {'; '.join(bs)}" if bs else '') + '.')
        s.end(s.key(raw), a, open, raw.get('lastAssistantMessage') or raw.get('last_assistant_message') or '')
        return None

    def ended(s, name):
        try: a = s.h.agents.named(str(name).removeprefix('hive ').strip())
        except Missing: return
        if not s.h.agents.hosted(a) or a.state == 'left' or a.handed is None or a.state == 'pending': return
        t = a.deleg and s.h.tasks.get(a.deleg)
        r = s.db.one("SELECT key FROM runs WHERE agent=? AND state='running'", (a.id,))
        s.end(r.key if r else None, a, bool(t) and t.state not in DONE)

    def end(s, k, a, open, said=''):
        from .sess import Sess
        with s.db.tx() as c:
            r = c.execute("SELECT * FROM runs WHERE key=? AND state='running'", (k,)).fetchone() if k else None
            if k and not r: return
            if r: c.execute("UPDATE runs SET state='ended',ended=?,why=? WHERE key=?", (now(), 'stopped before finishing' if open else 'finished', k))
            a = c.execute('SELECT * FROM agents WHERE id=?', (a.id,)).fetchone()
            if not open or a.state == 'left':
                if a.state != 'left': Sess(s.h, a.id).leave('its subagent finished')
                return
            t = s.h.tasks.get(a.deleg, c)
            s.h.faults.add(c, t.id, a.id, 'host', 'quit', 'its subagent stopped before finishing', said, made=s.h.faults.made(c, a.id, r.since if r else a.handed))
            n = c.execute("SELECT COUNT(*) n FROM faults WHERE task=? AND cmd='host'", (t.id,)).fetchone().n
            m = s.get(c)
            if n > s.cfg['restarts']:
                s.h.tasks.finish(c, a, t, 'failed', f'its subagent stopped {n} times before finishing; see faults')
                Sess(s.h, a.id).leave('its subagent kept stopping before finishing')
                if m: s.h.mail.put(c, None, [m['agent']], f'{a.name} stopped {n} times before finishing t{t.id}, so the task failed: retry it, split it, '
                                                          'or do it another way.', 'steer', 'host', log=False)
                return
            c.execute("UPDATE agents SET handed=NULL,state='pending' WHERE id=?", (a.id,))
            if m: s.h.mail.put(c, None, [m['agent']], f'{a.name} stopped before finishing t{t.id}; host() hands it out again with a brief of what it '
                                                      f'already did (restart {n} of {s.cfg["restarts"]}).', 'steer', 'host', log=False)

    def show(s):
        with s.db.tx() as c:
            m, run, q = s.live(c), s.running(c), s.queued(c)
            rs = c.execute('SELECT r.*,a.name FROM runs r JOIN agents a ON a.id=r.agent ORDER BY r.since DESC LIMIT 20').fetchall()
        return {'host': m and {'agent': s.h.agents.get(m['agent']).name, 'max': m['max'] or 'no limit', 'harness': m['harness'], 'since': ago(m['since'])},
                'running': [r.name for r in run], 'queued': [r.name for r in q],
                'subagents': [{'agent': r.name, 'subagent': r.key, 'state': r.state, 'since': ago(r.since)} | ({'why': r.why} if r.why else {}) for r in rs]}
