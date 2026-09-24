import contextlib, datetime, os, random, re, time
from collections import Counter, defaultdict

from .err import Clash, Denied
from .log import fmt
from .util import J, ago, clip, dumps, line, now, pid

ENV = {'rate', 'net'}
HARD = {'auth', 'setup'}
RESUME = {'context', 'turns', 'timeout', 'hang', 'quit'}
FREE = {'lost', 'stopped'}
MADE = ('file.created', 'file.changed', 'progress', 'finding', 'composition', 'insight', 'task.completed', 'task.submitted', 'agent.spawned')
SAY = {'rate': 'was rate limited', 'net': 'hit a network or server error', 'auth': 'failed to authenticate', 'setup': 'could not run its command',
       'context': 'ran out of context', 'turns': 'hit its turn limit', 'timeout': 'ran past its time limit', 'hang': 'stopped responding',
       'quit': 'exited without finishing', 'crash': 'crashed', 'lost': 'was lost when the runner stopped', 'stopped': 'was stopped with the runner'}
FIX = {'context': 'Split the task or narrow what it reads.', 'turns': 'Split the task or raise the agent turn limit.',
       'timeout': 'Split the task or raise [runner] timeout.', 'quit': 'Make the goal and the finishing step explicit.',
       'hang': 'See what it was waiting on; raise [runner] idle if it works long stretches without Hive calls.',
       'crash': 'Read its log, then fix the command or the environment.', 'rate': 'Add a fallback command, lower [runner] max, or wait for the reset.',
       'net': 'Check the network or the provider status, or add a fallback command.', 'auth': 'Fix the credentials, then run hive retry.',
       'setup': 'Install or configure the agent command (its program, API key, or model), then run hive retry.'}
CODE = r'(?:status|error|http|code|api)\W{0,12}'
PATS = [(k, re.compile(p, re.I)) for k, p in (
    ('rate', CODE + r'(?:429|529)\b|\b(?:429|529)\W{0,3}(?:too many|overloaded|rate)|rate.?limit(?:ed|.?exceeded|.?reached|.?error)|too many requests|'
             r'exceeded (?:your )?(?:current )?quota|quota (?:exceeded|exhausted)|resource.?exhausted|overloaded|usage limit|limit reached|'
             r'over capacity|throttled'),
    ('auth', CODE + r'40[13]\b|\b40[13]\W{0,3}(?:unauthori|forbidden)|^(?:unauthori[sz]ed|forbidden)\s*(?::|\(|$)|'
             r'(?:error\W{0,4}|status\W{0,4})(?:unauthori[sz]ed|forbidden|invalid.{0,16}(?:api.?key|token|credential)|'
             r'authentication.?(?:failed|error|required)|(?:token|credential|session)s? (?:has |have )?expired)|'
             r'please run /login|not logged in|log ?in (?:again|required)|credit balance is too low|authentication_error|invalid_api_key|'
             r'invalid x-api-key|incorrect api key provided'),
    ('setup', r'must specify the \w*api.?key|api.?key (?:is )?(?:missing|not (?:set|found|provided))|no api key|command not found|'
              r'executable file not found|unknown model|couldn.t set model|invalid model|model_not_found|'
              r'model\W{1,3}[\w./:-]{1,60}\W{1,3}(?:is not|was not|not) (?:found|available|supported)|model (?:does not exist|is not available)'),
    ('context', r'context.?(?:length|window)|too many tokens|prompt is too long|maximum context|ran out of room|input exceeds'),
    ('turns', r'max(?:imum)?.?(?:session.?)?turns|turn limit'),
    ('net', CODE + r'50[0234]\b|\b50[0234]\W{0,3}(?:internal|bad gateway|service unavailable|gateway)|'
            r'(?:request|connection|connect|read|socket|operation|api|upstream|gateway)\s+timed? ?out|timeout ?error|readtimeout|connecttimeout|'
            r'deadline exceeded|connection (?:reset|refused|error|'
            r'aborted|closed)|econnreset|econnrefused|etimedout|enotfound|network (?:error|is unreachable)|bad gateway|service unavailable|'
            r'internal server error|gateway time-?out|remote ?protocol ?error|stream (?:error|disconnected)|eof occurred|temporarily unavailable|'
            r'name resolution'))]
