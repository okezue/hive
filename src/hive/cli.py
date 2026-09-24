import argparse, json, os, sqlite3, sys, time
from pathlib import Path

from . import __version__
from .cfg import git, init as initDir, locate
from .err import Bad, Err, Missing
from .util import EVENTS, GROUPS, ago


def pick(x):
    from .reg import reg
    hs, p = (r.hives() if (r := reg()) else []), Path(x).expanduser()
    if x.isdigit() and 0 < int(x) <= len(hs): h = hs[int(x)-1]
    else:
        q = str(p.resolve())
        h = next((y for y in hs if q in (y.db, y.root)), None) or next((y for y in hs if y.name == x), None) or \
            (m[0] if len(m := [y for y in hs if y.name.startswith(x)]) == 1 else None)
    if h: return h.db, h.root
    if (p/'.hive'/'hive.db').exists(): return str(p.resolve()/'.hive'/'hive.db'), str(p.resolve())
    raise Missing(f'no hive matches {x!r}', 'hive ls lists them by number and name')


def opened(a, make=False):
    from .core import Hive
    db, root = pick(a.hive) if getattr(a, 'hive', None) else (a.db, a.root)
    c = locate(db, root, a.session)
    if not make and not c.db.exists():
        raise Missing(f'no hive at {c.root}', 'hive init makes one here; hive ls lists the hives on this machine; --hive NAME picks one')
    return Hive(c)


def actor(h, a):
    from .sess import Sess
    return Sess(h, h.agents.named(a.who).id) if getattr(a, 'who', None) else h.op()


def dump(v): print(json.dumps(v, ensure_ascii=False, indent=1, default=str))


def init(a):
    from .core import Hive
    from .prompt import mcp
    root = Path(a.root or '.').resolve()
    d = initDir(root)
    Hive.open(d/'hive.db', root).close()
    print(mcp(['hive', 'mcp'], {'HIVE_DB': str(d/'hive.db'), 'HIVE_ROOT': str(root)}))


def serve(a):
    from .core import Hive
    from .srv import Lazy, build, groups
    if a.http:
        if a.host not in ('127.0.0.1', 'localhost', '::1') and not os.environ.get('HIVE_KEY'):
            raise SystemExit('set HIVE_KEY before serving beyond localhost')
        return build(opened(a, True), groups(a.tools), strict=True).run('streamable-http', host=a.host, port=a.port)
    for k, v in (('HIVE_AGENT_TOKEN', a.token), ('HIVE_AGENT', a.agent), ('HIVE_ROLE', a.role), ('HIVE_WORKFLOW', a.workflow)):
        if v: os.environ[k] = v
    db, root = pick(a.hive) if a.hive else (a.db, a.root)
    build(Lazy(lambda: Hive.find(db, root, a.session, a.dir)), groups(a.tools), claims=True).run('stdio')


def config(a):
    from .prompt import mcp
    h = opened(a, True)
    env = {'HIVE_DB': str(h.cfg.db), 'HIVE_ROOT': str(h.root)} | ({'HIVE_AGENT': a.agent, 'HIVE_ROLE': a.role or 'implementer'} if a.agent else {})
    print(mcp(['hive', 'mcp'], env))


def status(a):
    v = actor(h := opened(a), a).overview('session')
    if a.json: return dump(v)
    print(h.root)
    for x in v['agents']:
        print(f"  {x['name']:<18}{x['role']:<13}{x.get('harness', ''):<9}{x['state']:<8}{x['seen']:<10}{' | '.join(filter(None, [x.get('status'), x.get('task')]))}")
    print('tasks', ' '.join(f'{k}={n}' for k, n in sorted(v['tasks']['counts'].items())) or '-')
    for t in v['tasks']['active']: print(f"  {t['id']:<6}{t['state']:<11}{t['owner'] or '-':<18}{t['title']}")
    for m in v.get('merges', []): print(f"  {m['mr']} {m['path']} {m['requester']} vs {','.join(filter(None, m['with']))}")
    f = h.faults.show(5)
    for g in f['commands']:
        if g['state'] != 'ok': print(f"  {g['command']}: {g['state']}{' '+g['retryIn'] if g.get('retryIn') else ''}{' ('+g['why']+')' if g.get('why') else ''}")
    for x in f['waiting'] + f['issues']: print(' ', x)
    for e in v['recent']: print(' ', e)


