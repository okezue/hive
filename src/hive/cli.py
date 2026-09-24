import argparse, json, os, sys, time
from pathlib import Path

from . import __version__
from .cfg import init as initDir
from .core import Hive
from .err import Err
from .hook import EVENTS
from .log import fmt
from .prompt import mcp
from .sess import Sess
from .srv import GROUPS


def opened(a): return Hive.open(a.db, a.root, a.session)


def actor(h, a): return Sess(h, h.agents.named(a.who).id) if getattr(a, 'who', None) else h.op()


def dump(v): print(json.dumps(v, ensure_ascii=False, indent=1, default=str))


def init(a):
    root = Path(a.root or '.').resolve()
    d = initDir(root)
    Hive.open(d/'hive.db', root).close()
    print(mcp(['hive', 'mcp'], {'HIVE_DB': str(d/'hive.db'), 'HIVE_ROOT': str(root)}))


def serve(a):
    from .srv import build, groups
    h = opened(a)
    if a.http:
        if a.host not in ('127.0.0.1', 'localhost', '::1') and not os.environ.get('HIVE_KEY'):
            raise SystemExit('set HIVE_KEY before serving beyond localhost')
        return build(h, groups(a.tools), strict=True).run('streamable-http', host=a.host, port=a.port)
    for k, v in (('HIVE_AGENT_TOKEN', a.token), ('HIVE_AGENT', a.agent), ('HIVE_ROLE', a.role), ('HIVE_WORKFLOW', a.workflow)):
        if v: os.environ[k] = v
    build(h, groups(a.tools)).run('stdio')


def config(a):
    h = opened(a)
    env = {'HIVE_DB': str(h.cfg.db), 'HIVE_ROOT': str(h.root)} | ({'HIVE_AGENT': a.agent, 'HIVE_ROLE': a.role or 'implementer'} if a.agent else {})
    print(mcp(['hive', 'mcp'], env))


def status(a):
    v = actor(h := opened(a), a).overview('session')
    if a.json: return dump(v)
    print(h.root)
    for x in v['agents']: print(f"  {x['name']:<18}{x['role']:<13}{x['state']:<8}{x['seen']:<10}{' | '.join(filter(None, [x.get('status'), x.get('task')]))}")
    print('tasks', ' '.join(f'{k}={n}' for k, n in sorted(v['tasks']['counts'].items())) or '-')
    for t in v['tasks']['active']: print(f"  {t['id']:<6}{t['state']:<11}{t['owner'] or '-':<18}{t['title']}")
    for m in v.get('merges', []): print(f"  {m['mr']} {m['path']} {m['requester']} vs {','.join(filter(None, m['with']))}")
    f = h.faults.show(5)
    for g in f['commands']:
        if g['state'] != 'ok': print(f"  {g['command']}: {g['state']}{' '+g['retryIn'] if g.get('retryIn') else ''}{' ('+g['why']+')' if g.get('why') else ''}")
    for x in f['waiting'] + f['issues']: print(' ', x)
    for e in v['recent']: print(' ', e)


def tail(a):
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
    dump(actor(opened(a), a).plan(d['tasks'], a.workflow or d.get('workflow'), a.chain or bool(d.get('chain'))))


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
    return main(a.event, a.format, Hive.open(a.db, a.root, a.session) if a.db or a.root or a.session else None)


def run(a):
    from .run import Runner
    kw = {'say': lambda t: print('[run]', t, flush=True), 'watch': a.watch} | ({'cmds': {'default': a.command}} if a.command else {}) | \
        ({'cap': a.max} if a.max else {})
    r = Runner.fromCfg(opened(a), **kw).run(a.timeout)
    dump(r)
    return 1 if r['stuck'] or r.get('paused') else 0


def parser():
    p = argparse.ArgumentParser(prog='hive')
    p.add_argument('--version', action='version', version=__version__)
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
        opt('--http', action='store_true'), opt('--host', default='127.0.0.1'), opt('--port', type=int, default=8765), name='mcp')
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
    cmd(hook, opt('event', choices=EVENTS), opt('--format', default='claude', choices=['claude', 'text']))
    cmd(run, opt('--max', type=int), opt('--timeout', type=float), opt('--watch', action='store_true'), opt('--command', nargs=argparse.REMAINDER))
    cmd(tree, opt('of', nargs='?'), opt('--depth', type=int, default=2), who=True)
    cmd(insights, opt('query', nargs='*'), opt('--limit', type=int, default=20), who=True)
    cmd(retry, opt('id', nargs='?'), opt('--note', default=''), who=True)
    cmd(faults, opt('--limit', type=int, default=20), opt('--json', action='store_true'), who=True)
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    try: return int(a.f(a) or 0)
    except Err as e:
        print(f'hive: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__': sys.exit(main())
