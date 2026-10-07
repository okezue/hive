import ctypes, ctypes.util, fcntl, hashlib, os, re, secrets, shlex, shutil, signal, subprocess, sys, threading, time, tomllib
from contextlib import suppress
from pathlib import Path

from .db import Db
from .err import Bad, Err, Missing
from .reg import alive, home as hhome
from .util import J, clip, dumps, now

SCHEMA = '''
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,key TEXT,kind TEXT,root TEXT,state TEXT,slot INTEGER,pid INTEGER,ts REAL,start REAL,end REAL,
  result TEXT);
CREATE INDEX IF NOT EXISTS runKey ON runs(key,state);
CREATE TABLE IF NOT EXISTS asks(run INTEGER,root TEXT,by TEXT,ts REAL,got INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS stats(kind TEXT PRIMARY KEY,peak REAL,secs REAL,jobs INTEGER,n INTEGER);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,val TEXT)
'''
ADD = (('runs', 'pg', 'INTEGER'),)
DEF = {'slots': 2, 'max': 2, 'free': 20, 'floor': 8, 'reserve': 2048, 'priority': 'low', 'jobs': 'auto', 'timeout': 3600, 'pausemax': 1800,
       'linger': 120, 'inputs': [], 'env': {}, 'pass': []}
PASS = ('PATH', 'HOME', 'USER', 'LOGNAME', 'SHELL', 'LANG', 'TMPDIR', 'DEVELOPER_DIR', 'SDKROOT', 'TOOLCHAINS', 'CC', 'CXX', 'CFLAGS', 'CXXFLAGS',
        'CPPFLAGS', 'LDFLAGS', 'RUSTFLAGS', 'RUSTC', 'RUSTUP_HOME', 'RUSTUP_TOOLCHAIN', 'CARGO_HOME', 'GOPATH', 'GOROOT', 'GOFLAGS', 'JAVA_HOME',
        'NODE_ENV', 'MACOSX_DEPLOYMENT_TARGET')
PRE = ('LC_', 'SWIFT', 'XCODE', 'NPM_CONFIG_')
D1 = re.compile(r'^(?P<f>[^\s:][^:\n]*?):(?P<l>\d+):(?:(?P<c>\d+):)?\s*(?P<s>fatal error|error|warning)(?:\[(?P<k>[^\]]+)\])?:\s*(?P<m>.*)$', re.M)
D2 = re.compile(r'^(?P<s>error|warning)(?:\[(?P<k>[^\]]+)\])?:\s*(?P<m>.*)\n\s*--> (?P<f>[^:\n]+):(?P<l>\d+):(?P<c>\d+)', re.M)
D3 = re.compile(r'^(?P<f>[^\s(][^(\n]*)\((?P<l>\d+),(?P<c>\d+)\):\s*(?P<s>error|warning)\s*(?P<k>TS\d+)?:\s*(?P<m>.*)$', re.M)
KEYS = re.compile(r'\{(slot|src|cache|jobs|root|home)\}')
NPM = ('h=$(shasum package-lock.json 2>/dev/null); [ "$h" = "$(cat {cache}/npm.stamp 2>/dev/null)" ] && [ -d node_modules ] || '
       '{ npm ci --prefer-offline --no-audit --no-fund >/dev/null && echo "$h" > {cache}/npm.stamp; } && ')
_lib = {}


def sha(b): return hashlib.sha1(b if isinstance(b, bytes) else b.encode()).hexdigest()


def git(root, *a, inp=None): return subprocess.run(['git', '-C', str(root), *a], input=inp, capture_output=True, check=True).stdout


def rj(f, d):
    try: return J(f.read_text(), d)
    except (OSError, ValueError): return d


def wj(f, v, mode=None):
    (t := f.with_name(f'.{f.name}.{os.getpid()}.{secrets.token_hex(3)}')).write_text(dumps(v))
    if mode: os.chmod(t, mode)
    os.replace(t, f)


def project(root):
    root = Path(root).resolve()
    try:
        top = Path(git(root, 'rev-parse', '--show-toplevel').decode().strip())
        c = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir').decode().strip())
    except (OSError, subprocess.CalledProcessError): return root, None, f"{re.sub(r'[^A-Za-z0-9._-]', '_', root.name)[:40]}-{sha(str(root))[:8]}"
    n = c.parent.name if c.name == '.git' else c.name.removesuffix('.git')
    return top, c, f"{re.sub(r'[^A-Za-z0-9._-]', '_', n)[:40]}-{sha(str(c))[:8]}"


