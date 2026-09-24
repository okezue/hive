import argparse, json, os, shutil, subprocess, sys, threading, time
from pathlib import Path

from hive import Hive
from hive.run import Runner

HIVE = str(Path(sys.executable).parent/'hive')
BASE = Path('/tmp/hive-live')
MODEL = 'grok-4.7-build-fast'
HOOKS = {'hooks': {'SessionStart': [{'hooks': [{'type': 'command', 'command': f'{HIVE} hook start'}]}],
                   'PreToolUse': [{'matcher': 'Edit|Write', 'hooks': [{'type': 'command', 'command': f'{HIVE} hook pre'}]}],
                   'PostToolUse': [{'hooks': [{'type': 'command', 'command': f'{HIVE} hook post'}]}],
                   'Stop': [{'hooks': [{'type': 'command', 'command': f'{HIVE} hook stop'}]}]}}
RULES = ('The MCP server named "hive" connects you with the other agents working in this folder. Read every Hive notice that comes back with '
         'tool results or hook feedback, and act on interrupts before anything else.')


def grok(turns, prompt=None, file=None):
    return ['grok', *(['--prompt-file', file] if file else ['-p', prompt]), '--cwd', '{root}', '-m', MODEL, '--sandbox', 'workspace',
            '--permission-mode', 'bypassPermissions', '--max-turns', str(turns), '--output-format', 'json', '--no-auto-update', '--rules', RULES]


def workspace(name, files, hooks=False):
    d = BASE/name
    shutil.rmtree(d, ignore_errors=True)
    (d/'.grok').mkdir(parents=True)
    for k, v in files.items(): (d/k).write_text(v)
    (d/'.grok'/'config.toml').write_text(f'[mcp_servers.hive]\ncommand = "{HIVE}"\nargs = ["mcp"]\nstartup_timeout_sec = 60\n')
    if hooks:
        (d/'.grok'/'hooks').mkdir()
        (d/'.grok'/'hooks'/'hive.json').write_text(json.dumps(HOOKS))
    subprocess.run([HIVE, 'init'], cwd=d, capture_output=True, check=True)
    # grok loads .grok/hooks only inside a git repository
    subprocess.run(['git', 'init', '-q'], cwd=d, check=True)
    return d


def env(d, **kw): return {**os.environ, 'GROK_FOLDER_TRUST': '0', 'HIVE_GLOBAL': str(d/'global.db'), **kw}


def agent(d, who, role, prompt, turns=60, secs=1200):
    argv = [x.replace('{root}', str(d)) for x in grok(turns, prompt)]
    t = time.time()
    p = subprocess.run(argv, env=env(d, HIVE_AGENT=who, HIVE_ROLE=role), capture_output=True, text=True, timeout=secs, cwd=d)
    (d/'out').mkdir(exist_ok=True)
    (d/'out'/f'{who}.json').write_text(p.stdout + '\n' + p.stderr[-4000:])
    try: text = json.loads(p.stdout).get('text', '')
    except ValueError: text = p.stdout[-500:]
    print(f'  {who} finished in {time.time()-t:.0f}s (exit {p.returncode}): {text[:160]!r}', flush=True)
    return text


def together(*runs):
    ts = [threading.Thread(target=lambda r=r: r()) for r in runs]
    for t in ts: t.start()
    for t in ts: t.join()


class Checks:
    def __init__(s, name): s.name, s.rows = name, []

    def __call__(s, ok, what):
        s.rows.append((bool(ok), what))
        print(f"  {'PASS' if ok else 'FAIL'}  {what}", flush=True)


