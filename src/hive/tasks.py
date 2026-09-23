from graphlib import CycleError, TopologicalSorter

from .err import Bad, Clash, Denied, Missing
from .util import J, ago, an, clip, dumps, line, now, pid, toks

TERMINAL = ('done', 'failed', 'cancelled')
DEAD = ('failed', 'cancelled', 'blocked')
DOWN = "WITH RECURSIVE down(id) AS (SELECT task FROM deps WHERE dep=? UNION SELECT d.task FROM deps d JOIN down ON d.dep=down.id) "


class Tasks:
    def __init__(s, db, log, mail, agents, roles, summ, tries=2):
        s.db, s.log, s.mail, s.agents, s.roles, s.summ, s.tries = db, log, mail, agents, roles, summ, tries

    def _d(s, t):
        if t: t.paths, t.notes = J(t.paths, []), J(t.notes, [])
        return t

    def get(s, i, c=None):
        if (t := s._d((c or s.db.conn()).execute('SELECT * FROM tasks WHERE id=?', (i,)).fetchone())) is None: raise Missing(f'no task t{i}')
        return t

    def unset(s, c, aid, i): c.execute('UPDATE agents SET task=NULL WHERE id=? AND task=?', (aid, i))

    def running(s, c, aid): return c.execute("SELECT id,title FROM tasks WHERE owner=? AND state='running' ORDER BY id", (aid,)).fetchall()

    def deps(s, i): return [r.dep for r in s.db.q('SELECT dep FROM deps WHERE task=? ORDER BY dep', (i,))]

    def show(s, t, names=None, full=False, after=None):
        names = s.agents.names() if names is None else names
        out = {'id': f't{t.id}', 'title': t.title, 'state': t.state, 'role': t.role, 'kind': t.kind, 'owner': names.get(t.owner),
               'after': [f't{d}' for d in (s.deps(t.id) if after is None else after)]}
        for k, v in (('prio', t.prio), ('verify', t.verify), ('checks', t.checks and f't{t.checks}'), ('paths', t.paths)):
            if v: out[k] = v
        if t.wf: out['workflow'] = s.agents.wfNames().get(t.wf)
        if full:
            out |= {'about': t.about, 'tries': t.tries, 'creator': names.get(t.creator), 'created': ago(t.ts)}
            for k in ('result', 'notes', 'parent'):
                if t[k]: out[k] = f't{t[k]}' if k == 'parent' else t[k]
        elif t.result: out['result'] = line(t.result)
        return out

    def list(s, state=None, role=None, wf=None, owner=None, limit=100):
        w, p = [], []
        if state:
            st = [x.strip() for x in state.split(',') if x.strip()]
            w.append(f"state IN ({','.join('?'*len(st))})")
            p += st
        for k, v in (('role', role), ('wf', wf), ('owner', owner)):
            if v is not None: w.append(k+'=?'); p.append(v)
        rows = s.db.q(f"SELECT * FROM tasks{' WHERE '+' AND '.join(w) if w else ''} ORDER BY id LIMIT ?", [*p, limit])
        after, names = {}, s.agents.names()
        if rows:
            for r in s.db.q(f"SELECT task,dep FROM deps WHERE task IN ({','.join('?'*len(rows))}) ORDER BY dep", [r.id for r in rows]):
                after.setdefault(r.task, []).append(r.dep)
        return [s.show(s._d(r), names, after=after.get(r.id, [])) for r in rows]

    def counts(s, wf=None):
        return {r.state: r.n for r in s.db.q('SELECT state,COUNT(*) n FROM tasks WHERE ? IS NULL OR wf=? GROUP BY state', (wf, wf))}

    def plan(s, a, specs, wf=None, chain=False):
        s.roles.need(a, 'plan', 'create tasks')
        if not specs: raise Bad('a plan needs at least one task')
        keyed = {}
        for i, sp in enumerate(specs):
            if not isinstance(sp, dict) or not str(sp.get('title', '')).strip(): raise Bad(f'task {i} needs a title')
            if (k := str(sp.get('key') or f'#{i}')) in keyed: raise Bad(f'duplicate key {k!r}')
            if sp.get('role'): s.roles.get(sp['role'])
            v = 'verifier' if sp.get('verify') is True else sp.get('verify') or None
            if v: s.roles.get(v)
            after = [sp['after']] if isinstance(sp.get('after'), str) else list(sp.get('after') or [])
            if chain and keyed: after.append(list(keyed)[-1])
            keyed[k] = {**sp, 'after': list(dict.fromkeys(map(str, after))), 'verify': v}
        try: order = list(TopologicalSorter({k: [x for x in sp['after'] if x in keyed] for k, sp in keyed.items()}).static_order())
        except CycleError as e: raise Bad('the plan has a dependency cycle: ' + ' -> '.join(map(str, e.args[1]))) from None
        with s.db.tx() as c:
            w, made = s.agents.wf(c, wf, a.id) if wf else a.wf, {}
            for k in order:
                sp = keyed[k]
                ds = [made[x] if x in keyed else s.get(pid('t', x, 'task'), c).id for x in sp['after']]
                st = [s.get(d, c).state for d in ds]
                state = 'blocked' if any(x in DEAD for x in st) else 'ready' if all(x == 'done' for x in st) else 'pending'
                owner = s.agents.named(sp['assignee']).id if sp.get('assignee') else None
                paths = [sp['paths']] if isinstance(sp.get('paths'), str) else sp.get('paths') or []
                made[k] = i = c.execute('INSERT INTO tasks(wf,title,about,role,kind,state,prio,creator,owner,parent,verify,paths,ts) '
                                        'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                        (w, sp['title'].strip(), sp.get('about') or '', sp.get('role'), sp.get('kind') or 'work', state,
                                         int(sp.get('prio') or 0), a.id, owner, pid('t', sp['parent'], 'task') if sp.get('parent') else None,
                                         sp['verify'], dumps(paths), now())).lastrowid
                c.executemany('INSERT OR IGNORE INTO deps VALUES(?,?)', [(i, d) for d in ds])
                s.log.sub(c, a.id, f'task:t{i}')
                s.log.add(c, a.id, 'task.created', f"t{i} [{sp.get('role') or 'any role'}] {line(sp['title'], 80)}"
                          f"{' after '+', '.join(f't{d}' for d in ds) if ds else ''} ({state})", f'task:t{i}', wf=w)
                if owner and owner != a.id:
                    s.mail.put(c, a, [owner], f"t{i} '{sp['title']}' is assigned to you ({state}). " +
                               ('Take it with take.' if state == 'ready' else 'It becomes ready when its dependencies finish.'),
                               'steer', 'task', {'task': f't{i}'})
        names = s.agents.names()
        return {'created': [{'key': k, **s.show(s.get(made[k]), names)} for k in keyed],
                'hint': 'tasks with no dependency path between them run concurrently'}

    def problem(s, t, a):
        if t.state != 'ready': return f'it is {t.state}'
        if t.owner not in (None, a.id): return 'it is reserved for another agent'
        if t.role and t.role != a.role: return f'it needs {an(t.role)}, and you are {an(a.role)}'
        if t.kind == 'verify':
            if not s.roles.can(a, 'verify'): return 'verification needs the verify capability'
            if t.checks and s.get(t.checks).owner == a.id: return 'you did the work being verified'
        return None

    def take(s, a, ref=None):
        s.roles.need(a, 'claim', 'take tasks')
        with s.db.tx() as c:
            if cur := s.running(c, a.id):
                if ref is None or pid('t', ref, 'task') not in [x.id for x in cur]:
                    raise Clash(f"you are still on t{cur[0].id} '{cur[0].title}'", 'finish it with done or fail first')
                return {'task': s.show(s.get(pid('t', ref, 'task'), c), full=True), 'note': 'already yours'}
            if ref is not None:
                t = s.get(pid('t', ref, 'task'), c)
                if p := s.problem(t, a): raise Clash(f'cannot take t{t.id}: {p}')
            else:
                rows = c.execute("SELECT * FROM tasks WHERE state='ready' AND (owner IS NULL OR owner=?) ORDER BY owner IS NULL,prio DESC,id",
                                 (a.id,)).fetchall()
                if (t := next((t for t in map(s._d, rows) if not s.problem(t, a)), None)) is None:
                    return {'task': None, 'note': f'no ready task for {an(a.role)} right now', 'counts': s.counts(a.wf)}
            c.execute("UPDATE tasks SET state='running',owner=?,startAt=?,tries=tries+? WHERE id=?", (a.id, now(), t.owner is None, t.id))
            s.agents.set(c, a.id, task=t.id)
            s.log.sub(c, a.id, f'task:t{t.id}')
            s.log.add(c, a.id, 'task.claimed', f'took t{t.id} {line(t.title, 80)}', f'task:t{t.id}', wf=t.wf)
            t = s.get(t.id, c)
        return {'task': s.show(t, full=True)} | s.depCtx(t, 2000)

    def mine(s, a, t, act):
        if t.owner != a.id and not s.roles.can(a, 'manage'):
            raise Denied(f"t{t.id} belongs to {s.agents.names().get(t.owner, 'nobody')}; only its owner or a coordinator can {act} it")

    def done(s, a, ref, result):
        if not (result or '').strip(): raise Bad('describe the result: what changed, where, and how it was checked')
        with s.db.tx() as c:
            t = s.get(pid('t', ref, 'task'), c)
            s.mine(a, t, 'finish')
            if t.kind == 'verify': raise Bad('verification tasks finish with verify')
            if t.state == 'ready' and t.owner == a.id: c.execute('UPDATE tasks SET startAt=? WHERE id=?', (now(), t.id))
            elif t.state != 'running': raise Clash(f't{t.id} is {t.state}, not running')
            s.unset(c, t.owner, t.id)
            if t.verify:
                c.execute("UPDATE tasks SET state='in_review',result=? WHERE id=?", (result, t.id))
                v = s.review(c, a, t, result)
                s.log.add(c, a.id, 'task.submitted', f't{t.id} submitted for verification as t{v}: {line(result, 100)}', f'task:t{t.id}', wf=t.wf)
                return {'task': s.show(s.get(t.id, c)), 'verification': f't{v}', 'note': 'a verifier checks it; you hear back if it is rejected'}
            s.finish(c, a, t, 'done', result)
            return {'task': s.show(s.get(t.id, c)), 'unblocked': s.ready(c, t.id)}

    def review(s, c, a, t, result):
        about = (f"Independently verify t{t.id} '{t.title}' finished by {a.name}.\n\nTask:\n{t.about or '(none)'}\n\nReported result:\n{result}\n\n"
                 f"Check the claim against the files and by running the relevant tests, then call verify('t{t.id}', ok=true|false, notes=...) "
                 "with concrete evidence.")
        v = c.execute("INSERT INTO tasks(wf,title,about,role,kind,state,creator,checks,paths,parent,ts) VALUES(?,?,?,?,'verify','ready',?,?,?,?,?)",
                      (t.wf, f'Verify t{t.id}: {t.title}', about, t.verify, a.id, t.id, dumps(t.paths), t.id, now())).lastrowid
        s.log.add(c, a.id, 'task.created', f't{v} [{t.verify}] verify t{t.id} (ready)', f'task:t{v}', wf=t.wf)
        if vs := [x.id for x in s.agents.all() if x.role == t.verify and x.id != a.id]:
            s.mail.put(c, a, vs, f"t{v} is ready: verify t{t.id} '{t.title}'. Take it with take('t{v}').", 'steer', 'task', {'task': f't{v}'})
        return v

    def verify(s, a, ref, ok, notes):
        s.roles.need(a, 'verify', 'verify tasks')
        if not (notes or '').strip(): raise Bad('give the evidence for your verdict in notes')
        with s.db.tx() as c:
            t = s.get(pid('t', ref, 'task'), c)
            if t.kind == 'verify' and t.state not in ('ready', 'running'): raise Clash(f't{t.id} is {t.state}')
            if t.kind == 'verify': v, o = t, s.get(t.checks, c)
            else:
                o, v = t, s._d(c.execute("SELECT * FROM tasks WHERE checks=? AND kind='verify' AND state IN ('ready','running') "
                                         "ORDER BY id DESC LIMIT 1", (t.id,)).fetchone())
            if o.state != 'in_review': raise Clash(f't{o.id} is {o.state}, not waiting for verification')
            if o.owner == a.id: raise Denied('you cannot verify your own work', 'ask another verifier')
            if v and v.owner not in (None, a.id) and not s.roles.can(a, 'manage'):
                raise Denied(f't{v.id} is being verified by {s.agents.names().get(v.owner)}')
            verdict = 'approved' if ok else 'rejected'
            if v:
                c.execute("UPDATE tasks SET state='done',owner=?,result=?,doneAt=?,startAt=COALESCE(startAt,?) WHERE id=?",
                          (a.id, f'{verdict}: {notes}', now(), now(), v.id))
                s.unset(c, a.id, v.id)
            c.execute('UPDATE tasks SET notes=? WHERE id=?', (dumps([*o.notes, {'by': a.name, 'verdict': verdict, 'notes': notes}]), o.id))
            s.log.add(c, a.id, 'task.verified' if ok else 'task.rejected', f't{o.id} {verdict}: {line(notes, 100)}', f'task:t{o.id}', wf=o.wf)
            if ok:
                s.finish(c, a, s.get(o.id, c), 'done', o.result or '', log=False)
                return {'task': s.show(s.get(o.id, c)), 'verdict': verdict, 'unblocked': s.ready(c, o.id)}
            if not o.owner or s.agents.get(o.owner).state == 'left':
                c.execute("UPDATE tasks SET state='ready',owner=NULL WHERE id=?", (o.id,))
                return {'task': s.show(s.get(o.id, c)), 'verdict': verdict, 'note': 'its author is gone, so it is ready for someone else'}
            c.execute("UPDATE tasks SET state='running' WHERE id=?", (o.id,))
            c.execute('UPDATE agents SET task=? WHERE id=? AND task IS NULL', (o.id, o.owner))
            if o.owner:
                s.mail.put(c, a, [o.owner], f"t{o.id} '{o.title}' was rejected by {a.name}: {notes}\nIt is yours again: fix it, then call done.",
                           'interrupt', 'task', {'task': f't{o.id}', 'verdict': verdict})
            return {'task': s.show(s.get(o.id, c)), 'verdict': verdict}

    def fail(s, a, ref, reason, retry=False):
        if not (reason or '').strip(): raise Bad('say why in reason')
        with s.db.tx() as c:
            t = s.get(pid('t', ref, 'task'), c)
            s.mine(a, t, 'fail')
            if t.state not in ('running', 'ready'): raise Clash(f't{t.id} is {t.state}')
            return {'task': s.show(s.get(s.drop(c, a, t, reason, retry), c))}

    def drop(s, c, a, t, why, retry=True):
        s.unset(c, t.owner, t.id)
        notes = dumps([*t.notes, {'by': a.name if a else 'runner', 'failed': why}])
        if retry and t.tries < s.tries:
            c.execute("UPDATE tasks SET state='ready',owner=NULL,notes=? WHERE id=?", (notes, t.id))
            s.log.add(c, a and a.id, 'task.released', f't{t.id} released for retry: {line(why, 100)}', f'task:t{t.id}', wf=t.wf)
        else:
            c.execute('UPDATE tasks SET notes=? WHERE id=?', (notes, t.id))
            s.finish(c, a, t, 'failed', why)
        return t.id

    def release(s, c, i, why):
        t = s.get(i, c)
        if t.state in TERMINAL or t.state == 'in_review': return t.state
        return s.get(s.drop(c, None, t, why), c).state

    def cancel(s, a, ref, reason):
        with s.db.tx() as c:
            t = s.get(pid('t', ref, 'task'), c)
            if t.creator != a.id and not s.roles.can(a, 'manage'): raise Denied('only the creator or a coordinator can cancel a task')
            if t.state in TERMINAL: raise Clash(f't{t.id} is already {t.state}')
            if t.state == 'running' and t.owner not in (None, a.id):
                s.mail.put(c, a, [t.owner], f"t{t.id} '{t.title}' was cancelled by {a.name}: {reason}. Stop working on it.", 'interrupt', 'task',
                           {'task': f't{t.id}'})
            s.unset(c, t.owner, t.id)
            s.finish(c, a, t, 'cancelled', reason)
            return {'task': s.show(s.get(t.id, c))}

    def reserve(s, c, a, i, aid):
        t = s.get(i, c)
        if t.state != 'ready' or t.owner not in (None, aid): raise Clash(f't{i} is {t.state}' + (' and reserved' if t.owner else ''))
        c.execute('UPDATE tasks SET owner=?,tries=tries+1 WHERE id=?', (aid, i))
        s.log.add(c, a.id, 'task.dispatched', f't{i} reserved for {s.agents.names().get(aid)}', f'task:t{i}', wf=t.wf)

    def finish(s, c, a, t, state, result, log=True):
        c.execute('UPDATE tasks SET state=?,result=?,doneAt=? WHERE id=?', (state, result, now(), t.id))
        if log: s.log.add(c, a and a.id, 'task.' + ('completed' if state == 'done' else state), f't{t.id} {state}: {line(result, 120)}',
                          f'task:t{t.id}', wf=t.wf)
        if t.creator and (a is None or t.creator != a.id):
            s.mail.put(c, a, [t.creator], f"t{t.id} '{t.title}' is {state}: {line(result, 300)}", 'steer' if state == 'done' else 'interrupt',
                       'task', {'task': f't{t.id}', 'state': state}, log=False)
        if state == 'done': return
        s.block(c, a, t.id, f't{t.id} {state}')
        c.execute("UPDATE tasks SET state='cancelled',doneAt=? WHERE checks=? AND kind='verify' AND state IN ('ready','running')", (now(), t.id))
        if t.kind == 'verify' and (o := s.get(t.checks, c)).state == 'in_review':
            s.finish(c, a, o, 'failed', f'verification t{t.id} {state}: {result}')

    def block(s, c, a, i, why):
        for r in c.execute(DOWN + "UPDATE tasks SET state='blocked' WHERE id IN (SELECT id FROM down) AND state IN ('pending','ready') "
                           "RETURNING id,owner,title,wf", (i,)).fetchall():
            s.log.add(c, a and a.id, 'task.blocked', f't{r.id} blocked: {why}', f'task:t{r.id}', wf=r.wf)
            if r.owner: s.mail.put(c, None, [r.owner], f"t{r.id} '{r.title}' is blocked because {why}.", 'steer', 'task', log=False)

    def ready(s, c, i):
        rows = sorted(c.execute("UPDATE tasks SET state='ready' WHERE state='pending' AND id IN (SELECT task FROM deps WHERE dep=?) AND NOT EXISTS "
                                "(SELECT 1 FROM deps d JOIN tasks x ON x.id=d.dep WHERE d.task=tasks.id AND x.state!='done') "
                                "RETURNING id,owner,title,wf", (i,)).fetchall(), key=lambda r: r.id)
        for r in rows:
            s.log.add(c, None, 'task.ready', f't{r.id} ready: its dependencies are done', f'task:t{r.id}', wf=r.wf)
            if r.owner: s.mail.put(c, None, [r.owner], f"t{r.id} '{r.title}' is ready. Take it with take('t{r.id}').", 'steer', 'task', log=False)
        return [f't{r.id}' for r in rows]

    def context(s, a, ref, budget=2000):
        t = s.get(pid('t', ref, 'task'))
        return {'task': s.show(t, full=True)} | s.depCtx(t, budget)

    def depCtx(s, t, budget):
        if not (ids := ([t.checks] if t.checks else []) + s.deps(t.id)): return {}
        names, ds = s.agents.names(), [s.get(d) for d in ids]
        total, share, out = sum(toks(d.result or '') for d in ds), max(200, budget//len(ds)), []
        for d in ds:
            e, r = {'id': f't{d.id}', 'title': d.title, 'state': d.state, 'by': names.get(d.owner)}, d.result or ''
            if total > budget and toks(r) > share:
                e |= {'summary': s.summ(r.splitlines(), share, f"result of t{d.id} '{d.title}'"), 'full': f"task('t{d.id}') has all of it"}
            else: e['result'] = r
            if d.notes: e['notes'] = [clip(dumps(n), 400) for n in d.notes[-3:]]
            out.append(e)
        return {'dependencies': out}
