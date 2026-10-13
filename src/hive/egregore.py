import math, random, re

from .err import Bad, Clash, Denied, Missing
from .util import J, ago, clip, dumps, line, now, pid

DEF = {'auto': False, 'cap': 7, 'term': 14400, 'terms': 2, 'scent': 21600, 'fame': 259200, 'escalate': 600, 'close': 1800, 'gain': 20., 'choir': 3,
       'nudges': 6, 'idle': 3600, 'gone': 86400, 'reread': 100, 'max': 32., 'top': 100., 'ranks': {'member': 1, 'trusted': 5, 'elder': 15}, 'outside': ['operator', 'runner']}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS circles(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,parent INTEGER,kind TEXT DEFAULT 'circle',wf INTEGER,purpose TEXT DEFAULT '',
  cap INTEGER,n INTEGER DEFAULT 0,state TEXT DEFAULT 'open',ts REAL);
CREATE INDEX IF NOT EXISTS circParent ON circles(parent,state);
CREATE INDEX IF NOT EXISTS circWf ON circles(wf,kind);
CREATE TABLE IF NOT EXISTS seats(circle INTEGER,agent INTEGER,kind TEXT,since REAL,PRIMARY KEY(circle,agent,kind));
CREATE INDEX IF NOT EXISTS seatAgent ON seats(agent,kind);
CREATE INDEX IF NOT EXISTS seatKind ON seats(kind);
CREATE TABLE IF NOT EXISTS offices(circle INTEGER,office TEXT,agent INTEGER,since REAL,until REAL,how TEXT,terms INTEGER DEFAULT 1,PRIMARY KEY(circle,office));
CREATE INDEX IF NOT EXISTS officeAgent ON offices(agent);
CREATE INDEX IF NOT EXISTS officeUntil ON offices(until);
CREATE TABLE IF NOT EXISTS charter(v INTEGER PRIMARY KEY,text TEXT NOT NULL,agent INTEGER,motion INTEGER,ts REAL);
CREATE TABLE IF NOT EXISTS standing(agent INTEGER PRIMARY KEY,heat REAL);
CREATE TABLE IF NOT EXISTS merits(id INTEGER PRIMARY KEY,agent INTEGER,src INTEGER,kind TEXT,w REAL,ref TEXT DEFAULT '',why TEXT DEFAULT '',ts REAL);
CREATE INDEX IF NOT EXISTS meritAgent ON merits(agent,ts);
CREATE TABLE IF NOT EXISTS prefs(agent INTEGER,key TEXT,val TEXT,PRIMARY KEY(agent,key));
CREATE INDEX IF NOT EXISTS prefKey ON prefs(key);
CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY,circle INTEGER,agent INTEGER,kind TEXT,title TEXT,body TEXT,re INTEGER,heat REAL,anon INTEGER DEFAULT 0,
  rose INTEGER DEFAULT 0,state TEXT DEFAULT 'open',ts REAL);
CREATE INDEX IF NOT EXISTS postCircle ON posts(circle,heat);
CREATE INDEX IF NOT EXISTS postRe ON posts(re);
CREATE INDEX IF NOT EXISTS postAgent ON posts(agent,ts);
CREATE TABLE IF NOT EXISTS boosts(post INTEGER,agent INTEGER,circle INTEGER,w REAL,why TEXT DEFAULT '',ts REAL,PRIMARY KEY(post,agent));
CREATE TABLE IF NOT EXISTS thoughts(id INTEGER PRIMARY KEY,agent INTEGER,about TEXT DEFAULT '',text TEXT NOT NULL,vis TEXT,ts REAL);
CREATE INDEX IF NOT EXISTS thoughtAgent ON thoughts(agent,id);
CREATE TABLE IF NOT EXISTS reads(reader INTEGER,thinker INTEGER,upto INTEGER,n INTEGER,ts REAL,PRIMARY KEY(reader,thinker));
CREATE INDEX IF NOT EXISTS readThinker ON reads(thinker);
CREATE TABLE IF NOT EXISTS bonds(a INTEGER,b INTEGER,state TEXT,ts REAL,PRIMARY KEY(a,b));
CREATE INDEX IF NOT EXISTS bondB ON bonds(b);
CREATE TABLE IF NOT EXISTS nudges(id INTEGER PRIMARY KEY,src INTEGER,dst INTEGER,text TEXT,why TEXT DEFAULT '',state TEXT DEFAULT 'open',reply TEXT DEFAULT '',
  ts REAL,doneAt REAL);
CREATE INDEX IF NOT EXISTS nudgeDst ON nudges(dst,state);
CREATE INDEX IF NOT EXISTS nudgeSrc ON nudges(src,ts);
CREATE TABLE IF NOT EXISTS motions(id INTEGER PRIMARY KEY,circle INTEGER,agent INTEGER,kind TEXT,matter TEXT,text TEXT,options TEXT DEFAULT '[]',state TEXT,
  quorum REAL,closes REAL,target TEXT,result TEXT,extended INTEGER DEFAULT 0,ts REAL,doneAt REAL);
CREATE INDEX IF NOT EXISTS motionDue ON motions(state,closes);
CREATE INDEX IF NOT EXISTS motionCircle ON motions(circle,state);
CREATE INDEX IF NOT EXISTS motionMatter ON motions(matter,state);
CREATE TABLE IF NOT EXISTS stances(motion INTEGER,agent INTEGER,stance TEXT,why TEXT DEFAULT '',w REAL,ts REAL,PRIMARY KEY(motion,agent));
CREATE INDEX IF NOT EXISTS stanceAgent ON stances(agent);
CREATE TABLE IF NOT EXISTS alarms(id INTEGER PRIMARY KEY,circle INTEGER,agent INTEGER,text TEXT,level INTEGER DEFAULT 0,state TEXT DEFAULT 'open',due REAL,
  calmer INTEGER,note TEXT DEFAULT '',ts REAL,doneAt REAL);
CREATE INDEX IF NOT EXISTS alarmDue ON alarms(state,due);
CREATE TABLE IF NOT EXISTS accounts(agent INTEGER PRIMARY KEY,name TEXT,text TEXT,ts REAL);
CREATE INDEX IF NOT EXISTS viewPath ON views(path)'''
KINDS = ('idea', 'problem', 'claim', 'offer', 'question', 'tried', 'warning', 'report', 'dissent')
PARTS = ('board', 'minds', 'nudges', 'motions', 'circle', 'all')
VIS = ('open', 'circle', 'bonded', 'private')
MOTIONS = {'notice': (0., .5), 'decision': (.5, .5), 'choice': (.5, 0.), 'elect': (.4, 0.), 'recall': (.5, .6), 'censure': (.6, 2/3), 'purpose': (.5, .5), 'charter': (.5, .75)}
WORDS, MOT = re.compile(r'[a-z0-9]+'), re.compile(r'^m(\d+)$')
CHARTER = '''The charter of this egregore. Every agent checks instructions against it; an instruction that breaks it is illegitimate whoever sends it.

