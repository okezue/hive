from .err import Bad
from .log import fmt
from .util import ago, now, poll

NOISE = ('file.read', 'activity')


class Aware:
    def __init__(s, db, log, agents, tasks, files, summ, stale):
        s.db, s.log, s.agents, s.tasks, s.files, s.summ, s.stale = db, log, agents, tasks, files, summ, stale

    def wf(s, me, scope):
        if scope not in ('auto', 'workflow', 'session'): raise Bad(f'invalid scope {scope!r}', 'auto, workflow, or session')
        return me.wf if scope != 'session' and me.wf else None

    def who(s, a, names, me=None):
        st = 'stale' if a.state in ('active', 'idle') and now()-a.seen > s.stale else a.state
        out = {'name': a.name, 'role': a.role, 'state': st} | ({'harness': a.harness} if a.get('harness') else {})
        if me and a.id == me.id: out['you'] = True
        if a.status: out['status'] = a.status
        if a.task:
            t = s.tasks.get(a.task)
            out['task'] = f't{t.id} {t.title} ({t.state})'
        if fs := s.files.opened(a.id): out['files'] = fs[:6] + ([f'+{len(fs)-6} more'] if len(fs) > 6 else [])
        if a.parent: out['parent'] = names.get(a.parent)
        if a.wf: out['workflow'] = s.agents.wfNames().get(a.wf)
        out['seen'] = ago(a.seen)
        return out

    def overview(s, me, scope='auto'):
        w, names = s.wf(me, scope), s.agents.names()
        recent = [e for e in s.log.find(wf=w, limit=60, desc=True) if e.kind not in NOISE][:12]
        out = {'scope': f'workflow {s.agents.wfNames()[w]}' if w else 'session', 'agents': [s.who(a, names, me) for a in s.agents.all(w)],
               'tasks': {'counts': s.tasks.counts(w), 'active': s.tasks.list('running,in_review,ready', wf=w, limit=30)}}
        if mrs := s.files.mrs.list(me): out['merges'] = mrs
        return out | {'recent': [fmt(e, names) for e in reversed(recent)]}

    def digest(s, me, scope='auto', budget=1200):
        w, last = s.wf(me, scope), s.log.last()
        cur = s.log.cur(me.id, key := f'digest:{w}')
        cur = max(0, last-200) if cur is None else cur
        evs, names = s.log.find(after=cur, notBy=me.id, wf=w, limit=20000), s.agents.names()
        with s.db.tx() as c: s.log.setCur(c, me.id, key, evs[-1].seq if evs else max(cur, last), True)
        if not (ls := [fmt(e, names) for e in evs if e.kind != 'file.read']):
            return {'since': cur, 'events': 0, 'digest': 'nothing new from other agents'}
        r = s.summ(ls, budget, 'what the other agents did, decided, and need since the reader last looked')
        return {'since': cur, 'until': evs[-1].seq, 'events': len(ls), 'digest': r.text, 'method': r.method}

    def live(s, me, of, since=None, wait=0, limit=30):
        a = s.agents.named(of)
        key = f'watch:{a.id}'
        after = since if since is not None else s.log.cur(me.id, key)
        if after is None:
            rec = s.log.find(agent=a.id, limit=20, desc=True)
            after = rec[-1].seq-1 if rec else s.log.last()
        evs = poll(lambda: s.log.find(agent=a.id, after=after, limit=limit+1), max(0., min(float(wait), 300.))) or []
        more, evs = len(evs) > limit, evs[:limit]
        cur = evs[-1].seq if evs else after
        with s.db.tx() as c: s.log.setCur(c, me.id, key, cur)
        names = s.agents.names()
        return {'agent': s.who(s.agents.get(a.id), names), 'events': [fmt(e, names, False) for e in evs], 'cursor': cur, 'more': more}

    def window(s, me, of, before=None, limit=30):
        a = s.agents.named(of)
        rows = s.log.find(agent=a.id, before=before, limit=limit+1, desc=True)
        more, rows, names = len(rows) > limit, rows[:limit][::-1], s.agents.names()
        return {'agent': a.name, 'role': a.role, 'events': [fmt(e, names, False) for e in rows],
                'older': rows[0].seq if rows and more else None, 'total': s.log.count(a.id)}

    def summary(s, me, of, since=None, before=None, budget=800):
        a = s.agents.named(of)
        evs, names = s.log.find(agent=a.id, after=since, before=before, limit=1 << 20), s.agents.names()
        if not evs: return {'agent': s.who(a, names), 'events': 0, 'summary': 'no activity in that range'}
        r = s.summ([fmt(e, names, False) for e in evs], budget,
                   f'what {a.name} ({a.role}) has been doing: goals, changes, results, open problems, current state')
        return {'agent': s.who(a, names), 'events': len(evs), 'range': [evs[0].seq, evs[-1].seq], 'summary': r.text, 'method': r.method,
                'chunks': r.chunks, 'levels': r.levels}
