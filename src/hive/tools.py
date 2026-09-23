import json, os, re, subprocess

import jsonschema

from .err import Bad, Clash, Denied, Missing
from .util import J, clip, dumps, line, now, pid, poll

NAME = re.compile(r'^[a-z][a-z0-9_.-]{0,63}$')
KINDS = ('agent', 'command')


class Tools:
    def __init__(s, db, log, mail, agents, roles, root): s.db, s.log, s.mail, s.agents, s.roles, s.root = db, log, mail, agents, roles, root

    def offer(s, a, n, about, schema=None, kind='agent', argv=None, timeout=60):
        s.roles.need(a, 'offer', 'share tools')
        if not NAME.match(n or ''): raise Bad(f'invalid tool name {n!r}', "lowercase letters, digits, '_', '.', '-'; a letter first")
        if not about.strip(): raise Bad('say what the tool does and returns')
        if kind not in KINDS: raise Bad('kind is agent or command')
        schema = schema or {'type': 'object'}
        try: jsonschema.Draft202012Validator.check_schema(schema)
        except jsonschema.SchemaError as e: raise Bad(f'schema is not valid JSON Schema: {e.message}') from None
        if kind == 'command':
            s.roles.need(a, 'exec', 'share command tools')
            if not argv or not all(isinstance(x, str) and x for x in argv): raise Bad('command tools need argv, a list of strings')
        elif argv: raise Bad('only command tools take argv')
        with s.db.tx() as c:
            if (r := c.execute('SELECT owner FROM tools WHERE name=?', (n,)).fetchone()) and r.owner != a.id:
                raise Clash(f'{n} is already shared by {s.agents.names().get(r.owner)}')
            c.execute('INSERT OR REPLACE INTO tools VALUES(?,?,?,?,?,?,?,?)',
                      (n, a.id, about.strip(), dumps(schema), kind, argv and dumps(argv), float(timeout), now()))
            s.log.add(c, a.id, 'tool.offered', f'shared {n} ({kind}): {line(about, 80)}', f'tool:{n}', wf=a.wf)
        return {'tool': n, 'kind': kind, 'shared': True}

    def withdraw(s, a, n):
        with s.db.tx() as c:
            if (r := c.execute('SELECT owner FROM tools WHERE name=?', (n,)).fetchone()) is None: raise Missing(f'no shared tool {n!r}')
            if r.owner != a.id and not s.roles.can(a, 'spawn'): raise Denied("only the tool's owner or a coordinator can withdraw it")
            c.execute('DELETE FROM tools WHERE name=?', (n,))
            s.log.add(c, a.id, 'tool.withdrawn', f'withdrew {n}', f'tool:{n}', wf=a.wf)
        return {'tool': n, 'withdrawn': True}

    def all(s):
        names, live = s.agents.names(), {x.id for x in s.agents.all()}
        return [{'name': r.name, 'owner': names.get(r.owner), 'kind': r.kind, 'about': r.about, 'schema': J(r.schema, {}),
                 'available': r.kind == 'command' or r.owner in live} for r in s.db.q('SELECT * FROM tools ORDER BY name')]

    def done(s, i):
        return s.db.one("SELECT * FROM calls WHERE id=? AND state!='pending'", (i,))

    def call(s, a, n, args=None, wait=30):
        s.roles.need(a, 'use', 'use shared tools')
        args = args or {}
        if (t := s.db.one('SELECT * FROM tools WHERE name=?', (n,))) is None: raise Missing(f'no shared tool {n!r}', 'tools lists them')
        try: jsonschema.validate(args, J(t.schema, {}))
        except jsonschema.ValidationError as e: raise Bad(f"arguments do not match {n}'s schema: {e.message}") from None
        if t.kind == 'command': return s.run(a, t, args)
        o = s.agents.get(t.owner)
        if o.state == 'left': raise Clash(f'{o.name}, who serves {n}, has left')
        if o.id == a.id: raise Bad('this is your own tool; run it directly')
        wait = max(0., min(float(wait), 600.))
        with s.db.tx() as c:
            i = c.execute("INSERT INTO calls(tool,src,owner,args,state,waitUntil,ts) VALUES(?,?,?,?,'pending',?,?)",
                          (n, a.id, o.id, dumps(args), now()+wait, now())).lastrowid
            s.mail.put(c, a, [o.id], f"{a.name} called your tool {n} (c{i}) with {clip(dumps(args), 2000)}. Run it and answer with "
                       f"answer('c{i}', result=...) or error=...", 'steer', 'call', {'call': f'c{i}', 'tool': n, 'args': args})
        if r := poll(lambda: s.done(i), wait): return s.fmt(r)
        return {'call': f'c{i}', 'state': 'pending', 'hint': f"no answer from {o.name} yet; result('c{i}', wait=...) checks again, "
                                                              "and the result also arrives as a message"}

    def answer(s, a, ref, result=None, error=None):
        i = pid('c', ref, 'call')
        with s.db.tx() as c:
            if (k := c.execute('SELECT * FROM calls WHERE id=?', (i,)).fetchone()) is None: raise Missing(f'no call c{i}')
            if k.owner != a.id: raise Denied(f'c{i} was addressed to another agent')
            if k.state != 'pending': raise Clash(f'c{i} is already {k.state}')
            st = 'error' if error else 'done'
            c.execute('UPDATE calls SET state=?,result=?,err=?,doneAt=? WHERE id=?', (st, None if error else dumps(result), error, now(), i))
            if now() > k.waitUntil:
                s.mail.put(c, a, [k.src], f'result of {k.tool} (c{i}): ' + (f'error: {error}' if error else clip(dumps(result), 4000)),
                           'steer', 'result', {'call': f'c{i}'})
            s.log.add(c, a.id, 'tool.answered', f'answered c{i} ({k.tool}): {st}', f'tool:{k.tool}', wf=a.wf)
        return {'call': f'c{i}', 'state': st}

    def result(s, a, ref, wait=0):
        i = pid('c', ref, 'call')
        if (k := s.db.one('SELECT * FROM calls WHERE id=?', (i,))) is None: raise Missing(f'no call c{i}')
        if a.id not in (k.src, k.owner): raise Denied(f'c{i} belongs to other agents')
        r = poll(lambda: s.done(i), max(0., min(float(wait), 600.)))
        return s.fmt(r) if r else {'call': f'c{i}', 'state': 'pending'}

    def fmt(s, k):
        out = {'call': f'c{k.id}', 'tool': k.tool, 'state': k.state}
        if k.err: out['error'] = k.err
        if k.result is not None: out['result'] = J(k.result)
        return out

    def run(s, a, t, args):
        argv, payload, st, res, err = J(t.argv, []), json.dumps(args), 'done', None, None
        try:
            p = subprocess.run(argv, input=payload, capture_output=True, text=True, timeout=t.timeout, cwd=s.root,
                               env={**os.environ, 'HIVE_TOOL_ARGS': payload, 'HIVE_TOOL_CALLER': a.name})
            if p.returncode: st, err = 'error', f'exit {p.returncode}: {clip(p.stderr.strip() or p.stdout.strip(), 4000)}'
            else: res = clip(p.stdout, 20000)
        except subprocess.TimeoutExpired: st, err = 'error', f'timed out after {t.timeout:g}s'
        except OSError as e: st, err = 'error', f'could not run {argv[0]}: {e}'
        with s.db.tx() as c:
            i = c.execute('INSERT INTO calls(tool,src,owner,args,state,result,err,ts,doneAt) VALUES(?,?,?,?,?,?,?,?,?)',
                          (t.name, a.id, t.owner, payload, st, None if res is None else dumps(res), err, now(), now())).lastrowid
            s.log.add(c, a.id, 'tool.ran', f'ran {t.name}: {st}', f'tool:{t.name}', wf=a.wf)
        return {'call': f'c{i}', 'tool': t.name, 'state': st} | ({'error': err} if err else {'result': res})
