import math

from .err import Bad, Clash, Denied, Missing
from .log import fmt
from .prompt import brief as briefText, lineage as lineageText
from .util import J, ago, an, dumps, line, now, pid, poll, toks

SETTLED = ('done', 'failed', 'cancelled', 'blocked')
LAUNCH = ('host', 'runner', 'none')
SUB = "WITH RECURSIVE sub(id,d) AS (SELECT ?,0 UNION ALL SELECT a.id,sub.d+1 FROM agents a JOIN sub ON a.parent=sub.id WHERE sub.d<64) "
ROLLUP = SUB + """SELECT
 (SELECT json_group_object(state,n) FROM (SELECT state,COUNT(*) n FROM agents WHERE id IN (SELECT id FROM sub) GROUP BY state)) agents,
 (SELECT json_group_object(state,n) FROM (SELECT state,COUNT(*) n FROM tasks WHERE owner IN (SELECT id FROM sub) AND kind!='verify' GROUP BY state)) tasks,
 (SELECT COUNT(*) FROM issues WHERE state='open' AND src IN (SELECT id FROM sub)) issues,
 (SELECT COUNT(*) FROM mrs WHERE state='open' AND src IN (SELECT id FROM sub)) merges,
 (SELECT COUNT(*) FROM msgs WHERE mode='interrupt' AND ackAt IS NULL AND dst IN (SELECT id FROM sub)) interrupts,
 (SELECT COUNT(*) FROM agents WHERE id IN (SELECT id FROM sub) AND state IN ('active','idle','pending') AND seen<?) stale,
 (SELECT MAX(seen) FROM agents WHERE id IN (SELECT id FROM sub)) last,
 (SELECT COUNT(*)-1 FROM sub) below"""


