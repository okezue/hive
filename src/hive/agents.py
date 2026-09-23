from .err import Anon, Bad, Clash, Missing
from .util import J, dumps, name, now, token

STATES = ('pending', 'active', 'idle', 'done', 'left')


class Agents:
    def __init__(s, db, log, roles, stale, seed=32):
        s.db, s.log, s.roles, s.stale, s.seed, s.left = db, log, roles, stale, seed, []

    def wf(s, c, n, creator=None):
        name(n, 'workflow name')
        r = c.execute('SELECT id FROM wfs WHERE name=?', (n,)).fetchone()
        return r.id if r else c.execute('INSERT INTO wfs(name,creator,ts) VALUES(?,?,?)', (n, creator, now())).lastrowid

    def wfId(s, n):
        if (r := s.db.one('SELECT id FROM wfs WHERE name=?', (n,))) is None: raise Missing(f'no workflow {n!r}')
        return r.id

    def wfNames(s): return {r.id: r.name for r in s.db.q('SELECT id,name FROM wfs')}

    def join(s, n, role, wf=None, parent=None, about='', takeover=False):
        name(n, 'agent name')
        s.roles.get(role)
        with s.db.tx() as c:
            w = s.wf(c, wf) if wf else None
            t, ts = token(n), now()
            if old := c.execute('SELECT * FROM agents WHERE name=?', (n,)).fetchone():
                if old.state != 'left' and ts-old.seen < s.stale and not takeover:
                    raise Clash(f'an active agent is already named {n!r}',
                                'pick another name, pass its token as agent, or join with takeover if you are it restarting')
                g = old.grants and dumps(sorted(set(J(old.grants)) & s.roles.get(role).caps))
                c.execute("UPDATE agents SET role=?,token=?,wf=?,about=?,state='active',status='',task=NULL,joined=?,seen=?,grants=? "
                          "WHERE id=?", (role, t, w, about, ts, ts, g, old.id))
                aid = old.id
            else:
                p = parent and c.execute('SELECT depth FROM agents WHERE id=?', (parent,)).fetchone()
                aid = c.execute('INSERT INTO agents(name,role,token,wf,parent,keeper,depth,budget,about,joined,seen) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                                (n, role, t, w, parent, parent, p.depth+1 if p else 0, 0 if parent else s.seed, about, ts, ts)).lastrowid
            s.log.add(c, aid, 'agent.joined', f'joined as {role}' + (f' in {wf}' if wf else ''), f'agent:{n}', wf=w)
            s.log.setCur(c, aid, 'notices', s.log.last())
        return s.get(aid)

    def get(s, aid):
        if (r := s.db.one('SELECT * FROM agents WHERE id=?', (aid,))) is None: raise Missing(f'no agent {aid}')
        return r

    def named(s, n):
        if (r := s.db.one('SELECT * FROM agents WHERE name=?', (n,))) is None: raise Missing(f'no agent named {n!r}', 'overview lists everyone')
        return r

    def byToken(s, t):
        if (r := s.db.one('SELECT * FROM agents WHERE token=?', (t,))) is None:
            raise Anon('unknown agent token', 'call join for a token, then pass it as agent')
        return r

    def names(s): return {r.id: r.name for r in s.db.q('SELECT id,name FROM agents')}

    def heir(s, c, aid):
        for i in s.above(aid):
            if (r := c.execute('SELECT * FROM agents WHERE id=?', (i,)).fetchone()).state != 'left': return r
        return None

    def below(s, aid, depth=64):
        return [r.id for r in s.db.q('WITH RECURSIVE sub(id,d) AS (SELECT ?,0 UNION ALL SELECT a.id,sub.d+1 FROM agents a JOIN sub ON a.parent=sub.id '
                                     'WHERE sub.d<?) SELECT id FROM sub', (aid, depth))]

    def above(s, aid):
        return [r.id for r in s.db.q('WITH RECURSIVE up(id,p,d) AS (SELECT id,parent,0 FROM agents WHERE id=? UNION ALL SELECT a.id,a.parent,up.d+1 '
                                     'FROM agents a JOIN up ON a.id=up.p WHERE up.d<64) SELECT id FROM up ORDER BY d', (aid,))]

    def all(s, wf=None, gone=False):
        return s.db.q('SELECT * FROM agents WHERE (? IS NULL OR wf=?) AND (? OR state!=\'left\') ORDER BY id', (wf, wf, gone))

    def touch(s, a):
        with s.db.tx() as c:
            return c.execute("UPDATE agents SET seen=?,calls=calls+1,state=CASE WHEN state IN ('idle','done','pending') THEN 'active' ELSE state END "
                             "WHERE id=? RETURNING *", (now(), a.id)).fetchone()

    def set(s, c, aid, **kv):
        if aid is None: return
        if kv.get('state', 'active') not in STATES: raise Bad(f"invalid state {kv['state']!r}", ', '.join(STATES))
        if 'role' in kv: s.roles.get(kv['role'])
        c.execute(f"UPDATE agents SET {','.join(k+'=?' for k in kv)} WHERE id=?", (*kv.values(), aid))
        if kv.get('state') == 'left':
            for f in s.left: f(c, aid)

    def resolve(s, to, me):
        live = [a for a in s.all() if a.id != me.id]
        if to in ('*', 'all'): return live
        if to == 'parent': return [a for a in live if a.id == me.parent]
        if to == 'keeper': return [a for a in live if a.id == (me.keeper or me.parent)]
        if to == 'children': return [a for a in live if a.parent == me.id]
        if to == 'siblings': return [a for a in live if me.parent and a.parent == me.parent]
        if to in ('subtree', 'ancestors'):
            ids = set(s.below(me.id) if to == 'subtree' else s.above(me.id)) - {me.id}
            return [a for a in live if a.id in ids]
        if to.startswith('role:'):
            s.roles.get(to[5:])
            return [a for a in live if a.role == to[5:]]
        if to.startswith('workflow:'):
            w = s.wfId(to[9:])
            return [a for a in live if a.wf == w]
        return [s.named(to)]
