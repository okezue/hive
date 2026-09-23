from .err import Bad, Missing
from .util import J, dumps, hms, line, now

MODES = ('queue', 'steer', 'interrupt')
PRI = "CASE mode WHEN 'interrupt' THEN 0 WHEN 'steer' THEN 1 ELSE 2 END,id"


class Mail:
    def __init__(s, db, log, agents): s.db, s.log, s.agents = db, log, agents

    def put(s, c, src, dsts, body, mode='queue', kind='chat', data=None, thread=None, re=None, log=True):
        if mode not in MODES: raise Bad(f'invalid mode {mode!r}', 'queue, steer, or interrupt')
        if not body.strip(): raise Bad('empty message')
        if re is not None and thread is None:
            if (p := c.execute('SELECT id,thread FROM msgs WHERE id=?', (re,)).fetchone()) is None: raise Missing(f'no message m{re}')
            thread = p.thread or f'm{p.id}'
        dsts, ts, d = list(dict.fromkeys(dsts)), now(), None if data is None else dumps(data)
        ids = [c.execute('INSERT INTO msgs(src,dst,kind,mode,body,data,thread,re,ts) VALUES(?,?,?,?,?,?,?,?,?)',
                         (src and src.id, x, kind, mode, body, d, thread, re, ts)).lastrowid for x in dsts]
        if log and ids:
            names = s.agents.names()
            s.log.add(c, src and src.id, 'msg.'+kind, f"to {', '.join(names.get(x, '?') for x in dsts)} ({mode}): {line(body, 120)}",
                      f'thread:{thread}' if thread else None, {'ids': ids}, src and src.wf)
        return ids

    def get(s, mid):
        if (m := s.db.one('SELECT * FROM msgs WHERE id=?', (mid,))) is None: raise Missing(f'no message m{mid}')
        return m

    def _q(s, where, p): return s.db.q(f'SELECT * FROM msgs WHERE {where} ORDER BY {PRI}', p)

    def box(s, a, limit=20, read=False, peek=False):
        ms = s.db.q(f"SELECT * FROM msgs WHERE dst=?{'' if read else ' AND readAt IS NULL'} ORDER BY {PRI} LIMIT ?", (a.id, limit))
        if not peek: s.mark([m.id for m in ms if m.readAt is None])
        return ms

    def mark(s, ids):
        if ids:
            with s.db.tx() as c:
                c.executemany('UPDATE msgs SET readAt=COALESCE(readAt,?),seenAt=COALESCE(seenAt,?) WHERE id=?', [(now(), now(), i) for i in ids])

    def ack(s, a, ids=None):
        ts = now()
        with s.db.tx() as c:
            if ids is None:
                return c.execute("UPDATE msgs SET ackAt=?,readAt=COALESCE(readAt,?),seenAt=COALESCE(seenAt,?) "
                                 "WHERE dst=? AND ackAt IS NULL AND mode='interrupt'", (ts, ts, ts, a.id)).rowcount
            for i in ids:
                if not c.execute('UPDATE msgs SET ackAt=COALESCE(ackAt,?),readAt=COALESCE(readAt,?),seenAt=COALESCE(seenAt,?) '
                                 'WHERE id=? AND dst=?', (ts, ts, ts, i, a.id)).rowcount:
                    raise Missing(f'm{i} is not addressed to {a.name}')
            return len(ids)

    def urgent(s, aid): return s._q("dst=? AND mode='interrupt' AND ackAt IS NULL", (aid,))

    def steers(s, aid): return s._q("dst=? AND mode='steer' AND readAt IS NULL", (aid,))

    def unread(s, aid): return s._q('dst=? AND readAt IS NULL', (aid,))

    def queued(s, aid): return s.db.one("SELECT COUNT(*) n FROM msgs WHERE dst=? AND mode='queue' AND readAt IS NULL", (aid,)).n

    def reply(s, aid, mid, src):
        return s.db.one('SELECT * FROM msgs WHERE dst=? AND re=? AND src=? ORDER BY id LIMIT 1', (aid, mid, src))

    def thread(s, t, limit=50):
        root = int(t[1:]) if t[:1] == 'm' and t[1:].isdigit() else -1
        seen = {}
        for m in s.db.q('SELECT * FROM msgs WHERE thread=? OR id=? ORDER BY id', (t, root)): seen.setdefault((m.src, m.body, m.ts), m)
        return list(seen.values())[-limit:]


def show(m, names, full=True):
    out = {'id': f'm{m.id}', 'from': names.get(m.src, 'hive'), 'kind': m.kind, 'mode': m.mode, 'at': hms(m.ts)}
    if m.thread: out['thread'] = m.thread
    if m.re: out['re'] = f'm{m.re}'
    out['body'] = m.body if full else line(m.body, 100)
    if full and m.data: out['data'] = J(m.data)
    return out