class Tree:
    def __init__(s, db, log, mail, agents, roles, tasks, summ, cfg):
        s.db, s.log, s.mail, s.agents, s.roles, s.tasks, s.summ, s.cfg, s.tips = db, log, mail, agents, roles, tasks, summ, cfg, None
        agents.left.append(s.gone)

    def at(s, me, of):
        if of in (None, '', 'here'): return s.agents.get(s.log.cur(me.id, 'tree') or me.id)
        if of in ('me', 'self'): return me
        a = s.agents.named(str(of).rsplit('/', 1)[-1])
        if '/' in of and not ('/'+s.path(a.id)).endswith('/'+of.strip('/')): raise Missing(f'no agent at {of}', f'{a.name} lives at {s.path(a.id)}')
        return a

    def kids(s, aid, limit=-1, after=0):
        return s.db.q('SELECT * FROM agents WHERE parent=? AND id>? ORDER BY id LIMIT ?', (aid, after, limit))

    def path(s, aid): return '/'.join(s.agents.names()[i] for i in reversed(s.agents.above(aid)))

    def spawn(s, a, goal, role=None, name=None, budget=None, launch='host', grants=None, deliver='', paths=None, verify=False, harness=None):
        s.roles.need(a, 'fork', 'spawn agents')
        role, cfg = role or a.role, s.cfg
        if not (goal or '').strip(): raise Bad('a child needs a goal: what it should achieve')
        if launch not in LAUNCH: raise Bad(f'launch is one of {", ".join(LAUNCH)}')
        if a.depth+1 > cfg.depth: raise Clash(f'{a.name} is at depth {a.depth}; the tree allows {cfg.depth} levels', 'do this yourself or escalate')
        mine, want = s.roles.caps(a), s.roles.get(role).caps
        if grants is not None and (bad := set(grants) - (mine & want)):
            raise Denied(f"you cannot grant {', '.join(sorted(bad))} to {an(role)}", 'a child gets at most what both you and its role allow')
        caps = frozenset(grants) & want & mine if grants is not None else want & mine
        with s.db.tx() as c:
            a = c.execute('SELECT * FROM agents WHERE id=?', (a.id,)).fetchone()
            if (n := c.execute("SELECT COUNT(*) n FROM agents k LEFT JOIN tasks t ON t.id=k.deleg WHERE k.parent=? AND k.state!='left' "
                               "AND (t.id IS NULL OR t.state NOT IN ('done','failed','cancelled','blocked'))", (a.id,)).fetchone().n) >= cfg.fanout:
                raise Clash(f'{a.name} already has {n} live children (limit {cfg.fanout})', 'gather or cancel some first')
            b = max(0, (a.budget-1)//2) if budget is None else int(budget)
            if b < 0 or a.budget < b+1:
                raise Clash(f'{a.name} has budget {a.budget}; a child costs 1 plus the budget it receives ({b})',
                            'ask for less, gather children to recover their unspent budget, or escalate with fund')
            taken = set(s.agents.names().values())
            base = name or f'{a.name}.{role[:4]}'
            n = name or next(x for x in (f'{base}{i}' for i in range(1, 10000)) if x not in taken)
            if name and name in taken: raise Clash(f'{name} is taken')
            kid = s.agents.join(n, role, s.agents.wfNames().get(a.wf), a.id, goal[:200])
            t = s.tasks.delegate(c, a, kid, goal, deliver, role, paths, verify, harness)
            c.execute("UPDATE agents SET budget=budget-? WHERE id=?", (b+1, a.id))
            c.execute("UPDATE agents SET budget=?,goal=?,deleg=?,launch=?,grants=?,state=?,task=NULL WHERE id=?",
                      (b, goal, t, launch, None if caps == want else dumps(sorted(caps)), 'pending', kid.id))
            s.log.add(c, a.id, 'agent.spawned', f'spawned {n} ({role}, budget {b}, {launch}) for t{t}: {line(goal, 100)}', f'agent:{a.name}',
                      {'child': n, 'task': f't{t}'}, a.wf)
            kid = c.execute('SELECT * FROM agents WHERE id=?', (kid.id,)).fetchone()
        out = {'agent': n, 'role': role, 'task': f't{t}', 'depth': kid.depth, 'budget': b, 'launch': launch, 'token': kid.token,
               'path': s.path(kid.id)} | ({'harness': harness} if harness else {})
        if caps != want: out['narrowed'] = sorted(want - caps)
        if launch == 'host': out |= {'prompt': s.prompt(kid), 'hint': 'start a subagent with this prompt; gather collects its result'}
        elif launch == 'runner': out['hint'] = "Hive's runner starts it as its own process; gather collects its result"
        return out

    def prompt(s, kid):
        kid = s.agents.get(kid.id)
        t = s.tasks.get(kid.deleg)
        chain = [s.agents.get(i) for i in reversed(s.agents.above(kid.id))]
        return lineageText(briefText(kid.name, kid.role, s.roles.get(kid.role).charter, kid.token), chain, t, kid.budget, s.cfg.depth-kid.depth,
                           sorted(J(kid.grants)) if kid.grants else None, s.tips(f'{kid.goal} {t.about}') if s.tips else None)

    def gather(s, me, of=None, secs=60, any=False, budget=2000):
        if of: ts = [s.tasks.get(s.pick(x)) for x in ([of] if isinstance(of, str) else of)]
        else: ts = [s.tasks.get(r.deleg) for r in s.db.q('SELECT deleg FROM agents WHERE parent=? AND deleg IS NOT NULL ORDER BY id', (me.id,))]
        if not ts: return {'done': True, 'settled': [], 'waiting': [], 'note': 'you have no delegated children'}
        ids = [t.id for t in ts]
        q = f"SELECT * FROM tasks WHERE id IN ({','.join('?'*len(ids))}) ORDER BY id"
        was = {t.id for t in ts if t.state in SETTLED}

        def check():
            rows = s.db.q(q, ids)
            ok = {r.id for r in rows if r.state in SETTLED}
            return rows if len(ok) == len(rows) or (any and ok - was) else None

        with s.db.tx() as c: s.agents.set(c, me.id, state='idle')
        try: rows = poll(check, max(0., min(float(secs), 900.))) or s.db.q(q, ids)
        finally:
            with s.db.tx() as c: s.agents.set(c, me.id, state='active')
        names, share = s.agents.names(), max(200, budget//max(1, len(rows)))
        out = {'settled': [], 'waiting': []}
        for r in rows:
            e = {'agent': names.get(r.owner), 'task': f't{r.id}', 'state': r.state}
            if r.state in SETTLED:
                res = r.result or ''
                e['result'] = res if toks(res) <= share else s.summ(res.splitlines(), share, f'result of t{r.id} {r.title}').text
            else: e['status'] = s.agents.get(r.owner).status if r.owner else ''
            out['settled' if r.state in SETTLED else 'waiting'].append(e)
        return {'done': not out['waiting'], **out}

    def pick(s, x):
        if r := s.db.one('SELECT deleg FROM agents WHERE name=?', (x,)):
            if not r.deleg: raise Bad(f'{x} has no delegated task')
            return r.deleg
        return pid('t', x, 'task')

    def fund(s, a, of, amount):
        k = s.agents.named(of)
        if a.id not in s.agents.above(k.id)[1:]: raise Denied(f'{k.name} is not below you')
        if amount < 1: raise Bad('fund at least 1')
        if k.state == 'left': raise Clash(f'{k.name} has left')
        with s.db.tx() as c:
            if c.execute('UPDATE agents SET budget=budget-? WHERE id=? AND budget>=? RETURNING budget', (amount, a.id, amount)).fetchone() is None:
                raise Clash(f'you do not have {amount} budget to give')
            c.execute('UPDATE agents SET budget=budget+? WHERE id=?', (amount, k.id))
            s.log.add(c, a.id, 'agent.funded', f'gave {amount} budget to {k.name}', f'agent:{k.name}', wf=a.wf)
        return {'agent': k.name, 'budget': s.agents.get(k.id).budget, 'yours': s.agents.get(a.id).budget}

    def gone(s, c, aid):
        a = c.execute('SELECT * FROM agents WHERE id=?', (aid,)).fetchone()
        h = a.parent and s.agents.heir(c, a.parent)
        kids = c.execute("SELECT id,name,parent FROM agents WHERE keeper=? AND state!='left' AND id!=?", (aid, aid)).fetchall()
        got = {}
        for k in kids:
            n = k.parent and s.agents.heir(c, k.parent)
            n = n if n and n.id != k.id else None
            c.execute('UPDATE agents SET keeper=? WHERE id=?', (n and n.id, k.id))
            s.mail.put(c, None, [k.id], f"{a.name}, who kept you, left. Your keeper is now {n.name if n else 'nobody: you are orphaned'}. "
                                        'Your lineage and inherited context are unchanged.', 'steer', 'custody', log=False)
            if n: got.setdefault(n.id, []).append(k.name)
        for i, ns in got.items(): s.mail.put(c, None, [i], f"{a.name} left; you now keep {', '.join(ns)}.", 'steer', 'custody', log=False)
        c.execute("UPDATE issues SET state='withdrawn',doneAt=? WHERE src=? AND state='open'", (now(), aid))
        for i in c.execute("SELECT id FROM issues WHERE holder=? AND state='open'", (aid,)).fetchall():
            c.execute('UPDATE issues SET holder=? WHERE id=?', (h and h.id, i.id))
            if h: s.mail.put(c, None, [h.id], f'issue i{i.id} was waiting on {a.name}, who left; it is yours now: issues()', 'steer', 'issue', log=False)
        if h and a.budget:
            c.execute('UPDATE agents SET budget=budget+? WHERE id=?', (a.budget, h.id))
            c.execute('UPDATE agents SET budget=0 WHERE id=?', (aid,))
            if a.deleg and (t := c.execute('SELECT notes FROM tasks WHERE id=?', (a.deleg,)).fetchone()):
                c.execute('UPDATE tasks SET notes=? WHERE id=?', (dumps([*J(t.notes, []), {'by': 'hive', 'budget': a.budget, 'to': h.name}]), a.deleg))
        if kids or a.budget: s.log.add(c, aid, 'agent.custody', f"left; {len(kids)} child(ren) and budget {a.budget} went to {h.name if h else 'nobody'}",
                                        f'agent:{a.name}', wf=a.wf)

    def adopt(s, a, of):
        k = s.agents.named(of)
        if k.id in s.agents.above(a.id): raise Denied('you cannot keep yourself or an ancestor')
        if a.id not in s.agents.above(k.id)[1:] and not s.roles.can(a, 'spawn'): raise Denied(f'{k.name} is not below you')
        with s.db.tx() as c:
            c.execute('UPDATE agents SET keeper=? WHERE id=?', (a.id, k.id))
            s.mail.put(c, a, [k.id], f'{a.name} keeps you now; escalate reaches {a.name}.', 'steer', 'custody')
        return {'agent': k.name, 'keeper': a.name}

    def escalate(s, a, need, options=None, fund=0, mode='interrupt'):
        if not need.strip(): raise Bad('say what decision you need')
        if fund < 0: raise Bad('fund cannot be negative')
        with s.db.tx() as c:
            h = c.execute('SELECT * FROM agents WHERE id=?', (a.keeper,)).fetchone() if a.keeper else None
            h = h if h and h.state != 'left' else a.parent and s.agents.heir(c, a.parent)
            i = c.execute('INSERT INTO issues(src,holder,need,options,fund,ts) VALUES(?,?,?,?,?,?)',
                          (a.id, h and h.id, need, dumps(options or []), int(fund), now())).lastrowid
            if h:
                s.mail.put(c, a, [h.id], f"issue i{i} from {a.name}: {need}" + (f"\noptions: {', '.join(options)}" if options else '') +
                           (f'\nasks for {fund} budget' if fund else '') + f"\nAnswer with decide('i{i}', choice=..., note=...), or choice='up' to pass it on.",
                           mode, 'issue', {'issue': f'i{i}'})
            s.log.add(c, a.id, 'issue.raised', f"i{i} to {h.name if h else 'nobody'}: {line(need, 100)}", f'agent:{a.name}', wf=a.wf)
        return {'issue': f'i{i}', 'holder': h.name if h else None} | ({} if h else {'note': 'no live ancestor to route it to; it stays open'})

    def decide(s, a, ref, choice, note='', fund=None):
        with s.db.tx() as c:
            if (x := c.execute('SELECT * FROM issues WHERE id=?', (i := pid('i', ref, 'issue'),)).fetchone()) is None: raise Missing(f'no issue i{i}')
            if x.state != 'open': raise Clash(f'i{i} is already {x.state}')
            if a.id != x.holder and a.id not in s.agents.above(x.src)[1:] and not (x.holder is None and s.roles.can(a, 'manage')):
                raise Denied(f'i{i} is not yours to decide')
            src = c.execute('SELECT * FROM agents WHERE id=?', (x.src,)).fetchone()
            if choice == 'up':
                hp = x.holder and c.execute('SELECT parent FROM agents WHERE id=?', (x.holder,)).fetchone()
                up = hp and hp.parent and s.agents.heir(c, hp.parent)
                if not up: raise Clash('there is nobody above you to pass it to')
                c.execute('UPDATE issues SET holder=? WHERE id=?', (up.id, i))
                s.mail.put(c, a, [up.id], f"issue i{i} from {src.name}, passed up by {a.name}: {x.need}\n{note}".strip(), 'interrupt', 'issue', {'issue': f'i{i}'})
                return {'issue': f'i{i}', 'holder': up.name}
            give = x.fund if fund is None else int(fund)
            if give < 0: raise Bad('fund cannot be negative')
            give = give if src.state != 'left' else 0
            if give and c.execute('UPDATE agents SET budget=budget-? WHERE id=? AND budget>=? RETURNING id', (give, a.id, give)).fetchone() is None:
                raise Clash(f'you do not have {give} budget to give', 'decide with fund=0, or pass it up')
            if give: c.execute('UPDATE agents SET budget=budget+? WHERE id=?', (give, src.id))
            c.execute("UPDATE issues SET state='decided',choice=?,note=?,doneAt=? WHERE id=?", (choice, note, now(), i))
            s.mail.put(c, a, [src.id], f"{a.name} decided i{i}: {choice}" + (f' ({note})' if note else '') + (f'; you got {give} budget' if give else ''),
                       'interrupt', 'decision', {'issue': f'i{i}', 'choice': choice})
            s.log.add(c, a.id, 'issue.decided', f'i{i} for {src.name}: {line(choice, 80)}', f'agent:{src.name}', wf=a.wf)
        return {'issue': f'i{i}', 'state': 'decided', 'funded': give}

    def issues(s, a, mine=True):
        names = s.agents.names()
        rows = s.db.q("SELECT * FROM issues WHERE state='open' AND (? OR holder=? OR src=?) ORDER BY id", (not mine, a.id, a.id))
        return [{'issue': f'i{x.id}', 'from': names.get(x.src), 'holder': names.get(x.holder), 'need': x.need, 'options': J(x.options, []),
                 'fund': x.fund, 'age': ago(x.ts)} for x in rows]

    def rollup(s, aid):
        r = s.db.one(ROLLUP, (aid, now()-s.cfg.stale))
        out = {'below': r.below, 'agents': J(r.agents, {}), 'tasks': J(r.tasks, {}), 'last': ago(r.last)}
        return out | {k: r[k] for k in ('issues', 'merges', 'interrupts', 'stale') if r[k]}

    def row(s, a, names):
        t = a.deleg and s.tasks.get(a.deleg)
        return ' · '.join([a.name, a.role, a.state] + ([f't{t.id} {t.state}'] if t else []) +
                          ([f'"{line(a.status or a.goal, 60)}"'] if a.status or a.goal else []))

    def node(s, me, of=None, limit=12):
        a, names = s.at(me, of), s.agents.names()
        t = a.deleg and s.tasks.get(a.deleg)
        out = {'name': a.name, 'path': s.path(a.id), 'role': a.role, 'state': a.state, 'depth': a.depth, 'budget': a.budget}
        if a.keeper != a.parent: out['keeper'] = names.get(a.keeper, 'nobody')
        for k, v in (('goal', a.goal), ('status', a.status), ('grants', a.grants and J(a.grants))):
            if v: out[k] = v
        if t: out['task'] = {'id': f't{t.id}', 'state': t.state, 'deliver': t.deliver} | ({'result': line(t.result, 300)} if t.result else {})
        ks, n = s.kids(a.id, limit), s.db.one('SELECT COUNT(*) n FROM agents WHERE parent=?', (a.id,)).n
        out['children'] = [s.row(k, names) for k in ks] + ([f'+{n-len(ks)} more' + (f': tree(of={a.name!r}, after={ks[-1].name!r})' if ks else '')]
                                                            if n > len(ks) else [])
        out['rollup'] = s.rollup(a.id)
        if nxt := s.hot(a.id): out['look'] = nxt
        return out

    def hot(s, aid):
        r = s.db.one(SUB + "SELECT a.name, CASE WHEN EXISTS(SELECT 1 FROM tasks t WHERE t.owner=a.id AND t.state='failed') THEN 'failed task' "
                     "WHEN EXISTS(SELECT 1 FROM issues i WHERE i.src=a.id AND i.state='open') THEN 'open issue' "
                     "WHEN EXISTS(SELECT 1 FROM mrs m WHERE m.src=a.id AND m.state='open') THEN 'merge request' "
                     "WHEN a.state IN ('active','idle','pending') AND a.seen<? THEN 'stale' END why FROM agents a "
                     "WHERE a.id IN (SELECT id FROM sub) AND a.id!=? AND why IS NOT NULL ORDER BY a.depth LIMIT 1", (aid, now()-s.cfg.stale, aid))
        return r and f"{r.name} needs attention ({r.why}): node('{r.name}')"

    def tree(s, me, of=None, depth=1, limit=12, after=None):
        if of == '*':
            roots = s.db.q("SELECT * FROM agents WHERE parent IS NULL AND state!='left' ORDER BY id")
            return {'tree': '\n'.join(s.tree(me, r.name, depth, limit)['tree'] for r in roots) or '(no agents)', 'roots': [r.name for r in roots]}
        a, names = s.at(me, of), s.agents.names()
        start = s.agents.named(after).id if after else 0
        out = [s.row(a, names) + (f' · {s.rollup(a.id)["below"]} below' if depth else '')]

        def walk(p, d, pre, first):
            ks = s.kids(p.id, limit, first)
            n = s.db.one('SELECT COUNT(*) n FROM agents WHERE parent=? AND id>?', (p.id, first)).n
            for i, k in enumerate(ks):
                last = i == len(ks)-1 and n <= len(ks)
                below = s.rollup(k.id)['below'] if d == depth else 0
                out.append(pre + ('└─ ' if last else '├─ ') + s.row(k, names) + (f' · {below} below' if below else ''))
                if d < depth: walk(k, d+1, pre + ('   ' if last else '│  '), 0)
            if n > len(ks): out.append(pre + f"└─ +{n-len(ks)} more" + (f": tree(of={p.name!r}, after={ks[-1].name!r})" if ks else ''))

        if depth: walk(a, 1, '', start)
        return {'tree': '\n'.join(out), 'root': a.name, 'path': s.path(a.id)}

    def walk(s, me, to='here'):
        cur = s.at(me, None)
        if to in ('here', '', None): nxt = cur
        elif to in ('me', 'self'): nxt = me
        elif to == 'up':
            if not cur.parent: raise Clash(f'{cur.name} is a root')
            nxt = s.agents.get(cur.parent)
        elif to == 'root': nxt = s.agents.get(s.agents.above(cur.id)[-1])
        elif to == 'down' or to.startswith('down:'):
            want = to.partition(':')[2]
            ks = [k for k in s.kids(cur.id) if not want or k.name == want]
            if not ks: raise Missing(f"{cur.name} has no child {want or ''}".strip(), 'tree shows the children')
            nxt = ks[0]
        elif to in ('next', 'prev'):
            sib = s.kids(cur.parent) if cur.parent else s.db.q('SELECT * FROM agents WHERE parent IS NULL ORDER BY id')
            i = [k.id for k in sib].index(cur.id) + (1 if to == 'next' else -1)
            if not 0 <= i < len(sib): raise Clash(f'no {to} sibling of {cur.name}')
            nxt = sib[i]
        else: nxt = s.agents.named(to.rsplit('/', 1)[-1])
        with s.db.tx() as c: s.log.setCur(c, me.id, 'tree', nxt.id)
        return s.node(me, nxt.name)

    def lineage(s, me, of=None):
        a = s.at(me, of)
        chain = []
        for i in reversed(s.agents.above(a.id)):
            x = s.agents.get(i)
            t = x.deleg and s.tasks.get(x.deleg)
            chain.append({'name': x.name, 'role': x.role, 'state': x.state} | ({'goal': x.goal} if x.goal else {}) |
                         ({'task': f't{t.id} {t.state}'} if t else {}))
        return {'path': s.path(a.id), 'chain': chain}

    def find(s, me, query='', within=None, state=None, role=None, limit=20):
        w = s.at(me, within) if within else None
        rows = s.db.q((SUB if w else '') + "SELECT a.*, t.title FROM agents a LEFT JOIN tasks t ON t.id=a.deleg WHERE " +
                      ('a.id IN (SELECT id FROM sub) AND ' if w else '') +
                      "lower(a.name||' '||a.goal||' '||a.status||' '||COALESCE(t.title,'')) LIKE ? AND (? IS NULL OR a.state=?) AND "
                      "(? IS NULL OR a.role=?) ORDER BY a.depth,a.id LIMIT ?",
                      ([w.id] if w else []) + [f'%{query.lower()}%', state, state, role, role, limit])
        names = s.agents.names()
        return {'found': [{'path': s.path(r.id), 'line': s.row(r, names)} for r in rows]}

    def brief(s, me, of=None, budget=800, depth=3):
        a = s.at(me, of)
        blockers = s.db.q(SUB + "SELECT a.name, (SELECT group_concat('t'||t.id||' failed: '||substr(COALESCE(t.result,''),1,80),'; ') FROM tasks t "
                          "WHERE t.owner=a.id AND t.state='failed') f, (SELECT group_concat('i'||i.id||': '||substr(i.need,1,80),'; ') FROM issues i "
                          "WHERE i.src=a.id AND i.state='open') i FROM agents a WHERE a.id IN (SELECT id FROM sub)", (a.id,))
        blocked = [f"{b.name}: {'; '.join(x for x in (b.f, b.i) if x)}" for b in blockers if b.f or b.i][:10]
        return {'node': a.name, 'path': s.path(a.id), 'blockers': blocked, 'rollup': s.rollup(a.id),
                'summary': s.recap(a, max(80, budget - toks('\n'.join(blocked))), depth)}

    def recap(s, a, budget, depth):
        names = s.agents.names()
        own = [fmt(e, names, False) for e in s.log.find(agent=a.id, limit=1 << 20)]
        ks = [k for k in s.kids(a.id)] if depth else []
        if not ks: return s.summ(own, budget, f'what {a.name} ({a.role}) did toward its goal: {a.goal or a.status}').text if own else '(no activity)'
        acts = [max(1, s.db.one(SUB + 'SELECT COUNT(*) n FROM events WHERE agent IN (SELECT id FROM sub)', (k.id,)).n) for k in ks]
        mineShare = max(60, budget//(len(ks)+2))
        room = max(0, budget - mineShare - 25*len(ks))
        w = [math.sqrt(x) for x in acts]
        parts = [s.summ(own, mineShare, f'what {a.name} ({a.role}) itself did: {a.goal or a.status}').text if own else '(no own activity)']
        for k, wk in zip(ks, w):
            share = 25 + int(room*wk/sum(w))
            head = s.row(k, names)
            parts.append(f'- {head}' if share < 80 else f'- {head}\n  ' + s.recap(k, share, depth-1).replace('\n', '\n  '))
        return '\n'.join(parts)
