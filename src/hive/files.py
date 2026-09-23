from fnmatch import fnmatchcase as fm

from .err import Bad, Clash, Missing
from .merge import Diff, NoMatch, apply, lines, merge, say
from .mr import Mrs
from .util import J, ago, an, dumps, now, sha

NOISY = ('committed', 'merged', 'overwritten')
PEND = 300


class Files:
    def __init__(s, db, log, mail, agents, roles, disk):
        s.db, s.log, s.mail, s.agents, s.roles, s.disk = db, log, mail, agents, roles, disk
        s.mrs = Mrs(s)

    def head(s, c, p):
        return c.execute('SELECT v.* FROM files f JOIN vers v ON v.path=f.path AND v.v=f.head WHERE f.path=?', (p,)).fetchone()

    def body(s, c, p, v):
        if (r := c.execute('SELECT body FROM vers WHERE path=? AND v=?', (p, v)).fetchone()) is None: raise Missing(f'{p} has no version {v}')
        return r.body

    def view(s, c, aid, p):
        r = c.execute('SELECT v FROM views WHERE agent=? AND path=?', (aid, p)).fetchone()
        return r and r.v

    def see(s, c, aid, p, v, pend=None):
        c.execute('INSERT OR REPLACE INTO views VALUES(?,?,?,?,?)', (aid, p, v, now(), pend))
        s.log.sub(c, aid, f'file:{p}')

    def after(s, c, p, lo, hi=1 << 62):
        return c.execute('SELECT v,agent,origin,what,ts FROM vers WHERE path=? AND v>? AND v<=? ORDER BY v', (p, lo, hi)).fetchall()

    def desc(s, c, p, lo, hi, skip=None):
        names = s.agents.names()
        return [{'version': r.v, 'author': names.get(r.agent, 'outside Hive'), 'changed': r.what}
                for r in s.after(c, p, lo, hi) if skip is None or r.agent != skip]

    def commit(s, c, aid, p, text, origin, prev, wf=None):
        if prev and text == prev.body:
            if aid: s.see(c, aid, p, prev.v)
            return {'path': p, 'version': prev.v, 'status': 'unchanged'}
        v, d, ts = (prev.v if prev else 0)+1, Diff(prev.body if prev else '', text), now()
        what = say(d.spans()) if prev else f'created ({len(d.b)} lines)'
        c.execute('INSERT INTO vers VALUES(?,?,?,?,?,?,?,?)', (p, v, text, sha(text), aid, origin, what, ts))
        c.execute('INSERT OR REPLACE INTO files VALUES(?,?,?)', (p, v, ts))
        s.disk.write(p, text)
        if aid: s.see(c, aid, p, v)
        warn = s.claimsHit(c, aid, p, d) if prev else []
        quiet = not prev and not aid
        s.log.add(c, aid, 'file.changed' if prev else 'file.tracked' if quiet else 'file.created', f'{p} v{v} ({origin}): {what}',
                  None if quiet else f'file:{p}', {'path': p, 'version': v, 'origin': origin, 'diff': d.text(60) if prev else ''}, wf)
        out = {'path': p, 'version': v, 'changed': what}
        if warn: out['warnings'] = warn
        return out

    def track(s, c, p):
        s.adopt(c, p)
        if (h := s.head(c, p)) is None: raise Missing(f'{p} does not exist', 'use write to create it')
        return h

    def adopt(s, c, p, a=None, origin='external'):
        disk, h = s.disk.read(p), s.head(c, p)
        if a is None and (r := c.execute('SELECT agent FROM views WHERE path=? AND pend>? ORDER BY pend DESC LIMIT 1', (p, now()-PEND)).fetchone()):
            a, origin = s.agents.get(r.agent), 'sync'
        if a: c.execute('UPDATE views SET pend=NULL WHERE agent=? AND path=?', (a.id, p))
        aid, wf = (a.id, a.wf) if a else (None, None)
        if h is None:
            return None if disk is None else {**s.commit(c, aid, p, disk, origin if a else 'tracked', None), 'status': 'tracked'}
        if disk is None or sha(disk) == h.sha: return None
        b = s.base(c, p, h, disk, a)
        if b == h.v: return {'status': 'committed', **s.commit(c, aid, p, disk, origin, h, wf)}
        m = merge(s.body(c, p, b), disk, h.body)
        if m.clean and m.text() == h.body:
            s.disk.write(p, h.body)
            return None
        if m.clean:
            return {'status': 'merged', **s.commit(c, aid, p, m.text(), origin+'+merge', h, wf), 'mergedWith': s.desc(c, p, b, h.v, aid),
                    'note': f'based on v{b}; merged with the newer changes and rewritten on disk'}
        if a is None:
            return {**s.commit(c, None, p, disk, 'external-overwrite', h), 'status': 'overwritten',
                    'warning': f'an outside edit replaced changes made after v{b}; older versions remain in diff'}
        s.disk.write(p, h.body)
        out = s.mrs.open(c, a, p, b, h, disk, m)
        out['note'] = f"it conflicts with newer changes; the file on disk was restored to v{h.v} and your version waits in {out['mr']}"
        return out

    def base(s, c, p, h, disk, a):
        vs, mine = {r.v for r in c.execute('SELECT v FROM vers WHERE path=? AND v>?', (p, h.v-8))}, a and s.view(c, a.id, p)
        if mine: vs.add(mine)
        # ties go to what the author last saw, then to the newest version
        b = min(vs, key=lambda v: (Diff(s.body(c, p, v), disk).size(), v != mine, -v))
        # never let "closest to head" hide an overlap with changes the author has not seen
        return mine if b == h.v and mine and mine < h.v and not merge(s.body(c, p, mine), disk, h.body).clean else b

    def claimsHit(s, c, aid, p, d):
        c.execute('DELETE FROM claims WHERE until<?', (now(),))
        warn, names, sp = [], s.agents.names(), d.spans()
        for k in c.execute('SELECT * FROM claims WHERE path=?', (p,)).fetchall():
            hit = [r for r in sp if r['oldStart'] <= k.hi and max(r['oldEnd'], r['oldStart']) >= k.lo]
            if hit and k.agent != aid:
                w = f'lines {k.lo}-{k.hi}'
                warn.append(f"you changed {p} inside {names.get(k.agent)}'s claimed region {w} ({k.note})")
                if aid:
                    s.mail.put(c, s.agents.get(aid), [k.agent], f'{names.get(aid)} changed {p} inside your claimed region {w}: '
                               f'{say(hit)}. Check it fits your plan.', 'steer', 'claim', {'path': p})
            c.execute('UPDATE claims SET lo=?,hi=? WHERE id=?', (*d.remap(k.lo, k.hi), k.id))
        return warn

    def scope(s, c, a, p):
        if not a.task: return None
        pats = J(c.execute('SELECT paths FROM tasks WHERE id=?', (a.task,)).fetchone().paths, [])
        if not pats or any(fm(p, x) for x in pats): return None
        s.log.add(c, a.id, 'scope.warning', f'edited {p}, outside t{a.task} paths', f'task:t{a.task}', wf=a.wf)
        return f"{p} is outside the paths of your task t{a.task} ({', '.join(pats)}); stay in your assignment or tell the task owner why"

    def others(s, c, a, p):
        names, out = s.agents.names(), {}
        if vw := c.execute("SELECT w.agent,w.v,a.role,a.seen FROM views w JOIN agents a ON a.id=w.agent "
                           "WHERE w.path=? AND w.agent!=? AND a.state!='left'", (p, a.id)).fetchall():
            out['openBy'] = [{'agent': names[x.agent], 'role': x.role, 'at': x.v, 'seen': ago(x.seen)} for x in vw]
        if ks := c.execute('SELECT * FROM claims WHERE path=? AND agent!=? AND until>=?', (p, a.id, now())).fetchall():
            out['claims'] = [{'agent': names.get(k.agent), 'lines': f'{k.lo}-{k.hi}', 'note': k.note} for k in ks]
        return out

    def blocked(s, c, a, p):
        if mr := s.mrs.blocking(c, a.id, p):
            raise Clash(f'your earlier change to {p} waits in merge request mr{mr.id}',
                        f"settle it first: merges('mr{mr.id}'), talk to the other author in thread mr{mr.id}, then propose or abandon")

    def finish(s, c, a, p, out, warn):
        if warn: out.setdefault('warnings', []).append(warn)
        return out | s.others(c, a, p)

    def onto(s, c, a, p, b, text, h, origin):
        if b == h.v: return {'status': 'applied', **s.commit(c, a.id, p, text, origin, h, a.wf)}
        if not 1 <= b < h.v: raise Bad(f'{p} has no version {b}; the head is v{h.v}')
        m = merge(s.body(c, p, b), text, h.body)
        if m.clean:
            return {'status': 'merged', **s.commit(c, a.id, p, m.text(), origin+'+merge', h, a.wf), 'mergedWith': s.desc(c, p, b, h.v, a.id)}
        return s.mrs.open(c, a, p, b, h, text, m)

    def read(s, a, p, start=None, end=None):
        s.roles.need(a, 'read', 'read files')
        p = s.disk.norm(p)
        with s.db.tx() as c:
            ad = s.adopt(c, p)
            if (h := s.head(c, p)) is None: raise Missing(f'{p} does not exist', 'use write to create it')
            prev = s.view(c, a.id, p)
            s.see(c, a.id, p, h.v)
            s.log.add(c, a.id, 'file.read', f'read {p} v{h.v}', wf=a.wf)
            ls = lines(h.body)
            out = {'path': p, 'version': h.v, 'lines': len(ls)}
            if start or end:
                lo, hi = max(1, start or 1), min(len(ls), end or len(ls))
                out |= {'start': lo, 'end': hi, 'content': ''.join(ls[lo-1:hi])}
            else: out['content'] = h.body
            if prev and prev < h.v: out['changedSince'] = s.desc(c, p, prev, h.v, a.id)
            if ad and ad['status'] in NOISY: out['outside'] = ad.get('warning') or f"adopted an outside edit as v{ad['version']}"
            return out | s.others(c, a, p)

    def write(s, a, p, text, base=None):
        s.roles.need(a, 'write', 'write files')
        p = s.disk.norm(p)
        if not isinstance(text, str): raise Bad('content must be a string')
        with s.db.tx() as c:
            s.blocked(c, a, p)
            s.adopt(c, p)
            h, warn = s.head(c, p), s.scope(c, a, p)
            if h is None: return s.finish(c, a, p, {**s.commit(c, a.id, p, text, 'write', None, a.wf), 'status': 'created'}, warn)
            if (b := base if base is not None else s.view(c, a.id, p)) is None:
                raise Clash(f'you have not read {p}, so Hive cannot tell which changes are yours',
                            f'read it first, or pass base={h.v} to replace v{h.v} on purpose')
            return s.finish(c, a, p, s.onto(c, a, p, b, text, h, 'write'), warn)

    def edit(s, a, p, edits, base=None):
        s.roles.need(a, 'write', 'edit files')
        p = s.disk.norm(p)
        if not edits: raise Bad('no edits')
        with s.db.tx() as c:
            s.blocked(c, a, p)
            s.adopt(c, p)
            if (h := s.head(c, p)) is None: raise Missing(f'{p} does not exist', 'use write to create it')
            warn, b = s.scope(c, a, p), base if base is not None else s.view(c, a.id, p)
            try: new = apply(h.body, edits)
            except NoMatch:
                if b is None or b >= h.v: raise
                try: mine = apply(s.body(c, p, b), edits)
                except NoMatch:
                    raise Bad(f'the text to replace is in neither v{h.v} nor your view v{b} of {p}',
                              f're-read it; changes since your view: {dumps(s.desc(c, p, b, h.v, a.id))}') from None
                return s.finish(c, a, p, s.onto(c, a, p, b, mine, h, 'edit'), warn)
            out = {'status': 'applied', **s.commit(c, a.id, p, new, 'edit', h, a.wf)}
            if b and b < h.v and out['status'] != 'unchanged': out['keptNewer'] = s.desc(c, p, b, h.v, a.id)
            return s.finish(c, a, p, out, warn)

    def sync(s, a, p):
        s.roles.need(a, 'write', 'record file edits')
        p = s.disk.norm(p)
        with s.db.tx() as c:
            if (mr := s.mrs.blocking(c, a.id, p)) and (h := s.head(c, p)) and s.disk.read(p) != h.body:
                s.disk.write(p, h.body)
                raise Clash(f'your earlier change to {p} waits in merge request mr{mr.id}, so this edit was not applied and the file is back at v{h.v}',
                            f"settle mr{mr.id} first: merges('mr{mr.id}'), then propose or abandon")
            s.blocked(c, a, p)
            warn, out = s.scope(c, a, p), s.adopt(c, p, a, 'sync')
            if (h := s.head(c, p)) is None: raise Missing(f'{p} does not exist')
            out = out or {'path': p, 'version': h.v, 'status': 'unchanged'}
            if out['status'] != 'conflict': s.see(c, a.id, p, h.v)
            return s.finish(c, a, p, out, warn)

    def prepare(s, a, p):
        p = s.disk.norm(p)
        if not s.roles.can(a, 'write'): return {'path': p, 'denied': f'{a.name} is {an(a.role)}, and that role cannot write files'}
        with s.db.tx() as c:
            if mr := s.mrs.blocking(c, a.id, p): return {'path': p, 'blocked': f'mr{mr.id}'}
            s.adopt(c, p)
            if (h := s.head(c, p)) is None: return {'path': p}
            out, b = {'path': p, 'version': h.v}, s.view(c, a.id, p)
            if b and b < h.v: out['changedSince'] = s.desc(c, p, b, h.v, a.id)
            s.see(c, a.id, p, b if b and b < h.v else h.v, now())
            return out | s.others(c, a, p)

    def saw(s, a, p):
        p = s.disk.norm(p)
        with s.db.tx() as c:
            if s.mrs.blocking(c, a.id, p): return None
            s.adopt(c, p)
            if h := s.head(c, p): s.see(c, a.id, p, h.v)
            return h and h.v

    def diff(s, a, p, since=None):
        s.roles.need(a, 'read', 'read files')
        p = s.disk.norm(p)
        with s.db.tx() as c:
            h = s.track(c, p)
            since = since if since is not None else s.view(c, a.id, p)
            since = max(0, h.v-5) if since is None else since
            names, prev, vs = s.agents.names(), s.body(c, p, since) if since >= 1 else '', []
            for r in c.execute('SELECT * FROM vers WHERE path=? AND v>? ORDER BY v', (p, since)).fetchall():
                vs.append({'version': r.v, 'author': names.get(r.agent, 'outside Hive'), 'origin': r.origin, 'changed': r.what,
                           'at': ago(r.ts), 'diff': Diff(prev, r.body).text(60)})
                prev = r.body
            return {'path': p, 'head': h.v, 'since': since, 'versions': vs}

    def release(s, a, p):
        p = s.disk.norm(p)
        with s.db.tx() as c:
            c.execute('DELETE FROM views WHERE agent=? AND path=?', (a.id, p))
            c.execute('DELETE FROM claims WHERE agent=? AND path=?', (a.id, p))
            s.log.unsub(c, a.id, f'file:{p}')
        return {'path': p, 'released': True}

    def claim(s, a, p, start, end, note, ttl=900):
        s.roles.need(a, 'write', 'claim file regions')
        p = s.disk.norm(p)
        if not 1 <= start <= end: raise Bad('claims need 1 <= start <= end')
        with s.db.tx() as c:
            s.track(c, p)
            ts = now()
            over = c.execute('SELECT * FROM claims WHERE path=? AND agent!=? AND until>=? AND lo<=? AND hi>=?',
                             (p, a.id, ts, end, start)).fetchall()
            k = c.execute('INSERT INTO claims(agent,path,lo,hi,note,until) VALUES(?,?,?,?,?,?)', (a.id, p, start, end, note, ts+ttl)).lastrowid
            s.log.sub(c, a.id, f'file:{p}')
            s.log.add(c, a.id, 'file.claimed', f'claimed {p} lines {start}-{end}: {note}', f'file:{p}', wf=a.wf)
            out = {'claim': f'k{k}', 'path': p, 'lines': f'{start}-{end}', 'expiresIn': int(ttl)}
            if over:
                names = s.agents.names()
                out['overlaps'] = [{'agent': names.get(x.agent), 'lines': f'{x.lo}-{x.hi}', 'note': x.note} for x in over]
                out['hint'] = 'someone already claimed part of this; coordinate before editing'
            return out

    def status(s, p=None):
        names = s.agents.names()
        with s.db.tx() as c:
            if p is None:
                rows = c.execute("SELECT f.path,f.head,f.ts,(SELECT COUNT(*) FROM views w JOIN agents a ON a.id=w.agent "
                                 "WHERE w.path=f.path AND a.state!='left') n FROM files f ORDER BY f.ts DESC LIMIT 100").fetchall()
                return {'files': [{'path': r.path, 'version': r.head, 'openBy': r.n, 'updated': ago(r.ts)} for r in rows],
                        'merges': [f'mr{m.id}' for m in s.mrs.opened(c)]}
            p = s.disk.norm(p)
            h = s.track(c, p)
            vw = c.execute("SELECT w.agent,w.v FROM views w JOIN agents a ON a.id=w.agent WHERE w.path=? AND a.state!='left'", (p,)).fetchall()
            ks = c.execute('SELECT * FROM claims WHERE path=? AND until>=?', (p, now())).fetchall()
            return {'path': p, 'version': h.v, 'author': names.get(h.agent, 'outside Hive'),
                    'openBy': [{'agent': names.get(x.agent), 'at': x.v} for x in vw],
                    'claims': [{'agent': names.get(k.agent), 'lines': f'{k.lo}-{k.hi}', 'note': k.note} for k in ks],
                    'merges': [f'mr{m.id}' for m in s.mrs.opened(c) if m.path == p]}

    def opened(s, aid): return [r.path for r in s.db.q('SELECT path FROM views WHERE agent=? ORDER BY ts', (aid,))]