def detect(r):
    if (r/'Cargo.toml').exists():
        return {n: {'cmd': ['cargo', n, '--message-format', 'short']} for n in ('check', 'build', 'test')}
    if (r/'Package.swift').exists():
        return {n: {'cmd': ['swift', n, '--scratch-path', '{cache}/swift', '-j', '{jobs}']} for n in ('build', 'test')}
    if xs := sorted(r.glob('*.xcworkspace')) or sorted(r.glob('*.xcodeproj')):
        x = xs[0]
        return {'build': {'cmd': ['xcodebuild', '-workspace' if x.suffix == '.xcworkspace' else '-project', x.name, '-scheme', x.stem, '-configuration',
                                  'Debug', '-derivedDataPath', '{cache}/dd', '-jobs', '{jobs}', '-quiet', 'build', 'CODE_SIGNING_ALLOWED=NO',
                                  'COMPILER_INDEX_STORE_ENABLE=NO', 'ONLY_ACTIVE_ARCH=YES', 'DEBUG_INFORMATION_FORMAT=dwarf'],
                          'outputs': ['{cache}/dd/Build/Products']}}
    if (r/'go.mod').exists(): return {'check': {'cmd': ['go', 'vet', './...']}, 'build': {'cmd': ['go', 'build', './...']}, 'test': {'cmd': ['go', 'test', './...']}}
    if (r/'package.json').exists():
        sc = rj(r/'package.json', {}).get('scripts', {})
        return ({'check': {'cmd': NPM + 'npx --no-install tsc --noEmit --pretty false'}} if (r/'tsconfig.json').exists() else {}) | \
            {n: {'cmd': NPM + f'npm run -s {n}'} for n in ('build', 'test') if n in sc}
    if (r/'Makefile').exists(): return {'build': {'cmd': ['make', '-j{jobs}']}}
    return {}


def conf(top, home):
    c, ks = dict(DEF), detect(top)
    for f in (home/'config.toml', top/'.hive'/'config.toml'):
        try: b = dict(tomllib.loads(f.read_text()).get('build') or {})
        except (OSError, tomllib.TOMLDecodeError): continue
        ks |= b.pop('kinds', {}) or {}
        c |= b
    return c | {'kinds': ks}


def store(cas, f=None, data=None):
    cas.mkdir(parents=True, exist_ok=True)
    t = cas/f'.t{os.getpid()}-{threading.get_ident()}-{secrets.token_hex(4)}'
    try:
        if data is None:
            with open(f, 'rb') as a, open(t, 'wb') as b: shutil.copyfileobj(a, b, 1 << 20)
        else: t.write_bytes(data)
        hs = hashlib.sha1(b'blob %d\0' % t.stat().st_size)
        with open(t, 'rb') as a:
            while ch := a.read(1 << 20): hs.update(ch)
        h = hs.hexdigest()
        if not (g := cas/h[:2]/h[2:]).exists():
            g.parent.mkdir(exist_ok=True)
            os.replace(t, g)
        return h
    finally: t.unlink(missing_ok=True)


def disk(top, d, cas, out, pre=''):
    try: ls = git(d, 'ls-files', '-s', '-z', '-co', '--exclude-standard').split(b'\0')
    except (OSError, subprocess.CalledProcessError): return
    for e in ls:
        if not e: continue
        p = (e.split(b'\t', 1)[1] if b'\t' in e else e).decode()
        if b'\t' in e and e.split()[0] == b'160000' or p.endswith('/'):
            disk(top, d/p.rstrip('/'), cas, out, pre + p.rstrip('/') + '/')
            continue
        read(d/p, pre+p, cas, out)


def read(f, p, cas, out):
    try:
        if f.is_symlink(): out[p] = [store(cas, data=os.readlink(f).encode()), '120000']
        elif f.is_file(): out[p] = [store(cas, f), '100755' if os.access(f, os.X_OK) else '100644']
    except FileNotFoundError: pass


