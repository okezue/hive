import json, os, re, sys
from contextlib import suppress

from .core import Hive
from .err import Err, Missing
from .sess import Sess
from .util import clip, line

READS = {'read', 'read_file', 'view', 'notebookread', 'open_file'}
EDITS = {'edit', 'write', 'multiedit', 'notebookedit', 'search_replace', 'edit_file', 'create_file', 'str_replace_editor',
         'str_replace_based_edit_tool', 'apply_patch', 'write_file', 'replace'}
KEYS = ('file_path', 'path', 'target_file', 'notebook_path', 'filePath', 'filename')
PATCH = re.compile(r'^(?:\*\*\* (?:Update|Add) File: (.+)|\+\+\+ b/(.+))$', re.M)
EVENTS = ('pre', 'post', 'prompt', 'stop', 'start', 'end')
NAMES = {'pre': 'PreToolUse', 'post': 'PostToolUse', 'prompt': 'UserPromptSubmit', 'stop': 'Stop', 'start': 'SessionStart'}


class Ev:
    def __init__(e, kind, raw):
        e.kind, e.raw = kind, raw
        e.tool = raw.get('tool_name') or raw.get('toolName') or ''
        inp = raw.get('tool_input') or raw.get('toolInput') or {}
        e.inp = inp if isinstance(inp, dict) else {'input': inp}

    @property
    def sub(e): return bool(e.raw.get('subagentType') or e.raw.get('subagent_type'))

    @property
    def hive(e): return e.tool.lower().startswith(('mcp__hive__', 'hive__'))

    @property
    def edit(e): return e.tool.split('__')[-1].lower() in EDITS

    @property
    def read(e): return e.tool.split('__')[-1].lower() in READS

    def paths(e):
        ps = [e.inp[k] for k in KEYS if isinstance(e.inp.get(k), str)]
        ps += [a or b for k in ('patch', 'input', 'diff') if isinstance(e.inp.get(k), str) for a, b in PATCH.findall(e.inp[k])]
        return list(dict.fromkeys(p.strip() for p in ps if p and p.strip()))

    def says(e):
        d = e.inp
        for k in ('command', 'cmd'):
            if isinstance(d.get(k), str): return f'{e.tool}: {line(d[k], 140)}'
        if ps := e.paths(): return f"{e.tool}: {', '.join(ps[:3])}"
        return next((f'{e.tool}: {line(d[k], 140)}' for k in ('pattern', 'query', 'url', 'prompt', 'description') if isinstance(d.get(k), str)),
                    e.tool)


def who(hive):
    if t := os.environ.get('HIVE_AGENT_TOKEN'): return hive.sess(t)
    if not (n := os.environ.get('HIVE_AGENT')): return None
    try: a = hive.agents.named(n)
    except Missing: a = None
    return Sess(hive, a.id) if a and a.state != 'left' else hive.join(n, os.environ.get('HIVE_ROLE', 'implementer'),
                                                                      os.environ.get('HIVE_WORKFLOW') or None)


def text(n):
    out = [f"INTERRUPT {m['id']} from {m['from']}: {m['body']}" + (' (still unacknowledged)' if m.get('reminder') else '')
           for m in n.get('interrupts', [])]
    if out: out.append('Handle the interrupts first, then acknowledge them with the Hive ack tool.')
    out += [f"Message {m['id']} from {m['from']}: {m['body']}" for m in n.get('messages', [])]
    out += [n['queued']] if n.get('queued') else []
    out += [f'Update: {u}' for u in n.get('updates', [])]
    out += ['Merge requests waiting on you: ' + ', '.join(n['mergesWaitingOnYou'])] if n.get('mergesWaitingOnYou') else []
    return '\n'.join(out + ([n['roleReminder']] if n.get('roleReminder') else []))