def coedit(c):
    d = workspace('coedit', {'config.py': 'TIMEOUT = 10\nRETRIES = 3\n\n\ndef connect(host):\n    return f"connecting to {host}"\n\n\ndef close(conn):\n'
                             '    return None\n'}, hooks=True)
    how = ('Work only through the hive tools, never your own file tools: first hive read config.py, then make your changes with hive edit. For '
           'the TIMEOUT change pass base=1 (the version you read). If an edit reports a conflict, or you get an interrupt about a merge request, '
           'talk to the other author with hive send (thread set to the merge request id, for example mr1), agree on a single TIMEOUT value, and '
           'settle it: one of you calls hive propose, the other hive respond. After your edits call hive wait(secs=40) and repeat until no merge '
           'request or interrupt waits on you. Acknowledge interrupts with hive ack once handled. Finally reply with the TIMEOUT value in the file.')
    together(lambda: agent(d, 'alice', 'implementer', f'You are alice. Change connect() so it returns f"connecting to {{host}} (timeout {{TIMEOUT}})", '
                                                     f'and set TIMEOUT to 30. {how}'),
             lambda: agent(d, 'bob', 'implementer', f"You are bob. Change close() so it returns 'closed', and set TIMEOUT to 60. {how}"))
    h, text = Hive.open(d/'.hive'/'hive.db', d), (d/'config.py').read_text()
    c('(timeout {TIMEOUT})' in text and "return 'closed'" in text, "both agents' changes to different functions are in config.py")
    c(text.count('TIMEOUT =') == 1 and compile(text, 'config.py', 'exec'), 'config.py has one TIMEOUT line and still compiles')
    mrs = h.db.q('SELECT * FROM mrs')
    c(mrs, 'the overlapping TIMEOUT edits opened a merge request')
    c(mrs and all(m.state in ('resolved', 'abandoned') for m in mrs), f"every merge request was settled: {[m.state for m in mrs]}")
    names = h.agents.names()
    talk = {names.get(m.src) for m in h.db.q("SELECT src FROM msgs WHERE thread LIKE 'mr%' AND src IS NOT NULL")}
    c({'alice', 'bob'} <= talk, f'both authors wrote in the merge request thread: {sorted(filter(None, talk))}')
    c(not h.db.q("SELECT id FROM msgs WHERE mode='interrupt' AND ackAt IS NULL"), 'no interrupt is left unacknowledged')
    h.close()


def hooks(c):
    d = workspace('hooks', {'util.py': 'def parse(s):\n    return s.split(",")\n\n\ndef helper(x):\n    return x * 2\n\n\ndef total(xs):\n    return sum(xs)\n'},
                  hooks=True)
    h = Hive.open(d/'.hive'/'hive.db', d)
    bob = h.join('bob')
    bob.read('util.py')
    bob.edit('util.py', [{'old': '    return sum(xs)', 'new': '    return sum(x for x in xs if x is not None)'}])
    carol = h.join('carol')

    sent = []

    def nudge():
        for _ in range(1200):
            if h.db.q("SELECT 1 FROM events WHERE agent=? AND kind='activity'", (carol.id,)):
                sent.append(bob.send('carol', 'Also rename helper() to assist() in util.py while you are there.', 'interrupt'))
                return
            time.sleep(.25)

    threading.Thread(target=nudge, daemon=True).start()
    agent(d, 'carol', 'implementer', 'You are carol. Using your own file tools (read_file and search_replace, not the hive MCP tools), add a one-line '
                                     'docstring to parse() in util.py. Follow any Hive notices that arrive with tool results. Reply with a summary.')
    text = (d/'util.py').read_text()
    c(h.db.one("SELECT COUNT(*) n FROM events WHERE agent=? AND kind='activity'", (carol.id,)).n >= 2, "the post hook logged carol's tool calls")
    c(sent, 'the interrupt was sent once carol was active')
    c(h.db.q("SELECT 1 FROM vers WHERE path='util.py' AND agent=? AND origin LIKE 'sync%'", (carol.id,)), "carol's native edits were synced into Hive")
    c('if x is not None' in text, "bob's earlier Hive edit survived carol's native edits")
    c('"""' in text or "'''" in text, 'carol added the docstring')
    c('def assist(' in text, 'carol followed the interrupt delivered through the hook')
    c(sent and not h.db.q("SELECT id FROM msgs WHERE dst=? AND mode='interrupt' AND ackAt IS NULL", (carol.id,)), 'carol acknowledged the interrupt')
    h.close()