ERR = re.compile(r'error|exception|fatal|fail|denied|invalid|refused|exceed|reached|unavailable|timed? ?out|too (?:many|long|low)|overloaded|'
                 r'exhausted|expired|throttled|not logged in|/login|ran out of room|maximum context|must specify|not found|missing|usage limit|'
                 r'rate.?limit|quota|forbidden|unauthori|\b(?:429|529|40[13]|50[0234])\b', re.I)
NARR = re.compile(r'^\s*"(text|thought|thinking|content|summary|reasoning|result|message)"\s*:')
FRAME = re.compile(r'^(File "|at |Traceback |During handling)')
CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
HINTS = [re.compile(p, re.I) for p in (
    r'retry.?after\W{0,4}(\d+(?:\.\d+)?\s*(?:ms|s|sec|seconds?|m|mins?|minutes?|h|hours?)?)\b',
    r'(?:try again|retry|resets?|available|wait)\w*\s+(?:in|after)\s+((?:\d+(?:\.\d+)?\s*[a-z]+[\s,]*(?:and\s+)?)+)',
    r'ratelimit.?reset\S*?\W{1,4}((?:\d+(?:\.\d+)?[a-z]+)+|\d+(?:\.\d+)?)',
    r'(?:\||reset\w*\W{1,4})(\d{10})\b')]
CLOCK = re.compile(r'resets?\s+(?:at\s+|on\s+)?(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2}),?\s+(?:at\s+)?)?'
                   r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)(?:\s*\(([\w/+-]+)\))?', re.I)
MONTHS = 'jan feb mar apr may jun jul aug sep oct nov dec'.split()
UNIT = {'ms': .001, 's': 1, 'm': 60, 'h': 3600, 'd': 86400}
PREFIX = ('python', 'node', 'bash', 'sh', 'zsh', 'uv', 'uvx', 'npx', 'bun', 'deno', 'ruby')


def span(x):
    x = x.strip().lower()
    if re.fullmatch(r'\d+(\.\d+)?', x): return float(x)
    got = re.findall(r'(\d+(?:\.\d+)?)\s*(ms|milli[a-z]*|s[a-z]*|m[a-z]*|h[a-z]*|d[a-z]*)', x)
    return sum(float(n)*UNIT['ms' if u.startswith(('ms', 'milli')) else u[0]] for n, u in got) if got else None


def clock(m):
    tz = None
    with contextlib.suppress(Exception):
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(m[6]) if m[6] else None
    at = datetime.datetime.now(tz)
    at = at.replace(month=MONTHS.index(m[1].lower()[:3])+1, day=int(m[2])) if m[1] else at
    at = at.replace(hour=int(m[3]) % 12 + (12 if m[5].lower() == 'pm' else 0), minute=int(m[4] or 0), second=0, microsecond=0)
    # timestamps rather than datetime differences, so a daylight-saving change in between is counted
    ts = lambda d: d.timestamp() if d.tzinfo else time.mktime(d.timetuple())
    d = ts(at)-now()
    if d >= 0: return d
    if m[1]: return ts(at.replace(year=at.year+1))-now() if d < -183*86400 else 60.
    return 60. if d > -3600 else ts(at+datetime.timedelta(days=1))-now()


def hint(ls):
    for x in reversed(ls):
        if m := CLOCK.search(x):
            with contextlib.suppress(ValueError): return min(max(1., clock(m)), 7*86400.)
        for p in HINTS:
            if (m := p.search(x)) and (v := span(m[1])) is not None:
                v = v-now() if v > 1e9 else v
                if v > 0: return min(max(1., v), 7*86400.)
    return None


def classify(code, text, skip=frozenset()):
    if code in (126, 127): return 'setup', f'exit code {code}: the command was not found or cannot run', None
    ls = [x.strip() for x in text.splitlines()[-200:] if x.strip() and len(x) <= 600 and not x[0].isspace() and not NARR.match(x)
          and not FRAME.match(x.strip()) and x.strip() not in skip]
    if code != 0:
        # the harness reports why it stopped in its last lines; earlier lines are tool output and prose
        for x in reversed(ls[-8:]):
            if ERR.search(x):
                for k, p in PATS:
                    if p.search(x): return k, line(x, 240), hint(ls[-8:]) if k in ENV else None
    return ('quit' if code == 0 else 'crash'), (f'exited with code {code}' + (f': {line(ls[-1], 200)}' if ls else '')), None