def snap(top, inputs, cas):
    ps, idx = ['--', *inputs] if inputs else [], {}
    for e in git(top, 'ls-files', '-s', '-z', *ps).split(b'\0'):
        if e:
            m, h, _ = e.split(b'\t', 1)[0].split()
            idx[e.split(b'\t', 1)[1].decode()] = (m.decode(), h.decode())
    dirty = {x.decode() for x in git(top, 'ls-files', '-m', '-d', '-o', '--exclude-standard', '-z', *ps).split(b'\0') if x}
    dirty |= {x[2:].decode() for x in git(top, 'ls-files', '-v', '-z', *ps).split(b'\0') if x and (x[:1] == b'S' or x[:1].islower())}
    if any(p.endswith('.gitattributes') for p in idx) or \
            (Path(git(top, 'rev-parse', '--path-format=absolute', '--git-common-dir').decode().strip())/'info'/'attributes').exists():
        a = git(top, 'check-attr', '-z', '--stdin', 'filter', 'eol', inp=b'\0'.join(p.encode() for p in idx)+b'\0').split(b'\0')
        dirty |= {a[i].decode() for i in range(0, len(a)-2, 3) if a[i+1] == b'filter' and a[i+2] not in (b'unspecified', b'unset')
                  or a[i+1] == b'eol' and a[i+2] == b'crlf'}
    out = {}
    for p, (m, h) in idx.items():
        if p.startswith('.hive/') or p in dirty: continue
        if m == '160000': disk(top, top/p, cas, out, p+'/')
        else: out[p] = [h, m]
    for p in dirty:
        if p.startswith('.hive/') or p in idx and idx[p][0] == '160000': continue
        if p.endswith('/'): disk(top, top/p.rstrip('/'), cas, out, p)
        else: read(top/p, p, cas, out)
    return out


