import asyncio, concurrent.futures, os, re, threading

from .err import Bad, Err
from .util import clip, dumps

NAME = re.compile(r'^[a-z][a-z0-9_-]{0,31}$')
VAR = re.compile(r'\$\{([A-Za-z_]\w*)(?::-([^}]*))?\}|\$([A-Za-z_]\w*)')


def expand(v):
    if isinstance(v, str): return VAR.sub(lambda m: os.environ.get(m[1] or m[3], m[2] or ''), v)
    if isinstance(v, list): return [expand(x) for x in v]
    if isinstance(v, dict): return {k: expand(x) for k, x in v.items()}
    return v


def spec(command=None, args=None, env=None, url=None, headers=None, cwd=None):
    if bool(command) == bool(url): raise Bad('give a command (stdio server) or a url (HTTP server), not both')
    if command: return {'command': command, 'args': list(args or []), 'env': dict(env or {})} | ({'cwd': cwd} if cwd else {})
    if args or env: raise Bad('args and env apply to command servers')
    return {'url': url} | ({'headers': dict(headers)} if headers else {})


def target(sp, root):
    sp = expand(sp)
    if u := sp.get('url'):
        if not sp.get('headers'): return u
        from mcp.client.streamable_http import httpx2, streamable_http_client
        return streamable_http_client(u, http_client=httpx2.AsyncClient(headers=sp['headers'], timeout=60))
    from mcp.client.stdio import StdioServerParameters
    env = {k: v for k, v in os.environ.items() if not k.startswith('HIVE_')} | {k: str(v) for k, v in sp.get('env', {}).items()}
    return StdioServerParameters(command=sp['command'], args=sp.get('args', []), env=env, cwd=sp.get('cwd') or str(root))


def text(r):
    out = []
    for c in r.content or []:
        t = getattr(c, 'type', '')
        out.append(c.text if t == 'text' else f"[{t} {getattr(getattr(c, 'resource', None), 'uri', '') or getattr(c, 'mime_type', '')}]")
    return '\n'.join(out)


class Gone(Exception):
    def __init__(s, why, sent=False):
        super().__init__(why)
        s.sent = sent


class Pool:
    def __init__(s, root): s.root, s.loop, s.ws, s.lock = root, None, {}, threading.Lock()

    def up(s):
        with s.lock:
            if s.loop is None:
                s.loop = asyncio.new_event_loop()
                threading.Thread(target=s.loop.run_forever, daemon=True, name='hive-mounts').start()
        return s.loop

    def do(s, name, sp, op, *a, timeout=120.):
        k = (name, dumps(sp))
        f = asyncio.run_coroutine_threadsafe(s.ask(k, sp, op, a), s.up())
        try: return f.result(timeout)
        except concurrent.futures.TimeoutError:
            f.cancel()
            s.forget(key=k)
            raise Err(f'{name} did not answer within {timeout:g}s', 'the connection was reset; call again, or mount it with a longer timeout') from None
        except Gone as e:
            raise Err(f'could not reach MCP server {name}: {e}' + ('; the call may have run before the connection broke, so it was not repeated' if e.sent else ''),
                      'call again, check its command or url with mount, or unmount it') from None

    def forget(s, name=None, key=None, wait=5.):
        if not s.loop: return

        async def go():
            ts = [s.ws.pop(k)[1] for k in list(s.ws) if (k == key if key else name in (None, k[0]))]
            for t in ts: t.cancel()
            if ts: await asyncio.wait(ts, timeout=wait)

        try: asyncio.run_coroutine_threadsafe(go(), s.loop).result(wait+1)
        except Exception: pass

    async def ask(s, k, sp, op, a):
        for i in range(2):
            if (w := s.ws.get(k)) is None or w[1].done():
                q = asyncio.Queue()
                w = s.ws[k] = (q, asyncio.ensure_future(s.serve(sp, q)))
            f = asyncio.get_running_loop().create_future()
            await w[0].put((op, a, f))
            try: return await f
            except Gone as e:
                if i or e.sent: raise

    async def serve(s, sp, q):
        from mcp.client import Client
        from mcp.shared.exceptions import MCPError
        from mcp.types import CONNECTION_CLOSED
        f = None
        try:
            async with Client(target(sp, s.root)) as c:
                while True:
                    op, a, f = await q.get()
                    try: r, bad = await (c.list_tools() if op == 'list' else c.call_tool(*a)), None
                    except MCPError as e:
                        if e.code == CONNECTION_CLOSED and e.message == 'Connection closed': raise
                        r, bad = None, Err(f'the server refused the call: {e.message}')
                    if not f.done(): f.set_exception(bad) if bad else f.set_result(r)
                    f = None
        except asyncio.CancelledError:
            if f and not f.done(): f.cancel()
            raise
        except BaseException as e:
            why = clip(f'{type(e).__name__}: {e}'.strip(': '), 400)
            if f and not f.done(): f.set_exception(Gone(why, True))
            while True:
                try: _, _, g = q.get_nowait()
                except asyncio.QueueEmpty: break
                if not g.done(): g.set_exception(Gone(why))
