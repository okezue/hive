import math, os, re, secrets, sqlite3
from collections import defaultdict
from pathlib import Path

from .db import LIB, Db
from .err import Bad, Denied, Missing
from .tasks import SETTLED, TERMINAL
from .util import J, ago, clip, dumps, line, now, pid

KINDS = ('fact', 'result', 'decision', 'problem', 'method', 'verdict')
SORTS = ('observed', 'reusable')
STANCES = ('support', 'against')
SYNTH = ('composer', 'distiller')
BOOST = {'established': .15, 'proposed': 0., 'contested': -.3}
STOP = frozenset('the and for with that this from are was were been have has had not but you your our its into over under than then them they '
                 'their there what when where which while will would should could can may might also just very more most less such only other '
                 'some any each both all about after before because'.split())
UP = "WITH RECURSIVE up(id,p,k) AS (SELECT id,parent,kind FROM tasks WHERE id=? UNION ALL SELECT t.id,t.parent,t.kind FROM tasks t JOIN up ON t.id=up.p) "

COMPOSE = ("Compose what {n} and the agents under it found into one account.\n1. stale('{n}') lists the nodes below whose compositions are "
           "missing or out of date, deepest first. Compose those branches first: if you have budget, spawn sub-composers (role composer) "
           "with a goal like \"compose <node>\" and gather them; otherwise compose them yourself.\n2. material('{n}') gives {n}'s own "
           "findings, each child's composition or raw findings, and flagged contradictions.\n3. compose('{n}', text, sources=[f.., cp..]) "
           "records the account. Cite what you used or deliberately set aside, name contradictions and gaps, add nothing no agent found.\n"
           "4. Finish with done and a one-paragraph summary.")
DISTILL = ("Find insights in {n}'s tree worth keeping beyond this session. harvest('{n}') shows each branch's composition or findings, echoes "
           "across branches, and the saved insights that look related. For a pattern seen in more than one independent branch (observed) or a "
           "lesson that would help future work (reusable): weigh an existing insight with your evidence, or distill a new one citing findings "
           "from each branch. Contest insights the evidence contradicts with weigh(stance='against'). Finish with done, listing what you saved.")


def words(t): return {w for w in re.findall(r'[a-z0-9_]{3,}', t.lower()) if w not in STOP}


def qs(xs): return ','.join('?'*len(xs))


class Lib:
    def __init__(s, path, pre, ro=False): s.db, s.pre = Db(path, schema=LIB, add=(), ro=ro), pre

    def get(s, i):
        if (r := s.db.one('SELECT * FROM insights WHERE id=?', (i,))) is None: raise Missing(f'no insight {s.pre}{i}')
        return r