class Odb:
    def __init__(s, common, cas): s.cas, s.p = cas, common and subprocess.Popen(['git', '--git-dir', str(common), 'cat-file', '--batch'],
                                                                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def to(s, h, f):
        if (c := s.cas/h[:2]/h[2:]).exists():
            shutil.copyfile(c, f)
            return True
        if not s.p: return False
        s.p.stdin.write(h.encode()+b'\n')
        s.p.stdin.flush()
        head = s.p.stdout.readline().split()
        if len(head) < 3 or head[1] == b'missing': return False
        n = int(head[2])
        with open(f, 'wb') as o:
            while n:
                o.write(ch := s.p.stdout.read(min(n, 1 << 20)))
                n -= len(ch)
        s.p.stdout.read(1)
        return True

    def text(s, h):
        t = s.cas/f'.r{os.getpid()}-{threading.get_ident()}'
        try: return t.read_bytes() if s.to(h, t) else None
        finally: t.unlink(missing_ok=True)

    def close(s):
        if s.p:
            with suppress(OSError): s.p.stdin.close()
            s.p.wait()


def diff(want, have): return sum(have.get(p) != v for p, v in want.items()) + sum(p not in want for p in have)


def sig(f):
    with suppress(OSError):
        st = os.lstat(f)
        return [st.st_size, st.st_mtime_ns, st.st_ino]
    return None


def clear(src, f):
    for a in reversed(f.relative_to(src).parents[:-1]):
        if (x := src/a).is_symlink() or x.is_file(): x.unlink()
    if f.is_dir() and not f.is_symlink(): shutil.rmtree(f)
    elif f.is_symlink() or f.exists(): f.unlink()


def prune(src, f):
    with suppress(OSError):
        while (f := f.parent) != src and src in f.parents and not any(f.iterdir()): f.rmdir()


def sync(src, want, have, odb, ever=(), sigs=None):
    n, out = 0, {}
    for p in [p for p in (have or ever) if p not in want]:
        f = src/p
        if f.is_symlink() or f.is_file():
            f.unlink()
            n += 1
            prune(src, f)
    for p, (h, m) in want.items():
        f = src/p
        if have.get(p) == [h, m] and (f.exists() or f.is_symlink()) and (sigs is None or p not in sigs or sig(f) == sigs[p]):
            out[p] = sig(f)
            continue
        if p.startswith('/') or '..' in Path(p).parts: raise Err(f'refusing to sync {p!r}')
        clear(src, f)
        f.parent.mkdir(parents=True, exist_ok=True)
        if m == '120000':
            if (d := odb.text(h)) is None: raise Err(f'no content for {p} ({h[:10]})', 'build again')
            os.symlink(d.decode(), f)
        else:
            t = f.with_name(f'.{f.name}.hive~')
            if not odb.to(h, t):
                t.unlink(missing_ok=True)
                raise Err(f'no content for {p} ({h[:10]})', 'the file may have changed again; build again')
            os.chmod(t, 0o755 if m == '100755' else 0o644)
            os.replace(t, f)
        out[p] = sig(f)
        n += 1
    return n, out


def free():
    if sys.platform == 'darwin':
        v, n = ctypes.c_int(0), ctypes.c_size_t(4)
        if libc().sysctlbyname(b'kern.memorystatus_level', ctypes.byref(v), ctypes.byref(n), None, 0) == 0 and v.value: return float(v.value)
    with suppress(OSError, KeyError, ValueError):
        m = {k: int(v.split()[0]) for k, v in (ln.split(':', 1) for ln in open('/proc/meminfo'))}
        return 100.*m['MemAvailable']/m['MemTotal']
    return 100.


def total(): return os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')/2**20


def libc():
    if 'c' not in _lib: _lib['c'] = ctypes.CDLL(ctypes.util.find_library('c'))
    return _lib['c']


def group(pg):
    tot = 0
    if sys.platform == 'darwin':
        if 'p' not in _lib:
            try: _lib['p'] = ctypes.CDLL('/usr/lib/libproc.dylib')
            except OSError: _lib['p'] = None
        if lib := _lib['p']:
            buf = (ctypes.c_int*8192)()
            for p in buf[:max(0, min(8192, lib.proc_listpgrppids(pg, buf, ctypes.sizeof(buf))))]:
                ri = (ctypes.c_uint64*64)()
                if p and lib.proc_pid_rusage(p, 2, ri) == 0: tot += ri[9]
            return tot/2**20
    with suppress(OSError):
        for d in os.listdir('/proc'):
            if d.isdigit():
                with suppress(OSError, ValueError, IndexError):
                    if int(open(f'/proc/{d}/stat').read().rsplit(')', 1)[1].split()[2]) == pg:
                        tot += int(open(f'/proc/{d}/statm').read().split()[1])*os.sysconf('SC_PAGE_SIZE')
    return tot/2**20


def wrap(cmd, pri):
    if pri == 'background': return (['taskpolicy', '-b'] if sys.platform == 'darwin' and shutil.which('taskpolicy') else ['nice', '-n', '19']) + cmd
    return ['nice', '-n', '10'] + cmd if pri == 'low' else cmd


def clone(a, b):
    b.parent.mkdir(parents=True, exist_ok=True)
    t = b.with_name(f'.{b.name}.{os.getpid()}.{secrets.token_hex(3)}')
    flag = ['-c', '-R'] if sys.platform == 'darwin' else ['--reflink=auto', '-a']
    if subprocess.run(['cp', *flag, str(a), str(t)], capture_output=True).returncode:
        shutil.copytree(a, t, symlinks=True) if a.is_dir() else shutil.copy2(a, t)
    if b.is_dir() and not b.is_symlink():
        os.replace(b, old := b.with_name(f'.{b.name}.old{secrets.token_hex(3)}'))
        os.replace(t, b)
        shutil.rmtree(old, ignore_errors=True)
    else: os.replace(t, b)


def newest(p):
    if not p.is_dir() or p.is_symlink(): return p.lstat().st_mtime
    return max([p.lstat().st_mtime, *(os.lstat(os.path.join(d, x)).st_mtime for d, ds, fs in os.walk(p) for x in fs + ds)])


def diags(text, src, cwd):
    out, seen, s = [], set(), src.resolve()
    hits = [(m.start(), m) for rx in (D1, D2, D3) for m in rx.finditer(text)]
    for _, m in sorted(hits, key=lambda x: x[0]):
        p = Path(m['f'].strip())
        p = p if p.is_absolute() else cwd/p
        try: f = str(p.resolve().relative_to(s))
        except (ValueError, OSError): f = str(p)
        sev = 'error' if 'error' in m['s'] else 'warning'
        if (k := (f, m['l'], m['m'].strip())) in seen: continue
        seen.add(k)
        out.append({'file': f, 'line': int(m['l']), 'col': int(m['c'] or 0), 'severity': sev, 'message': clip(m['m'].strip(), 300)} |
                   ({'code': m['k']} if m['k'] else {}))
    return out


def fill(x, vals, q=False): return KEYS.sub(lambda m: shlex.quote(str(vals[m[1]])) if q else str(vals[m[1]]), str(x))


def home(key):
    (h := hhome()/'build'/key).mkdir(parents=True, exist_ok=True)
    return h


def queue(h): return Db(h/'queue.db', schema=SCHEMA, add=ADD)


def show(r, pos=None, by=None):
    return {'build': f'b{r.id}', 'kind': r.kind, 'state': r.state} | ({'position': pos} if pos is not None else {}) | \
        ({'by': by} if by else {}) | J(r.result, {})


def deliver(h, r, top):
    if not (arts := J(r.result, {}).get('artifacts')): return []
    out, got = top/'.hive'/'out'/r.kind, []
    out.mkdir(parents=True, exist_ok=True)
    if not (top/'.hive'/'.gitignore').exists():
        with suppress(OSError): (top/'.hive'/'.gitignore').write_text('*\n!config.toml\n!.gitignore\n')
    with open(out/'.lock', 'a') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        for a in arts:
            d, mark = out/a, out/f'.{a.replace("/", "_")}.run'
            if (s := h/'out'/str(r.id)/a).exists() and not (d.exists() and rj(mark, None) == r.id):
                clone(s, d)
                wj(mark, r.id)
            if d.exists(): got.append(str(d))
    return got


def envOf(c): return {k: v for k, v in os.environ.items() if k in PASS or k.startswith(PRE) or k in (c.get('pass') or [])}


def ask(root, kind=None, wait=120., by='', rid=None, force=False):
    top, common, key = project(root)
    h = home(key)
    q = queue(h)
    if rid is None:
        if common is None: raise Missing(f'{top} is not in a git repository', 'build snapshots files through git; run git init and commit, or build there yourself')
        c = conf(top, h)
        if not (ks := c['kinds']):
            raise Missing('this project has no build commands', f'add [build.kinds.<name>] cmd = [...] to {top}/.hive/config.toml or {h}/config.toml')
        kind = kind or ('build' if 'build' in ks else next(iter(ks)))
        if kind not in ks: raise Missing(f'no build kind {kind!r}', f"kinds here: {', '.join(ks)}")
        man, env = snap(top, c['inputs'], h/'cas'), envOf(c)
        spec = {'kind': kind, **ks[kind], 'env': {**c['env'], **(ks[kind].get('env') or {})}}
        k = sha(dumps(sorted(man.items())) + dumps(spec) + dumps(sorted((x, y) for x, y in env.items() if x != 'TMPDIR')) +
                (str(top) if '{root}' in dumps(spec) else ''))
        with q.tx() as t:
            r = None if force else t.execute("SELECT * FROM runs WHERE key=? AND state='done' ORDER BY id DESC LIMIT 1", (k,)).fetchone()
            if r: t.execute('INSERT INTO asks VALUES(?,?,?,?,0)', (r.id, str(top), by, now()))
            else:
                if x := t.execute("SELECT * FROM runs WHERE key=? AND state IN ('queued','running') ORDER BY id LIMIT 1", (k,)).fetchone(): rid = x.id
                else:
                    rid = t.execute("INSERT INTO runs(key,kind,root,state,ts) VALUES(?,?,?,'queued',?)", (k, kind, str(top), now())).lastrowid
                    (h/'runs').mkdir(exist_ok=True)
                    wj(h/'runs'/f'{rid}.json', {'want': man, 'spec': spec, 'env': env, 'common': str(common), 'top': str(top),
                                                'cfg': {x: c[x] for x in DEF if x not in ('inputs', 'env', 'pass')}}, 0o600)
                t.execute('INSERT INTO asks VALUES(?,?,?,?,0)', (rid, str(top), by, now()))
                start(h, t)
        if r: return show(r) | {'cached': True, 'artifacts': deliver(h, r, top)}
    else:
        try: rid = int(str(rid).strip().lstrip('b'))
        except ValueError: raise Bad(f'{rid!r} is not a build id', 'build ids look like b12') from None
    end, chk = time.monotonic()+max(0., float(wait)), 0.
    while True:
        if (r := q.one('SELECT * FROM runs WHERE id=?', (rid,))) is None: raise Missing(f'no build b{rid} for this project')
        if r.state in ('done', 'error'): return show(r) | ({'artifacts': got} if (got := deliver(h, r, top)) else {})
        if time.monotonic()-chk > 10:
            chk = time.monotonic()
            with q.tx() as t: start(h, t)
        if time.monotonic() >= end:
            pos = q.one("SELECT COUNT(*) n FROM runs WHERE state='queued' AND id<?", (rid,)).n
            return show(r, pos) | {'hint': f'still {r.state}; call build again with id="b{rid}" to wait for it'}
        time.sleep(.5)


def start(h, t):
    if (r := t.execute("SELECT val FROM meta WHERE key='worker'").fetchone()) and now()-J(r.val).get('ts', 0) < 30 and alive(J(r.val).get('pid')): return
    with open(h/'worker.log', 'a') as log:
        p = subprocess.Popen([sys.executable, '-m', 'hive', 'build', '--work', str(h)], cwd=h, stdin=subprocess.DEVNULL, stdout=log,
                             stderr=subprocess.STDOUT, start_new_session=True, env={k: v for k, v in os.environ.items() if not k.startswith('HIVE_AGENT')})
    t.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('worker', dumps({'pid': p.pid, 'ts': now()})))
    threading.Thread(target=p.wait, daemon=True).start()


