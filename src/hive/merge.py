from difflib import SequenceMatcher
from typing import NamedTuple

from .err import Bad


def lines(t): return t.splitlines(keepends=True)


def sm(a, b): return SequenceMatcher(None, a, b, autojunk=False)


def end(ls):
    ls = list(ls)
    if ls and not ls[-1].endswith('\n'): ls[-1] += '\n'
    return ls


class Ch(NamedTuple):
    lo: int
    hi: int
    new: tuple
    side: int


class Hunk(NamedTuple):
    lo: int
    hi: int
    base: tuple
    ours: tuple
    theirs: tuple

    def where(h):
        if h.lo == h.hi: return f'insertion before base line {h.lo+1}'
        return f'base line {h.hi}' if h.hi-h.lo == 1 else f'base lines {h.lo+1}-{h.hi}'

    def dict(h, i, a='ours', b='theirs'):
        return {'index': i, 'where': h.where(), 'base': ''.join(h.base), a: ''.join(h.ours), b: ''.join(h.theirs)}


PICKS = {'ours': lambda h: [*h.ours], 'theirs': lambda h: [*h.theirs], 'base': lambda h: [*h.base],
         'ours+theirs': lambda h: end(h.ours)+[*h.theirs], 'theirs+ours': lambda h: end(h.theirs)+[*h.ours]}


class Merged(list):
    @property
    def hunks(s): return [x for x in s if isinstance(x, Hunk)]

    @property
    def clean(s): return not s.hunks

    def text(s):
        if not s.clean: raise ValueError('unresolved conflicts')
        return ''.join(x for seg in s for x in seg)

    def marked(s, a='ours', b='theirs'):
        out = []
        for x in s:
            out += [f'<<<<<<< {a}\n', *end(x.ours), '||||||| base\n', *end(x.base), '=======\n', *end(x.theirs), f'>>>>>>> {b}\n'] \
                if isinstance(x, Hunk) else x
        return ''.join(out)

    def pick(s, cs):
        if len(cs) != len(s.hunks): raise Bad(f'expected {len(s.hunks)} resolutions, got {len(cs)}')
        out, it = [], iter(enumerate(cs))
        for n, x in enumerate(s):
            if not isinstance(x, Hunk):
                out += x
                continue
            i, c = next(it)
            if isinstance(c, dict) and 'text' in c: ls = lines(str(c['text']))
            elif (k := c.get('take') if isinstance(c, dict) else c) in PICKS: ls = PICKS[k](x)
            else: raise Bad(f'resolution {i} is {c!r}', "use ours, theirs, base, ours+theirs, theirs+ours, or {'text': ...}")
            if ls and not ls[-1].endswith('\n') and n < len(s)-1: ls[-1] += '\n'
            out += ls
        return ''.join(out)


def changes(b, o, side): return [Ch(i, j, tuple(o[k:l]), side) for t, i, j, k, l in sm(b, o).get_opcodes() if t != 'equal']


def touch(a, b):
    if a.lo == a.hi and b.lo == b.hi: return a.lo == b.lo
    if a.lo == a.hi: a, b = b, a
    # an insertion at the edge of a pure deletion is ambiguous (orphaned decorators, trailing lines); anywhere else at an edge is fine
    if b.lo == b.hi: return a.lo < b.lo < a.hi or (not a.new and a.lo <= b.lo <= a.hi)
    return b.lo < a.hi and a.lo < b.hi


def splice(b, cs, lo, hi):
    out, p = [], lo
    for c in sorted(cs):
        out += b[p:c.lo] + list(c.new)
        p = c.hi
    return out + b[p:hi]