def tail(a):
    from .log import fmt
    h = opened(a)
    aid = h.agents.named(a.agent).id if a.agent else None
    last = 0
    for e in reversed(h.log.find(agent=aid, limit=a.limit, desc=True)):
        print(fmt(e, h.agents.names()))
        last = e.seq
    last = last or h.log.last()
    while a.follow:
        time.sleep(.5)
        for e in h.log.find(agent=aid, after=last, limit=500):
            print(fmt(e, h.agents.names()), flush=True)
            last = e.seq


def history(a): dump(actor(opened(a), a).watch(a.agent, 'window', before=a.before, limit=a.limit))


def summary(a):
    x = actor(opened(a), a)
    print(x.watch(a.agent, 'summary', budget=a.budget)['summary'] if a.agent else x.digest('session', a.budget)['digest'])


def send(a): dump(actor(opened(a), a).send(a.to, a.body, a.mode, a.thread))


def tasks(a):
    x = actor(opened(a), a)
    if a.id: return dump(x.task(a.id))
    r = x.tasks(a.state, scope='session')
    if a.json: return dump(r)
    for t in r['tasks']:
        print(f"{t['id']:<6}{t['state']:<11}{t['role'] or 'any':<13}{t['owner'] or '-':<18}{t['title']}{' < '+','.join(t['after']) if t['after'] else ''}")


def plan(a):
    d = json.loads(sys.stdin.read() if a.file == '-' else Path(a.file).read_text())
    d = d if isinstance(d, dict) else {'tasks': d}
    dump(actor(opened(a, True), a).plan(d['tasks'], a.workflow or d.get('workflow'), a.chain or bool(d.get('chain'))))


def files(a): dump(actor(opened(a), a).files(a.path))


def insights(a):
    for x in actor(opened(a), a).recall(' '.join(a.query), limit=a.limit)['insights']:
        print(f"{x['insight']:<6}{x['kind']:<9}{x['state']:<12}{x['conf']:<5} {x['title']}")


def tree(a): print(actor(opened(a), a).tree(a.of or '*', a.depth, 50)['tree'])


def retry(a): dump(actor(opened(a), a).retry(a.id, a.note))


def faults(a):
    f = actor(opened(a), a).faults(a.limit)
    if a.json: return dump(f)
    for g in f['commands']: print(f"{g['command']:<32}{g['state']:<9}x{g['concurrency']:<5}{g.get('retryIn', ''):<9}{g.get('why', '')}")
    for k in ('waiting', 'issues', 'faults'):
        if f[k]: print(k, *f[k], sep='\n  ')


def merges(a): dump(actor(opened(a), a).merges(a.id, a.state))


def hook(a):
    from .hook import main
    if not (a.db or a.root or a.session): return main(a.event, a.format)
    from .core import Hive
    return main(a.event, a.format, Hive.open(a.db, a.root, a.session))


def run(a):
    from .run import Runner
    kw = {'say': lambda t: print('[run]', t, flush=True), 'watch': a.watch} | ({'cmds': {'default': a.command or a.harness}} if a.command or a.harness else {}) | \
        ({'cap': a.max} if a.max else {})
    r = Runner.fromCfg(opened(a, True), **kw).run(a.timeout)
    dump(r)
    return 1 if r['stuck'] or r.get('paused') else 0


def ls(a):
    from .db import Db
    from .reg import reg
    out = []
    for i, x in enumerate(reg().hives() if reg() else [], 1):
        d = Db(x.db, ro=True)
        try:
            ags = d.q("SELECT * FROM agents WHERE state!='left' ORDER BY seen DESC")
            n = {r.state: r.n for r in d.q('SELECT state,COUNT(*) n FROM tasks GROUP BY state')}
            last = max([x.seen, *(r.seen or 0 for r in d.q('SELECT seen FROM agents ORDER BY seen DESC LIMIT 1'))])
        except sqlite3.Error: ags, n, last = [], {}, x.seen
        finally: d.close()
        if a.live and not ags: continue
        out.append({'n': i, 'name': x.name, 'root': x.root, 'db': x.db, 'last': ago(last), 'tasks': n,
                    'agents': [{'name': r.name, 'role': r.role, 'state': r.state} | ({'harness': r.harness} if r.get('harness') else {}) for r in ags]})
    if a.json: return dump(out)
    if not out: return print('no hives yet' if not a.live else 'no hive has live agents')
    for h in out:
        ag = ', '.join(f"{g['name']}" + (f" ({g['harness']})" if g.get('harness') else '') for g in h['agents'][:6]) + \
            (f", +{len(h['agents'])-6}" if len(h['agents']) > 6 else '')
        ts = ' '.join(f'{k}={v}' for k, v in sorted(h['tasks'].items()) if k in ('ready', 'running', 'in_review', 'pending', 'failed'))
        print(f"{h['n']:>3}  {h['name']:<22}{len(h['agents']):>2} live  {h['last']:<9} {h['root']}" + (f'\n       {ag}' if ag else '') +
              (f'\n       tasks {ts}' if ts else ''))