class Know:
    def __init__(s, h):
        s.h, k = h, h.cfg.insights
        s.auto, s.min, s.libs, s.ro = bool(k.get('auto', True)), int(k.get('min', 2)), {}, {}
        s.paths = {'project': h.cfg.dir/'insights.db', 'global': os.environ.get('HIVE_GLOBAL') or k.get('global', '~/.hive/insights.db')}
        with h.db.tx() as c:
            c.execute('INSERT OR IGNORE INTO meta VALUES(?,?)', ('session', secrets.token_hex(6)))
            s.session = c.execute("SELECT val FROM meta WHERE key='session'").fetchone().val
        h.tasks.hooks.append(s.done)

    def lib(s, scope, make=True):
        if scope not in s.paths: raise Bad("scope is 'project' or 'global'")
        pre, p = 'in' if scope == 'project' else 'ig', Path(s.paths[scope]).expanduser()
        if make:
            if scope not in s.libs: s.libs[scope] = Lib(p, pre)
            return s.libs[scope]
        if scope in s.libs: return s.libs[scope]
        if scope not in s.ro and p.exists(): s.ro[scope] = Lib(p, pre, True)
        return s.ro.get(scope)

    def ref(s, x):
        scope = 'global' if str(x).startswith('ig') else 'project'
        if (lib := s.lib(scope, make=False)) is None: raise Missing(f'no {scope} insight library yet')
        lib.get(i := pid(lib.pre, x, 'insight'))
        return scope, i

    def under(s, aid): return s.h.agents.below(aid)

    def latest(s, node): return s.h.db.one('SELECT * FROM comps WHERE node=? ORDER BY id DESC LIMIT 1', (node,))

    def finding(s, i):
        if (r := s.h.db.one('SELECT * FROM findings WHERE id=?', (i,))) is None: raise Missing(f'no finding f{i}')
        return r

    def fline(s, f, names): return f"f{f.id} [{f.kind}] {names.get(f.agent, '?')}: {f.text}" + (f" (refs {', '.join(J(f.refs))})" if J(f.refs) else '')

    def fit(s, ls, budget, focus): return s.h.summ(ls, budget, focus + '; keep every id such as f12 or cp3 exactly').text if ls else ''

    def put(s, c, aid, text, kind, refs, tags, conf, task):
        i = c.execute('INSERT INTO findings(agent,task,text,kind,refs,tags,conf,ts) VALUES(?,?,?,?,?,?,?,?)',
                      (aid, task, text, kind, dumps(refs or []), dumps(tags or []), max(0., min(1., float(conf))), now())).lastrowid
        s.h.log.add(c, aid, 'finding', f'f{i} [{kind}] {line(text, 120)}', f"agent:{s.h.agents.names().get(aid)}")
        return i

    def note(s, a, text, kind='fact', refs=None, tags=None, conf=.7):
        s.h.roles.need(a, 'post', 'record findings')
        if not (text or '').strip(): raise Bad('a finding needs text')
        if kind not in KINDS: raise Bad(f"kind is one of {', '.join(KINDS)}")
        for r in refs or []:
            if str(r).startswith('against:'): s.finding(pid('f', r[8:], 'finding'))
        with s.h.db.tx() as c: i = s.put(c, a.id, text.strip(), kind, refs, tags, conf, a.task)
        return {'finding': f'f{i}', 'path': s.h.tree.path(a.id)}

    def synth(s, c, t, owner):
        if owner and c.execute('SELECT role FROM agents WHERE id=?', (owner,)).fetchone().role in SYNTH: return True
        return bool(c.execute(UP + "SELECT 1 FROM up WHERE k IN ('compose','distill') LIMIT 1", (t.id,)).fetchone())

    def lca(s, ids):
        chains = [s.h.agents.above(i)[::-1] for i in ids if i]
        top = None
        for xs in zip(*chains):
            if len(set(xs)) > 1: break
            top = xs[0]
        return top

    def done(s, c, a, t, state, result):
        owner = a and a.id if t.kind == 'verify' else t.owner
        if t.kind in ('compose', 'distill') or s.synth(c, t, owner): return
        if state == 'done' and owner and (result or '').strip():
            s.put(c, owner, clip(result, 4000), 'verdict' if t.kind == 'verify' else 'result', [f't{t.checks or t.id}'], [],
                  .8 if t.kind == 'verify' else .7, t.checks or t.id)
        if not s.auto: return
        if t.owner and t.kind == 'work' and state == 'done' and len(subs := c.execute(
                "SELECT owner FROM tasks WHERE parent=? AND kind!='verify' AND state='done'", (t.id,)).fetchall()) >= s.min \
                and (n := s.lca([t.owner, *[r.owner for r in subs]])): s.enqueue(c, 'compose', n)
        for p in {t.owner and c.execute('SELECT parent FROM agents WHERE id=?', (t.owner,)).fetchone().parent, t.creator} - {None}:
            if s.settled(c, p): s.enqueue(c, 'compose', p)

    def settled(s, c, p):
        ks = c.execute(f"SELECT a.id,t.id tid,t.state,t.creator FROM agents a JOIN tasks t ON t.id=a.deleg WHERE a.parent=? AND a.role NOT IN ({qs(SYNTH)})",
                       (p, *SYNTH)).fetchall()
        if sum(k.state == 'done' for k in ks) < s.min or any(k.state not in SETTLED for k in ks): return False
        who, ts = list({p, *(k.id for k in ks), *(k.creator for k in ks if k.creator)}), [k.tid for k in ks]
        return not c.execute(f"SELECT 1 FROM tasks WHERE state NOT IN ({qs(SETTLED)}) AND kind NOT IN ('compose','distill') "
                             f"AND (creator IN ({qs(who)}) OR checks IN ({qs(ts)})) LIMIT 1", [*SETTLED, *who, *ts]).fetchone()

    def staffed(s, c, role):
        if c.execute(f"SELECT 1 FROM agents a LEFT JOIN tasks t ON t.id=a.deleg WHERE a.role=? AND a.state!='left' AND a.seen>? "
                     f"AND (t.id IS NULL OR t.state NOT IN ({qs(TERMINAL)}))", (role, now()-s.h.cfg.stale, *TERMINAL)).fetchone(): return True
        if (r := c.execute("SELECT val FROM meta WHERE key='runner'").fetchone()) and now()-(m := J(r.val))['ts'] < max(60, 5*s.h.cfg.runner.get('poll', 1)) \
                and {role, 'default'} & set(m['roles']): return True
        rs = s.h.cfg.runner.get('roles', {})
        return bool(rs.get(role, {}).get('command') or rs.get('default', {}).get('command'))

    def enqueue(s, c, kind, node):
        role = 'composer' if kind == 'compose' else 'distiller'
        if c.execute("SELECT 1 FROM tasks WHERE kind=? AND node=? AND state IN ('pending','ready','running')", (kind, node)).fetchone() \
                or not s.staffed(c, role): return None
        n = c.execute('SELECT name FROM agents WHERE id=?', (node,)).fetchone().name
        title, about = (f"Compose what {n}'s subtree found", COMPOSE) if kind == 'compose' else (f"Distill insights from {n}'s tree", DISTILL)
        return s.h.tasks.file(c, None, title, about.format(n=n), role, kind, node)

    def findings(s, me, of=None, deep=True, kind=None, since=0, limit=50):
        a, names = s.h.tree.at(me, of), s.h.agents.names()
        ids = s.under(a.id) if deep else [a.id]
        rows = s.h.db.q(f'SELECT * FROM findings WHERE agent IN ({qs(ids)}) AND (? IS NULL OR kind=?) AND id>? ORDER BY id DESC LIMIT ?',
                        [*ids, kind, kind, since or 0, limit])
        return {'of': a.name, 'findings': [{'id': f'f{r.id}', 'kind': r.kind, 'by': names.get(r.agent), 'path': s.h.tree.path(r.agent),
                                            'text': r.text, 'refs': J(r.refs, []), 'conf': r.conf, 'at': ago(r.ts)} for r in rows]}

    def scan(s, root):
        ids = s.under(root)
        rows = s.h.db.q(f'SELECT id,parent,name,depth,role FROM agents WHERE id IN ({qs(ids)})', ids)
        kids, fs = defaultdict(list), defaultdict(list)
        for r in rows:
            if r.id != root: kids[r.parent].append(r.id)
        for f in s.h.db.q(f'SELECT id,agent FROM findings WHERE agent IN ({qs(ids)})', ids): fs[f.agent].append(f.id)
        comps = {r.node: r for r in s.h.db.q(f'SELECT * FROM comps WHERE id IN (SELECT MAX(id) FROM comps WHERE node IN ({qs(ids)}) GROUP BY node)', ids)}
        sub, by = {}, {}

        def walk(x):
            got, who = list(fs.get(x, [])), {x} if fs.get(x) else set()
            for k in kids.get(x, []):
                g, w = walk(k)
                got, who = got+g, who | w
            sub[x], by[x] = got, who
            return got, who

        walk(root)
        rs = {r.id: r for r in rows}
        for x in kids: kids[x] = [k for k in kids[x] if sub[k] or k in comps or rs[k].role not in SYNTH]
        return rs, kids, comps, sub, by

    def gap(s, cp, fs): return [f for f in fs if f not in set(J(cp.covers, []))] if cp else list(fs)

    def stale(s, me, of=None, limit=30):
        a = s.h.tree.at(me, of)
        rows, kids, comps, sub, by = s.scan(a.id)
        order = []

        def post(x):
            for k in kids.get(x, []): post(k)
            order.append(x)

        post(a.id)
        out = []
        for x in order:
            cp = comps.get(x)
            if not cp and len(by[x]) < 2: continue
            miss, newer = s.gap(cp, sub[x]), [k for k in kids.get(x, []) if comps.get(k) and cp and comps[k].id > cp.id]
            if cp and not miss and not newer: continue
            out.append({'node': rows[x].name, 'path': s.h.tree.path(x), 'why': 'never composed' if not cp else
                        f'{len(miss)} finding(s) not covered' if miss else 'a child was recomposed', 'findings': len(sub[x])} |
                       ({'composition': f'cp{cp.id}'} if cp else {}))
        return {'of': a.name, 'stale': out[:limit], 'more': max(0, len(out)-limit),
                'hint': 'deepest first: compose (or delegate) the branches before the node above them'}

    def material(s, me, of=None, budget=3000):
        a, names = s.h.tree.at(me, of), s.h.agents.names()
        rows, kids, comps, sub, _ = s.scan(a.id)
        share = max(150, budget//(len(kids.get(a.id, []))+2))
        own = s.h.db.q('SELECT * FROM findings WHERE agent=? ORDER BY id', (a.id,))
        out = {'node': a.name, 'path': s.h.tree.path(a.id), 'goal': a.goal,
               'own': s.fit([s.fline(f, names) for f in own], share*2 if kids.get(a.id) else budget, f"{a.name}'s own findings"), 'children': []}
        for k in kids.get(a.id, []):
            ids = s.under(k)
            fs = {f.id: f for f in s.h.db.q(f'SELECT * FROM findings WHERE agent IN ({qs(ids)}) ORDER BY id', ids)}
            cp, e = comps.get(k), {'node': rows[k].name, 'goal': s.h.agents.get(k).goal}
            if cp:
                miss = s.gap(cp, fs)
                e |= {'composition': f'cp{cp.id}', 'fresh': not miss, 'text': s.fit(cp.text.splitlines(), share, f'composition of {rows[k].name}')}
                if miss: e['notCovered'] = s.fit([s.fline(fs[f], names) for f in miss], share//2, f'findings under {rows[k].name} its composition misses')
            else: e |= {'uncomposed': len(fs), 'findings': s.fit([s.fline(f, names) for f in fs.values()], share, f'findings under {rows[k].name}')}
            out['children'].append(e)
        ids = s.under(a.id)
        if clash := s.h.db.q(f"SELECT * FROM findings WHERE agent IN ({qs(ids)}) AND refs LIKE '%against:%'", ids):
            out['contradictions'] = [f"f{f.id} ({names.get(f.agent)}) contradicts {', '.join(r[8:] for r in J(f.refs) if r.startswith('against:'))}: "
                                     f'{line(f.text, 160)}' for f in clash]
        return out | {'hint': f"cite the f and cp ids you used or set aside in compose('{a.name}', text, sources=[...]); compose uncomposed large children first"}

    def compose(s, a, of, text, sources=None, gaps=''):
        s.h.roles.need(a, 'compose', 'record compositions')
        n = s.h.tree.at(a, of)
        if not (text or '').strip(): raise Bad('the composition is empty')
        ids = set(s.under(n.id))
        fs = {r.id: r for r in s.h.db.q(f'SELECT id,agent FROM findings WHERE agent IN ({qs(list(ids))})', list(ids))}
        if not fs: raise Bad(f'nothing to compose: no findings under {n.name}')
        srcs, covers = [], set()
        for x in sources or []:
            x = str(x)
            if x.startswith('cp'):
                r = s.h.db.one('SELECT node,covers FROM comps WHERE id=?', (i := pid('cp', x, 'composition'),))
                if r is None or r.node not in ids or r.node == n.id: raise Bad(f'cp{i} is not a composition of a node below {n.name}')
                srcs.append(f'cp{i}')
                covers |= set(J(r.covers, []))
            else:
                if (i := pid('f', x, 'finding')) not in fs: raise Bad(f'f{i} is not a finding under {n.name}')
                srcs.append(f'f{i}')
                covers.add(i)
        if not srcs: raise Bad('cite the findings and compositions you combined in sources')
        prev = s.latest(n.id)
        v = prev.v+1 if prev else 1
        with s.h.db.tx() as c:
            i = c.execute('INSERT INTO comps(node,author,text,sources,gaps,upto,v,ts,covers) VALUES(?,?,?,?,?,?,?,?,?)',
                          (n.id, a.id, text.strip(), dumps(srcs), gaps or '', max(fs), v, now(), dumps(sorted(covers)))).lastrowid
            s.h.log.add(c, a.id, 'composition', f'cp{i} v{v} of {n.name}: {line(text, 120)}', f'agent:{n.name}', wf=a.wf)
            branches = sum(any(fs[f].agent in set(s.under(k.id)) for f in fs) for k in s.h.tree.kids(n.id))
            if s.auto and n.parent is None and branches >= 2: s.enqueue(c, 'distill', n.id)
        miss = [f'f{f}' for f in sorted(set(fs) - covers)]
        out = {'composition': f'cp{i}', 'node': n.name, 'version': v, 'sources': len(srcs)}
        return out | ({'notCovered': miss[:20], 'hint': 'uncovered findings keep this node stale; cite them if you considered them'} if miss else {})

    def gist(s, me, of=None):
        a = s.h.tree.at(me, of)
        if not (cp := s.latest(a.id)): return {'node': a.name, 'composition': None, 'hint': f"nothing composed yet; material('{a.name}') shows the raw findings"}
        ids = s.under(a.id)
        miss = s.gap(cp, [r.id for r in s.h.db.q(f'SELECT id FROM findings WHERE agent IN ({qs(ids)})', ids)])
        return {'node': a.name, 'composition': f'cp{cp.id}', 'version': cp.v, 'by': s.h.agents.names().get(cp.author), 'at': ago(cp.ts),
                'fresh': not miss, 'text': cp.text, 'sources': J(cp.sources, [])} | ({'gaps': cp.gaps} if cp.gaps else {}) | ({'notCovered': len(miss)} if miss else {})

    def branch(s, aid):
        if not aid: return None
        a = s.h.agents.get(aid)
        if a.role in SYNTH or (a.depth == 0 and s.h.tree.kids(aid, 1)): return None
        ch = s.h.agents.above(aid)
        return f"{s.session}#{s.h.agents.names().get(ch[-2] if len(ch) > 1 else ch[-1])}"

    def evidence(s, refs):
        out, names = [], s.h.agents.names()
        for x in refs:
            x = str(x)
            if x.startswith('cp'):
                if (r := s.h.db.one('SELECT * FROM comps WHERE id=?', (i := pid('cp', x, 'composition'),))) is None: raise Missing(f'no composition cp{i}')
                aid, text, x = r.node, r.text, f'cp{i}'
            elif x.startswith('t'):
                r = s.h.tasks.get(pid('t', x, 'task'))
                if r.state != 'done' or not r.result: raise Bad(f't{r.id} has no result to cite yet')
                aid, text, x = r.owner, r.result, f't{r.id}'
            else:
                r = s.finding(pid('f', x, 'finding'))
                aid, text, x = r.agent, r.text, f'f{r.id}'
            out.append({'ref': x, 'text': clip(text, 500), 'agent': names.get(aid), 'path': aid and s.h.tree.path(aid), 'branch': s.branch(aid)})
        return out

    def add(s, scope, i, ev, stance):
        with s.lib(scope).db.tx() as c:
            for e in ev:
                if not c.execute('SELECT 1 FROM evidence WHERE insight=? AND ref=? AND stance=? AND session=?', (i, e['ref'], stance, s.session)).fetchone():
                    c.execute('INSERT INTO evidence(insight,stance,ref,text,agent,path,branch,session,ts) VALUES(?,?,?,?,?,?,?,?,?)',
                              (i, stance, e['ref'], e['text'], e['agent'], e['path'], e['branch'], s.session, now()))
            r = c.execute("SELECT COUNT(DISTINCT CASE WHEN stance='support' THEN branch END) p, COUNT(DISTINCT CASE WHEN stance='against' THEN branch END) q "
                          'FROM evidence WHERE insight=?', (i,)).fetchone()
            conf = (r.p+1)/(r.p+r.q+2)
            st = 'established' if r.p >= 2 and conf >= .7 else 'contested' if r.q and conf < .5 else 'proposed'
            c.execute("UPDATE insights SET support=?,against=?,conf=?,seen=?,state=CASE WHEN state='retired' THEN state ELSE ? END WHERE id=?",
                      (r.p, r.q, conf, now(), st, i))

    def show(s, lib, i, ev=5):
        r = lib.get(i)
        out = {'insight': f'{lib.pre}{i}', 'kind': r.kind, 'title': r.title, 'body': r.body, 'state': r.state, 'conf': round(r.conf, 2),
               'support': r.support, 'against': r.against, 'uses': r.uses, 'tags': J(r.tags, []), 'by': r.author, 'scope': 'project' if lib.pre == 'in' else 'global'}
        if ev:
            out['evidence'] = [f"{e.stance} {e.ref} ({e.agent}, {e.path}): {line(e.text, 140)}"
                               for e in lib.db.q('SELECT * FROM evidence WHERE insight=? ORDER BY id DESC LIMIT ?', (i, ev))]
        return out

    def everything(s, scope=None):
        out = []
        for sc in [scope] if scope else ['project', 'global']:
            if lib := s.lib(sc, make=False):
                try: out += [(lib, r) for r in lib.db.q("SELECT * FROM insights WHERE state!='retired'")]
                except sqlite3.Error: pass
        return out

    def similar(s, text, at=.5):
        w = words(text)
        hits = [(len(w & (d := words(f'{r.title} {r.body}')))/len(w | d), lib, r) for lib, r in s.everything() if w]
        return [{'insight': f'{lib.pre}{r.id}', 'title': r.title, 'state': r.state, 'overlap': round(x, 2)} for x, lib, r in sorted(hits, key=lambda h: -h[0]) if x >= at][:5]

    def distill(s, a, title, body, kind='observed', evidence=None, tags=None, scope='project', into=None, force=False):
        s.h.roles.need(a, 'distill', 'save insights')
        if kind not in SORTS: raise Bad("kind is 'observed' (a pattern seen in the work) or 'reusable' (a lesson for future work)")
        if not title.strip() or not body.strip(): raise Bad('an insight needs a title and a body')
        if not (ev := s.evidence(evidence or [])): raise Bad('cite evidence: findings (f..), compositions (cp..), or tasks (t..) that show it')
        if into:
            sc, i = s.ref(into)
            s.add(sc, i, ev, 'support')
            return s.show(s.lib(sc), i) | {'status': 'merged'}
        lib = s.lib(scope)
        with lib.db.tx() as c:
            if not force and (sim := s.similar(f'{title} {body}')):
                return {'status': 'similar', 'candidates': sim, 'hint': 'pass into=<id> to add your evidence to one, or force=true to keep a separate insight'}
            i = c.execute('INSERT INTO insights(kind,title,body,tags,author,ts,seen) VALUES(?,?,?,?,?,?,?)',
                          (kind, title.strip(), body.strip(), dumps(tags or []), a.name, now(), now())).lastrowid
            s.add(scope, i, ev, 'support')
        with s.h.db.tx() as c: s.h.log.add(c, a.id, 'insight', f'{lib.pre}{i} [{kind}] {line(title, 100)}', 'insight', wf=a.wf)
        return s.show(lib, i) | {'status': 'saved'}

    def weigh(s, a, ref, stance='support', evidence=None, note=''):
        s.h.roles.need(a, 'post', 'weigh insights')
        if stance not in STANCES: raise Bad("stance is 'support' or 'against'")
        sc, i = s.ref(ref)
        if not (ev := s.evidence(evidence or [])):
            if not (note or '').strip(): raise Bad('give evidence refs, or a note saying what you observed')
            ev = [{'ref': f'note:{a.name}', 'text': note, 'agent': a.name, 'path': s.h.tree.path(a.id),
                   'branch': s.branch(a.id) if stance == 'against' else None}]
        s.add(sc, i, ev, stance)
        with s.h.db.tx() as c: s.h.log.add(c, a.id, 'insight.weighed', f'{stance} {ref}', 'insight', wf=a.wf)
        return s.show(s.lib(sc), i) | ({'note': 'support from a note is recorded but does not raise confidence; cite findings for that'}
                                       if stance == 'support' and not evidence else {})

    def retire(s, a, ref, reason):
        if not (s.h.roles.can(a, 'distill') or s.h.roles.can(a, 'manage')): raise Denied('only distillers and coordinators retire insights')
        if not reason.strip(): raise Bad('say why it is retired')
        sc, i = s.ref(ref)
        with s.lib(sc).db.tx() as c: c.execute("UPDATE insights SET state='retired',note=? WHERE id=?", (reason, i))
        return s.show(s.lib(sc), i, 0)

    def rank(s, query='', kind=None, state=None, scope=None):
        rows = [(lib, r) for lib, r in s.everything(scope) if (not kind or r.kind == kind) and (not state or r.state == state)]
        docs = [(lib, r, words(f"{r.title} {r.body} {' '.join(J(r.tags, []))}")) for lib, r in rows]
        q, df = words(query or ''), defaultdict(int)
        for *_, d in docs:
            for w in d: df[w] += 1
        idf = {w: math.log((len(docs)+1)/(df[w]+1))+1 for w in q}
        norm = sum(idf.values()) or 1
        scored = sorted((((sum(idf[w] for w in q & d)/norm if q else 0) + .25*r.conf + BOOST.get(r.state, 0), lib, r)
                         for lib, r, d in docs if not q or q & d), key=lambda x: -x[0])
        return [(lib, r) for _, lib, r in scored]

    def bump(s, hits):
        for lib, r in hits:
            if not lib.db.ro:
                try:
                    with lib.db.tx() as c: c.execute('UPDATE insights SET uses=uses+1 WHERE id=?', (r.id,))
                except sqlite3.Error: pass

    def recall(s, query='', kind=None, state=None, scope=None, limit=8):
        top = s.rank(query, kind, state, scope)[:limit]
        s.bump(top)
        return [s.show(lib, r.id, 2) for lib, r in top]

    def tips(s, text, limit=3):
        if not words(text): return []
        try:
            top = s.rank(text, state='established')[:limit]
            s.bump(top)
            return [f'{lib.pre}{r.id} [{r.kind}, conf {round(r.conf, 2)}] {r.title}: {line(r.body, 200)}' for lib, r in top]
        except (sqlite3.Error, OSError): return []

    def harvest(s, me, of=None, budget=3000):
        a, names = s.h.tree.at(me, of), s.h.agents.names()
        rows, kids, comps, _, _ = s.scan(a.id)
        bs = kids.get(a.id) or [a.id]
        share = max(150, budget//(len(bs)+2))
        out, terms = {'root': a.name, 'branches': []}, defaultdict(lambda: defaultdict(list))
        if (cp := comps.get(a.id)) and bs != [a.id]: out['composition'] = {'id': f'cp{cp.id}', 'text': s.fit(cp.text.splitlines(), share, f'composition of {a.name}')}
        for b in bs:
            ids = s.under(b) if b != a.id else [a.id]
            sub = s.h.db.q(f'SELECT * FROM findings WHERE agent IN ({qs(ids)}) ORDER BY id', ids)
            for f in sub:
                for w in words(f.text): terms[w][b].append(f'f{f.id}')
            e = {'branch': rows[b].name, 'goal': s.h.agents.get(b).goal, 'agents': len(ids)}
            if (bc := comps.get(b)) and b != a.id: e['composition'] = {'id': f'cp{bc.id}', 'text': s.fit(bc.text.splitlines(), share//2, f'composition of {rows[b].name}')}
            e['findings'] = s.fit([s.fline(f, names) for f in sub], share//2 if 'composition' in e else share, f'findings in the {rows[b].name} branch')
            out['branches'].append(e)
        seed = ' '.join([a.goal or '', cp.text if cp else ''] + [s.h.agents.get(b).goal or '' for b in bs])
        if echo := sorted(((len(v), w, v) for w, v in terms.items() if len(v) > 1), key=lambda x: (-x[0], x[1]))[:8]:
            out['echoes'] = [{'term': w, 'in': {rows[b].name: fs[:3] for b, fs in v.items()}} for _, w, v in echo]
        return out | {'related': [s.show(lib, r.id, 2) for lib, r in s.rank(seed)[:5]],
                      'hint': 'a pattern in two or more branches is independently corroborated: cite a finding from each; weigh related insights before distilling new ones'}
