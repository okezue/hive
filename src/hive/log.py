from fnmatch import fnmatchcase as fm

from .util import J, dumps, hms, now


class Log:
    def __init__(s, db): s.db = db

    def add(s, c, agent, kind, text, topic=None, data=None, wf=None):
        return c.execute('INSERT INTO events(ts,agent,wf,kind,topic,text,data) VALUES(?,?,?,?,?,?,?)',
                         (now(), agent, wf, kind, topic, text, None if data is None else dumps(data))).lastrowid

    def last(s): return s.db.one('SELECT COALESCE(MAX(seq),0) n FROM events').n

    def find(s, agent=None, after=None, before=None, wf=None, notBy=None, kinds=(), limit=100, desc=False):
        w, p = [], []
        for cond, v in (('agent=?', agent), ('seq>?', after), ('seq<?', before), ('wf=?', wf)):
            if v is not None: w.append(cond); p.append(v)
        if notBy is not None: w.append('(agent IS NULL OR agent!=?)'); p.append(notBy)
        if kinds: w.append(f"kind IN ({','.join('?'*len(kinds))})"); p += list(kinds)
        where = ' WHERE '+' AND '.join(w) if w else ''
        rows = s.db.q(f"SELECT * FROM events{where} ORDER BY seq {'DESC' if desc else 'ASC'} LIMIT ?", [*p, limit])
        for r in rows: r.data = J(r.data)
        return rows

    def count(s, agent): return s.db.one('SELECT COUNT(*) n FROM events WHERE agent=?', (agent,)).n

    def sub(s, c, agent, topic): c.execute('INSERT OR IGNORE INTO subs VALUES(?,?)', (agent, topic))

    def unsub(s, c, agent, topic): c.execute('DELETE FROM subs WHERE agent=? AND topic=?', (agent, topic))

    def topics(s, agent): return [r.topic for r in s.db.q('SELECT topic FROM subs WHERE agent=? ORDER BY topic', (agent,))]

    def cur(s, agent, n):
        r = s.db.one('SELECT seq FROM cursors WHERE agent=? AND name=?', (agent, n))
        return r and r.seq

    def setCur(s, c, agent, n, seq, grow=False):
        c.execute('INSERT INTO cursors VALUES(?,?,?) ON CONFLICT(agent,name) DO UPDATE SET seq='+('max(seq,excluded.seq)' if grow else 'excluded.seq'),
                  (agent, n, seq))


def fmt(e, names, who=True):
    return f"#{e.seq} {hms(e.ts)} {names.get(e.agent, 'hive')+' ' if who else ''}{e.kind}: {e.text}"


def match(pats, e, actor):
    for p in pats:
        if p.startswith('agent:'):
            if actor and fm('agent:'+actor, p): return True
        elif p.startswith('kind:'):
            if fm('kind:'+e.kind, p): return True
        elif e.topic and fm(e.topic, p): return True
    return False
