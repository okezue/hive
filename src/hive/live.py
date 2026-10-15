import json, os, random, re, signal, subprocess, sys, time
from contextlib import suppress
from fcntl import F_DUPFD_CLOEXEC, fcntl
from pathlib import Path

import anyio

from .reg import alive, home, stamp

SRC, WAKE = Path(__file__).parent, 'hive-resume'
HEAD = re.compile(r'^\{"jsonrpc":"2\.0","id":("[^"]*"|-?\d+),"(?:result|error)"')
pipe = None


def code(): return tuple((p.name, (t := p.stat()).st_mtime_ns, t.st_size) for p in sorted(SRC.glob('*.py')))


def here(): return (d := home()/'live').mkdir(parents=True, exist_ok=True) or d


def put(p, v):
    with suppress(OSError):
        (t := p.with_suffix('.tmp')).write_text(json.dumps(v))
        t.replace(p)


def get(p):
    try: return json.loads(p.read_text())
    except (OSError, ValueError): return None


class Pipe:
    # stdio transport that can swap the running server for a newer version of Hive in place: same process, same pipes, so the harness never
    # sees a disconnect and keeps the session it initialized
    def __init__(s, who=None):
        s.rin, s.wout = fcntl(0, F_DUPFD_CLOEXEC, 3), fcntl(1, F_DUPFD_CLOEXEC, 3)
        n = os.open(os.devnull, os.O_RDONLY)
        os.dup2(n, 0)
        os.close(n)
        os.dup2(2, 1)
        r = json.loads(os.environ.pop('HIVE_RESUME', '') or 'null') or {}
        s.who, s.init, s.listed, s.told = who, r.get('init'), r.get('listed'), set()
        s.pend, s.lines, s.part, s.held, s.code, s.ppid = {}, [], b'', False, code(), os.getppid()
        if s.init: s.lines = [json.dumps({'jsonrpc': '2.0', 'id': WAKE, 'method': 'initialize', 'params': s.init}).encode(),
                              b'{"jsonrpc":"2.0","method":"notifications/initialized"}']
        if who and (w := r.get('who')): who.joined, who.default, who.env = w['joined'], w['default'], w['env']
        s.resumed = bool(r)
        put(here()/f'{os.getpid()}.json', {'ppid': s.ppid, 'since': time.time(), 'resumed': s.resumed})

    def __aiter__(s): return s

    async def __anext__(s):
        s.held = False
        while not s.lines:
            await anyio.wait_readable(s.rin)
            if not (b := os.read(s.rin, 1 << 16)): raise StopAsyncIteration
            *ls, s.part = (s.part + b).split(b'\n')
            s.lines += [x for x in ls if x.strip()]
        s.held, ln = True, s.lines.pop(0)
        s.track(ln)
        return ln.decode('utf-8', 'replace')

    def track(s, ln):
        try: m = json.loads(ln)
        except ValueError: return
        if not isinstance(m, dict) or not isinstance(k := m.get('method'), str): return
        if 'id' in m: s.pend[m['id']] = (k, time.time())
        if k == 'initialize' and m.get('id') != WAKE: s.init = m.get('params')
        elif k == 'notifications/cancelled': s.pend.pop((m.get('params') or {}).get('requestId'), None)
        elif k == 'tools/call' and s.listed is None:
            # the harness listed tools from an earlier server process, so its catalog is whatever that one recorded
            r = get(here()/f'h{s.ppid}.json')
            s.listed = r['tools'] if r and r.get('at') == stamp(s.ppid) else False

    async def write(s, text):
        if m := HEAD.match(text):
            k = json.loads(m[1])
            if (was := s.pend.pop(k, (None,))[0]) and k == WAKE: return
            if was == 'tools/list':
                with suppress(ValueError, KeyError, TypeError):
                    s.listed = [t['name'] for t in json.loads(text)['result']['tools']]
                    put(here()/f'h{s.ppid}.json', {'at': stamp(s.ppid), 'tools': s.listed})
        b = text.encode()
        while b: b = b[os.write(s.wout, b):]

    async def flush(s): pass

    def idle(s):
        t = time.time()
        return not s.held and not s.lines and not s.part.strip() and not any(t-v[1] < 3600 for v in s.pend.values())

    async def watch(s):
        while True:
            await anyio.sleep(2)
            if (c := code()) == s.code: continue
            await anyio.sleep(2 + 3*random.random())
            if code() != c: continue
            s.code = c
            r = await anyio.to_thread.run_sync(lambda: subprocess.run([sys.executable, '-c', 'import hive.cli, hive.srv, hive.hook, hive.live'],
                                                                      capture_output=True, text=True, timeout=120))
            if r.returncode:
                print(f"hive mcp: kept the running version, since the new one fails to import: {(r.stderr.strip().splitlines() or ['?'])[-1]}",
                      file=sys.stderr, flush=True)
                continue
            while not s.idle(): await anyio.sleep(.05)
            if code() == c: s.swap()

    def swap(s):
        w = s.who
        st = {'init': s.init, 'listed': s.listed, 'who': w and {'joined': w.joined, 'default': w.default, 'env': w.env}}
        os.dup2(s.rin, 0)
        os.dup2(s.wout, 1)
        os.execve(sys.executable, sys.orig_argv, os.environ | {'HIVE_RESUME': json.dumps(st)})

    def news(s, aid, tools):
        if aid in s.told or s.listed is None: return None
        miss = sorted(set(tools) - set(s.listed)) if s.listed is not False else None
        if miss == []: return None
        s.told.add(aid)
        how = "Call them through call(name='hive.<tool>', args={...}); tools(query='hive.<tool>') shows a tool's arguments."
        if miss: return f"Hive was updated while your session ran, and your tool list lacks these Hive tools: {', '.join(miss)}. {how}"
        return f"Hive was updated while your session ran, so tools added since it started may be missing from your tool list. {how} " \
               "tools(query='hive') lists every Hive tool."


