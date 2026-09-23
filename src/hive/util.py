import hashlib, json, re, secrets, time

from .err import Bad

now = time.time
NAME = re.compile(r'^[A-Za-z][\w.-]{0,63}$')


class R(dict):
    def __getattr__(s, k):
        try: return s[k]
        except KeyError: raise AttributeError(k) from None

    __setattr__ = dict.__setitem__


def row(cur, r):
    return R(zip([d[0] for d in cur.description], r))


def sha(t): return hashlib.sha256(t.encode()).hexdigest()


def dumps(v): return json.dumps(v, ensure_ascii=False, separators=(',', ':'), default=str)


def J(t, d=None): return d if t is None or t=='' else json.loads(t)


def token(n): return f'{n}.{secrets.token_urlsafe(6)}'


def name(n, what='name'):
    if not isinstance(n, str) or not NAME.match(n):
        raise Bad(f'invalid {what} {n!r}', 'a letter, then up to 63 letters, digits, _ . -')
    return n


def pid(p, v, what):
    if isinstance(v, int) and not isinstance(v, bool): return v
    t = str(v or '').strip()
    t = t[len(p):] if t.startswith(p) else t
    if not t.isdigit(): raise Bad(f'invalid {what} id {v!r}', f'like {p}12')
    return int(t)


def toks(t): return (len(t)+3)//4


def clip(t, n, m=' …'): return t if len(t) <= n else t[:max(0, n-len(m))] + m


def line(t, n=160): return clip(' '.join(str(t).split()), n)


def an(w): return ('an ' if w[:1].lower() in 'aeiou' else 'a ') + w


def hms(ts): return time.strftime('%H:%M:%S', time.localtime(ts))


def ago(ts):
    if ts is None: return None
    d = max(0, int(now()-ts))
    return f'{d}s ago' if d<60 else f'{d//60}m ago' if d < 3600 else f'{d//3600}h{d%3600//60:02d}m ago'


def poll(f, secs, d=.05, cap=.5):
    end = time.monotonic() + max(0., secs)
    while not (r := f()) and time.monotonic() < end:
        time.sleep(min(d, max(0., end-time.monotonic())))
        d = min(cap, d*1.6)
    return r