def recent(root, n=10):
    q = queue(home(project(root)[2]))
    return [show(r, by=sorted({a.by for a in q.q('SELECT DISTINCT by FROM asks WHERE run=?', (r.id,)) if a.by}))
            for r in q.q('SELECT * FROM runs ORDER BY id DESC LIMIT ?', (n,))]


def lock(f):
    f.parent.mkdir(parents=True, exist_ok=True)
    x = open(f, 'a')
    try: fcntl.flock(x, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        x.close()
        return None
    return x


class Worker:
    def __init__(s, h):
        s.h, s.q, s.live, s.stop = Path(h), queue(Path(h)), {}, threading.Event()

    def beat(s):
        while not s.stop.wait(5):
            with suppress(Exception), s.q.tx() as c: c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('worker', dumps({'pid': os.getpid(), 'ts': now()})))

    def gate(s, cfg):
        for i in range(max(1, int(cfg['max']))):
            if g := lock(hhome()/'build'/'.run'/f'{i}.lock'): return g
        return None

    def jobs(s, kind, cfg):
        if str(cfg['jobs']).isdigit(): return int(cfg['jobs'])
        st = s.q.one('SELECT * FROM stats WHERE kind=?', (kind,))
        per = st.peak/max(1, st.jobs) if st and st.peak else 1500.
        return max(1, min(os.cpu_count() or 1, int((total()*free()/100 - cfg['reserve'])//per)))

    def fits(s, kind, cfg):
        if free() < cfg['free']: return False
        if not s.live: return True
        st = s.q.one('SELECT * FROM stats WHERE kind=?', (kind,))
        return bool(st and st.peak) and st.peak*1.25 < total()*free()/100 - cfg['reserve']

    def have(s, n): return rj(s.h/'slots'/str(n)/'manifest.json', {})

    def slot(s, want, cfg):
        for n in sorted((n for n in range(1, max(1, int(cfg['slots']))+1) if n not in s.live), key=lambda n: (diff(want, s.have(n)), n)):
            if sl := lock(s.h/'slots'/str(n)/'lock'): return n, sl
        return None, None

    def reap(s):
        for r in s.q.q("SELECT * FROM runs WHERE state='running'"):
            if r.pg:
                for sg in (signal.SIGCONT, signal.SIGKILL):
                    with suppress(OSError): os.killpg(r.pg, sg)
        with s.q.tx() as c: c.execute("UPDATE runs SET state='queued',slot=NULL,pg=NULL WHERE state='running'")

    def run(s):
        if not (lk := lock(s.h/'worker.lock')): return 0
        with s.q.tx() as c: c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('worker', dumps({'pid': os.getpid(), 'ts': now()})))
        s.reap()
        threading.Thread(target=s.beat, daemon=True).start()
        quiet, linger = time.monotonic(), 120.
        try:
            while True:
                for n, t in list(s.live.items()):
                    if not t.is_alive(): s.live.pop(n)
                for r in s.q.q("SELECT * FROM runs WHERE state='queued' ORDER BY id"):
                    if (f := rj(s.h/'runs'/f'{r.id}.json', None)) is None:
                        with s.q.tx() as c: c.execute("UPDATE runs SET state='error',result=? WHERE id=?", (dumps({'ok': False, 'error': 'its request file is gone'}), r.id))
                        continue
                    cfg, linger = DEF | f['cfg'], float(f['cfg'].get('linger', 120))
                    if not s.fits(r.kind, cfg) or (g := s.gate(cfg)) is None: break
                    n, sl = s.slot(f['want'], cfg)
                    if n is None:
                        g.close()
                        break
                    with s.q.tx() as c: c.execute("UPDATE runs SET state='running',slot=?,pid=?,start=? WHERE id=?", (n, os.getpid(), now(), r.id))
                    (t := threading.Thread(target=s.one, args=(r, f, n, g, sl), daemon=True)).start()
                    s.live[n] = t
                if s.live or s.q.one("SELECT 1 FROM runs WHERE state='queued'"): quiet = time.monotonic()
                elif time.monotonic()-quiet > linger:
                    s.gc()
                    return 0
                time.sleep(.5)
        finally:
            s.stop.set()
            lk.close()

    def gc(s, keep=200, days=7):
        with suppress(Exception):
            old = s.q.q("SELECT id FROM runs WHERE state IN ('done','error') AND id NOT IN (SELECT id FROM runs ORDER BY id DESC LIMIT ?) AND ts<?",
                        (keep, now()-days*86400))
            for r in old:
                for f in (s.h/'runs'/f'{r.id}.json', s.h/'runs'/f'{r.id}.log'): f.unlink(missing_ok=True)
                shutil.rmtree(s.h/'out'/str(r.id), ignore_errors=True)
            with s.q.tx() as c:
                c.executemany('DELETE FROM runs WHERE id=?', [(r.id,) for r in old])
                c.execute('DELETE FROM asks WHERE run NOT IN (SELECT id FROM runs)')
            for d, _, fs in os.walk(s.h/'cas'):
                for x in fs:
                    if now()-os.lstat(p := os.path.join(d, x)).st_mtime > 2*86400: os.unlink(p)

    def one(s, r, f, n, g, sl):
        d, cfg, k = s.h/'slots'/str(n), DEF | f['cfg'], f['spec']
        src, cache, t0, res = d/'src', d/'cache', now(), {}
        src.mkdir(parents=True, exist_ok=True)
        cache.mkdir(parents=True, exist_ok=True)
        try:
            m, busy, pf, sf = d/'manifest.json', d/'manifest.syncing', d/'paths.json', d/'stat.json'
            have, sigs = rj(m, {}), rj(sf, None)
            ever = set(rj(pf, []))
            wj(pf, sorted(ever | set(f['want'])))
            if m.exists(): os.replace(m, busy)
            odb = Odb(f.get('common'), s.h/'cas')
            try: changed, now_ = sync(src, f['want'], have, odb, ever, sigs if have else None)
            finally: odb.close()
            wj(sf, now_)
            wj(m, f['want'])
            busy.unlink(missing_ok=True)
            res = s.go(r, f, k, cfg, d, src, cache, changed, t0, (g, sl))
            st = 'done' if res.pop('cache') else 'error'
        except Exception as e:
            res, st = {'ok': False, 'error': clip(f'{type(e).__name__}: {e}', 500), 'secs': round(now()-t0, 1), 'slot': n}, 'error'
        finally:
            g.close()
            sl.close()
        with s.q.tx() as c:
            c.execute('UPDATE runs SET state=?,end=?,result=?,pg=NULL WHERE id=?', (st, now(), dumps(res), r.id))
            if res.get('peak') and res.get('code') == 0:
                o = c.execute('SELECT * FROM stats WHERE kind=?', (r.kind,)).fetchone()
                c.execute('INSERT OR REPLACE INTO stats VALUES(?,?,?,?,?)', (r.kind, max(res['peak'], o.peak*.8) if o else res['peak'], res['secs'],
                                                                             res['jobs'], (o.n if o else 0)+1))

    def go(s, r, f, k, cfg, d, src, cache, changed, t0, fds):
        cfg = cfg | {x: k[x] for x in ('timeout', 'priority', 'floor', 'jobs', 'pausemax') if x in k}
        jobs = s.jobs(r.kind, cfg)
        v = {'slot': d, 'src': src, 'cache': cache, 'jobs': jobs, 'root': f['top'], 'home': s.h}
        cwd = src/fill(k.get('cwd') or '.', v)
        env = (f.get('env') or {x: y for x, y in os.environ.items() if not x.startswith('HIVE_')}) | {
            'CARGO_TARGET_DIR': str(cache/'target'), 'CARGO_BUILD_JOBS': str(jobs), 'HIVE_JOBS': str(jobs), 'HIVE_SLOT': str(d)} | \
            {x: fill(y, v) for x, y in (k.get('env') or {}).items()}
        env.setdefault('PATH', os.defpath)
        cmd = [fill(x, v) for x in k['cmd']] if isinstance(k['cmd'], list) else ['sh', '-c', fill(k['cmd'], v, True)]
        lf = s.h/'runs'/f'{r.id}.log'
        with open(lf, 'wb') as log:
            p = subprocess.Popen(wrap(cmd, cfg['priority']), cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True, pass_fds=tuple(x.fileno() for x in fds))
        with s.q.tx() as c: c.execute('UPDATE runs SET pg=? WHERE id=?', (p.pid, r.id))
        peak, paused, held, why, last = 0., 0., None, '', time.monotonic()-1.9
        while p.poll() is None:
            time.sleep(.5)
            if time.monotonic()-last >= 2:
                last, peak = time.monotonic(), max(peak, group(p.pid))
            fr = free()
            if held is None and fr < cfg['floor']:
                with suppress(OSError): os.killpg(p.pid, signal.SIGSTOP)
                held = time.monotonic()
            elif held is not None and fr >= cfg['floor']+10:
                with suppress(OSError): os.killpg(p.pid, signal.SIGCONT)
                paused, held = paused+time.monotonic()-held, None
            hold = paused+(time.monotonic()-held if held else 0)
            why = why or ('timeout' if now()-t0-hold > cfg['timeout'] else 'paused' if hold > cfg['pausemax'] else '')
            if why:
                for sg in (signal.SIGCONT, signal.SIGTERM):
                    with suppress(OSError): os.killpg(p.pid, sg)
                with suppress(subprocess.TimeoutExpired): p.wait(15)
                with suppress(OSError): os.killpg(p.pid, signal.SIGKILL)
                p.wait()
        code = p.returncode
        with open(lf, 'rb') as fh:
            fh.seek(max(0, lf.stat().st_size-600_000))
            text = fh.read().decode(errors='replace')
        ds = diags(text, src, cwd)
        errs = [x for x in ds if x['severity'] == 'error']
        arts, names = [], set()
        for o in k.get('outputs') or [] if code == 0 else []:
            a = Path(fill(o, v))
            a = a if a.is_absolute() else cwd/a
            if a.exists() and newest(a) >= t0-1:
                base = next((str(a.relative_to(b)) for b in (cache, src) if b in a.parents), a.name)
                name = next(x for x in (base, *(f'{base}.{i}' for i in range(2, 99))) if x not in names)
                names.add(name)
                clone(a, s.h/'out'/str(r.id)/name)
                arts.append(name)
        stable = code == 0 or (code is not None and 0 < code < 126 and errs and not why)
        return {'cache': bool(stable), 'ok': code == 0, 'code': code, 'secs': round(now()-t0, 1), 'slot': int(d.name), 'synced': changed, 'jobs': jobs,
                'peak': round(peak or 50.)} | ({'paused': round(paused)} if paused else {}) | \
            ({'timedOut': cfg['timeout']} if why == 'timeout' else {'stopped': f"paused for over {cfg['pausemax']}s"} if why else {}) | \
            ({'errors': errs[:40], 'errorCount': len(errs)} if errs else {}) | ({'warnings': len(ds)-len(errs)} if len(ds) > len(errs) else {}) | \
            ({'artifacts': arts} if arts else {}) | ({'tail': '\n'.join(text.rstrip().splitlines()[-30:])} if code != 0 and not errs else {}) | \
            {'log': str(lf)}