def backoff(n, lo=5., hi=600.): return min(hi, lo*2**min(n, 30))*random.uniform(.5, 1)


def label(cmd):
    xs = [os.path.basename(cmd[0])]
    if xs[0].startswith(PREFIX) and (rest := [x for x in cmd[1:] if not x.startswith('-')]): xs.append(os.path.basename(rest[0]))
    xs += [cmd[i+1] for i, x in enumerate(cmd[:-1]) if x in ('-m', '--model')]
    return ' '.join(dict.fromkeys(xs))


def clean(t): return CTRL.sub('', t or '')


def tail(path, n=6000):
    try:
        with open(path, 'rb') as f:
            f.seek(max(0, os.path.getsize(path)-n))
            return clean(f.read().decode(errors='replace'))
    except (OSError, TypeError): return ''




def dur(x):
    x = max(0, int(x))
    return f'{x}s' if x < 90 else f'{x//60}m' if x < 5400 else f'{x//3600}h {x % 3600//60}m'


def tag(k): return f'runner [{k}] '


class Faults:
    def __init__(s, h): s.h = h

    def made(s, c, aid, since):
        ids = s.h.agents.below(aid)
        return c.execute(f"SELECT COUNT(*) n FROM events WHERE agent IN ({','.join('?'*len(ids))}) AND ts>? AND kind IN ({','.join('?'*len(MADE))})",
                         (*ids, since, *MADE)).fetchone().n

    def add(s, c, t, aid, cmd, kind, why='', text='', code=None, secs=0., wait=0., made=0, lone=0):
        c.execute('INSERT INTO faults(task,agent,cmd,kind,why,tail,code,secs,wait,ts,made,lone) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                  (t, aid, cmd, kind, clean(why), clean(text), code, secs, wait, now(), made, lone))
        s.h.log.add(c, aid, 'agent.fault', f"t{t} {SAY.get(kind, kind)}" + (f': {line(clean(why), 140)}' if why else '') +
                    (f'; retrying in {dur(wait)}' if wait >= 1 else ''), f'task:t{t}')

    def reset(s, c=None):
        r = (c or s.h.db.conn()).execute("SELECT val FROM meta WHERE key='reset'").fetchone()
        return float(r.val) if r else 0.

    def counts(s, ids):
        out, cut = defaultdict(Counter), s.reset()
        for r in s.h.db.q(f"SELECT task,kind,cmd,made,lone,ts FROM faults WHERE task IN ({','.join('?'*len(ids))}) ORDER BY id", ids) if ids else []:
            if r.kind == 'retry': out[r.task] = Counter()
            elif not (r.kind in ENV | HARD and r.ts <= cut):
                # a rate limit or network error counts against the task only when other agents succeeded on the command meanwhile
                k = 'onward' if r.made and r.kind in RESUME else ('drift' if r.made else r.kind if r.lone else 'held') if r.kind in ENV else r.kind
                out[r.task][k, r.cmd] += 1
        return out

    def brief(s, t, aid=None, budget=700):
        if not (fs := s.h.db.q("SELECT * FROM faults WHERE task=? AND kind!='retry' ORDER BY id", (t.id,))): return ''
        h, names = s.h, s.h.agents.names()
        who = sorted({f.agent for f in fs if f.agent} | ({aid} if aid else set()))
        q = ','.join('?'*len(who))
        out = [f'Hive restarted this task; this is attempt {len(fs)+1}. Everything earlier attempts saved is still in place, as listed below. Rely on '
               'it instead of re-checking finished steps, and spend your turns on what remains.', 'Why earlier attempts stopped:']
        out += [f"- {names.get(f.agent, '?')} {SAY.get(f.kind, f.kind)} after {dur(f.secs)}" + (f': {line(f.why, 160)}' if f.why else '') +
                ('' if f.made or f.kind in ENV | HARD | FREE else ' (it saved no progress)') for f in fs[-6:]]
        if evs := h.db.q(f"SELECT * FROM events WHERE agent IN ({q}) AND kind!='agent.fault' ORDER BY seq", who):
            out += ['What was done (from the Hive log):', h.summ([fmt(e, names, False) for e in evs], budget,
                                                                 'what was already done toward the task: files changed, results, decisions, and what was '
                                                                 'in progress when it stopped').text]
        if vs := h.db.q(f'SELECT path,MAX(v) v FROM vers WHERE agent IN ({q}) GROUP BY path ORDER BY path', who):
            out.append('Files changed: ' + ', '.join(f'{r.path} (v{r.v})' for r in vs[:20]))
        if fd := h.db.q(f'SELECT id,text FROM findings WHERE agent IN ({q}) ORDER BY id DESC LIMIT 8', who):
            out += ['Findings recorded:'] + [f'- f{r.id} {line(r.text, 160)}' for r in fd[::-1]]
        if st := [r.status for r in h.db.q(f"SELECT status FROM agents WHERE id IN ({q}) AND status!=''", who)]:
            out.append('Last progress: ' + ' | '.join(line(x, 160) for x in st))
        if fs[-1].tail.strip(): out += ['Last output before it stopped:', '\n'.join('> '+x for x in clip(fs[-1].tail.strip()[-700:], 700).splitlines())]
        if fs[-1].kind in ('turns', 'context', 'timeout', 'hang'):
            out.append('Work in smaller steps this time and record progress with progress and note as you go, so another restart loses nothing.')
        return clean('\n'.join(out))

    def gates(s, c=None):
        r = (c or s.h.db.conn()).execute("SELECT val FROM meta WHERE key='gates'").fetchone()
        return J(r.val, {}) if r else {}

    def save(s, c, gs): c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('gates', dumps(gs)))

    def resume(s, a, note):
        h = s.h
        h.roles.need(a, 'manage', 'resume paused agent commands')
        with h.db.tx() as c:
            gs = s.gates(c)
            for g in gs.values(): g.update(paused='', hard=False, until=0, strikes=0, since=0, probe=0, hits=0, why='', last='', at=now())
            s.save(c, gs)
            c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('reset', str(now())))
            n = c.execute("UPDATE issues SET state='decided',choice='retry',note=?,doneAt=? WHERE state='open' AND need LIKE 'runner [%'",
                          (note, now())).rowcount
            h.log.add(c, a.id, 'runner.resumed', f"resumed {len(gs)} agent command(s){': '+line(note, 100) if note else ''}", 'runner')
        return {'commands': sorted(gs), 'issuesClosed': n, 'note': 'running runners pick this up on their next step; failures before now stop counting'}

    def retry(s, a, ref=None, note=''):
        if ref is None: return s.resume(a, note)
        from .tasks import DEAD, DOWN
        h = s.h
        with h.db.tx() as c:
            t = h.tasks.get(pid('t', ref, 'task'), c)
            if t.creator != a.id and not h.roles.can(a, 'manage') and not (t.owner and a.id in h.agents.above(t.owner)[1:]):
                raise Denied('only the creator, an ancestor of its owner, or a coordinator can retry a task')
            if t.kind != 'verify' and t.verify and t.state in DEAD and (t.result or '').startswith('verification t') and (v := c.execute(
                    "SELECT * FROM tasks WHERE checks=? AND kind='verify' ORDER BY id DESC LIMIT 1", (t.id,)).fetchone()) and v.state in DEAD:
                t = h.tasks._d(v)
            if t.state not in DEAD and not (t.state == 'ready' and (t.wake or 0) > now()):
                raise Clash(f't{t.id} is {t.state}', 'retry reopens failed, cancelled, or blocked tasks, or skips a retry wait')
            o = t.kind == 'verify' and h.tasks.get(t.checks, c)
            if o and o.state not in (*DEAD, 'in_review'): raise Clash(f't{o.id}, which t{t.id} verifies, is {o.state}')
            ds = c.execute('SELECT d.dep,x.state FROM deps d JOIN tasks x ON x.id=d.dep WHERE d.task=?', (t.id,)).fetchall()
            if bad := [f't{d.dep}' for d in ds if d.state in DEAD]: raise Clash(f"t{t.id} depends on {', '.join(bad)}", 'retry those first')
            k = c.execute("SELECT * FROM agents WHERE deleg=? AND (launch='runner' OR parent=(SELECT id FROM agents WHERE name='runner')) "
                          'ORDER BY id DESC LIMIT 1', (t.id,)).fetchone()
            st = 'ready' if all(d.state == 'done' for d in ds) else 'pending'
            c.execute('UPDATE tasks SET state=?,owner=?,result=NULL,doneAt=NULL,wake=0,notes=? WHERE id=?',
                      (st, k and k.id, dumps([*t.notes, {'by': a.name, 'retried': note or 'retry'}]), t.id))
            if k:
                back = next((x['budget'] for x in reversed(t.notes) if isinstance(x, dict) and 'budget' in x), 0)
                if back and (hr := k.parent and h.agents.heir(c, k.parent)) and (give := min(back, hr.budget)):
                    c.execute('UPDATE agents SET budget=budget-? WHERE id=?', (give, hr.id))
                    c.execute('UPDATE agents SET budget=budget+? WHERE id=?', (give, k.id))
                h.agents.set(c, k.id, state='pending', task=None)
            if o and o.state in DEAD:
                got = (t.about or '').split('Reported result:\n', 1)[-1].split('\n\nCheck the claim', 1)[0]
                c.execute("UPDATE tasks SET state='in_review',result=?,doneAt=NULL WHERE id=?", (got, o.id))
            s.add(c, t.id, a.id, '', 'retry', note)
            dead = f"SELECT 1 FROM deps d JOIN tasks y ON y.id=d.dep WHERE d.task=? AND y.state IN ({','.join('?'*len(DEAD))})"
            for x in [t] + ([o] if o else []):
                # a dependent is unblocked once none of its dependencies is dead; repeat so longer paths settle too
                while sum(c.execute("UPDATE tasks SET state='pending' WHERE id=? AND state='blocked'", (r.id,)).rowcount
                          for r in c.execute(DOWN + 'SELECT id FROM down', (x.id,)).fetchall() if not c.execute(dead, (r.id, *DEAD)).fetchone()): pass
                c.execute(DOWN + "UPDATE tasks SET state='ready' WHERE id IN (SELECT id FROM down) AND state='pending' AND NOT EXISTS "
                          "(SELECT 1 FROM deps d JOIN tasks y ON y.id=d.dep WHERE d.task=tasks.id AND y.state!='done')", (x.id,))
            n = sum(c.execute("UPDATE issues SET state='decided',choice='retry',note=?,doneAt=? WHERE state='open' AND substr(need,1,?)=?",
                              (note, now(), len(p), p)).rowcount for p in {f't{t.id} ', *([f't{o.id} '] if o else [])})
            h.log.add(c, a.id, 'task.retried', f"t{t.id} reopened ({st}){' for '+k.name if k else ''}{': '+line(note, 100) if note else ''}", f'task:t{t.id}')
        return {'task': h.tasks.show(h.tasks.get(t.id)), 'agent': k and k.name, 'issuesClosed': n,
                'note': 'the runner restarts it with a brief of the earlier attempts' if k else 'it is ready for any agent or runner to take'}

    def show(s, limit=20):
        h, names, t = s.h, s.h.agents.names(), now()
        gs = [{'command': k, 'state': ('paused' if g.get('hard') else 'probing') if g.get('paused') else 'cooling' if g.get('until', 0) > t else 'ok',
               'concurrency': round(g.get('cap', 0), 1)} | ({'why': g['why']} if g.get('why') else {}) |
              ({'retryIn': dur(max(g.get('until', 0), g.get('probe', 0) if g.get('paused') else 0)-t)} if max(g.get('until', 0), g.get('probe', 0)) > t else {})
              for k, g in sorted(s.gates().items())]
        fs = [f"t{f.task} {names.get(f.agent, '-')} {SAY.get(f.kind, f.kind) if f.kind != 'retry' else 'retried'}" + (f': {line(f.why, 120)}' if f.why else '') +
              f' ({ago(f.ts)})' for f in h.db.q('SELECT * FROM faults ORDER BY id DESC LIMIT ?', (limit,))]
        wait = [f't{r.id} in {dur(r.wake-t)}' for r in h.db.q("SELECT id,wake FROM tasks WHERE state='ready' AND wake>? ORDER BY wake", (t,))]
        iss = [f'i{r.id} {line(r.need, 200)}' for r in h.db.q("SELECT * FROM issues WHERE state='open' AND (need LIKE 'runner [%' OR options LIKE '%retry%') "
                                                              'ORDER BY id')]
        return {'commands': gs, 'faults': fs, 'waiting': wait, 'issues': iss}