def runner(c):
    d = workspace('runner', {'text.py': '', 'README.md': '# text utils\n'})
    h = Hive.open(d/'.hive'/'hive.db', d)
    h.op().plan([{'key': 'code', 'title': 'Implement slugify(text) in text.py', 'role': 'implementer', 'verify': True, 'paths': ['text.py', 'test_text.py'],
                  'about': 'slugify lowercases, turns every run of non-alphanumeric characters into one hyphen, and strips hyphens at the ends. '
                           'Add test_text.py with plain asserts under if __name__ == "__main__" and run it.'},
                 {'key': 'docs', 'title': 'Document slugify in README.md', 'role': 'implementer', 'after': ['code'], 'paths': ['README.md']}])
    r = Runner(h, {'default': grok(60, file='{promptFile}')}, cap=2, poll=1, say=lambda t: print('  [run]', t, flush=True),
               env={'GROK_FOLDER_TRUST': '0', 'HIVE_GLOBAL': str(d/'global.db')}).run(1800)
    c(r['stuck'] == {}, f"the runner finished the plan: {r['counts']}")
    c(h.tasks.get(1).state == 'done' and any('approved' in (t.result or '') for t in h.db.q("SELECT result FROM tasks WHERE kind='verify'")),
      'the implementation passed independent verification')
    ok = subprocess.run([sys.executable, '-c', "from text import slugify; assert slugify('  Hello, World!! ') == 'hello-world', slugify('  Hello, World!! ')"],
                        cwd=d, capture_output=True, text=True)
    c(ok.returncode == 0, f'slugify works: {ok.stderr.strip()[-200:]}')
    c('slugify' in (d/'README.md').read_text(), 'the dependent docs task ran after the code task and documented slugify')
    c(h.db.one("SELECT COUNT(*) n FROM findings WHERE kind IN ('result','verdict')").n >= 3, 'results and the verdict became findings')
    ts = h.db.q('SELECT * FROM tasks ORDER BY id')
    comp, last = [t for t in ts if t.kind == 'compose'], max(t.doneAt or 0 for t in ts if t.kind in ('work', 'verify'))
    c(len(comp) == 1 and comp[0].ts >= last, f'one compose task was filed, after the whole plan settled: {[(t.id, t.state) for t in comp]}')
    cp = h.db.one("SELECT * FROM comps WHERE node=(SELECT id FROM agents WHERE name='runner') ORDER BY id DESC LIMIT 1")
    work = {f.id for f in h.db.q("SELECT f.id FROM findings f JOIN agents a ON a.id=f.agent WHERE a.role NOT IN ('composer','distiller')")}
    c(cp and work <= set(json.loads(cp.covers)), f"the composer covered every finding of the plan: {cp and f'cp{cp.id}'} {sorted(work)}")
    c(any(t.kind == 'distill' and t.state == 'done' for t in ts), 'the distill task that follows a root composition finished')
    h.close()