def project(a): return Path(a.root).resolve() if a.root else git(Path.cwd().resolve()) or Path.cwd().resolve()


def install(a):
    from .harness import doctor, found, install as put
    root, ns = project(a), a.harness or found()
    if not ns: raise Missing('no agent CLI found on PATH', 'name one: hive install claude|codex|grok|gemini|cursor|opencode')
    bad = 0
    for n in ns:
        ch = put(n, 'project' if a.project else 'user', root, not a.no_hooks, a.dry_run)
        for f, what in ch: print(f'{n}: {what} {f}')
        if not ch: print(f'{n}: already set up')
        if not a.dry_run and not a.no_check: bad += not report(doctor(n, root, native=True))
    return 1 if bad else 0


def uninstall(a):
    from .harness import uninstall as drop
    for n in a.harness:
        ch = drop(n, 'project' if a.project else 'user', project(a), a.dry_run)
        for f, what in ch: print(f'{n}: {what} {f}')
        if not ch: print(f'{n}: nothing to remove')


def report(d):
    print(f"{d['harness']}: {'ok' if d['ok'] else 'not working'}")
    for k in ('bin', 'installed', 'hooks', 'config', 'server', 'native', 'trust', 'note', 'fix'):
        if d.get(k): print(f'  {k:<10}{d[k]}')
    return d['ok']


def doctor(a):
    from .harness import ORDER, doctor as check, found, installed
    root = project(a)
    ns = a.harness or [n for n in ORDER if installed(n, root)] or found()
    if not ns: raise Missing('no agent CLI found on PATH and Hive is installed in none', 'hive install <harness>')
    return 0 if all([report(check(n, root, not a.quick)) for n in ns]) else 1


def start(a):
    from .harness import start as go
    return go(opened(a, True), a.harness, ' '.join(a.prompt), a.role, a.name, a.task, a.print, a.model, a.extra, a.workflow,
              say=lambda t: print(f'hive: {t}', file=sys.stderr, flush=True))


def mount(a):
    x = actor(h := opened(a, True), a)
    if a.frm:
        from .harness import servers
        got = {k: v for k, v in servers(a.frm, h.root).items() if k != 'hive' and (not a.names or k in a.names)}
        if miss := set(a.names) - set(got): raise Missing(f"{a.frm} has no MCP server named {', '.join(sorted(miss))}", f"it has: {', '.join(sorted(got)) or 'none'}")
        bad = 0
        for k, v in got.items():
            n = k.lower().replace('.', '-')[:32]
            try:
                r = x.mount(n, v.get('command'), v.get('args'), v.get('env'), v.get('url'), v.get('headers'), v.get('cwd'), a.timeout)
                print(f"{n}: {len(r['tools'])} tools")
            except Err as e:
                bad += 1
                print(f'{n}: {e}')
        return 1 if bad else 0
    if not a.names:
        for m in x.tools()['mounts']: print(f"{m['name']:<16}{m['tools']:>4} tools  {m['server']}  (by {m['by']})")
        return
    if len(a.names) > 1: raise Bad('mount one server at a time, or use --from')
    kv = lambda xs: dict(y.split('=', 1) for y in xs or [])
    if not a.url and not a.extra: raise Bad('give the server command after --, or --url')
    dump(x.mount(a.names[0], a.extra[0] if a.extra else None, a.extra[1:], kv(a.env), a.url, kv(a.header), None, a.timeout))


def unmount(a): dump(actor(opened(a), a).unmount(a.name))