def merge(base, ours, theirs):
    if ours == theirs or theirs == base: return Merged([lines(ours)])
    if ours == base: return Merged([lines(theirs)])
    b, groups = lines(base), []
    for c in sorted(changes(b, lines(ours), 0) + changes(b, lines(theirs), 1)):
        if groups and any(touch(x, c) for x in groups[-1][2]):
            lo, hi, g = groups[-1]
            groups[-1] = (min(lo, c.lo), max(hi, c.hi), g+[c])
        else: groups.append((c.lo, c.hi, [c]))
    out, pos = Merged(), 0

    def emit(ls):
        if ls:
            if out and not isinstance(out[-1], Hunk): out[-1] += ls
            else: out.append(list(ls))

    for lo, hi, g in groups:
        emit(b[pos:lo])
        x, y, r = splice(b, [c for c in g if not c.side], lo, hi), splice(b, [c for c in g if c.side], lo, hi), b[lo:hi]
        if x == y or y == r: emit(x)
        elif x == r: emit(y)
        else: out.append(Hunk(lo, hi, tuple(r), tuple(x), tuple(y)))
        pos = hi
    emit(b[pos:])
    return out or Merged([[]])


class NoMatch(Bad):
    def __init__(s, i): super().__init__(f"edit {i}: 'old' text not found", 're-read the file; it may have changed')


def apply(t, edits):
    for i, e in enumerate(edits):
        old, new = e.get('old', e.get('old_string')), e.get('new', e.get('new_string'))
        if not isinstance(old, str) or not isinstance(new, str): raise Bad(f"edit {i} needs strings 'old' and 'new'")
        if not old: raise Bad(f"edit {i} has an empty 'old'", 'use write to create or replace a whole file')
        if not (n := t.count(old)): raise NoMatch(i)
        if n > 1 and not e.get('all'): raise Bad(f"edit {i}: 'old' occurs {n} times", 'add surrounding text, or set all')
        t = t.replace(old, new, -1 if e.get('all') else 1)
    return t


def rng(a, b):
    n, s = b-a, a+1
    return str(s) if n == 1 else f'{s-1 if not n else s},{n}'


class Diff:
    def __init__(d, old, new):
        d.a, d.b = lines(old), lines(new)
        d.m = sm(d.a, d.b)
        d.ops = d.m.get_opcodes()

    def spans(d):
        return [{'start': k+1, 'end': l, 'added': l-k, 'removed': j-i, 'oldStart': i+1, 'oldEnd': j}
                for t, i, j, k, l in d.ops if t != 'equal']

    def size(d): return sum(max(j-i, l-k) for t, i, j, k, l in d.ops if t != 'equal')

    def text(d, cap=40, n=1):
        if all(o[0] == 'equal' for o in d.ops): return ''
        out = []
        for g in d.m.get_grouped_opcodes(n):
            out.append(f'@@ -{rng(g[0][1], g[-1][2])} +{rng(g[0][3], g[-1][4])} @@\n')
            for t, i, j, k, l in g:
                out += [' '+x for x in d.a[i:j]] if t == 'equal' else ['-'+x for x in d.a[i:j]] + ['+'+x for x in d.b[k:l]]
        out = [x if x.endswith('\n') else x+'\n' for x in out]
        return ''.join(out[:cap] + ([f'... {len(out)-cap} more diff lines\n'] if len(out) > cap else []))

    def remap(d, lo, hi):
        if not d.b: return 1, 1

        def at(i, e):
            for t, i1, i2, j1, j2 in d.ops:
                if i1 <= i < i2: return j1+i-i1+e if t == 'equal' else (j2 if e else j1)
            return len(d.b)

        s = min(at(lo-1, 0), len(d.b)-1)
        return s+1, min(max(at(hi-1, 1) if hi > 0 else 0, s+1), len(d.b))


def say(spans, cap=6):
    out = []
    for r in spans[:cap]:
        w = (f"deleted after line {r['start']-1}" if r['start'] > 1 else 'deleted at top') if not r['added'] else \
            f"line {r['start']}" if r['start'] == r['end'] else f"lines {r['start']}-{r['end']}"
        out.append(f"{w} (+{r['added']}/-{r['removed']})")
    if len(spans) > cap: out.append(f'{len(spans)-cap} more regions')
    return ', '.join(out) or 'no line changes'