def tree(c):
    code = ('import time\n\n\ndef {f}(order):\n    for attempt in range(5):\n        try:\n            return _send(order)\n        except:\n            pass\n'
            '        time.sleep(attempt)\n    return None\n\n\ndef _send(order):\n    raise TimeoutError("{f} backend timed out")\n')
    d = workspace('tree', {'billing.py': code.format(f='charge') + '\n\ndef invoice(order):\n    return {"total": order["amount"] * 1.2}\n',
                           'shipping.py': code.format(f='ship') + '\n\ndef label(order):\n    return order["address"].upper()\n'})
    h = Hive.open(d/'.hive'/'hive.db', d)
    lead = h.join('lead', 'coordinator')
    ask = ('Review {m} for reliability problems. Record every concrete problem you find with hive note (kind problem, refs like {m}:12) as you go. '
           'Finish with done, summarizing the problems.')
    lead.spawn(ask.format(m='billing.py') + ' Also spawn one helper with hive spawn (role researcher, launch runner) to review invoice() in billing.py, '
               'gather its result, and include it in your summary.', 'researcher', budget=2, launch='runner', deliver='the reliability problems in billing.py')
    lead.spawn(ask.format(m='shipping.py'), 'researcher', budget=0, launch='runner', deliver='the reliability problems in shipping.py')
    r = Runner(h, {'default': grok(60, file='{promptFile}')}, cap=3, poll=1, say=lambda t: print('  [run]', t, flush=True),
               env={'GROK_FOLDER_TRUST': '0', 'HIVE_GLOBAL': str(d/'global.db')}).run(2400)
    c(r['stuck'] == {}, f"the runner finished every task, including the automatic compose and distill tasks: {r['counts']}")
    deep = h.db.q('SELECT a.name, t.state FROM agents a JOIN tasks t ON t.id=a.deleg WHERE a.depth=2')
    c(deep and all(x.state == 'done' for x in deep), f'a runner-launched researcher spawned its own runner child that finished: {[tuple(x.values()) for x in deep]}')
    branches = {p.split('/')[1] for f in h.db.q("SELECT agent FROM findings WHERE kind!='result'") if (p := h.tree.path(f.agent)).startswith('lead/')}
    c(len(branches) == 2, f'both branches recorded findings with note: {sorted(branches)}')
    g = lead.gist('lead')
    c(g['composition'], f"a composer composed the lead's subtree (covers everything: {g.get('fresh')})")
    per = {h.agents.names().get(x.node): x.n for x in h.db.q("SELECT node, COUNT(*) n FROM tasks WHERE kind='compose' AND creator IS NULL GROUP BY node")}
    c(per and all(n == 1 for n in per.values()), f'each node got one automatic compose task: {per}')
    ins = h.know.recall('retry exception timeout swallow', limit=5)
    c(ins, f"a distiller saved insights: {[(x['insight'], x['state'], x['support'], x['title']) for x in ins]}")
    c(any(x['support'] >= 2 for x in ins), 'at least one insight is backed by both independent branches')
    nxt = Hive.open(d/'.hive'/'sessions'/'next.db', d)
    tips = nxt.know.tips('add retries with backoff and error logging to the payment client')
    c(tips, f'a new session finds the saved insight for a related goal: {tips[:1]}')
    nxt.close()
    h.close()


SCENARIOS = {'coedit': coedit, 'hooks': hooks, 'runner': runner, 'tree': tree}


def main():
    global MODEL
    p = argparse.ArgumentParser(description='Drive real Grok agents through Hive and check the results.')
    p.add_argument('only', nargs='*', help=' '.join(SCENARIOS))
    p.add_argument('--model', default=MODEL)
    a = p.parse_args()
    if bad := set(a.only) - set(SCENARIOS): p.error(f"unknown scenarios: {' '.join(sorted(bad))}")
    MODEL = a.model
    report = {}
    for n in a.only or SCENARIOS:
        print(f'== {n}', flush=True)
        c, t = Checks(n), time.time()
        try: SCENARIOS[n](c)
        except Exception as e: c(False, f'scenario crashed: {e!r}')
        report[n] = {'secs': round(time.time()-t), 'checks': c.rows}
        print(f"== {n}: {sum(ok for ok, _ in c.rows)}/{len(c.rows)} checks passed in {report[n]['secs']}s", flush=True)
    BASE.mkdir(exist_ok=True)
    (BASE/'report.json').write_text(json.dumps(report, indent=1))
    return 0 if all(ok for r in report.values() for ok, _ in r['checks']) else 1


if __name__ == '__main__': sys.exit(main())
