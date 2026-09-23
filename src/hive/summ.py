import os, re
from dataclasses import asdict, dataclass

import httpx

from .util import clip, now, sha, toks

SYSTEM = ('You condense activity logs and reports from software agents working together. Keep what another agent needs to '
          'coordinate: decisions, results, files and line ranges changed, open problems, conflicts, blockers, and who is doing '
          'what. Drop routine noise. Keep identifiers (t3, m12, mr2, paths, versions) exact. Compact plain text, no preamble.')

WEIGHTS = [(re.compile(p, re.I), w) for p, w in (
    (r'\b(fail|error|exception|conflict|reject|blocked|merge|cancel)', 6),
    (r'\b(completed|verified|approved|resolved|done|decid|result|handoff)', 5),
    (r'\b(task\.|took|submitted|progress|context\.set|share)', 3),
    (r'\b(file\.changed|file\.created|edited|created)', 2),
    (r'\b(msg\.|asked|told)', 2),
    (r'\b(file\.read|activity)', -2))]


class Fail(Exception): pass


def size(ls): return sum(toks(x)+1 for x in ls)


def chunks(ls, cap):
    # greedy from the start: old chunks stay identical as the log grows, so their cached summaries keep hitting
    cap, out, cur, used = max(16, cap), [], [], 0
    for x in ls:
        for piece in [x] if toks(x) <= cap else [x[i:i+cap*4-8] for i in range(0, len(x), cap*4-8)]:
            if cur and used+toks(piece)+1 > cap:
                out.append(cur)
                cur, used = [], 0
            cur.append(piece)
            used += toks(piece)+1
    return out+[cur] if cur else out


class Extract:
    name = 'extractive'

    def __call__(s, text, focus, target):
        ls = [x for x in text.splitlines() if x.strip()]
        if size(ls) <= target: return '\n'.join(ls)
        head = f'[{len(ls)} lines condensed]'
        room, n, used, keep = max(8, target-toks(head)-4), len(ls), 0, set()
        score = lambda i: 1+2*i/max(1, n-1)+sum(w for p, w in WEIGHTS if p.search(ls[i]))
        for i in sorted(range(n), key=lambda i: (-score(i), -i)):
            if used+toks(ls[i])+1 <= room:
                keep.add(i)
                used += toks(ls[i])+1
        if not keep:
            i = max(range(n), key=score)
            ls[i], keep = clip(ls[i], room*4), {i}
        out, prev = [head], -1
        for i in sorted(keep):
            if i > prev+1: out.append(f'… {i-prev-1} lines omitted')
            out.append(ls[i])
            prev = i
        return '\n'.join(out + ([f'… {n-prev-1} lines omitted'] if prev < n-1 else []))


class Llm:
    def __init__(s, url, key, model, timeout=60.):
        s.url, s.key, s.model, s.timeout, s.name = url.rstrip('/'), key, model, timeout, f'llm:{model}'

    def __call__(s, text, focus, target):
        try:
            r = httpx.post(f'{s.url}/chat/completions', headers={'Authorization': f'Bearer {s.key}'}, timeout=s.timeout,
                           json={'model': s.model, 'temperature': .2, 'max_tokens': max(64, int(target*1.5)),
                                 'messages': [{'role': 'system', 'content': SYSTEM},
                                              {'role': 'user', 'content': f'Focus: {focus}\nAt most about {target} tokens.\n\n{text}'}]})
            r.raise_for_status()
            out = r.json()['choices'][0]['message']['content']
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e: raise Fail(f'summary request failed: {e}') from e
        if not isinstance(out, str) or not out.strip(): raise Fail('summary request returned nothing')
        return out.strip()


def backend(cfg):
    pick = os.environ.get('HIVE_SUMMARIZER', cfg.get('backend', 'auto'))
    key = os.environ.get('HIVE_LLM_API_KEY') or os.environ.get(cfg.get('api_key_env', 'XAI_API_KEY'), '')
    if pick == 'llm' and not key: raise Fail("the 'llm' summarizer needs HIVE_LLM_API_KEY or XAI_API_KEY")
    if key and pick in ('auto', 'llm'):
        return Llm(os.environ.get('HIVE_LLM_BASE_URL', cfg.get('base_url', 'https://api.x.ai/v1')), key,
                   os.environ.get('HIVE_LLM_MODEL', cfg.get('model', 'grok-4.5')))
    return Extract()


@dataclass
class Summary:
    text: str
    method: str
    source: int
    chunks: int = 1
    levels: int = 0
    calls: int = 0
    cached: int = 0

    def dict(s): return asdict(s)


class Summ:
    def __init__(s, fn, db=None, chunk=3000, depth=6):
        s.fn, s.db, s.chunk, s.depth, s.fallback = fn, db, max(64, chunk), depth, Extract()

    def __call__(s, ls, budget, focus):
        budget, src = max(32, budget), size(ls)
        if src <= budget: return Summary('\n'.join(ls), 'verbatim', src)
        st, items, lv, first = {'calls': 0, 'cached': 0, 'fell': 0}, list(ls), 0, 1
        target = max(48, min(budget, s.chunk//4))
        while size(items) > s.chunk and lv < s.depth:
            cs = chunks(items, s.chunk)
            first = len(cs) if not lv else first
            f = focus if not lv else f'{focus}; these summarize consecutive parts, oldest first'
            red = [s.one('\n'.join(x), f, target, st) for x in cs]
            items = red if size(red) < size(items) else [clip(x, target*4) for x in red]
            lv += 1
        if lv and len(items) == 1 and toks(items[0]) <= budget: text = items[0]
        else:
            text = s.one('\n'.join(items), focus if not lv else f'{focus}; merge these part summaries, oldest first, into one', budget, st)
            lv += 1
        name = getattr(s.fn, 'name', 'custom')
        method = name if not st['fell'] else 'extractive' if st['fell'] == st['calls'] else name+'+extractive'
        return Summary(clip(text, budget*4), method, src, first, lv, st['calls'], st['cached'])

    def one(s, text, focus, target, st):
        key = sha(f"{getattr(s.fn, 'name', 'custom')}|{target}|{focus}|{text}")
        if s.db and (r := s.db.one('SELECT text FROM summs WHERE key=?', (key,))):
            st['cached'] += 1
            return r.text
        st['calls'] += 1
        try: out = s.fn(text, focus, target)
        except Fail:
            st['fell'] += 1
            return s.fallback(text, focus, target)
        if s.db:
            with s.db.tx() as c: c.execute('INSERT OR REPLACE INTO summs VALUES(?,?,?)', (key, out, now()))
        return out
