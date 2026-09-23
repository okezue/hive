from .err import Bad, Clash, Denied, Missing
from .mail import show
from .merge import Diff, merge
from .util import J, ago, clip, dumps, line, now, pid

ALIAS = {'requester': 'ours', 'current': 'theirs', 'both': 'ours+theirs', 'requester+current': 'ours+theirs', 'current+requester': 'theirs+ours'}


def who(m): return [m.src, *[x for x in m.parties if x != m.src]]


def hunks(merged): return [{k: clip(v, 1500) if isinstance(v, str) else v for k, v in h.dict(i, 'requester', 'current').items()}
                           for i, h in enumerate(merged.hunks)]


def alias(c):
    if isinstance(c, str): return ALIAS.get(c, c)
    if isinstance(c, dict) and isinstance(c.get('take'), str): return {'take': ALIAS.get(c['take'], c['take'])}
    return c


class Mrs:
    def __init__(s, f): s.f, s.db = f, f.db

    def _d(s, m):
        if m:
            m.parties, m.hunks, m.prop, m.oks = J(m.parties, []), J(m.hunks, []), J(m.prop), J(m.oks, [])
        return m

    def get(s, c, ref):
        if (m := s._d(c.execute('SELECT * FROM mrs WHERE id=?', (i := pid('mr', ref, 'merge request'),)).fetchone())) is None:
            raise Missing(f'no merge request mr{i}')
        return m

    def opened(s, c=None): return [s._d(m) for m in (c or s.db.conn()).execute("SELECT * FROM mrs WHERE state='open' ORDER BY id")]

    def blocking(s, c, aid, p):
        return s._d(c.execute("SELECT * FROM mrs WHERE state='open' AND src=? AND path=? LIMIT 1", (aid, p)).fetchone())

    def involving(s, aid): return [m for m in s.opened() if aid in who(m)]

    def live(s, ids): return [a.id for a in s.f.agents.all() if a.id in ids]

    def waiting(s, m): return [x for x in s.live(who(m)) if not m.prop or x not in m.oks]

    def open(s, c, a, p, base, h, body, merged):
        authors = {r.agent for r in s.f.after(c, p, base, h.v) if r.agent is not None and r.agent != a.id}
        parties, names = s.live(authors), s.f.agents.names()
        hs = hunks(merged)
        i = c.execute('INSERT INTO mrs(path,src,parties,base,head,body,hunks,ts) VALUES(?,?,?,?,?,?,?,?)',
                      (p, a.id, dumps(parties), base, h.v, body, dumps(hs), now())).lastrowid
        ref, where, them = f'mr{i}', '; '.join(x.where() for x in merged.hunks), ', '.join(names.get(x, '?') for x in parties)
        if parties:
            s.f.mail.put(c, a, parties, f"Merge request {ref}: {a.name} edited {p} from v{base} while you changed it, and the edits "
                         f"overlap ({where}). Reconcile it with {a.name} in thread {ref}, then one of you calls propose and the other "
                         f"respond. merges('{ref}') shows both versions.", 'interrupt', 'merge', {'mr': ref, 'path': p, 'hunks': hs}, ref)
        s.f.log.add(c, a.id, 'merge.opened', f"{ref} on {p}: {len(hs)} conflict(s) with {them or 'no active author'}", f'file:{p}',
                    {'mr': ref}, a.wf)
        nxt = (f"Your change was not applied. Agree on the result with {them} in thread {ref} (send with thread='{ref}'), then call "
               f"propose('{ref}', picks=[...one per conflict], note=...); they accept with respond.") if parties else \
              (f"The other change came from outside Hive or from an agent who left: settle it with propose('{ref}', ...) or drop yours "
               f"with abandon('{ref}').")
        return {'status': 'conflict', 'mr': ref, 'path': p, 'yourBase': base, 'head': h.v, 'with': [names.get(x) for x in parties],
                'conflicts': hs, 'next': nxt}

    def show(s, a, ref):
        names = s.f.agents.names()
        with s.db.tx() as c:
            m = s.get(c, ref)
            out = {'mr': f'mr{m.id}', 'path': m.path, 'state': m.state, 'requester': names.get(m.src),
                   'with': [names.get(x) for x in m.parties], 'requesterBase': m.base, 'headWhenOpened': m.head, 'opened': ago(m.ts),
                   'conflicts': m.hunks, 'waitingFor': [names.get(x) for x in s.waiting(m)] if m.state == 'open' else []}
            if m.prop:
                out['proposal'] = {'by': names.get(m.prop['by']), 'note': m.prop['note'], 'acceptedBy': [names.get(x) for x in m.oks],
                                   'diff': Diff(s.f.body(c, m.path, m.head), m.prop['body']).text(80)}
            if m.state == 'resolved': out['version'] = m.v
            if m.note: out['note'] = m.note
            if th := s.f.mail.thread(f'mr{m.id}', 20): out['thread'] = [show(x, names) for x in th]
            return out

    def list(s, a, state='open', mine=False):
        names = s.f.agents.names()
        ms = [s._d(m) for m in s.db.q("SELECT * FROM mrs WHERE ?='all' OR state=? ORDER BY id DESC LIMIT 50", (state, state))]
        return [{'mr': f'mr{m.id}', 'path': m.path, 'state': m.state, 'requester': names.get(m.src), 'with': [names.get(x) for x in m.parties],
                 'conflicts': len(m.hunks), 'proposal': bool(m.prop), 'waitingFor': [names.get(x) for x in s.waiting(m)] if m.state == 'open' else []}
                for m in ms if not mine or a.id in who(m)]

    def part(s, c, a, ref):
        m = s.get(c, ref)
        if m.state != 'open': raise Clash(f'mr{m.id} is already {m.state}')
        if a.id not in who(m) and not s.f.roles.can(a, 'manage'):
            raise Denied(f'{a.name} is not part of mr{m.id}', 'only its authors or a coordinator can act on it')
        return m

    def propose(s, a, ref, note, picks=None, content=None):
        if not note.strip(): raise Bad('explain the resolution in note', 'the other author reads it before accepting')
        with s.db.tx() as c:
            m = s.part(c, a, ref)
            if content is None:
                if picks is None: raise Bad('give picks (one per conflict) or the full resolved content')
                content = merge(s.f.body(c, m.path, m.base), m.body, s.f.body(c, m.path, m.head)).pick([alias(x) for x in picks])
            m.prop, m.oks = {'by': a.id, 'body': content, 'note': note, 'at': now()}, [a.id]
            c.execute('UPDATE mrs SET prop=?,oks=? WHERE id=?', (dumps(m.prop), dumps(m.oks), m.id))
            if not (wait := s.waiting(m)): return s.apply(c, m, a)
            s.f.mail.put(c, a, wait, f"{a.name} proposed a resolution for mr{m.id} ({m.path}): {note}\nReview it with merges('mr{m.id}') and "
                         f"answer with respond('mr{m.id}', ok=true|false, note=...).", 'interrupt', 'proposal',
                         {'mr': f'mr{m.id}', 'diff': Diff(s.f.body(c, m.path, m.head), content).text(60)}, f'mr{m.id}')
            names = s.f.agents.names()
            return {'mr': f'mr{m.id}', 'status': 'proposed', 'waitingFor': [names.get(x) for x in wait]}

    def respond(s, a, ref, ok, note=''):
        with s.db.tx() as c:
            m = s.part(c, a, ref)
            if not m.prop: raise Clash(f'mr{m.id} has no proposal yet', 'discuss in the thread or make one with propose')
            if a.id == (by := m.prop['by']): raise Clash('this is your proposal; the other author answers it')
            if not ok:
                if not note.strip(): raise Bad('say why you reject it in note')
                c.execute("UPDATE mrs SET prop=NULL,oks='[]' WHERE id=?", (m.id,))
                s.f.mail.put(c, a, [x for x in s.live(who(m)) if x != a.id], f'{a.name} rejected the proposal for mr{m.id}: {note}',
                             'interrupt', 'rejected', thread=f'mr{m.id}')
                return {'mr': f'mr{m.id}', 'status': 'rejected'}
            m.oks = sorted({*m.oks, a.id})
            c.execute('UPDATE mrs SET oks=? WHERE id=?', (dumps(m.oks), m.id))
            if note.strip(): s.f.mail.put(c, a, [by], f'accepted mr{m.id}: {note}', 'steer', 'accepted', thread=f'mr{m.id}')
            if wait := s.waiting(m):
                names = s.f.agents.names()
                return {'mr': f'mr{m.id}', 'status': 'accepted', 'waitingFor': [names.get(x) for x in wait]}
            return s.apply(c, m, s.f.agents.get(by))

    def abandon(s, a, ref, note=''):
        with s.db.tx() as c:
            m = s.part(c, a, ref)
            if a.id != m.src and not s.f.roles.can(a, 'manage'): raise Denied(f"only mr{m.id}'s requester or a coordinator can abandon it")
            c.execute("UPDATE mrs SET state='abandoned',doneAt=?,note=? WHERE id=?", (now(), note, m.id))
            if rest := [x for x in s.live(who(m)) if x != a.id]:
                s.f.mail.put(c, a, rest, f'{a.name} abandoned mr{m.id} on {m.path}; the current version stands. {note}'.strip(), 'steer',
                             'abandoned', thread=f'mr{m.id}')
            s.f.log.add(c, a.id, 'merge.abandoned', f'mr{m.id} on {m.path} abandoned: {line(note, 80)}', f'file:{m.path}', wf=a.wf)
        return {'mr': f'mr{m.id}', 'status': 'abandoned'}

    def apply(s, c, m, author):
        body, h, names, ref = m.prop['body'], s.f.head(c, m.path), s.f.agents.names(), f'mr{m.id}'
        if h.v != m.head:
            mm = merge(s.f.body(c, m.path, m.head), body, h.body)
            if not mm.clean:
                new = {r.agent for r in s.f.after(c, m.path, m.head, h.v) if r.agent is not None}
                parties = sorted({*m.parties, *new} - {m.src})
                hs = hunks(mm)
                c.execute("UPDATE mrs SET base=?,head=?,body=?,hunks=?,parties=?,prop=NULL,oks='[]' WHERE id=?",
                          (m.head, h.v, body, dumps(hs), dumps(parties), m.id))
                s.f.mail.put(c, None, s.live([m.src, *parties]), f"{ref}: the agreed resolution conflicts with later changes to {m.path}; "
                             f"settle the new conflicts with merges('{ref}') and propose.", 'interrupt', 'merge', thread=ref)
                return {'mr': ref, 'status': 'reopened', 'conflicts': hs}
            body = mm.text()
        out = s.f.commit(c, author.id, m.path, body, 'merge-request', h, author.wf)
        c.execute("UPDATE mrs SET state='resolved',doneAt=?,v=? WHERE id=?", (now(), out['version'], m.id))
        if rest := [x for x in s.live(who(m)) if x != author.id]:
            s.f.mail.put(c, None, rest, f"{ref} resolved: {m.path} is v{out['version']} with the agreed resolution.", 'steer', 'resolved', thread=ref)
        s.f.log.add(c, author.id, 'merge.resolved', f"{ref} resolved as {m.path} v{out['version']} (agreed by "
                    f"{', '.join(names.get(x, '?') for x in m.oks)})", f'file:{m.path}', wf=author.wf)
        return {'mr': ref, 'status': 'resolved', 'path': m.path, 'version': out['version']}
