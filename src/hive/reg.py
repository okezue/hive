import ctypes, os, shlex, subprocess, sys
from contextlib import suppress
from pathlib import Path

from .db import Db
from .util import now

SCHEMA = '''
CREATE TABLE IF NOT EXISTS hives(db TEXT PRIMARY KEY,root TEXT,name TEXT,ts REAL,seen REAL);
CREATE TABLE IF NOT EXISTS binds(pid INTEGER,at TEXT,db TEXT,root TEXT,agent TEXT,token TEXT,harness TEXT,ts REAL,PRIMARY KEY(pid,at))
'''
WRAP = {'sh', 'bash', 'zsh', 'dash', 'fish', 'ksh', 'env', 'nice', 'nohup', 'timeout', 'uv', 'uvx', 'npx', 'npm', 'pnpm', 'bunx', 'caffeinate', 'script', 'sudo', 'xargs'}
PKG = {'@anthropic-ai/claude-code': 'claude', '@google/gemini-cli': 'gemini', '@openai/codex': 'codex', 'opencode-ai': 'opencode'}
KNOWN = ('claude', 'codex', 'grok', 'gemini', 'cursor-agent', 'opencode', 'aider', 'goose', 'amp', 'qwen', 'crush')
PS = '/bin/ps' if os.path.exists('/bin/ps') else 'ps'
_open, _lib = {}, []


class Bsd(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in ('flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid', 'rgid', 'svuid', 'svgid', 'rfu')] + \
        [('comm', ctypes.c_char*16), ('name', ctypes.c_char*32)] + [(n, ctypes.c_uint32) for n in ('nfiles', 'pgid', 'pjobc', 'tdev', 'tpgid')] + \
        [('nice', ctypes.c_int32), ('sec', ctypes.c_uint64), ('usec', ctypes.c_uint64)]


class Short(ctypes.Structure):
    _fields_ = [('pid', ctypes.c_uint32), ('ppid', ctypes.c_uint32), ('pgid', ctypes.c_uint32), ('status', ctypes.c_uint32), ('comm', ctypes.c_char*16),
                ('flags', ctypes.c_uint32), ('uid', ctypes.c_uint32), ('gid', ctypes.c_uint32), ('ruid', ctypes.c_uint32), ('rgid', ctypes.c_uint32),
                ('svuid', ctypes.c_uint32), ('svgid', ctypes.c_uint32), ('rfu', ctypes.c_uint32)]


def lib():
    if not _lib:
        try: _lib.append(ctypes.CDLL('/usr/lib/libproc.dylib'))
        except OSError: _lib.append(None)
    return _lib[0]


def bsd(p, short=False):
    if sys.platform != 'darwin' or not lib(): return None
    b = (Short if short else Bsd)()
    return b if lib().proc_pidinfo(int(p), 13 if short else 3, 0, ctypes.byref(b), ctypes.sizeof(b)) == ctypes.sizeof(b) else None


def alive(p):
    if not p: return False
    try: os.kill(p, 0)
    except ProcessLookupError: return False
    except PermissionError: return True
    except OSError: return False
    return True


def legacy(p):
    try: return subprocess.run([PS, '-o', 'lstart=', '-p', str(p)], capture_output=True, text=True, timeout=5,
                               env={**os.environ, 'TZ': 'UTC', 'LC_ALL': 'C'}).stdout.strip()
    except (OSError, subprocess.SubprocessError): return ''


def stamp(p):
    if b := bsd(p): return f'{b.sec}.{b.usec:06d}'
    try:
        with open(f'/proc/{p}/stat') as f: return f.read().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError): return legacy(p)


def same(p, was):
    if not alive(p): return False
    got = (legacy(p) if ' ' in was else stamp(p)) if was else ''
    return not (was and got and got != was)


def home(): return Path(os.environ.get('HIVE_HOME') or '~/.hive').expanduser()


def mark(on):
    with suppress(OSError): (home()/'bound').touch() if on else (home()/'bound').unlink(missing_ok=True)


def unmark():
    if not (home()/'bound').exists() or not (r := reg()): return
    with suppress(Exception), r.db.tx() as c:
        if not any(alive(x.pid) and os.path.exists(x.db) for x in c.execute('SELECT pid,db FROM binds').fetchall()): mark(False)


def reg():
    p = home()/'hives.db'
    if (r := _open.get(p)) is None:
        try: r = _open[p] = Reg(p)
        except Exception: return None
    return r


