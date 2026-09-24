from __future__ import annotations

from typing import Any

from typing_extensions import NotRequired, TypedDict

from .err import Anon, Bad, Clash, Denied, Missing
from .log import fmt
from .mail import show
from .merge import lines as split
from .prompt import brief, task as taskPrompt
from .util import J, dumps, line, now, pid, poll

TOPICS = ('file:', 'context:', 'agent:', 'task:', 'tool:', 'thread:', 'kind:')


class Edit(TypedDict):
    old: str
    new: str
    all: NotRequired[bool]


class Spec(TypedDict):
    title: str
    key: NotRequired[str]
    about: NotRequired[str]
    role: NotRequired[str]
    after: NotRequired[list[str]]
    verify: NotRequired[bool | str]
    paths: NotRequired[list[str]]
    prio: NotRequired[int]
    kind: NotRequired[str]
    assignee: NotRequired[str]
    parent: NotRequired[str]


class Sess:
    def __init__(s, hive, aid): s.hive, s.id = hive, aid

    @property
    def agent(s): return s.hive.agents.get(s.id)

    @property
    def name(s): return s.agent.name

    @property
    def token(s): return s.agent.token

    def _me(s):
        if (a := s.hive.agents.get(s.id)).state == 'left': raise Anon(f'{a.name} has left the hive', 'join again')
        return s.hive.agents.touch(a)

    def _tx(s): return s.hive.db.tx()

    def notices(s, eat=True):
        a = s.agent
        return {} if a.state == 'left' else s.hive.notice(a, eat)

    def me(s):
        a, h = s._me(), s.hive
        r = h.roles.get(a.role)
        return {'name': a.name, 'role': a.role, 'charter': r.charter, 'caps': sorted(h.roles.caps(a)), 'token': a.token,
                'workflow': h.agents.wfNames().get(a.wf), 'parent': h.agents.names().get(a.parent), 'task': a.task and f't{a.task}',
                'follows': h.log.topics(a.id), 'files': h.files.opened(a.id)}

    def welcome(s):
        a = s.agent
        o = s.hive.aware.overview(a)
        return {'agent': a.name, 'token': a.token, 'role': a.role, 'brief': brief(a.name, a.role, s.hive.roles.get(a.role).charter, a.token),
                'others': [x for x in o['agents'] if not x.get('you')], 'tasks': o['tasks']['counts']}

    def progress(s, text: str, state: str | None = None):
        a = s._me()
        if not text.strip(): raise Bad('progress text is empty')
        if state not in (None, 'active', 'idle', 'done'): raise Bad('state is active, idle, or done', 'use leave to go')
        with s._tx() as c:
            s.hive.agents.set(c, a.id, status=line(text, 300), **({'state': state} if state else {}))
            s.hive.log.add(c, a.id, 'progress', line(text, 300), f'agent:{a.name}', wf=a.wf)
        return {'ok': True}

    def record(s, text, data=None):
        a = s.agent
        with s._tx() as c:
            c.execute('UPDATE agents SET seen=? WHERE id=?', (now(), a.id))
            s.hive.log.add(c, a.id, 'activity', line(text, 200), data=data, wf=a.wf)

    def idle(s):
        with s._tx() as c: s.hive.agents.set(c, s.id, state='idle')

    def leave(s, note: str = ''):
        a, out = s._me(), {'left': True}
        with s._tx() as c:
            for t in c.execute("SELECT id FROM tasks WHERE owner=? AND (state='running' OR (state='ready' AND id=?))", (a.id, a.deleg or -1)).fetchall():
                out[f't{t.id}'] = s.hive.tasks.release(c, t.id, f'{a.name} left the hive. {note}'.strip())
            c.execute('DELETE FROM views WHERE agent=?', (a.id,))
            c.execute('DELETE FROM claims WHERE agent=?', (a.id,))
            s.hive.agents.set(c, a.id, state='left')
            s.hive.log.add(c, a.id, 'agent.left', 'left' + (f': {line(note, 120)}' if note else ''), f'agent:{a.name}', wf=a.wf)
        return out

    def blockers(s):
        a, h = s.agent, s.hive
        out = [f"unacknowledged interrupts {', '.join(f'm{m.id}' for m in u)}: handle them, then ack them"] if (u := h.mail.urgent(a.id)) else []
        out += [f"merge request mr{m.id} on {m.path} waits on you: merges('mr{m.id}')" for m in h.files.mrs.involving(a.id)
                if a.id in h.files.mrs.waiting(m)]
        return out + [f"issue i{x.id} waits on your decision: issues()" for x in h.db.q("SELECT id FROM issues WHERE holder=? AND state='open'", (a.id,))]

    def overview(s, scope: str = 'auto'): return s.hive.aware.overview(s._me(), scope)

    def digest(s, scope: str = 'auto', budget: int = 1200): return s.hive.aware.digest(s._me(), scope, budget)

    def watch(s, of: str, view: str = 'live', since: int | None = None, before: int | None = None, limit: int = 30, wait: float = 0,
              budget: int = 800):
        a, w = s._me(), s.hive.aware
        if view == 'live': return w.live(a, of, since, wait, limit)
        if view == 'window': return w.window(a, of, before, limit)
        if view == 'summary': return w.summary(a, of, since, before, budget)
        raise Bad(f'unknown view {view!r}', 'live, window, or summary')

    def roles(s):
        s._me()
        return {'roles': [{'name': r.name, 'charter': r.charter, 'caps': sorted(r.caps), 'builtin': r.builtin} for r in s.hive.roles.all()]}

    def _to(s, a, to):
        found = {}
        for t in [to] if isinstance(to, str) else to:
            if t in ('*', 'all') or t.startswith('workflow:'): s.hive.roles.need(a, 'broadcast', 'broadcast')
            got = s.hive.agents.resolve(t, a)
            if len(got) == 1 and got[0].state == 'left': raise Clash(f'{got[0].name} has left the hive')
            found |= {x.id: x for x in got if x.state != 'left'}
        if not found: raise Missing(f'nobody matches {to!r}', 'overview lists agents and roles')
        return list(found.values())

    def send(s, to: str | list[str], body: str, mode: str = 'queue', thread: str | None = None, re: str | None = None):
        a = s._me()
        s.hive.roles.need(a, 'send', 'send messages')
        dst = s._to(a, to)
        with s._tx() as c:
            ids = s.hive.mail.put(c, a, [x.id for x in dst], body, mode, thread=thread, re=pid('m', re, 'message') if re else None)
        return {'sent': [f'm{i}' for i in ids], 'to': [x.name for x in dst], 'mode': mode}

    def inbox(s, limit: int = 20, all: bool = False):
        a, names = s._me(), s.hive.agents.names()
        return {'messages': [show(m, names) for m in s.hive.mail.box(a, limit, all)],
                'unacked': [f'm{m.id}' for m in s.hive.mail.urgent(a.id)]}

    def ack(s, ids: list[str] | str = 'all'):
        a = s._me()
        ids = None if ids in ('all', ['all']) else [pid('m', i, 'message') for i in ([ids] if isinstance(ids, str | int) else ids)]
        return {'acked': s.hive.mail.ack(a, ids)}

    def ask(s, to: str, question: str, wait: float = 120, mode: str = 'steer'):
        a = s._me()
        s.hive.roles.need(a, 'send', 'send messages')
        if len(dst := s._to(a, to)) != 1: raise Bad('ask one agent at a time', 'send reaches several')
        with s._tx() as c:
            [i] = s.hive.mail.put(c, a, [dst[0].id], f'{question}\n({a.name} is waiting: answer with send(to={a.name!r}, re=<this id>, body=...))',
                                  mode, 'question', {'expectsReply': True})
        if (r := poll(lambda: s.hive.mail.reply(a.id, i, dst[0].id), max(0., min(wait, 900.)))) is None:
            return {'asked': f'm{i}', 'reply': None, 'hint': f'no answer from {dst[0].name} within {wait:g}s; it will reach your inbox'}
        s.hive.mail.mark([r.id])
        return {'asked': f'm{i}', 'reply': show(r, s.hive.agents.names())}

    def wait(s, secs: float = 60):
        a = s._me()
        with s._tx() as c: s.hive.agents.set(c, a.id, state='idle')
        woke = bool(poll(lambda: s.hive.notice.pending(a), max(0., min(secs, 900.))))
        with s._tx() as c: s.hive.agents.set(c, a.id, state='active')
        names = s.hive.agents.names()
        return {'woke': woke, 'messages': [show(m, names) for m in s.hive.mail.box(a, 50)]}

    def share(s, to: str | list[str], note: str = '', key: str | None = None, path: str | None = None, lines: str | None = None,
              task: str | None = None, msg: str | None = None, text: str | None = None, mode: str = 'steer'):
        a, h = s._me(), s.hive
        h.roles.need(a, 'send', 'share')
        if key: att, what = {'context': h.board.get(a, key)}, f'context entry {key}'
        elif path:
            h.roles.need(a, 'read', 'read files')
            p = h.disk.norm(path)
            with s._tx() as c: hd = h.files.track(c, p)
            ls = split(hd.body)
            try: lo, hi = map(int, (lines.split('-') + [lines])[:2]) if lines else (1, len(ls))
            except ValueError: raise Bad("lines looks like '10-40' or '12'") from None
            att, what = {'file': p, 'version': hd.v, 'lines': f'{lo}-{hi}', 'content': ''.join(ls[lo-1:hi])}, f'{p} lines {lo}-{hi} (v{hd.v})'
        elif task: att, what = {'task': h.tasks.show(t := h.tasks.get(pid('t', task, 'task')), full=True)}, f't{t.id}'
        elif msg:
            m = h.mail.get(pid('m', msg, 'message'))
            if a.id not in (m.src, m.dst): raise Denied(f'm{m.id} is not yours to share')
            att, what = {'message': show(m, h.agents.names())}, f'message m{m.id}'
        elif text: att, what = {'text': text}, 'a note'
        else: raise Bad('share needs one of key, path, task, msg, or text')
        dst = s._to(a, to)
        with s._tx() as c:
            ids = h.mail.put(c, a, [x.id for x in dst], f'{a.name} shared {what}' + (f': {note}' if note else ''), mode, 'share', att)
        return {'shared': what, 'to': [x.name for x in dst], 'ids': [f'm{i}' for i in ids]}

    def handoff(s, to: str, note: str, mode: str = 'steer'):
        a, h = s._me(), s.hive
        h.roles.need(a, 'send', 'hand off work')
        if not note.strip(): raise Bad('say what you hand over and what is left in note')
        dst, names = s._to(a, to), h.agents.names()
        pack = {'from': a.name, 'role': a.role, 'note': note, 'status': a.status,
                'activity': h.summ([fmt(e, names, False) for e in h.log.find(agent=a.id, limit=1 << 20)], 600,
                                   f"{a.name}'s work so far, for the agent taking it over").text}
        if a.task: pack['task'] = h.tasks.show(h.tasks.get(a.task), full=True)
        if vw := h.db.q('SELECT path,v FROM views WHERE agent=?', (a.id,)): pack['files'] = [{'path': x.path, 'version': x.v} for x in vw]
        with s._tx() as c:
            ids = h.mail.put(c, a, [x.id for x in dst], f'Handoff from {a.name}: {note}', mode, 'handoff', pack)
        return {'to': [x.name for x in dst], 'ids': [f'm{i}' for i in ids], 'package': pack}

    def follow(s, topics: list[str], stop: bool = False):
        a = s._me()
        if bad := [t for t in topics if not t.startswith(TOPICS)]: raise Bad(f'invalid topics {bad}', 'start with ' + ', '.join(TOPICS))
        with s._tx() as c:
            for t in topics: (s.hive.log.unsub if stop else s.hive.log.sub)(c, a.id, t)
        return {'follows': s.hive.log.topics(a.id)}

    def put(s, key: str, value: Any, scope: str = 'auto', expect: int | None = None, tags: list[str] | None = None):
        a = s._me()
        s.hive.roles.need(a, 'post', 'write shared context')
        return s.hive.board.put(a, key, value, scope, expect, tags)

    def get(s, key: str, scope: str = 'auto', history: int = 0): return s.hive.board.get(s._me(), key, scope, history)

    def keys(s, prefix: str = '', scope: str = 'auto', tag: str | None = None): return {'keys': s.hive.board.keys(s._me(), prefix, scope, tag)}

    def drop(s, key: str, scope: str = 'auto'):
        a = s._me()
        s.hive.roles.need(a, 'post', 'write shared context')
        return s.hive.board.drop(a, key, scope)

    def read(s, path: str, start: int | None = None, end: int | None = None): return s.hive.files.read(s._me(), path, start, end)

    def edit(s, path: str, edits: list[Edit], base: int | None = None): return s.hive.files.edit(s._me(), path, [dict(e) for e in edits], base)

    def write(s, path: str, content: str, base: int | None = None): return s.hive.files.write(s._me(), path, content, base)

    def sync(s, path: str): return s.hive.files.sync(s._me(), path)

    def prepare(s, path): return s.hive.files.prepare(s.agent, path)

    def saw(s, path): return s.hive.files.saw(s.agent, path)

    def diff(s, path: str, since: int | None = None): return s.hive.files.diff(s._me(), path, since)

    def release(s, path: str): return s.hive.files.release(s._me(), path)

    def claim(s, path: str, start: int, end: int, note: str, ttl: float = 900): return s.hive.files.claim(s._me(), path, start, end, note, ttl)

    def files(s, path: str | None = None):
        s._me()
        return s.hive.files.status(path)

    def merges(s, id: str | None = None, state: str = 'open'):
        a = s._me()
        return s.hive.files.mrs.show(a, id) if id else {'merges': s.hive.files.mrs.list(a, state)}

    def propose(s, id: str, note: str, picks: list[str | dict[str, str]] | None = None, content: str | None = None):
        return s.hive.files.mrs.propose(s._me(), id, note, picks, content)

    def respond(s, id: str, ok: bool, note: str = ''): return s.hive.files.mrs.respond(s._me(), id, ok, note)

    def abandon(s, id: str, note: str = ''): return s.hive.files.mrs.abandon(s._me(), id, note)

    def plan(s, tasks: list[Spec], workflow: str | None = None, chain: bool = False):
        return s.hive.tasks.plan(s._me(), [dict(t) for t in tasks], workflow, chain)

    def tasks(s, state: str | None = None, role: str | None = None, mine: bool = False, scope: str = 'auto'):
        a = s._me()
        w = s.hive.aware.wf(a, scope)
        return {'tasks': s.hive.tasks.list(state, role, w, a.id if mine else None), 'counts': s.hive.tasks.counts(w)}

    def task(s, id: str, budget: int = 2000): return s.hive.tasks.context(s._me(), id, budget)

    def take(s, id: str | None = None): return s.hive.tasks.take(s._me(), id)

    def done(s, id: str, result: str): return s.hive.tasks.done(s._me(), id, result)

    def fail(s, id: str, reason: str, retry: bool = False): return s.hive.tasks.fail(s._me(), id, reason, retry)

    def verify(s, id: str, ok: bool, notes: str): return s.hive.tasks.verify(s._me(), id, ok, notes)

    def cancel(s, id: str, reason: str): return s.hive.tasks.cancel(s._me(), id, reason)

    def dispatch(s, id: str, name: str | None = None, budget: int = 0):
        a, h = s._me(), s.hive
        h.roles.need(a, 'spawn', 'dispatch agents')
        with s._tx() as c:
            t = h.tasks.get(pid('t', id, 'task'), c)
            if t.state != 'ready' or t.owner: raise Clash(f"t{t.id} is {t.state}{' and reserved' if t.owner else ''}", 'only free ready tasks dispatch')
            role = t.role or ('verifier' if t.kind == 'verify' else 'implementer')
            taken, n = set(h.agents.names().values()), name or f'{role}-t{t.id}'
            n = next(x for x in [n, *(f'{n}-{i}' for i in range(2, 1000))] if x not in taken) if not name else n
            if budget < 0 or c.execute('UPDATE agents SET budget=budget-? WHERE id=? AND budget>=? RETURNING id', (budget, a.id, budget)).fetchone() is None:
                raise Clash(f'you cannot give budget {budget}', 'dispatch with a budget you have (default 0)')
            want, mine = h.roles.get(role).caps, h.roles.caps(a)
            kid = h.join(n, role, h.agents.wfNames().get(t.wf), a.name, f'dispatched for t{t.id}')
            h.tasks.reserve(c, a, t.id, kid.id)
            c.execute('UPDATE agents SET budget=?,goal=?,deleg=?,grants=? WHERE id=?',
                      (budget, t.about or t.title, t.id, None if want <= mine else dumps(sorted(want & mine)), kid.id))
        return {'agent': n, 'role': role, 'token': kid.token, 'task': f't{t.id}', 'prompt': s.promptFor(kid, t.id),
                'hint': f'start an agent with this prompt; it acts in the hive as {n}'}

    def promptFor(s, kid, i):
        a, h = kid.agent, s.hive
        if a.launch: return h.tree.prompt(a)
        t = h.tasks.get(i)
        return taskPrompt(brief(a.name, a.role, h.roles.get(a.role).charter, a.token), h.tasks.show(t, full=True),
                          h.tasks.context(a, i).get('dependencies'), None if t.kind == 'verify' else h.know.tips(f'{t.title} {t.about}'))

    def define(s, name: str, charter: str, caps: list[str]):
        a = s._me()
        s.hive.roles.need(a, 'define', 'define roles')
        r = s.hive.roles.define(name, charter, caps)
        return {'name': r.name, 'charter': r.charter, 'caps': sorted(r.caps)}

    def assign(s, of: str, role: str):
        a, h = s._me(), s.hive
        h.roles.need(a, 'spawn', 'change roles')
        t, ch = h.agents.named(of), h.roles.get(role).charter
        with s._tx() as c:
            h.agents.set(c, t.id, role=role, grants=t.grants and dumps(sorted(set(J(t.grants)) & h.roles.get(role).caps)))
            h.mail.put(c, a, [t.id], f'{a.name} changed your role from {t.role} to {role}. Your charter now: {ch}', 'interrupt', 'role')
            h.log.add(c, a.id, 'agent.role', f'{t.name}: {t.role} -> {role}', f'agent:{t.name}', wf=a.wf)
        return {'agent': t.name, 'role': role}

    def spawn(s, goal: str, role: str | None = None, name: str | None = None, budget: int | None = None, launch: str = 'host',
              grants: list[str] | None = None, deliver: str = '', paths: list[str] | None = None, verify: bool | str = False):
        return s.hive.tree.spawn(s._me(), goal, role, name, budget, launch, grants, deliver, paths, verify)

    def gather(s, of: list[str] | str | None = None, secs: float = 60, any: bool = False, budget: int = 2000):
        return s.hive.tree.gather(s._me(), of, secs, any, budget)

    def tree(s, of: str | None = None, depth: int = 1, limit: int = 12, after: str | None = None):
        return s.hive.tree.tree(s._me(), of, depth, limit, after)

    def node(s, of: str | None = None, limit: int = 12): return s.hive.tree.node(s._me(), of, limit)

    def walk(s, to: str = 'here'): return s.hive.tree.walk(s._me(), to)

    def path(s, of: str | None = None): return s.hive.tree.lineage(s._me(), of)

    def find(s, query: str = '', within: str | None = None, state: str | None = None, role: str | None = None, limit: int = 20):
        return s.hive.tree.find(s._me(), query, within, state, role, limit)

    def brief(s, of: str | None = None, budget: int = 800, depth: int = 3): return s.hive.tree.brief(s._me(), of, budget, depth)

    def fund(s, of: str, amount: int): return s.hive.tree.fund(s._me(), of, amount)

    def adopt(s, of: str): return s.hive.tree.adopt(s._me(), of)

    def escalate(s, need: str, options: list[str] | None = None, fund: int = 0, mode: str = 'interrupt'):
        return s.hive.tree.escalate(s._me(), need, options, fund, mode)

    def decide(s, id: str, choice: str, note: str = '', fund: int | None = None): return s.hive.tree.decide(s._me(), id, choice, note, fund)

    def issues(s, all: bool = False): return {'issues': s.hive.tree.issues(s._me(), not all)}

    def note(s, text: str, kind: str = 'fact', refs: list[str] | None = None, tags: list[str] | None = None, conf: float = .7):
        return s.hive.know.note(s._me(), text, kind, refs, tags, conf)

    def findings(s, of: str | None = None, deep: bool = True, kind: str | None = None, since: int = 0, limit: int = 50):
        return s.hive.know.findings(s._me(), of, deep, kind, since, limit)

    def material(s, of: str | None = None, budget: int = 3000): return s.hive.know.material(s._me(), of, budget)

    def compose(s, of: str, text: str, sources: list[str] | None = None, gaps: str = ''):
        return s.hive.know.compose(s._me(), of, text, sources, gaps)

    def gist(s, of: str | None = None): return s.hive.know.gist(s._me(), of)

    def stale(s, of: str | None = None, limit: int = 30): return s.hive.know.stale(s._me(), of, limit)

    def harvest(s, of: str | None = None, budget: int = 3000): return s.hive.know.harvest(s._me(), of, budget)

    def distill(s, title: str, body: str, kind: str = 'observed', evidence: list[str] | None = None, tags: list[str] | None = None,
                scope: str = 'project', into: str | None = None, force: bool = False):
        return s.hive.know.distill(s._me(), title, body, kind, evidence, tags, scope, into, force)

    def recall(s, query: str = '', kind: str | None = None, state: str | None = None, scope: str | None = None, limit: int = 8):
        s._me()
        return {'insights': s.hive.know.recall(query, kind, state, scope, limit)}

    def weigh(s, id: str, stance: str = 'support', evidence: list[str] | None = None, note: str = ''):
        return s.hive.know.weigh(s._me(), id, stance, evidence, note)

    def retire(s, id: str, reason: str): return s.hive.know.retire(s._me(), id, reason)

    def retry(s, id: str | None = None, note: str = ''): return s.hive.faults.retry(s._me(), id, note)

    def faults(s, limit: int = 20):
        s._me()
        return s.hive.faults.show(limit)

    def offer(s, name: str, about: str, schema: dict[str, Any] | None = None, kind: str = 'agent', argv: list[str] | None = None,
              timeout: float = 60):
        return s.hive.tools.offer(s._me(), name, about, schema, kind, argv, timeout)

    def tools(s):
        s._me()
        return {'tools': s.hive.tools.all()}

    def call(s, name: str, args: dict[str, Any] | None = None, wait: float = 30): return s.hive.tools.call(s._me(), name, args, wait)

    def answer(s, id: str, result: Any = None, error: str | None = None): return s.hive.tools.answer(s._me(), id, result, error)

    def result(s, id: str, wait: float = 0): return s.hive.tools.result(s._me(), id, wait)

    def withdraw(s, name: str): return s.hive.tools.withdraw(s._me(), name)
