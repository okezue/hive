from fnmatch import fnmatchcase as fm

from .err import Bad, Clash, Missing
from .util import J, dumps, hms, line, now


def peek(v): return line(v if isinstance(v, str) else dumps(v), 100)


class Board:
    def __init__(s, db, log, agents): s.db, s.log, s.agents = db, log, agents

    def scope(s, a, sc):
        if sc in (None, '', 'auto'): return f'wf:{a.wf}' if a.wf else 'session'
        if sc == 'session': return sc
        if sc == 'workflow':
            if not a.wf: raise Bad('you are not in a workflow', "use scope='session'")
            return f'wf:{a.wf}'
        raise Bad(f'invalid scope {sc!r}', 'auto, workflow, or session')

    def scopes(s, a, sc):
        x = s.scope(a, sc)
        return [x, 'session'] if sc in (None, '', 'auto') and x != 'session' else [x]

    def label(s, sc): return f"workflow {s.agents.wfNames().get(int(sc[3:]))}" if sc.startswith('wf:') else sc

    def put(s, a, key, val, sc=None, expect=None, tags=None):
        if not key or len(key) > 200: raise Bad('keys are 1-200 characters')
        x, enc = s.scope(a, sc), dumps(val)
        with s.db.tx() as c:
            r = c.execute('SELECT v,tags,agent FROM ctx WHERE scope=? AND key=?', (x, key)).fetchone()
            if expect is not None and expect != (v := r.v if r else 0):
                raise Clash(f'{key!r} is at version {v}, not {expect}', 're-read it, merge your change into the latest value, retry')
            n = c.execute('SELECT COALESCE(MAX(v),0)+1 n FROM ctxLog WHERE scope=? AND key=?', (x, key)).fetchone().n
            tg = dumps(tags) if tags is not None else r.tags if r else '[]'
            c.execute('INSERT OR REPLACE INTO ctx VALUES(?,?,?,?,?,?,?)', (x, key, enc, n, a.id, tg, now()))
            c.execute('INSERT INTO ctxLog VALUES(?,?,?,?,?,?)', (x, key, n, enc, a.id, now()))
            s.log.add(c, a.id, 'context.set', f'{key} v{n} in {s.label(x)}: {peek(val)}', f'context:{key}', wf=a.wf)
        return {'key': key, 'scope': s.label(x), 'version': n}

    def get(s, a, key, sc=None, history=0):
        names = s.agents.names()
        for x in s.scopes(a, sc):
            if r := s.db.one('SELECT * FROM ctx WHERE scope=? AND key=?', (x, key)):
                out = {'key': key, 'scope': s.label(x), 'value': J(r.val), 'version': r.v, 'author': names.get(r.agent, 'hive'),
                       'at': hms(r.ts), 'tags': J(r.tags, [])}
                if history:
                    out['history'] = [{'version': h.v, 'author': names.get(h.agent, 'hive'), 'at': hms(h.ts), 'value': J(h.val)}
                                      for h in s.db.q('SELECT * FROM ctxLog WHERE scope=? AND key=? AND v<? ORDER BY v DESC LIMIT ?',
                                                      (x, key, r.v, history))]
                return out
        raise Missing(f'no context entry {key!r}', 'keys lists what exists')

    def keys(s, a, prefix='', sc=None, tag=None):
        names = s.agents.names()
        return [{'key': r.key, 'scope': s.label(x), 'version': r.v, 'author': names.get(r.agent, 'hive'), 'at': hms(r.ts),
                 'tags': J(r.tags, []), 'preview': peek(J(r.val))}
                for x in s.scopes(a, sc) for r in s.db.q('SELECT * FROM ctx WHERE scope=? ORDER BY key', (x,))
                if (not prefix or r.key.startswith(prefix) or fm(r.key, prefix)) and (not tag or tag in J(r.tags, []))]

    def drop(s, a, key, sc=None):
        x = s.scope(a, sc)
        with s.db.tx() as c:
            if (r := c.execute('DELETE FROM ctx WHERE scope=? AND key=? RETURNING v', (x, key)).fetchone()) is None:
                raise Missing(f'no context entry {key!r} in {s.label(x)}')
            c.execute('INSERT INTO ctxLog VALUES(?,?,?,NULL,?,?)', (x, key, r.v+1, a.id, now()))
            s.log.add(c, a.id, 'context.deleted', f'deleted {key}', f'context:{key}', wf=a.wf)
        return {'key': key, 'deleted': True}