def info(p):
    if b := bsd(p): return b.ppid, (b.name or b.comm).decode(errors='replace')
    if b := bsd(p, True): return b.ppid, b.comm.decode(errors='replace')
    try:
        with open(f'/proc/{p}/stat') as f: st = f.read()
        return int(st.rsplit(')', 1)[1].split()[1]), st[st.index('(')+1:st.rindex(')')]
    except (OSError, ValueError, IndexError): pass
    try: out = subprocess.run([PS, '-o', 'ppid=,comm=', '-p', str(p)], capture_output=True, text=True, timeout=5).stdout.split(None, 1)
    except (OSError, subprocess.SubprocessError): return 0, ''
    return (int(out[0]), os.path.basename(out[1].strip().lstrip('-'))) if len(out) == 2 and out[0].isdigit() else (0, '')


def chain(p=None, stop=()):
    out, p = [], p or os.getpid()
    while p > 1 and len(out) < 48:
        q, n = info(p)
        out.append((p, n))
        if q == p or p in stop: break
        p = q
    return out


def args(p):
    try:
        with open(f'/proc/{p}/cmdline', 'rb') as f: return f.read().replace(b'\0', b' ').decode(errors='replace')
    except OSError: pass
    try: return subprocess.run([PS, '-o', 'args=', '-p', str(p)], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError): return ''


def known(w):
    w = os.path.basename(w).lower().lstrip('.')
    return next(('cursor' if k == 'cursor-agent' else k for k in KNOWN if w == k or w.startswith((k+'-', k+'.', k+'_'))), '')


def script(p):
    a = args(p)
    try: ws = shlex.split(a)[1:]
    except ValueError: ws = a.split()[1:]
    for w in ws[:8]:
        if w.startswith('-'): continue
        return known(w) or next((v for x, v in PKG.items() if x in w), '')
    return ''


def host(pid=None):
    for p, n in chain(pid)[1:]:
        if n in WRAP: continue
        k = known(n) or (script(p) if n in ('node', 'bun', 'deno') or n.startswith('python') else '')
        return (p, k) if k else (None, '')
    return None, ''


def inside(root, cwd): return cwd == root or root in cwd.parents


class Reg:
    def __init__(s, path): s.db = Db(path, schema=SCHEMA, add=())

    def seen(s, db, root, name):
        db, t = str(db), now()
        if (r := s.db.one('SELECT seen,root FROM hives WHERE db=?', (db,))) and t-r.seen < 60 and r.root == str(root): return
        with s.db.tx() as c:
            c.execute('INSERT INTO hives VALUES(?,?,?,?,?) ON CONFLICT(db) DO UPDATE SET root=excluded.root,name=excluded.name,seen=excluded.seen',
                      (db, str(root), name, t, t))

    def hives(s):
        rows = s.db.q('SELECT * FROM hives ORDER BY seen DESC')
        if gone := [r.db for r in rows if not os.path.exists(r.db)]:
            with s.db.tx() as c: c.executemany('DELETE FROM hives WHERE db=?', [(g,) for g in gone])
        return [r for r in rows if r.db not in gone]

    def bind(s, pid, db, root, agent, token, harness='', at=None):
        at = stamp(pid) if at is None else at
        with s.db.tx() as c:
            c.execute('DELETE FROM binds WHERE pid=? OR token=?', (pid, token))
            c.execute('INSERT INTO binds VALUES(?,?,?,?,?,?,?,?)', (pid, at, str(db), str(root), agent, token, harness, now()))
            c.executemany('DELETE FROM binds WHERE pid=?', [(r.pid,) for r in c.execute('SELECT DISTINCT pid,db FROM binds').fetchall()
                                                            if not alive(r.pid) or not os.path.exists(r.db)])
        mark(True)

    def unbind(s, pid=None, token=None):
        with s.db.tx() as c:
            c.execute('DELETE FROM binds WHERE pid=? OR token=?', (pid, token))
            if not c.execute('SELECT 1 FROM binds').fetchone(): mark(False)

    def holder(s, pid): return next((r for r in s.db.q('SELECT * FROM binds WHERE pid=?', (pid,)) if same(pid, r.at)), None)


def nearest(rows, pid=None):
    by = {}
    for r in rows:
        if alive(r.pid) and os.path.exists(r.db): by.setdefault(r.pid, []).append(r)
    if not by:
        unmark()
        return None
    for p, _ in chain(pid, set(by)):
        for r in by.get(p, ()):
            if same(p, r.at): return r
    return None


def mine(pid=None, cwd=None):
    if not (p := home()/'hives.db').exists(): return None
    with suppress(Exception):
        d = Db(p, ro=True)
        try: b = nearest(d.q('SELECT * FROM binds'), pid)
        finally: d.close()
        if b and cwd is not None and not inside(Path(b.root).resolve(), Path(cwd).resolve()): return None
        return b
    return None