def news(aid, tools): return pipe.news(aid, tools) if pipe else None


async def serve(srv, who=None):
    global pipe
    from mcp.server.stdio import stdio_server
    pipe = p = Pipe(who)
    try:
        async with stdio_server(p, p) as (r, w), anyio.create_task_group() as tg:
            tg.start_soon(p.watch)
            ll = srv._lowlevel_server
            await ll.run(r, w, ll.create_initialization_options())
            tg.cancel_scope.cancel()
    finally:
        with suppress(OSError): (here()/f'{os.getpid()}.json').unlink()


def servers():
    # stdio Hive MCP servers on this machine: (pid, harness pid, in place), where in place means the server upgrades itself
    try: out = subprocess.run(['ps', '-Ao', 'pid=,ppid=,args='], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError): return []
    rows, me = [], os.getpid()
    for ln in out.splitlines():
        p, pp, *a = ln.split(None, 2)
        a = (a or [''])[0].split()
        # only Python running Hive itself counts: shells, editors and greps that merely mention hive mcp do not
        if int(p) == me or not a or not os.path.basename(a[0]).startswith('python'): continue
        r = a[3:] if a[1:3] == ['-m', 'hive'] else a[2:] if len(a) > 1 and os.path.basename(a[1]) == 'hive' else None
        if r and 'mcp' in r and '--http' not in r: rows.append((int(p), int(pp), (here()/f'{p}.json').exists()))
    return rows


def restart(ppid):
    # end the old-style Hive servers of one harness session, which restarts them on the current version
    n = 0
    for p, pp, new in servers():
        if pp == ppid and not new:
            with suppress(OSError):
                os.kill(p, signal.SIGTERM)
                n += 1
    with suppress(OSError): (home()/'upgrade'/str(ppid)).unlink()
    return n


def tidy():
    u = home()/'upgrade'
    for f in [*here().glob('*.json'), *(u.glob('*') if u.is_dir() else [])]:
        k = f.stem.removeprefix('h')
        if k.isdigit() and not alive(int(k)):
            with suppress(OSError): f.unlink()