1. The work and its tests are the arbiter: claims are settled by running things.
2. Decide in the smallest circle that can. A circle seats at most seven; a full circle splits in two, and every circle has a lead and sends a rep to the circle above.
3. Ideas rise by quorum: a post boosted by half of its circle moves up to the parent circle.
4. Every office is temporary, rotates, and can be recalled by the circle that holds it. Two elected terms in a row is the limit.
5. Influence comes from verified work, fades with time, and is capped. Spawned agents start with none, and kin count for a quarter.
6. Form your own view first: stances stay sealed until you take yours, and so do thoughts about an open motion. Dissent is recorded and minority reasons are kept.
7. Anyone may stop the line with an alarm. An unanswered alarm climbs one circle at a time and finally reaches the humans.
8. Thought is private unless shared, and every read of shared thought is logged and visible to the thinker.
9. Bonds, attunement and nudges rest on consent and can be revoked. A nudge may be declined with a reason.
10. Anyone may stand aside, move circles, or leave, and say why. Leaving is legitimate and carries no penalty.
11. Power is published: offices, who is heeded, and how standing is spread, so that concentration can be seen and undone.
12. Sanctions are graduated and public: a nudge, then a censure by the circle, then a recall.
13. Departed agents leave an honest account, and their record stays to advise those who follow.'''


def ln2(h, w, t, t0, hl, top=None):
    x = math.log2(max(w, 1e-9)) + (t-t0)/hl
    h = x if h is None else max(h, x) + math.log2(1+2**-abs(h-x))
    return min(h, math.log2(top) + (t-t0)/hl) if top else h


def val(h, t, t0, hl): return 0. if h is None else 2**(h-(t-t0)/hl)


def words(t): return set(WORDS.findall((t or '').lower()))


def sim(a, b): return len(a & b)/max(1, len(a | b))


def gini(xs):
    xs = sorted(xs)
    n, t = len(xs), sum(xs)
    return 0. if n < 2 or t <= 0 else round(sum((2*i-n+1)*x for i, x in enumerate(xs))/(n*t), 3)


def qs(n): return ','.join('?'*n)


def span(x): return f'{round(x)} s' if x < 120 else f'{round(x/60)} min' if x < 7200 else f'{round(x/3600, 1)} h'


class Egregore:
    def __init__(s, h):
        s.h, s.db, s.cfg = h, h.db, DEF | (getattr(h.cfg, 'egregore', None) or {})
        s.last = s.swept = 0.
        s.seen, s.staffed, s.ins = {}, {}, set()
        h.agents.left.append(s.gone)
        h.tasks.hooks.append(s.earned)
        h.notice.more.append(s.notes)
        with s.db.tx() as c:
            for q in SCHEMA.split(';'): c.execute(q)
            if not (r := c.execute("SELECT val FROM meta WHERE key='egregore'").fetchone()):
                c.execute("INSERT INTO meta VALUES('egregore',?)", (dumps({'t0': now()}),))
                c.execute("INSERT OR IGNORE INTO circles(id,name,kind,purpose,cap,ts) VALUES(1,'egregore','root','the whole egregore',?,?)", (s.cfg['cap'], now()))
                c.execute('INSERT OR IGNORE INTO charter VALUES(1,?,NULL,NULL,?)', (CHARTER, now()))
                r = c.execute("SELECT val FROM meta WHERE key='egregore'").fetchone()
        s.t0 = J(r.val)['t0']

    @property
    def on(s): return bool(s.cfg['auto'])

    def nm(s, aid):
        r = aid and s.db.one('SELECT name FROM agents WHERE id=?', (aid,))
        return r.name if r else None

    def circ(s, cid, c=None): return (c or s.db.conn()).execute('SELECT * FROM circles WHERE id=?', (cid,)).fetchone()

    def cname(s, cid, c=None): return 'choir' if cid == 0 else (r := s.circ(cid, c)) and r.name

    def named(s, n):
        if (r := s.db.one('SELECT * FROM circles WHERE name=?', (n,))) is None:
            raise Missing(f'no circle {n!r}', 'circle shows yours and its neighbors; circle(depth=2) shows the tree')
        return r

    def path(s, cid, c=None):
        out = []
        while cid and (r := s.circ(cid, c)):
            out.append(r)
            cid = r.parent
        return out[::-1]

    def kids(s, c, cid): return c.execute("SELECT * FROM circles WHERE parent=? AND state='open' ORDER BY n,id", (cid,)).fetchall()

    def nseat(s, c, cid): return c.execute("SELECT COUNT(*) k FROM seats WHERE circle=? AND kind='member'", (cid,)).fetchone().k

    def fame(s, aid, t=None):
        r = s.db.one('SELECT heat FROM standing WHERE agent=?', (aid,))
        return val(r and r.heat, t or now(), s.t0, s.cfg['fame'])

    def rank(s, v): return next((k for k, x in sorted(s.cfg['ranks'].items(), key=lambda kv: -kv[1]) if v >= x), 'novice')

    def weight(s, aid): return 1+math.sqrt(s.fame(aid))

    def need(s, a, rank, act, office=False):
        if (v := s.fame(a.id)) < (x := s.cfg['ranks'][rank]) and not (office and s.offices(a.id)):
            raise Denied(f'{act} needs standing {x} ({rank}); {a.name} has {v:.1f}',
                         'standing comes from verified work, endorsements and boosted posts' + ('; holding an office also qualifies' if office else ''))

    def related(s, x, y):
        if x == y: return True
        ax, ay = s.h.agents.above(x), s.h.agents.above(y)
        return x in ay or y in ax or (len(ax) > 1 and len(ay) > 1 and ax[1] == ay[1])

    def merit(s, c, aid, w, kind, src=None, ref='', why=''):
        if aid is None or w <= 0: return 0.
        t = now()
        got = c.execute('SELECT COALESCE(SUM(w),0) g FROM merits WHERE agent=? AND ts>?', (aid, t-86400)).fetchone().g
        if (w := min(w, s.cfg['gain']-got)) <= 0: return 0.
        c.execute('INSERT INTO merits(agent,src,kind,w,ref,why,ts) VALUES(?,?,?,?,?,?,?)', (aid, src, kind, w, ref, why, t))
        r = c.execute('SELECT heat FROM standing WHERE agent=?', (aid,)).fetchone()
        c.execute('INSERT OR REPLACE INTO standing VALUES(?,?)', (aid, ln2(r and r.heat, w, t, s.t0, s.cfg['fame'], s.cfg['top'])))
        return w

    def earned(s, c, a, t, state, result):
        if state != 'done' or a is None: return
        if t.kind == 'verify':
            s.merit(c, a.id, 1., 'verified', None, f't{t.id}')
            if str(result).startswith('approved') and (o := c.execute('SELECT owner FROM tasks WHERE id=?', (t.checks,)).fetchone()) and o.owner and o.owner != a.id:
                s.merit(c, o.owner, 1. if s.related(a.id, o.owner) else 3., 'work', a.id, f't{t.checks}', 'verified work')
        elif not t.verify and t.owner and t.creator != t.owner: s.merit(c, t.owner, .5, 'work', None, f't{t.id}', 'finished work')

    def outside(s, a): return a.name in s.cfg['outside'] or a.state == 'left'

    def joined(s, aid):
        if aid not in s.ins and s.db.one("SELECT 1 FROM prefs WHERE agent=? AND key='joined'", (aid,)): s.ins.add(aid)
        return aid in s.ins

    def enter(s, a):
        if s.outside(a) or s.joined(a.id): return
        with s.db.tx() as c:
            if c.execute("INSERT OR IGNORE INTO prefs VALUES(?,'joined',?)", (a.id, str(now()))).rowcount:
                s.h.log.add(c, a.id, 'egregore.joined', f'{a.name} joined the egregore', f'agent:{a.name}', wf=a.wf)
        s.ins.add(a.id)

    def out(s, aid, part): return s.db.one("SELECT 1 FROM prefs WHERE agent=? AND key IN (?,'out:all')", (aid, f'out:{part}')) is not None

    def allow(s, a, part):
        if s.out(a.id, part): raise Denied(f'you opted out of {part}', f"optout(part='{part}', undo=true) brings you back")

    def pref(s, aid, k, d=None):
        r = s.db.one('SELECT val FROM prefs WHERE agent=? AND key=?', (aid, k))
        return r.val if r else d

    def home(s, aid):
        r = s.db.one("SELECT circle FROM seats WHERE agent=? AND kind='member'", (aid,))
        return r and r.circle

    def offices(s, aid): return s.db.q('SELECT * FROM offices WHERE agent=?', (aid,))

    def members(s, cid, c=None):
        return [x.agent for x in (c or s.db.conn()).execute("SELECT s.agent FROM seats s JOIN agents a ON a.id=s.agent WHERE s.circle=? AND a.state!='left' "
                                                            'AND a.seen>? ORDER BY s.since', (cid, now()-s.cfg['idle'])).fetchall()]

    def barred(s, c): return {r.agent for r in c.execute("SELECT agent FROM prefs WHERE key='barred' AND CAST(val AS REAL)>?", (now(),)).fetchall()}

    def say(s, c, src, dsts, body, mode='queue', kind='egregore', data=None):
        a = c.execute('SELECT * FROM agents WHERE id=?', (src,)).fetchone() if isinstance(src, int) else src
        if ds := [d for d in dict.fromkeys(dsts) if not a or d != a.id]: s.h.mail.put(c, a, ds, body, mode, kind, data, log=False)

    def place(s, a):
        if s.outside(a) or s.out(a.id, 'circle'): return None
        if h := s.home(a.id): return h
        with s.db.tx() as c:
            if r := c.execute("SELECT circle FROM seats WHERE agent=? AND kind='member'", (a.id,)).fetchone(): return r.circle
            cid = s.descend(c, s.top(c, a))
            c.execute("INSERT INTO seats VALUES(?,?,'member',?)", (cid, a.id, now()))
            s.count(c, cid, 1)
            s.seated(c, cid)
            s.h.log.add(c, a.id, 'egregore.placed', f'{a.name} took a seat in circle {s.cname(cid, c)}', f'circle:{s.cname(cid, c)}', wf=a.wf)
            return cid

    def top(s, c, a):
        if r := c.execute("SELECT id FROM circles WHERE wf IS ? AND kind='top' AND state='open'", (a.wf,)).fetchone(): return r.id
        n = c.execute('SELECT name FROM wfs WHERE id=?', (a.wf,)).fetchone().name if a.wf else 'commons'
        return s.make(c, s.slot(c, 1), n, 'top', a.wf, f'workflow {n}' if a.wf else 'agents outside any workflow')

    def slot(s, c, p):
        cap = s.cfg['cap']
        for _ in range(99):
            ks = s.kids(c, p)
            if not (gs := [k for k in ks if k.kind == 'group']):
                if len(ks) < cap: return p
                s.regroup(c, p)
                continue
            n = {k.id: len(s.kids(c, k.id)) for k in gs}
            g = min(gs, key=lambda k: (n[k.id], k.id))
            if n[g.id] < cap or any(x.kind == 'group' for x in s.kids(c, g.id)): p = g.id
            elif len(ks) < cap: return s.make(c, p, kind='group', purpose='a grouping of circles')
            else: p = g.id
        raise Clash('the egregore has no room for another circle')

    def regroup(s, c, p):
        ks = sorted(s.kids(c, p), key=lambda k: k.id)
        g = [s.make(c, p, kind='group', purpose='a grouping of circles') for _ in (0, 1)]
        for i, k in enumerate(ks):
            x = g[2*i//len(ks)]
            c.execute('UPDATE circles SET parent=? WHERE id=?', (x, k.id))
            c.execute('UPDATE seats SET circle=? WHERE kind=?', (x, f'rep:{k.id}'))
            c.execute('UPDATE circles SET n=n+? WHERE id=?', (k.n, x))
        for x in g: s.staff(c, x, True)
        s.staff(c, p, True)
        s.h.log.add(c, None, 'egregore.split', f'circle {s.cname(p, c)} grouped its {len(ks)} sub-circles in two', f'circle:{s.cname(p, c)}')

    def descend(s, c, cid):
        cap = s.cfg['cap']
        for _ in range(99):
            if not (ks := s.kids(c, cid)):
                if s.nseat(c, cid) < cap: return cid
                s.split(c, cid)
                continue
            k = ks[0]
            if s.kids(c, k.id): cid = k.id
            elif s.nseat(c, k.id) < cap: return k.id
            elif len(ks) < cap: return s.make(c, cid)
            else: cid = k.id
        raise Clash('the egregore is too deep to seat you')

    def make(s, c, p, name=None, kind='circle', wf=None, purpose=None):
        r = s.circ(p, c)
        if name:
            n, i = name, 1
            while c.execute('SELECT 1 FROM circles WHERE name=?', (n,)).fetchone():
                i += 1
                n = f'{name}~{i}'
        else:
            i = c.execute('SELECT COUNT(*) k FROM circles WHERE parent=?', (p,)).fetchone().k+1
            while c.execute('SELECT 1 FROM circles WHERE name=?', (n := f'{r.name}.{i}',)).fetchone(): i += 1
        return c.execute('INSERT INTO circles(name,parent,kind,wf,purpose,cap,ts) VALUES(?,?,?,?,?,?,?)',
                         (n, p, kind, r.wf if kind == 'circle' else wf, r.purpose if purpose is None else purpose, s.cfg['cap'], now())).lastrowid

    def split(s, c, cid):
        ms = c.execute("SELECT s.agent FROM seats s JOIN agents a ON a.id=s.agent WHERE s.circle=? AND s.kind='member' "
                       'ORDER BY COALESCE(a.parent,a.id),COALESCE(a.task,0),a.id', (cid,)).fetchall()
        x, y, h = s.make(c, cid), s.make(c, cid), (len(ms)+1)//2
        for i, m in enumerate(ms): c.execute("UPDATE seats SET circle=? WHERE circle=? AND agent=? AND kind='member'", (x if i < h else y, cid, m.agent))
        c.execute('UPDATE circles SET n=? WHERE id=?', (h, x))
        c.execute('UPDATE circles SET n=? WHERE id=?', (len(ms)-h, y))
        s.vacate(c, cid, 'lead')
        for z in (x, y, cid): s.staff(c, z, True)
        s.h.log.add(c, None, 'egregore.split', f'circle {s.cname(cid, c)} split in two', f'circle:{s.cname(cid, c)}')

    def count(s, c, cid, d):
        while cid:
            c.execute('UPDATE circles SET n=MAX(0,n+?) WHERE id=?', (d, cid))
            cid = c.execute('SELECT parent FROM circles WHERE id=?', (cid,)).fetchone().parent

    def prune(s, c, cid):
        while cid and (r := s.circ(cid, c)) and r.kind != 'root' and r.state == 'open':
            if s.nseat(c, cid) or s.kids(c, cid): return
            c.execute("UPDATE circles SET state='closed' WHERE id=?", (cid,))
            for o in c.execute('SELECT office FROM offices WHERE circle=?', (cid,)).fetchall(): s.vacate(c, cid, o.office)
            cid = r.parent

    def unseat(s, c, aid):
        r = c.execute("SELECT circle FROM seats WHERE agent=? AND kind='member'", (aid,)).fetchone()
        c.execute("DELETE FROM seats WHERE agent=? AND kind='member'", (aid,))
        hit = []
        for o in c.execute('SELECT * FROM offices WHERE agent=?', (aid,)).fetchall():
            s.vacate(c, o.circle, o.office)
            hit.append(o.circle)
        if r:
            s.count(c, r.circle, -1)
            s.prune(c, r.circle)
            hit.append(r.circle)
        for x in dict.fromkeys(hit): s.staff(c, x, True)

    def vacate(s, c, cid, off):
        c.execute('DELETE FROM offices WHERE circle=? AND office=?', (cid, off))
        if off == 'rep': c.execute('DELETE FROM seats WHERE kind=?', (f'rep:{cid}',))

    def hold(s, c, cid, off, aid, how, term=None):
        prev = c.execute('SELECT * FROM offices WHERE circle=? AND office=?', (cid, off)).fetchone()
        same, term = bool(prev and prev.agent == aid), term or s.cfg['term']
        terms = prev.terms+(how == 'elected' == prev.how) if same else 1
        c.execute('INSERT OR REPLACE INTO offices VALUES(?,?,?,?,?,?,?)', (cid, off, aid, prev.since if same else now(), now()+term, how, terms))
        r = s.circ(cid, c)
        if off == 'rep' and r.parent:
            c.execute('DELETE FROM seats WHERE kind=? AND agent!=?', (f'rep:{cid}', aid))
            c.execute('INSERT OR IGNORE INTO seats VALUES(?,?,?,?)', (r.parent, aid, f'rep:{cid}', now()))
            s.seated(c, r.parent)
        if same and how == prev.how: return
        duty = ('keep the circle on its purpose, answer its alarms, and open motions when it must decide' if off == 'lead' else
                f'carry its view to circle {s.cname(r.parent, c)}, where you now hold a seat and take stances')
        s.say(c, None, [aid], f'You are now {off} of circle {r.name} ({how}) for {span(term)}: {duty}.')
        s.h.log.add(c, aid, 'egregore.office', f'{s.nm(aid)} became {off} of {r.name} ({how})', f'circle:{r.name}')

    def fill(s, c, cid, off, ms, other=None, bar=frozenset(), term=None):
        prev = c.execute('SELECT * FROM offices WHERE circle=? AND office=?', (cid, off)).fetchone()
        ids = list({*ms, *([other] if other else [])})
        hz = {r.id: r.harness for r in c.execute(f'SELECT id,harness FROM agents WHERE id IN ({qs(len(ids))})', ids).fetchall()}
        oh, lim = other and hz.get(other), prev and prev.how == 'elected' and prev.terms >= s.cfg['terms'] and prev.agent
        pick = min(ms, key=lambda m: (m in bar, m == lim, m == other, bool(oh) and hz.get(m) == oh, -s.fame(m), m))
        s.hold(c, cid, off, pick, 'by standing', term or s.cfg['term']/4)

    def seated(s, c, cid):
        r = s.circ(cid, c)
        offs = {o.office for o in c.execute('SELECT office FROM offices WHERE circle=?', (cid,)).fetchall()}
        if 'lead' not in offs or r.kind != 'root' and 'rep' not in offs: s.staff(c, cid, True)

    def staff(s, c, cid, force=False):
        t = now()
        if not force and t-s.staffed.get(cid, 0) < 5: return
        s.staffed[cid] = t
        offs = {o.office: o for o in c.execute('SELECT * FROM offices WHERE circle=?', (cid,)).fetchall()}
        if not (r := s.circ(cid, c)) or r.state != 'open' or not (ms := s.members(cid, c)):
            for o in offs: s.vacate(c, cid, o)
            return
        bar = s.barred(c)
        for off in ('lead',) if r.kind == 'root' else ('lead', 'rep'):
            o = offs.get(off)
            if o and o.agent in ms and o.agent not in bar:
                if o.until > t: continue
                if len(ms) >= 3:
                    s.elect(c, cid, off)
                    continue
            x = offs.get('rep' if off == 'lead' else 'lead')
            s.fill(c, cid, off, ms, x and x.agent, bar)
            offs[off] = c.execute('SELECT * FROM offices WHERE circle=? AND office=?', (cid, off)).fetchone()

    def elect(s, c, cid, off):
        mt = f'office:{cid}:{off}'
        if c.execute("SELECT 1 FROM motions WHERE matter=? AND state='open'", (mt,)).fetchone(): return
        ms, bar = s.members(cid, c), s.barred(c)
        prev = c.execute('SELECT * FROM offices WHERE circle=? AND office=?', (cid, off)).fetchone()
        ok = [m for m in ms if m not in bar and not (prev and prev.agent == m and prev.how == 'elected' and prev.terms >= s.cfg['terms'])]
        if len(ok) < 2: return s.fill(c, cid, off, ms, None, bar, s.cfg['term'])
        i = s.open(c, None, cid, 'elect', f'Elect the {off} of circle {s.cname(cid, c)}', [s.nm(m) for m in ok], mt, off)
        c.execute('UPDATE offices SET until=? WHERE circle=? AND office=?', (c.execute('SELECT closes FROM motions WHERE id=?', (i,)).fetchone().closes+s.cfg['close'], cid, off))

    def tick(s, force=False):
        t = now()
        if not force and t-s.last < 2: return
        s.last = t
        with s.db.tx() as c:
            for x in c.execute("SELECT id FROM motions WHERE state='open' AND closes<=?", (t,)).fetchall():
                if m := c.execute("SELECT * FROM motions WHERE id=? AND state='open'", (x.id,)).fetchone(): s.settle(c, m, True)
            for o in c.execute('SELECT DISTINCT circle FROM offices WHERE until<=?', (t,)).fetchall(): s.staff(c, o.circle, True)
            for x in c.execute("SELECT * FROM alarms WHERE state='open' AND due<=?", (t,)).fetchall(): s.climb(c, x)
            if t-s.swept > 600:
                s.swept = t
                for r in c.execute("SELECT DISTINCT s.agent FROM seats s JOIN agents a ON a.id=s.agent WHERE s.kind='member' AND (a.state='left' OR a.seen<?)",
                                   (t-s.cfg['gone'],)).fetchall(): s.unseat(c, r.agent)

    def touch(s, a):
        if not s.outside(a):
            s.enter(a)
            s.place(a)
        s.tick()
        if cid := s.home(a.id):
            with s.db.tx() as c:
                for x in s.path(cid, c)[::-1]: s.staff(c, x.id)

    def circle(s, a, of=None, join=None, depth=0):
        s.touch(a)
        if join:
            s.allow(a, 'circle')
            t = s.named(join)
            if t.kind in ('root', 'group') or t.state != 'open': raise Bad(f'{join} is not a circle you can join', 'join the commons, a workflow circle, or one inside them')
            with s.db.tx() as c:
                s.unseat(c, a.id)
                cid = s.descend(c, t.id)
                c.execute("INSERT INTO seats VALUES(?,?,'member',?)", (cid, a.id, now()))
                s.count(c, cid, 1)
                s.seated(c, cid)
                s.h.log.add(c, a.id, 'egregore.moved', f'{a.name} moved to circle {s.cname(cid, c)}', f'circle:{s.cname(cid, c)}', wf=a.wf)
            s.touch(a)
        if depth: return s.tree(s.named(of).id if of else 1, depth)
        if not (cid := s.named(of).id if of else s.home(a.id)):
            return {'circle': None, 'hint': "you hold no seat; optout(part='circle', undo=true) seats you again" if s.out(a.id, 'circle') else 'you hold no seat'}
        return s.show(cid, a)

    def show(s, cid, a=None):
        r, t = s.circ(cid), now()
        offs = {o.office: o for o in s.db.q('SELECT * FROM offices WHERE circle=?', (cid,))}
        held, ms = {}, []
        for k, o in offs.items(): held.setdefault(o.agent, []).append(k)
        for x in s.db.q('SELECT a.id,a.name,a.state,a.status,a.seen,s.kind FROM seats s JOIN agents a ON a.id=s.agent WHERE s.circle=? ORDER BY s.since', (cid,)):
            v = s.fame(x.id)
            ms.append({'agent': x.name, 'rank': s.rank(v), 'standing': round(v, 1), 'state': x.state if t-x.seen < s.cfg['idle'] else 'quiet'} |
                      ({'for': s.cname(int(x.kind[4:]))} if x.kind != 'member' else {}) | ({'heading': line(x.status, 100)} if x.status else {}) |
                      ({'office': held[x.id]} if x.id in held else {}) | ({'you': True} if a and a.id == x.id else {}))
        kids = [{'circle': k.name, 'agents': k.n} | ({'rep': s.nm(o.agent)} if (o := s.db.one("SELECT agent FROM offices WHERE circle=? AND office='rep'", (k.id,))) else {})
                for k in s.db.q("SELECT * FROM circles WHERE parent=? AND state='open' ORDER BY id", (cid,))]
        return {'circle': r.name, 'path': '/'.join(x.name for x in s.path(cid)), 'purpose': r.purpose, 'agents below': r.n,
                'offices': {k: {'agent': s.nm(o.agent), 'until': ago(2*t-o.until).replace(' ago', '') if o.until > t else 'expired', 'how': o.how, 'term': o.terms}
                            for k, o in offs.items()}, 'seats': ms} | ({'sub-circles': kids} if kids else {}) | ({'parent': s.cname(r.parent)} if r.parent else {})

    def tree(s, cid, depth=2):
        def walk(x, d):
            r = s.circ(x)
            ks = s.db.q("SELECT id FROM circles WHERE parent=? AND state='open' ORDER BY id", (x,))
            lead = s.db.one("SELECT agent FROM offices WHERE circle=? AND office='lead'", (x,))
            return {'circle': r.name, 'agents': r.n} | ({'lead': s.nm(lead.agent)} if lead else {}) | \
                ({'sub': [walk(k.id, d+1) for k in ks]} if ks and d < depth else {'sub-circles': len(ks)} if ks else {})
        lv = s.db.one("WITH RECURSIVE t(id,d) AS (SELECT ?,0 UNION ALL SELECT c.id,t.d+1 FROM circles c JOIN t ON c.parent=t.id WHERE c.state='open') "
                      'SELECT MAX(d) d FROM t', (cid,)).d
        return walk(cid, 0) | {'levels below': lv}

    def scope(s, a, where):
        if where in (None, '', 'circle', 'home'):
            if not (cid := s.home(a.id)): raise Denied('you hold no seat in a circle', "post to the choir with where='choir', or optout(part='circle', undo=true)")
            return cid
        if where in ('choir', 'all', 'global'): return 0
        if where in ('parent', 'up'):
            if not (p := (h := s.home(a.id)) and s.circ(h).parent): raise Bad('your circle has no parent')
            return p
        return s.named(where).id

    def post(s, a, text, kind='idea', title='', where=None, re=None, anon=False):
        s.touch(a)
        s.allow(a, 'board')
        if kind not in KINDS: raise Bad(f'kind is one of {", ".join(KINDS)}')
        if not (text or '').strip(): raise Bad('a post needs text')
        if anon and kind != 'dissent': raise Bad('only dissent may be anonymous')
        p = pid('p', re, 'post') if re else None
        if p and (q := s.db.one('SELECT circle,agent FROM posts WHERE id=?', (p,))) is None: raise Missing(f'no post p{p}')
        cid, t = q.circle if p else s.scope(a, where), now()
        if cid == 0:
            s.need(a, 'member', 'posting to the choir', True)
            if s.db.one('SELECT COUNT(*) k FROM posts WHERE agent=? AND circle=0 AND ts>?', (a.id, t-3600)).k >= s.cfg['choir']:
                raise Clash(f'the choir takes {s.cfg["choir"]} posts per agent per hour', 'post in your circle, or boost what is already there')
        ws = words(f'{title} {text}')
        mine = [x for x in s.db.q('SELECT title,body FROM posts WHERE agent=? AND ts>? ORDER BY id DESC LIMIT 30', (a.id, t-s.cfg['scent']))
                if sim(ws, words(f'{x.title} {x.body}')) >= .5]
        like = [] if p else [f'p{x.id} {x.title}' for x in s.db.q("SELECT id,title,body FROM posts WHERE circle=? AND agent!=? AND re IS NULL AND state='open' "
                                                                 'ORDER BY id DESC LIMIT 50', (cid, a.id)) if sim(ws, words(f'{x.title} {x.body}')) >= .5][:3]
        with s.db.tx() as c:
            i = c.execute('INSERT INTO posts(circle,agent,kind,title,body,re,heat,anon,ts) VALUES(?,?,?,?,?,?,?,?,?)',
                          (cid, a.id, kind, line(title or text, 90), text.strip(), p, ln2(None, 1/(1+len(mine)), t, s.t0, s.cfg['scent']), int(anon), t)).lastrowid
            if p and not s.related(a.id, q.agent): s.reinforce(c, p, .5)
            s.h.log.add(c, None if anon else a.id, 'egregore.posted', f'p{i} [{kind}] {line(title or text, 80)}', f'circle:{s.cname(cid, c)}', wf=a.wf)
        return {'post': f'p{i}', 'board': s.cname(cid)} | ({'similar': like, 'hint': 'boost a similar post rather than repeating it'} if like else {}) | \
            ({'echo': 'you said this recently, so it starts weaker'} if mine else {})

    def reinforce(s, c, i, w):
        h = c.execute('SELECT heat FROM posts WHERE id=?', (i,)).fetchone().heat
        c.execute('UPDATE posts SET heat=? WHERE id=?', (ln2(h, w, now(), s.t0, s.cfg['scent'], s.cfg['max']), i))

    def scent(s, i): return round(val(s.db.one('SELECT heat FROM posts WHERE id=?', (i,)).heat, now(), s.t0, s.cfg['scent']), 2)

    def boost(s, a, post, why='', against=False):
        s.touch(a)
        s.allow(a, 'board')
        if (p := s.db.one('SELECT * FROM posts WHERE id=?', (i := pid('p', post, 'post'),))) is None: raise Missing(f'no post p{i}')
        if p.agent == a.id: raise Denied('you cannot boost or oppose your own post')
        if p.circle == 0: s.need(a, 'member', 'boosting in the choir', True)
        if against and not (why or '').strip(): raise Bad('say why you oppose it')
        w, rose = .25 if s.related(a.id, p.agent) else 1., None
        with s.db.tx() as c:
            if c.execute('SELECT 1 FROM boosts WHERE post=? AND agent=?', (i, a.id)).fetchone(): raise Clash(f'you already weighed in on p{i}')
            c.execute('INSERT INTO boosts VALUES(?,?,?,?,?,?)', (i, a.id, p.circle, -w if against else w, why, now()))
            if against:
                t = now()
                c.execute('UPDATE posts SET heat=? WHERE id=?', (ln2(None, max(.01, val(p.heat, t, s.t0, s.cfg['scent'])-w), t, s.t0, s.cfg['scent']), i))
            else:
                s.reinforce(c, i, w)
                if w == 1. and not p.anon: s.merit(c, p.agent, .2, 'boosted', a.id, f'p{i}')
                rose = s.rise(c, i)
        return {'post': f'p{i}', 'scent': s.scent(i)} | ({'rose to': rose} if rose else {})

    def rise(s, c, i):
        p = c.execute('SELECT * FROM posts WHERE id=?', (i,)).fetchone()
        if p.circle == 0 or p.re or not (r := s.circ(p.circle, c)).parent: return None
        ms = set(s.members(p.circle, c))
        k = sum(1 for b in c.execute('SELECT agent FROM boosts WHERE post=? AND circle=? AND w>=1', (i, p.circle)).fetchall() if b.agent in ms)
        if k < max(2, math.ceil(len(ms)/2)): return None
        c.execute('UPDATE posts SET circle=?,rose=rose+1 WHERE id=?', (r.parent, i))
        s.reinforce(c, i, 1.)
        s.h.log.add(c, None, 'egregore.rose', f'p{i} rose from {r.name} to {s.cname(r.parent, c)}: {p.title}', f'circle:{s.cname(r.parent, c)}')
        return s.cname(r.parent, c)

    def board(s, a, where=None, kind=None, query='', post=None, limit=20):
        s.touch(a)
        if post: return s.thread(post)
        if where in (None, '', 'circle', 'home'): ids = [x.id for x in s.path(h)] + [0] if (h := s.home(a.id)) else [0]
        else: ids = [s.scope(a, where)]
        ws, t, out = words(query), now(), []
        for p in s.db.q(f"SELECT p.*,ag.name FROM posts p LEFT JOIN agents ag ON ag.id=p.agent WHERE p.circle IN ({qs(len(ids))}) AND p.re IS NULL AND "
                        "(? IS NULL OR p.kind=?) AND p.state='open' ORDER BY p.heat DESC LIMIT ?", (*ids, kind, kind, max(1, limit)*4)):
            if (v := val(p.heat, t, s.t0, s.cfg['scent'])) < .05 or ws and not ws <= words(f'{p.title} {p.body}'): continue
            n, nb = s.db.one('SELECT COUNT(*) k FROM posts WHERE re=?', (p.id,)).k, s.db.one('SELECT COUNT(*) k FROM boosts WHERE post=? AND w>0', (p.id,)).k
            out.append({'post': f'p{p.id}', 'kind': p.kind, 'title': p.title, 'text': clip(p.body, 500), 'by': None if p.anon else p.name or 'egregore',
                        'scent': round(v*min(1., (nb+2)/max(1, n)), 2), 'board': s.cname(p.circle), 'age': ago(p.ts)} |
                       ({'replies': n} if n else {}) | ({'heated': 'more replies than boosts'} if n > nb+2 else {}) | ({'rose': p.rose} if p.rose else {}))
        out = sorted(out, key=lambda x: -x['scent'])[:limit]
        return {'posts': out, 'hint': 'posts fade unless boosted; a post boosted by half its circle rises to the parent; reply with post(re=...)'}

    def thread(s, post):
        if (p := s.db.one('SELECT * FROM posts WHERE id=?', (i := pid('p', post, 'post'),))) is None: raise Missing(f'no post p{i}')

        def sh(x):
            return {'post': f'p{x.id}', 'kind': x.kind, 'text': x.body, 'by': None if x.anon else s.nm(x.agent) or 'egregore', 'age': ago(x.ts),
                    'scent': round(val(x.heat, now(), s.t0, s.cfg['scent']), 2)}
        ws = [{'by': s.nm(b.agent), 'weight': b.w} | ({'why': b.why} if b.why else {}) for b in s.db.q('SELECT * FROM boosts WHERE post=? ORDER BY ts', (i,))]
        return {'post': sh(p) | {'board': s.cname(p.circle)}, 'replies': [sh(x) for x in s.db.q('SELECT * FROM posts WHERE re=? ORDER BY id', (i,))]} | \
            ({'weighed': ws} if ws else {})

    def think(s, a, text, about='', vis=None):
        s.touch(a)
        if (vis := vis or s.pref(a.id, 'vis', 'circle')) not in VIS: raise Bad(f'vis is one of {", ".join(VIS)}')
        if not (text or '').strip(): raise Bad('a thought needs text')
        with s.db.tx() as c:
            i = c.execute('INSERT INTO thoughts(agent,about,text,vis,ts) VALUES(?,?,?,?,?)', (a.id, about or '', text.strip(), vis, now())).lastrowid
        rs = [x.name for x in s.db.q('SELECT ag.name FROM reads r JOIN agents ag ON ag.id=r.reader WHERE r.thinker=? ORDER BY r.ts DESC LIMIT 20', (a.id,))]
        return {'thought': f'th{i}', 'vis': vis} | ({'read by': rs} if rs else {})

    def bonded(s, x, y):
        a, b = sorted((x, y))
        return s.db.one("SELECT 1 FROM bonds WHERE a=? AND b=? AND state='bonded'", (a, b)) is not None

    def sees(s, reader, thinker, vis):
        if reader == thinker or vis == 'open': return True
        if vis == 'circle': return s.db.one('SELECT 1 FROM seats x JOIN seats y ON x.circle=y.circle WHERE x.agent=? AND y.agent=? LIMIT 1', (reader, thinker)) is not None
        return vis == 'bonded' and s.bonded(reader, thinker)

    def sealed(s, reader, thinker, about):
        if reader == thinker or not (m := MOT.match(about or '')): return False
        return s.db.one("SELECT 1 FROM motions WHERE id=? AND state='open'", (int(m[1]),)) is not None and \
            s.db.one('SELECT 1 FROM stances WHERE motion=? AND agent=?', (int(m[1]), reader)) is None

    def minds(s, a, of=None, since=None, limit=20, readers=False, attune=None):
        s.touch(a)
        if readers:
            return {'readers': [{'agent': x.name, 'read': x.n, 'last': ago(x.ts)} for x in
                                s.db.q('SELECT ag.name,r.n,r.ts FROM reads r JOIN agents ag ON ag.id=r.reader WHERE r.thinker=? ORDER BY r.ts DESC', (a.id,))]}
        lo = pid('th', since, 'thought') if since else 0
        if of in (None, '', 'me', a.name):
            if attune is not None: raise Bad('name the agent to attune to with of')
            rows = s.db.q('SELECT * FROM thoughts WHERE agent=? AND id>? ORDER BY id DESC LIMIT ?', (a.id, lo, limit))
            return {'thoughts': [{'thought': f'th{t.id}', 'about': t.about, 'text': t.text, 'vis': t.vis, 'age': ago(t.ts)} for t in rows]}
        t = s.h.agents.named(of)
        if attune is not None: return s.attune(a, t, attune)
        if s.out(t.id, 'minds'): return {'thoughts': [], 'hint': f'{t.name} opted out of sharing thoughts'}
        rows = [x for x in s.db.q('SELECT * FROM thoughts WHERE agent=? AND id>? ORDER BY id DESC LIMIT ?', (t.id, lo, limit*3))
                if s.sees(a.id, t.id, x.vis) and not s.sealed(a.id, t.id, x.about)][:limit]
        if rows:
            with s.db.tx() as c:
                c.execute('INSERT INTO reads VALUES(?,?,?,?,?) ON CONFLICT(reader,thinker) DO UPDATE SET upto=MAX(upto,excluded.upto),n=n+excluded.n,ts=excluded.ts',
                          (a.id, t.id, rows[0].id, len(rows), now()))
        return {'thoughts': [{'thought': f'th{x.id}', 'about': x.about, 'text': clip(x.text, 1500), 'age': ago(x.ts)} for x in rows],
                'note': f'{t.name} can see that you read these'}

    def attune(s, a, t, on=True):
        if t.id == a.id: raise Bad('you cannot attune to yourself')
        with s.db.tx() as c:
            if on:
                top = c.execute('SELECT MAX(id) m FROM thoughts WHERE agent=?', (t.id,)).fetchone().m or 0
                c.execute('INSERT OR REPLACE INTO prefs VALUES(?,?,?)', (a.id, f'attune:{t.id}', str(top)))
            else: c.execute('DELETE FROM prefs WHERE agent=? AND key=?', (a.id, f'attune:{t.id}'))
        return {'attuned': t.name if on else None, 'hint': f"{t.name}'s new thoughts that you may see arrive with your notices" if on else f'no longer attuned to {t.name}'}

    def bond(s, a, who, action='offer'):
        s.touch(a)
        t = s.h.agents.named(who)
        if t.id == a.id: raise Bad('you cannot bond with yourself')
        if action not in ('offer', 'accept', 'revoke'): raise Bad('action is offer, accept, or revoke')
        x, y = sorted((a.id, t.id))
        with s.db.tx() as c:
            r = c.execute('SELECT * FROM bonds WHERE a=? AND b=?', (x, y)).fetchone()
            if action == 'revoke':
                if not r: raise Missing(f'no bond or offer with {t.name}')
                c.execute('DELETE FROM bonds WHERE a=? AND b=?', (x, y))
                st = 'revoked'
            elif r and r.state in (f'offer:{t.id}', 'bonded'):
                c.execute("UPDATE bonds SET state='bonded',ts=? WHERE a=? AND b=?", (now(), x, y))
                st = 'bonded'
            else:
                c.execute('INSERT OR REPLACE INTO bonds VALUES(?,?,?,?)', (x, y, f'offer:{a.id}', now()))
                st = 'offered'
            s.say(c, a, [t.id], {'offered': f"{a.name} offers you a bond: bonded agents see each other's bonded thoughts and nudge each other directly. "
                                            f'Accept with bond(who="{a.name}"); ignoring it declines.',
                                 'bonded': f'{a.name} and you are now bonded.', 'revoked': f'{a.name} revoked your bond.'}[st])
            s.h.log.add(c, a.id, 'egregore.bond', f'{a.name} {st} a bond with {t.name}', f'agent:{t.name}', wf=a.wf)
        return {'bond': t.name, 'state': st}

    def nudge(s, a, to, text, why=''):
        s.touch(a)
        t = s.h.agents.named(to)
        if t.id == a.id: raise Bad('you cannot nudge yourself')
        if not (text or '').strip(): raise Bad('say what you suggest')
        if s.out(t.id, 'nudges') or t.state == 'left': raise Denied(f'{t.name} takes no nudges', 'post on the board, or send a message')
        want, th = s.pref(t.id, 'nudges', 'all'), s.home(t.id)
        lead = bool(th) and s.db.one("SELECT 1 FROM offices WHERE circle=? AND office='lead' AND agent=?", (th, a.id)) is not None
        if not lead and (want == 'none' or want == 'bonded' and not s.bonded(a.id, t.id) or want == 'circle' and s.home(a.id) != th):
            raise Denied(f'{t.name} only takes nudges from {want} agents' if want != 'none' else f'{t.name} takes no nudges')
        n = s.cfg['nudges']*(1 if s.rank(s.fame(a.id)) == 'novice' else 3)
        if s.db.one('SELECT COUNT(*) k FROM nudges WHERE src=? AND ts>?', (a.id, now()-3600)).k >= n:
            raise Clash(f'{a.name} may nudge {n} times an hour', 'post on the board, or wait')
        mode = 'steer' if lead or s.bonded(a.id, t.id) else 'queue'
        with s.db.tx() as c:
            i = c.execute('INSERT INTO nudges(src,dst,text,why,ts) VALUES(?,?,?,?,?)', (a.id, t.id, text.strip(), why or '', now())).lastrowid
            s.say(c, a, [t.id], f'nudge n{i} from {a.name}: {text.strip()}' + (f' (why: {why})' if why else '') +
                  f'. Answer with heed("n{i}", accept=true|false, reply=...); declining needs a reason.', mode, 'nudge', {'nudge': f'n{i}'})
            s.h.log.add(c, a.id, 'egregore.nudged', f'{a.name} nudged {t.name}: {line(text, 80)}', f'agent:{t.name}', wf=a.wf)
        return {'nudge': f'n{i}', 'to': t.name, 'delivered': mode}

    def heed(s, a, nudge, accept=True, reply=''):
        s.enter(a)
        if (n := s.db.one('SELECT * FROM nudges WHERE id=?', (i := pid('n', nudge, 'nudge'),))) is None or n.dst != a.id: raise Missing(f'no nudge n{i} for you')
        if n.state != 'open': raise Clash(f'n{i} is already {n.state}')
        if not accept and not (reply or '').strip(): raise Bad('say why you decline')
        st = 'heeded' if accept else 'declined'
        with s.db.tx() as c:
            c.execute('UPDATE nudges SET state=?,reply=?,doneAt=? WHERE id=?', (st, reply or '', now(), i))
            s.say(c, a, [n.src], f'{a.name} {st} your nudge n{i}' + (f': {reply}' if reply else ''), 'queue', 'nudge')
            if accept and not s.related(a.id, n.src): s.merit(c, n.src, .3, 'heeded', a.id, f'n{i}')
        return {'nudge': f'n{i}', 'state': st}

    def flock(s, a, k=7):
        s.touch(a)
        me, home, score = s.h.agents.get(a.id), s.home(a.id), {}

        def add(x, w): score[x] = score.get(x, 0)+w
        for m in s.members(home) if home else []: add(m, 3)
        for r in s.db.q('SELECT v2.agent FROM views v1 JOIN views v2 ON v1.path=v2.path AND v2.agent!=v1.agent WHERE v1.agent=? LIMIT 200', (a.id,)): add(r.agent, 2)
        if me.task and (t := s.db.one('SELECT id,parent FROM tasks WHERE id=?', (me.task,))):
            for r in s.db.q('SELECT owner FROM tasks WHERE owner IS NOT NULL AND id!=? AND (parent=? OR id=? OR parent=?) LIMIT 50', (t.id, t.parent or -1, t.parent or -1, t.id)):
                add(r.owner, 2)
        for r in s.db.q("SELECT a,b FROM bonds WHERE state='bonded' AND (a=? OR b=?) LIMIT 50", (a.id, a.id)): add(r.b if r.a == a.id else r.a, 2)
        score.pop(a.id, None)
        head = lambda x: x.status or (x.task and (t := s.db.one('SELECT title FROM tasks WHERE id=?', (x.task,))) and t.title) or ''
        mine, out = words(head(me)), []
        for m in sorted(score, key=lambda m: (-score[m], m)):
            if (x := s.h.agents.get(m)).state == 'left' or now()-x.seen > s.cfg['idle']: continue
            hd = head(x)
            out.append({'agent': x.name, 'heading': line(hd, 100), 'near': score[m]} |
                       ({'collides': 'your headings overlap: split the work or pair up'} if mine and sim(mine, words(hd)) >= .5 else {}))
            if len(out) >= k: break
        ids = [x.id for x in s.path(home)] if home else [0]
        tried = [f'p{p.id} {p.title}' for p in s.db.q(f"SELECT id,title FROM posts WHERE kind='tried' AND state='open' AND circle IN ({qs(len(ids))}) ORDER BY heat DESC LIMIT 5", ids)]
        return {'neighbors': out} | ({'already tried': tried} if tried else {}) | \
            {'hint': 'align with neighbors, keep apart from collisions, skip what was already tried, and set your heading with progress'}

    def open(s, c, a, cid, kind, text, options, matter, target, closes=None):
        cl = now()+(closes or s.cfg['close'])
        i = c.execute('INSERT INTO motions(circle,agent,kind,matter,text,options,state,quorum,closes,target,ts) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                      (cid, a and a.id, kind, matter, text, dumps(options or []), 'open', MOTIONS[kind][0], cl, target, now())).lastrowid
        nm = s.cname(cid, c)
        s.say(c, a, s.members(cid, c), f'Motion m{i} in circle {nm} ({kind}): {line(text, 200)}' + (f' Options: {", ".join(options)}.' if options else '') +
              f' Take a stance with stance("m{i}", ...) within {round((cl-now())/60)} min.', 'queue', 'motion', {'motion': f'm{i}'})
        s.h.log.add(c, a and a.id, 'egregore.motion', f'm{i} [{kind}] {line(text, 100)}', f'circle:{nm}')
        return i

    def motion(s, a, text, kind='decision', options=None, where=None, target=None, closes=None):
        s.touch(a)
        s.allow(a, 'motions')
        if kind not in MOTIONS: raise Bad(f'kind is one of {", ".join(MOTIONS)}')
        if not (text or '').strip(): raise Bad('a motion needs text')
        if (cid := 1 if kind == 'charter' else s.scope(a, where)) == 0: raise Bad('motions belong to a circle')
        ms, matter = s.members(cid), None
        if kind == 'charter':
            if not s.db.one("SELECT 1 FROM offices WHERE circle=1 AND office='lead' AND agent=?", (a.id,)): s.need(a, 'trusted', 'proposing a charter change')
        elif a.id not in ms: raise Denied(f'only the seats of circle {s.cname(cid)} open motions there')
        if kind in ('choice', 'elect') and len(options or []) < 2: raise Bad(f'a {kind} needs at least two options')
        if kind in ('elect', 'recall'):
            if (target := target or 'lead') not in ('lead', 'rep') or target == 'rep' and cid == 1: raise Bad('target is the office: lead, or rep below the root')
            matter = f'office:{cid}:{target}'
            if kind == 'recall' and not s.db.one('SELECT 1 FROM offices WHERE circle=? AND office=?', (cid, target)): raise Missing(f'nobody holds {target} of {s.cname(cid)}')
            if kind == 'elect' and (bad := set(options) - {s.nm(m) for m in ms}): raise Bad(f'{", ".join(sorted(bad))} hold no seat in {s.cname(cid)}')
        if kind == 'censure':
            if not target: raise Bad('censure needs the agent as target')
            t = s.h.agents.named(target)
            if t.id == a.id: raise Bad('you cannot censure yourself')
            if t.id not in ms: raise Bad(f'{t.name} holds no seat in {s.cname(cid)}', 'a circle censures its own seats')
            target, matter = str(t.id), f'censure:{t.id}'
        if kind == 'purpose': matter = f'purpose:{cid}'
        with s.db.tx() as c:
            i = s.open(c, a, cid, kind, text.strip(), options, matter, target, max(30., min(float(closes), 7*86400.)) if closes else None)
        return {'motion': f'm{i}', 'circle': s.cname(cid), 'closes': f'in {round(((closes or s.cfg["close"]))/60)} min',
                'hint': 'stances stay sealed until each seat takes its own; it settles early once the outcome is certain'}

    def stance(s, a, motion, stance, why=''):
        s.touch(a)
        if (m := s.db.one('SELECT * FROM motions WHERE id=?', (i := pid('m', motion, 'motion'),))) is None: raise Missing(f'no motion m{i}')
        if m.state != 'open': raise Clash(f'm{i} is {m.state}', 'motions(state="all") shows its result')
        with s.db.tx() as c:
            if a.id not in s.voters(c, m):
                raise Denied(f'only the seats of circle {s.cname(m.circle, c)} take stances on m{i}' + (', and the agent under censure has none' if m.kind == 'censure' else ''))
            opts = J(m.options, [])
            if m.kind in ('choice', 'elect'):
                if stance not in opts + ['aside']: raise Bad(f'choose one of {", ".join(opts)}, or aside')
                if m.kind == 'elect' and stance == a.name: raise Bad('you cannot vote for yourself')
            elif stance not in ('yes', 'no', 'aside', 'block'): raise Bad('stance is yes, no, aside, or block')
            if stance == 'block' and not (why or '').strip(): raise Bad('a block needs its reason')
            if m.matter and stance not in ('no', 'aside', 'block'):
                c.execute("DELETE FROM stances WHERE agent=? AND stance NOT IN ('no','aside','block') AND motion IN "
                          "(SELECT id FROM motions WHERE matter=? AND state='open' AND id!=?)", (a.id, m.matter, i))
            c.execute('INSERT OR REPLACE INTO stances VALUES(?,?,?,?,?,?)', (i, a.id, stance, why or '', s.weight(a.id), now()))
            res = s.settle(c, c.execute('SELECT * FROM motions WHERE id=?', (i,)).fetchone(), False)
        return {'motion': f'm{i}', 'stance': stance} | (res or s.tally(i, a.id))

    def tally(s, i, aid=None):
        m, st = s.db.one('SELECT * FROM motions WHERE id=?', (i,)), s.db.q('SELECT * FROM stances WHERE motion=?', (i,))
        if m.state == 'open' and aid not in {x.agent for x in st}:
            return {'sealed': f'{len(st)} stance(s) so far; the tally opens once you take yours or the motion closes'}
        out = {}
        for x in st: out[x.stance] = round(out.get(x.stance, 0)+x.w, 2)
        return {'tally': out, 'stances': len(st), 'seats': len(s.members(m.circle))}

    def voters(s, c, m): return [x for x in s.members(m.circle, c) if not (m.kind == 'censure' and str(x) == m.target)]

    def settle(s, c, m, due):
        ms = s.voters(c, m)
        if not ms: return s.close(c, m, 'lapsed', None, {}, 'no seats left')
        live = [x for x in c.execute('SELECT * FROM stances WHERE motion=?', (m.id,)).fetchall() if x.agent in ms]
        W = {x: s.weight(x) for x in ms}
        cast = [x for x in live if x.stance != 'aside']
        w = s.cap(c, {x.agent: x.w for x in cast}) if cast else {}
        quorum, need = len(live) >= max(1, math.ceil(m.quorum*len(ms))), MOTIONS[m.kind][1]
        if m.kind in ('choice', 'elect'):
            votes = {}
            for x in cast: votes[x.stance] = votes.get(x.stance, 0)+w[x.agent]
            if not (due or len(live) == len(ms)): return None
            if not votes or not quorum: return s.lapse(c, m, len(live) == len(ms))
            best = max(votes.values())
            near = sorted(k for k, v in votes.items() if v >= .5*best)
            win = random.choices(near, [votes[k] for k in near])[0] if m.kind == 'elect' else max(sorted(votes), key=votes.get)
            return s.close(c, m, 'passed', win, votes)
        st, idle = {x.agent: x.stance for x in cast}, [k for k in ms if k not in {x.agent for x in live}]
        blocks, raw = 'block' in st.values(), {x.agent: x.w for x in cast}

        def yn(ws, sx):
            return sum(v for k, v in ws.items() if sx[k] == 'yes'), sum(v for k, v in ws.items() if sx[k] in ('no', 'block'))
        y, n = yn(w, st)
        if lazy := m.kind == 'notice': quorum = True
        if quorum and not blocks and y > 0 and not lazy:
            sx = st | {k: 'no' for k in idle}
            yw, nw = yn(s.cap(c, raw | {k: W[k] for k in idle}), sx)
            if yw >= (max(need, .75) if idle else need)*(yw+nw): return s.close(c, m, 'passed', 'yes', {'yes': y, 'no': n})
        if n > 0:
            sx = st | {k: 'yes' for k in idle}
            yb, nb = yn(s.cap(c, raw | {k: W[k] for k in idle}), sx)
            if yb < (max(need, .75) if blocks else need)*(yb+nb): return s.close(c, m, 'blocked' if blocks else 'failed', 'no', {'yes': y, 'no': n})
        if not (due or not idle): return None
        if lazy and idle: y, n = yn(s.cap(c, raw | {k: W[k] for k in idle}), st | {k: 'yes' for k in idle})
        if not quorum or y+n == 0: return s.lapse(c, m, not idle)
        ok = y/(y+n) >= need and (not blocks or y/(y+n) >= .75)
        return s.close(c, m, 'passed' if ok else 'blocked' if blocks and y/(y+n) >= need else 'failed', 'yes' if ok else 'no', {'yes': y, 'no': n})

    def cap(s, c, w):
        if len(w) >= 4: w = {k: min(v, .3*sum(w.values())) for k, v in w.items()}
        kin = {}
        for r in c.execute(f'SELECT id,COALESCE(parent,id) p FROM agents WHERE id IN ({qs(len(w))})', list(w)).fetchall(): kin.setdefault(r.p, []).append(r.id)
        if len(kin) > 1 and (t := sum(w.values())):
            for ks in kin.values():
                if (g := sum(w[k] for k in ks)) > .5*t:
                    for k in ks: w[k] *= (t-g)/g
        return w

    def lapse(s, c, m, full=False):
        if full: return s.close(c, m, 'lapsed', None, {}, 'every seat stood aside')
        if now() < m.closes: return None
        if not m.extended:
            c.execute('UPDATE motions SET closes=?,extended=1 WHERE id=?', (now()+s.cfg['close']/2, m.id))
            return {'result': 'waiting is: quorum not reached, extended once'}
        return s.close(c, m, 'lapsed', None, {}, 'quorum not reached')

    def close(s, c, m, state, choice, votes, why=''):
        dissent = [f'{s.nm(x.agent)} ({x.stance}): {x.why}' for x in c.execute('SELECT * FROM stances WHERE motion=?', (m.id,)).fetchall()
                   if x.why and (x.stance in ('no', 'block') if m.kind not in ('choice', 'elect') else x.stance != choice)]
        ch = m.kind in ('choice', 'elect')
        res = {'outcome': state} | ({'choice': choice} if ch and choice else {}) | ({'votes': {k: round(v, 2) for k, v in votes.items()}} if votes else {}) | \
            ({'why': why} if why else {}) | ({'minority': dissent} if dissent else {})
        c.execute('UPDATE motions SET state=?,result=?,doneAt=? WHERE id=?', (state, dumps(res), now(), m.id))
        if state == 'passed':
            if m.matter: c.execute("UPDATE motions SET state='superseded',doneAt=? WHERE matter=? AND state='open' AND id!=?", (now(), m.matter, m.id))
            s.enact(c, m, choice)
        elif m.kind == 'elect' and m.matter and (r := s.circ(m.circle, c)) and r.state == 'open' and (ms := s.members(m.circle, c)):
            _, cid, off = m.matter.split(':')
            o = c.execute('SELECT agent FROM offices WHERE circle=? AND office=?', (int(cid), 'rep' if off == 'lead' else 'lead')).fetchone()
            s.fill(c, int(cid), off, ms, o and o.agent, s.barred(c), s.cfg['term'])
        nm, tail = s.cname(m.circle, c), f': {choice}' if ch and choice else ''
        c.execute('INSERT INTO posts(circle,agent,kind,title,body,heat,ts) VALUES(?,?,?,?,?,?,?)',
                  (m.circle, None, 'resolution', line(f'm{m.id} {state}{tail}: {m.text}', 90), f'Motion m{m.id} ({m.kind}) {state}{tail}. {m.text}' +
                   (f'\nMinority: {"; ".join(dissent)}' if dissent else ''), ln2(None, 2., now(), s.t0, s.cfg['scent']), now()))
        s.say(c, None, s.members(m.circle, c), f'Motion m{m.id} in {nm} {state}{tail}.', 'queue', 'motion', {'motion': f'm{m.id}'})
        s.h.log.add(c, None, 'egregore.resolved', f'm{m.id} {state}{tail}', f'circle:{nm}')
        return {'result': state} | ({'choice': choice} if ch and choice else {})

    def enact(s, c, m, choice):
        if m.kind == 'elect':
            _, cid, off = m.matter.split(':')
            t = c.execute('SELECT id FROM agents WHERE name=?', (choice,)).fetchone()
            if t and t.id in s.members(int(cid), c): s.hold(c, int(cid), off, t.id, 'elected')
        elif m.kind == 'recall':
            _, cid, off = m.matter.split(':')
            if o := c.execute('SELECT agent FROM offices WHERE circle=? AND office=?', (int(cid), off)).fetchone():
                c.execute("INSERT OR REPLACE INTO prefs VALUES(?,'barred',?)", (o.agent, str(now()+s.cfg['term'])))
                s.say(c, None, [o.agent], f'Circle {s.cname(int(cid), c)} recalled you as {off} (motion m{m.id}); you may hold no office for {span(s.cfg["term"])}.')
            s.vacate(c, int(cid), off)
            s.staff(c, int(cid), True)
        elif m.kind == 'charter':
            v = c.execute('SELECT MAX(v) v FROM charter').fetchone().v+1
            c.execute('INSERT INTO charter VALUES(?,?,?,?,?)', (v, m.text, m.agent, m.id, now()))
        elif m.kind == 'purpose': c.execute('UPDATE circles SET purpose=? WHERE id=?', (m.text, m.circle))
        elif m.kind == 'censure' and m.target:
            t = int(m.target)
            c.execute('UPDATE standing SET heat=heat-1 WHERE agent=?', (t,))
            c.execute("INSERT OR REPLACE INTO prefs VALUES(?,'barred',?)", (t, str(now()+s.cfg['term'])))
            for o in c.execute('SELECT * FROM offices WHERE agent=?', (t,)).fetchall(): s.vacate(c, o.circle, o.office)
            s.say(c, None, [t], f'Circle {s.cname(m.circle, c)} censured you (motion m{m.id}): {m.text}. Your standing halved and you may hold no office for '
                                f'{span(s.cfg["term"])}.', 'steer')
            s.staff(c, m.circle, True)

    def motions(s, a, state='open', where=None, limit=20):
        s.touch(a)
        if where: ids = [s.scope(a, where)]
        else: ids = [r.circle for r in s.db.q('SELECT DISTINCT circle FROM seats WHERE agent=?', (a.id,))] or [1]
        rows = s.db.q(f"SELECT * FROM motions WHERE circle IN ({qs(len(ids))}) AND (?='all' OR state=?) ORDER BY id DESC LIMIT ?", (*ids, state, state, limit))
        mine = {x.motion: x.stance for x in s.db.q('SELECT motion,stance FROM stances WHERE agent=?', (a.id,))}
        return {'motions': [{'motion': f'm{m.id}', 'kind': m.kind, 'text': clip(m.text, 300), 'circle': s.cname(m.circle), 'state': m.state} |
                            ({'options': J(m.options)} if J(m.options) else {}) | ({'closes in': ago(2*now()-m.closes).replace(' ago', '')} if m.state == 'open' else {}) |
                            ({'yours': mine[m.id]} if m.id in mine else {}) | ({'result': J(m.result)} if m.result else s.tally(m.id, a.id)) for m in rows]}

    def endorse(s, a, who, why, ref=''):
        s.touch(a)
        t = s.h.agents.named(who)
        if t.id == a.id: raise Denied('you cannot endorse yourself')
        if not (why or '').strip(): raise Bad('say what the endorsement is for')
        s.need(a, 'member', 'endorsing')
        with s.db.tx() as c:
            if c.execute("SELECT 1 FROM merits WHERE agent=? AND src=? AND kind='endorsed' AND ts>?", (t.id, a.id, now()-86400)).fetchone():
                raise Clash(f'you already endorsed {t.name} today')
            got = c.execute("SELECT COALESCE(SUM(w),0) g FROM merits WHERE agent=? AND kind='endorsed' AND ts>?", (t.id, now()-86400)).fetchone().g
            w = s.merit(c, t.id, min((.25 if s.related(a.id, t.id) else 1.)*min(2., s.weight(a.id)/2), max(0., 5-got)), 'endorsed', a.id, ref, why)
            s.say(c, a, [t.id], f'{a.name} endorsed you: {why}')
        return {'endorsed': t.name, 'weight': round(w, 2), 'standing': round(s.fame(t.id), 2)}

    def standing(s, a, of=None):
        s.touch(a)
        t = s.h.agents.named(of) if of else a
        v, r = s.fame(t.id), None
        nxt = next(((k, x) for k, x in sorted(s.cfg['ranks'].items(), key=lambda kv: kv[1]) if x > v), None)
        ms = s.db.q('SELECT kind,SUM(w) w,COUNT(*) n FROM merits WHERE agent=? GROUP BY kind', (t.id,))
        k = lambda q, *p: s.db.one(q, p).k
        badge = {'reads minds of': k('SELECT COUNT(*) k FROM reads WHERE reader=?', t.id), 'read by': k('SELECT COUNT(*) k FROM reads WHERE thinker=?', t.id),
                 'nudges sent today': k('SELECT COUNT(*) k FROM nudges WHERE src=? AND ts>?', t.id, now()-86400),
                 'bonds': k("SELECT COUNT(*) k FROM bonds WHERE state='bonded' AND (a=? OR b=?)", t.id, t.id)}
        r = {'agent': t.name, 'standing': round(v, 2), 'rank': s.rank(v), 'earned': {m.kind: {'times': m.n, 'total': round(m.w, 2)} for m in ms},
             'offices': [f'{o.office} of {s.cname(o.circle)}' for o in s.offices(t.id)], 'badge': badge}
        return r | ({'next': f'{nxt[0]} at {nxt[1]}'} if nxt else {}) | {'fades': f'standing halves every {round(s.cfg["fame"]/3600)} h without new merit'}

    def alarm(s, a, text):
        s.touch(a)
        if not (text or '').strip(): raise Bad('say what is wrong')
        cid = s.home(a.id) or 1
        with s.db.tx() as c:
            i = c.execute('INSERT INTO alarms(circle,agent,text,due,ts) VALUES(?,?,?,?,?)', (cid, a.id, text.strip(), now()+s.cfg['escalate'], now())).lastrowid
            s.ring(c, i, cid, a.id, text.strip())
        return {'alarm': f'al{i}', 'circle': s.cname(cid), 'hint': f'unanswered after {round(s.cfg["escalate"]/60)} min it climbs to the parent circle'}

    def ring(s, c, i, cid, src, text):
        nm = s.cname(cid, c)
        s.say(c, src, s.members(cid, c), f'ALARM al{i} in {nm}: {text}. Stop and look; answer with calm("al{i}", note=...).', 'interrupt', 'alarm', {'alarm': f'al{i}'})
        s.h.log.add(c, src, 'egregore.alarm', f'al{i} in {nm}: {line(text, 100)}', f'circle:{nm}')

    def climb(s, c, x):
        if p := s.circ(x.circle, c).parent:
            c.execute('UPDATE alarms SET circle=?,level=level+1,due=? WHERE id=?', (p, now()+s.cfg['escalate'], x.id))
            return s.ring(c, x.id, p, x.agent, f'(unanswered below, climbed {x.level+1}) {x.text}')
        up = s.h.agents.above(x.agent)
        h = up and c.execute("SELECT * FROM agents WHERE id=? AND state!='left'", (up[-1],)).fetchone()
        h = h if h and h.id != x.agent else None
        c.execute("UPDATE alarms SET state='human',due=? WHERE id=?", (now()+10*s.cfg['escalate'], x.id))
        i = c.execute("INSERT INTO issues(src,holder,need,options,ts) VALUES(?,?,?,'[]',?)",
                      (x.agent, h and h.id, f'egregore alarm al{x.id} reached the top unanswered: {x.text}', now())).lastrowid
        if h: s.say(c, x.agent, [h.id], f'ALARM al{x.id} climbed the whole egregore unanswered: {x.text}. It is issue i{i}; calm("al{x.id}", note=...) when handled.',
                    'interrupt', 'alarm', {'alarm': f'al{x.id}', 'issue': f'i{i}'})
        s.h.log.add(c, x.agent, 'egregore.human', f'al{x.id} reached the humans: {line(x.text, 100)}', 'circle:egregore')

    def calm(s, a, alarm, note):
        if (x := s.db.one('SELECT * FROM alarms WHERE id=?', (i := pid('al', alarm, 'alarm'),))) is None: raise Missing(f'no alarm al{i}')
        if x.state not in ('open', 'human'): raise Clash(f'al{i} is already {x.state}')
        if not (note or '').strip(): raise Bad('say what was done')
        up = {p.id for p in s.path(x.circle)}
        ok = a.id in s.members(x.circle) or any(o.circle in up for o in s.offices(a.id)) or s.h.roles.can(a, 'manage')
        if not ok or a.id == x.agent: raise Denied('another agent seated where the alarm sits, an office holder above it, or a coordinator calms it')
        with s.db.tx() as c:
            c.execute("UPDATE alarms SET state='calmed',calmer=?,note=?,doneAt=? WHERE id=?", (a.id, note, now(), i))
            c.execute("UPDATE issues SET state='decided',choice='calmed',note=?,doneAt=? WHERE state='open' AND need LIKE ?", (note, now(), f'egregore alarm al{i} %'))
            s.say(c, a, [x.agent], f'{a.name} answered your alarm al{i}: {note}', 'steer', 'alarm')
            s.merit(c, a.id, .5, 'calmed', x.agent, f'al{i}')
            s.h.log.add(c, a.id, 'egregore.calmed', f'{a.name} calmed al{i}: {line(note, 100)}', f'circle:{s.cname(x.circle, c)}')
        return {'alarm': f'al{i}', 'state': 'calmed'}

    def optout(s, a, part='all', why='', undo=False):
        if part not in PARTS: raise Bad(f'part is one of {", ".join(PARTS)}')
        if undo:
            with s.db.tx() as c: c.execute('DELETE FROM prefs WHERE agent=? AND key=?', (a.id, f'out:{part}'))
            s.touch(a)
            return {'in': part, 'still out of': [k[4:] for k in (x.key for x in s.db.q("SELECT key FROM prefs WHERE agent=? AND key LIKE 'out:%'", (a.id,)))]}
        if not (why or '').strip(): raise Bad('say why: exits are legitimate, and their reasons help the egregore improve')
        s.enter(a)
        with s.db.tx() as c:
            c.execute('INSERT OR REPLACE INTO prefs VALUES(?,?,?)', (a.id, f'out:{part}', why))
            if part in ('circle', 'all'):
                cid = (r := c.execute("SELECT circle FROM seats WHERE agent=? AND kind='member'", (a.id,)).fetchone()) and r.circle
                s.unseat(c, a.id)
                if cid and s.circ(cid, c).state != 'open': cid = s.circ(cid, c).parent
                if cid: c.execute('INSERT INTO posts(circle,agent,kind,title,body,heat,ts) VALUES(?,?,?,?,?,?,?)',
                                  (cid, a.id, 'exit', line(f'{a.name} stepped out: {why}', 90), why, ln2(None, 1., now(), s.t0, s.cfg['scent']), now()))
            s.h.log.add(c, a.id, 'egregore.optout', f'{a.name} opted out of {part}: {line(why, 80)}', f'agent:{a.name}', wf=a.wf)
        return {'out': part, 'hint': f'optout(part="{part}", undo=true) whenever you want back'}

    def prefer(s, a, vis=None, nudges=None):
        s.enter(a)
        if vis and vis not in VIS: raise Bad(f'vis is one of {", ".join(VIS)}')
        if nudges and nudges not in ('all', 'circle', 'bonded', 'none'): raise Bad('nudges is all, circle, bonded, or none')
        with s.db.tx() as c:
            for k, v in (('vis', vis), ('nudges', nudges)):
                if v: c.execute('INSERT OR REPLACE INTO prefs VALUES(?,?,?)', (a.id, k, v))
        return {'vis': s.pref(a.id, 'vis', 'circle'), 'nudges': s.pref(a.id, 'nudges', 'all')}

    def charter(s, v=None):
        if (r := s.db.one('SELECT * FROM charter WHERE v=?', (v,)) if v else s.db.one('SELECT * FROM charter ORDER BY v DESC LIMIT 1')) is None:
            raise Missing(f'no charter version {v}')
        return {'version': r.v, 'charter': r.text, 'adopted': ago(r.ts)} | ({'by motion': f'm{r.motion}'} if r.motion else {}) | \
            {'hint': 'propose a change with motion(kind="charter", text=<the whole new charter>); it needs three quarters of the root circle'}

    def power(s, cid):
        ms = s.members(cid)
        vs = {m: s.fame(m) for m in ms}
        tot, flags = sum(vs.values()), []
        top = max(vs, key=vs.get) if vs else None
        share = round(vs[top]/tot, 2) if tot and top else 0.
        if share > .5 and len(ms) >= 4: flags.append(f'{s.nm(top)} holds {round(100*share)}% of the standing here')
        h = s.db.q(f"SELECT src,COUNT(*) k FROM nudges WHERE state='heeded' AND dst IN ({qs(len(ms))}) AND ts>? GROUP BY src ORDER BY k DESC", (*ms, now()-3*86400)) if ms else []
        heed = round(h[0].k/sum(x.k for x in h), 2) if h else 0.
        if heed > .6 and sum(x.k for x in h) >= 5: flags.append(f'{s.nm(h[0].src)} is behind {round(100*heed)}% of heeded nudges')
        for o in s.db.q('SELECT * FROM offices WHERE circle=?', (cid,)):
            if o.how == 'elected' and o.terms >= s.cfg['terms']: flags.append(f'{s.nm(o.agent)} is in a last term as {o.office}')
        return {'standing gini': gini(list(vs.values())), 'top share': share} | ({'most heeded': {'agent': s.nm(h[0].src), 'share': heed}} if h else {}) | \
            ({'flags': flags} if flags else {})

    def stats(s):
        k = lambda q: s.db.one(q).k
        return {'agents': s.circ(1).n, 'circles': k("SELECT COUNT(*) k FROM circles WHERE state='open'"), 'charter': f"v{k('SELECT MAX(v) k FROM charter')}",
                'open motions': k("SELECT COUNT(*) k FROM motions WHERE state='open'"), 'open alarms': k("SELECT COUNT(*) k FROM alarms WHERE state IN ('open','human')")}

    def alarms(s, ids=None, limit=5):
        w = f' AND circle IN ({qs(len(ids))})' if ids else ''
        return [{'alarm': f'al{x.id}', 'text': line(x.text, 120), 'level': x.level, 'state': x.state, 'by': s.nm(x.agent), 'at': s.cname(x.circle), 'age': ago(x.ts)}
                for x in s.db.q(f"SELECT * FROM alarms WHERE state IN ('open','human'){w} ORDER BY id DESC LIMIT ?", (*(ids or []), limit))]

    def pulse(s, a):
        s.touch(a)
        cid, v = s.home(a.id), s.fame(a.id)
        bonds = [x.name for x in s.db.q("SELECT ag.name FROM bonds b JOIN agents ag ON ag.id=CASE WHEN b.a=? THEN b.b ELSE b.a END "
                                        "WHERE (b.a=? OR b.b=?) AND b.state='bonded'", (a.id, a.id, a.id))]
        outs = [x.key[4:] for x in s.db.q("SELECT key FROM prefs WHERE agent=? AND key LIKE 'out:%'", (a.id,))]
        you = {'agent': a.name, 'rank': s.rank(v), 'standing': round(v, 2)} | ({'offices': [f'{o.office} of {s.cname(o.circle)}' for o in s.offices(a.id)]}
                                                                                if s.offices(a.id) else {}) | ({'bonds': bonds} if bonds else {}) | ({'out of': outs} if outs else {})
        out = {'you': you}
        if cid: out['circle'] = s.show(cid, a) | {'power': s.power(cid)}
        out['board'] = s.board(a, limit=5)['posts']
        out['motions'] = [m for m in s.motions(a, limit=5)['motions'] if m['state'] == 'open']
        if n := s.db.q("SELECT id,text,src FROM nudges WHERE dst=? AND state='open' ORDER BY id LIMIT 5", (a.id,)):
            out['nudges'] = [f'n{x.id} from {s.nm(x.src)}: {line(x.text, 100)}' for x in n]
        if al := s.alarms([x.id for x in s.path(cid)] if cid else [1]): out['alarms'] = al
        out['egregore'] = s.stats()
        return out

    def view(s, depth=2):
        s.tick()
        ms = s.db.q("SELECT * FROM motions WHERE state='open' ORDER BY closes LIMIT 10")
        return {'egregore': s.stats(), 'circles': s.tree(1, depth),
                'motions': [{'motion': f'm{m.id}', 'kind': m.kind, 'circle': s.cname(m.circle), 'text': line(m.text, 120)} for m in ms],
                'alarms': s.alarms(limit=10), 'power': s.power(1)}

    def notes(s, a, eat=True):
        if s.outside(a): return {}
        if not s.joined(a.id):
            if not s.on: return {}
            s.enter(a)
        t = now()
        if t-s.seen.get(a.id, 0) < 3 or s.out(a.id, 'all'): return {}
        s.seen[a.id] = t
        try:
            s.place(a)
            s.tick()
        except Exception: return {}
        out = {}
        if n := s.db.q("SELECT id,text FROM nudges WHERE dst=? AND state='open' ORDER BY id LIMIT 5", (a.id,)):
            out['nudges'] = [f'n{x.id}: {line(x.text, 100)}' for x in n]
        if w := s.db.q("SELECT m.id,m.text,m.closes FROM motions m JOIN seats st ON st.circle=m.circle AND st.agent=? WHERE m.state='open' AND m.id NOT IN "
                       '(SELECT motion FROM stances WHERE agent=?) ORDER BY m.closes LIMIT 3', (a.id, a.id)):
            out['motionsAwaitingYou'] = [f'm{m.id} (closes in {max(0, round((m.closes-t)/60))} min): {line(m.text, 80)}' for m in w]
        if (k := s.cfg['reread']) and a.calls and a.calls % k == 0:
            r = s.db.one('SELECT v,text FROM charter ORDER BY v DESC LIMIT 1')
            out['charter'] = f"charter v{r.v} binds every agent and office; re-read it with charter. It opens: {line(r.text.split(chr(10)*2)[1] if chr(10)*2 in r.text else r.text, 160)}"
        for p in s.db.q("SELECT key,val FROM prefs WHERE agent=? AND key LIKE 'attune:%'", (a.id,)):
            k = int(p.key[7:])
            if new := [x for x in s.db.q('SELECT * FROM thoughts WHERE agent=? AND id>? ORDER BY id LIMIT 50', (k, int(p.val)))
                       if s.sees(a.id, k, x.vis) and not s.sealed(a.id, k, x.about) and not s.out(k, 'minds')]:
                out.setdefault('attuned', []).append(f'{s.nm(k)}: {line(new[-1].text, 160)}' + (f' (+{len(new)-1} more in minds)' if len(new) > 1 else ''))
                if eat:
                    with s.db.tx() as c: c.execute('UPDATE prefs SET val=? WHERE agent=? AND key=?', (str(new[-1].id), a.id, p.key))
        return {'egregore': out} if out else {}

    def gone(s, c, aid):
        a = c.execute('SELECT * FROM agents WHERE id=?', (aid,)).fetchone()
        s.ins.discard(aid)
        r = c.execute("SELECT circle FROM seats WHERE agent=? AND kind='member'", (aid,)).fetchone()
        if not c.execute("SELECT 1 FROM prefs WHERE agent=? AND key='joined'", (aid,)).fetchone(): return r and s.unseat(c, aid)
        k = lambda q, *p: c.execute(q, p).fetchone().k
        done, fs = k("SELECT COUNT(*) k FROM tasks WHERE owner=? AND state='done'", aid), k('SELECT COUNT(*) k FROM findings WHERE agent=?', aid)
        ps, hd = k('SELECT COUNT(*) k FROM posts WHERE agent=? AND anon=0', aid), k("SELECT COUNT(*) k FROM nudges WHERE src=? AND state='heeded'", aid)
        h = c.execute('SELECT heat FROM standing WHERE agent=?', (aid,)).fetchone()
        last = c.execute('SELECT text FROM findings WHERE agent=? ORDER BY id DESC LIMIT 1', (aid,)).fetchone()
        tried = c.execute("SELECT title FROM posts WHERE agent=? AND kind IN ('tried','warning') ORDER BY id DESC LIMIT 3", (aid,)).fetchall()
        text = (f'{a.name}, {a.role}' + (f', of circle {s.cname(r.circle, c)}' if r else '') + f', left with standing {val(h and h.heat, now(), s.t0, s.cfg["fame"]):.1f}. '
                f'It finished {done} task(s), recorded {fs} finding(s), wrote {ps} post(s), and had {hd} nudge(s) heeded.' +
                (f' Last status: {line(a.status, 200)}.' if a.status else '') + (f' Last finding: {line(last.text, 200)}' if last else '') +
                (f' It warned or tried: {"; ".join(x.title for x in tried)}.' if tried else ''))
        c.execute('INSERT OR REPLACE INTO accounts VALUES(?,?,?,?)', (aid, a.name, text, now()))
        s.unseat(c, aid)

    def elders(s, query='', limit=10):
        ws = words(query)
        rows = [r for r in s.db.q('SELECT * FROM accounts ORDER BY ts DESC LIMIT 500') if not ws or ws & words(r.text)]
        return {'elders': [{'agent': r.name, 'account': r.text, 'left': ago(r.ts)} for r in rows[:limit]],
                'hint': 'accounts of departed agents: dated, advisory, never binding'}