def parser():
    p = argparse.ArgumentParser(prog='hive')
    p.add_argument('--version', action='version', version=__version__)
    p.add_argument('-H', '--hive', help='a hive from hive ls: number, name, or path')
    p.add_argument('--db')
    p.add_argument('--root')
    p.add_argument('--session')
    sub = p.add_subparsers(dest='cmd', required=True)

    def cmd(f, *args, who=False, name=None):
        q = sub.add_parser(name or f.__name__)
        for x in args: q.add_argument(*x[0], **x[1]) if isinstance(x, tuple) else q.add_argument(x)
        if who: q.add_argument('--as', dest='who')
        q.set_defaults(f=f)
        return q

    opt = lambda *n, **kw: (n, kw)
    cmd(init)
    cmd(serve, opt('--agent'), opt('--role'), opt('--workflow'), opt('--token'), opt('--tools', help=','.join(GROUPS)),
        opt('--http', action='store_true'), opt('--host', default='127.0.0.1'), opt('--port', type=int, default=8765),
        opt('--dir', help='project to use when nothing else names a hive'), name='mcp')
    cmd(config, opt('--agent'), opt('--role'), name='mcp-config')
    cmd(status, opt('--json', action='store_true'), who=True)
    cmd(tail, opt('--agent'), opt('--limit', type=int, default=30), opt('-f', '--follow', action='store_true'))
    cmd(history, 'agent', opt('--before', type=int), opt('--limit', type=int, default=30), who=True)
    cmd(summary, opt('--agent'), opt('--budget', type=int, default=800), who=True)
    cmd(send, 'to', 'body', opt('--mode', default='steer', choices=['queue', 'steer', 'interrupt']), opt('--thread'), who=True)
    cmd(tasks, opt('id', nargs='?'), opt('--state'), opt('--json', action='store_true'), who=True)
    cmd(plan, 'file', opt('--workflow'), opt('--chain', action='store_true'), who=True)
    cmd(files, opt('path', nargs='?'), who=True)
    cmd(merges, opt('id', nargs='?'), opt('--state', default='open'), who=True)
    cmd(hook, opt('event', choices=EVENTS), opt('--format', default='claude', choices=['claude', 'gemini', 'text']))
    cmd(run, opt('--max', type=int), opt('--timeout', type=float), opt('--watch', action='store_true'), opt('--harness'),
        opt('--command', nargs=argparse.REMAINDER))
    cmd(tree, opt('of', nargs='?'), opt('--depth', type=int, default=2), who=True)
    cmd(insights, opt('query', nargs='*'), opt('--limit', type=int, default=20), who=True)
    cmd(retry, opt('id', nargs='?'), opt('--note', default=''), who=True)
    cmd(faults, opt('--limit', type=int, default=20), opt('--json', action='store_true'), who=True)
    cmd(ls, opt('--live', action='store_true'), opt('--json', action='store_true'))
    hs = opt('harness', nargs='*', help='claude, codex, grok, gemini, cursor, opencode (default: every one on PATH)')
    cmd(install, hs, opt('--project', action='store_true'), opt('--no-hooks', action='store_true'), opt('--dry-run', action='store_true'),
        opt('--no-check', action='store_true'))
    cmd(uninstall, opt('harness', nargs='+'), opt('--project', action='store_true'), opt('--dry-run', action='store_true'))
    cmd(doctor, hs, opt('--quick', action='store_true', help="skip asking the harness's own mcp list"))
    cmd(start, opt('harness'), opt('prompt', nargs='*'), opt('--name'), opt('--role', default='implementer'), opt('--task'), opt('--workflow'),
        opt('-p', '--print', action='store_true', help='run headless and print the output'), opt('--model'))
    cmd(mount, opt('names', nargs='*'), opt('--from', dest='frm'), opt('--url'), opt('--env', action='append'), opt('--header', action='append'),
        opt('--timeout', type=float, default=120), who=True)
    cmd(unmount, 'name', who=True)
    return p


def sub(argv):
    i = 0
    while i < len(argv):
        if argv[i] in ('-H', '--hive', '--db', '--root', '--session'): i += 2
        elif argv[i].startswith('-'): i += 1
        else: return argv[i]
    return None


def main(argv=None):
    argv, extra = list(sys.argv[1:] if argv is None else argv), []
    if sub(argv) in ('start', 'mount') and '--' in argv: argv, extra = argv[:argv.index('--')], argv[argv.index('--')+1:]
    a = parser().parse_args(argv)
    a.extra = extra
    try: return int(a.f(a) or 0)
    except Err as e:
        print(f'hive: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__': sys.exit(main())