def synced(p, r):
    st, out = r.get('status'), []
    if st == 'merged':
        by = ', '.join(sorted({v['author'] for v in r.get('mergedWith', [])}))
        out.append(f"Hive: your edit to {p} was based on an older version, so it was merged with changes by {by}; the file now has "
                   f"both (v{r['version']}). Re-read before editing it again.")
    elif st == 'conflict':
        out.append(f"Hive: your edit to {p} overlaps a newer change by {', '.join(x for x in r.get('with') or [] if x) or 'another author'}. "
                   f"{r.get('note', '')} {r.get('next', '')}".strip())
        out += [f"Conflict {h['index']} at {h['where']}:\nyours:\n{clip(h['requester'], 600)}\ntheirs:\n{clip(h['current'], 600)}"
                for h in r.get('conflicts', [])[:3]]
    out += [f'Hive warning: {w}' for w in r.get('warnings', [])]
    if ob := r.get('openBy'): out.append(f"Hive: {ob[0]['agent']} ({ob[0]['role']}) also has {p} open and was told about your change.")
    return '\n'.join(out), st == 'conflict'


def emit(fmt, ev, ctx=None, deny=None, block=None):
    if fmt == 'text': return deny or block or ctx or ''
    spec, out = {'hookEventName': ev}, {}
    if deny: spec |= {'permissionDecision': 'deny', 'permissionDecisionReason': deny}
    elif ctx and not block: spec['additionalContext'] = clip(ctx, 9500)
    if block: out |= {'decision': 'block', 'reason': clip(block, 9500)}
    return json.dumps(out | ({'hookSpecificOutput': spec} if len(spec) > 1 else {}), ensure_ascii=False)


def handle(kind, raw, hive, x, fmt='claude'):
    if kind not in EVENTS: raise ValueError(f'unknown hook event {kind!r}')
    e = Ev(kind, raw)
    if x is None or e.sub: return None
    cwd = raw.get('cwd') or str(hive.root)

    def mine():
        out = []
        for p in e.paths():
            try: hive.disk.norm(os.path.join(cwd, p))
            except Err: continue
            out.append(os.path.join(cwd, p))
        return out

    if kind == 'pre':
        if not e.edit: return None
        notes = []
        for p in mine():
            r = x.prepare(p)
            if d := r.get('denied'): return emit(fmt, NAMES[kind], deny=f'Hive: {d}. Ask an implementer to make the change.')
            if b := r.get('blocked'):
                return emit(fmt, NAMES[kind], deny=f"Hive: your earlier change to {r['path']} waits in merge request {b}. Settle it first "
                                                   f"(merges('{b}'), talk to the other author, then propose or abandon).")
            notes += [f"Hive: {r['path']} changed since you last looked: v{c['version']} by {c['author']} ({c['changed']}). String "
                      'replacements still apply to the current file; re-read it before rewriting the whole file.' for c in r.get('changedSince', [])]
        return emit(fmt, NAMES[kind], '\n'.join(notes)) if notes else None
    if kind == 'post':
        notes, bad = [], False
        if not e.hive: x.record(e.says())
        for p in mine() if e.read else []:
            with suppress(Err): x.saw(p)
        for p in mine() if e.edit else []:
            try: t, b = synced(os.path.relpath(p, cwd), x.sync(p))
            except Err as err: t, b = f'Hive: {err}', False
            if t: notes.append(t)
            bad |= b
        if n := text(x.notices()):
            notes.append(n)
            bad |= 'INTERRUPT' in n
        return emit(fmt, NAMES[kind], '\n'.join(notes), block='\n'.join(notes) if bad else None) if notes else None
    if kind in ('prompt', 'start'):
        if kind == 'start':
            w = x.welcome()
            t = w['brief'] + '\n\nOthers here: ' + json.dumps(w['others'], ensure_ascii=False)
        else: t = text(x.notices())
        return emit(fmt, NAMES[kind], t) if t else None
    if kind == 'stop':
        if e.raw.get('reason') not in (None, 'end_turn'): return None
        if bs := x.blockers(): return emit(fmt, NAMES[kind], block='Hive: before you stop, ' + '; '.join(bs))
        x.idle()
        return None
    x.leave('session ended')
    return None


def main(kind, fmt='claude', hive=None):
    try:
        raw = sys.stdin.read()
        if not hive and not (os.environ.get('HIVE_AGENT_TOKEN') or os.environ.get('HIVE_AGENT')): return 0
        hive = hive or Hive.open()
        if out := handle(kind, json.loads(raw) if raw.strip() else {}, hive, who(hive), fmt): print(out)
    except Exception as err:
        print(f'hive hook {kind}: {err}', file=sys.stderr)
    return 0
