import asyncio, json, os, socket, subprocess, sys, textwrap, time

import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

from hive import Hive
from hive.run import Runner

AGENT = textwrap.dedent('''
    import asyncio, json, os, re, sys
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters

    cfg = json.load(open(sys.argv[1]))['mcpServers']['hive']

    async def main():
        async with Client(StdioServerParameters(command=cfg['command'], args=cfg['args'], env={**os.environ, **cfg['env']})) as c:
            async def call(n, **a):
                r = await c.call_tool(n, a)
                if r.is_error: raise SystemExit(f'{n} failed: {r.content[0].text}')
                return json.loads(r.content[0].text.split('\\n-----')[0])
            me, t = await call('me'), os.environ['HIVE_TASK']
            task = (await call('task', id=t))['task']
            await call('take', id=t)
            if task['kind'] == 'verify':
                await call('verify', id=task['checks'], ok=True, notes=f"{me['name']} re-read notes.txt and found both lines filled")
                return
            if task['kind'] == 'compose':
                m = await call('material', of=task['node'])
                fs = sorted({*re.findall(r'\\bf\\d+\\b', ' '.join(e.get('findings', '') for e in m['children']))})
                cp = await call('compose', of=task['node'], text=f"{len(fs)} findings: both slots of notes.txt were filled and verified", sources=fs)
                return await call('done', id=t, result=f"composed {cp['composition']} from {len(fs)} findings")
            if task['kind'] == 'distill':
                h = await call('harvest', of=task['node'])
                ev = [re.findall(r'\\bf\\d+\\b', b['findings'])[0] for b in h['branches'] if b['findings']]
                i = await call('distill', title='Split slot edits merge cleanly', body='Agents editing separate lines of one file finish without conflicts.',
                               kind='reusable', evidence=ev)
                return await call('done', id=t, result=f"saved {i['insight']} ({i['status']})")
            await call('read', path='notes.txt')
            slot = 'ALPHA' if 'alpha' in task['title'] else 'BETA'
            await call('edit', path='notes.txt', edits=[{'old': f'{slot}: todo', 'new': f"{slot}: done by {me['name']}"}])
            await call('note', text=f"{me['name']} filled {slot}", refs=['notes.txt'])
            await call('done', id=t, result=f"filled {slot} in notes.txt")

    asyncio.run(main())
''')


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def cli(root, *a, env=None, stdin=''):
    return subprocess.run([sys.executable, '-m', 'hive', '--db', str(root/'.hive'/'hive.db'), '--root', str(root), *a], input=stdin, text=True,
                          capture_output=True, env={**os.environ, **(env or {})}, timeout=60)


def body(r): return json.loads(r.content[0].text.split('\n-----')[0])


def testRunnerAgentsSpeakMcpOverStdio(root, tmp_path):
    (root/'notes.txt').write_text('ALPHA: todo\nkeep\nBETA: todo\n')
    (a := tmp_path/'agent.py').write_text(AGENT)
    h = Hive.open(root/'.hive'/'hive.db', root)
    h.op().plan([{'key': 'a', 'title': 'fill alpha', 'verify': True}, {'key': 'b', 'title': 'fill beta'}])
    lines = []
    r = Runner(h, {'default': [sys.executable, str(a), '{mcp}']}, cap=2, poll=.1, say=lines.append).run(120)
    logs = '\n'.join(p.read_text() for p in (h.cfg.dir/'run').glob('*.log'))
    assert r['stuck'] == {}, logs
    text = (root/'notes.txt').read_text()
    assert 'ALPHA: done by implementer-t1' in text and 'BETA: done by implementer-t2' in text and 'keep' in text, logs
    assert h.tasks.get(1).state == 'done' and 'approved' in h.tasks.get(3).result
    kinds = [e.kind for e in h.log.find(limit=500)]
    assert kinds.count('file.changed') == 2 and kinds.count('finding') >= 3 and 'task.verified' in kinds
    ks = {t.kind: t for t in h.db.q('SELECT * FROM tasks')}
    assert r['counts'] == {'done': 5} and ks['compose'].result.startswith('composed cp1') and 'saved in1' in ks['distill'].result, logs
    assert set(json.loads(h.db.one('SELECT covers FROM comps').covers)) == {f.id for f in h.db.q('SELECT id FROM findings')}
    got = h.join('later', 'researcher').recall('slot edits merge')['insights'][0]
    assert got['state'] == 'established' and got['support'] >= 2 and got['by'] == 'distiller-t5'
    h.close()


async def testHttpServerEndToEnd(root):
    p = port()
    srv = subprocess.Popen([sys.executable, '-m', 'hive', '--db', str(root/'.hive'/'hive.db'), '--root', str(root), 'mcp', '--http', '--port', str(p)],
                           env={**os.environ, 'HIVE_KEY': 'sesame'}, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        for _ in range(100):
            try:
                socket.create_connection(('127.0.0.1', p), .2).close()
                break
            except OSError: time.sleep(.1)
        async with Client(f'http://127.0.0.1:{p}/mcp') as c:
            assert (await c.call_tool('join', {'name': 'mallory', 'role': 'coordinator'})).is_error
            boss = body(await c.call_tool('join', {'name': 'boss', 'role': 'coordinator', 'key': 'sesame'}))['token']
            assert (await c.call_tool('me', {})).is_error
            kid = body(await c.call_tool('spawn', {'goal': 'look at the logs', 'role': 'researcher', 'launch': 'none', 'agent': boss}))
            f = body(await c.call_tool('note', {'text': 'logs rotate hourly', 'agent': kid['token']}))
            assert f['path'] == 'boss/boss.rese1'
            tree = body(await c.call_tool('tree', {'of': 'me', 'agent': boss}))['tree']
            assert 'boss.rese1' in tree
    finally:
        srv.terminate()
        srv.wait(10)


async def testSharedToolsAndViewsAcrossProcesses(root):
    mk = lambda n: StdioServerParameters(command=sys.executable, args=['-m', 'hive', '--db', str(root/'.hive'/'hive.db'), '--root', str(root), 'mcp',
                                                                      '--agent', n], env={**os.environ, 'HIVE_SUMMARIZER': 'extract'})
    async with Client(mk('alice')) as a, Client(mk('bob')) as b:
        call = lambda c, n, **k: c.call_tool(n, k)
        await call(a, 'offer', name='square', about='squares n', schema={'type': 'object', 'properties': {'n': {'type': 'integer'}}, 'required': ['n']})
        cur = body(await call(b, 'watch', of='alice'))['cursor']

        async def serve():
            while True:
                for m in body(await call(a, 'wait', secs=10))['messages']:
                    if m.get('kind') == 'call': return body(await call(a, 'answer', id=m['data']['call'], result=m['data']['args']['n']**2))

        srv = asyncio.create_task(serve())
        assert body(await call(b, 'call', name='square', args={'n': 7}, wait=20))['result'] == 49 and (await srv)['state'] == 'done'
        assert (await call(b, 'call', name='square', args={'n': 'x'})).is_error
        seen = body(await call(b, 'watch', of='alice', since=cur))
        assert 'tool.answered' in json.dumps(seen['events'])
        later = asyncio.create_task(call(b, 'watch', of='alice', since=seen['cursor'], wait=15))
        await asyncio.sleep(.5)
        await call(a, 'note', text='squares stay under 2**31 for n below 46341')
        got = body(await later)['events']
        assert len(got) == 1 and '46341' in got[0]
        win = body(await call(b, 'watch', of='alice', view='window', limit=2))
        assert len(win['events']) == 2 and win['older'] and body(await call(b, 'watch', of='alice', view='window', before=win['older']))['events']
        s = body(await call(b, 'watch', of='alice', view='summary', budget=400))
        assert s['events'] >= 3 and 'square' in s['summary']


def testHookCommandEndToEnd(root):
    h = Hive.open(root/'.hive'/'hive.db', root)
    h.join('hooky')
    bob = h.join('bob')
    env = {'HIVE_AGENT': 'hooky'}
    r = cli(root, 'hook', 'post', env=env, stdin=json.dumps({'toolName': 'run_terminal_command', 'toolInput': {'command': 'make test'}, 'cwd': str(root)}))
    assert r.returncode == 0 and r.stdout == ''
    assert any(e.text == 'run_terminal_command: make test' for e in h.log.find(kinds=['activity']))
    bob.send('hooky', 'stop and rebase first', 'interrupt')
    r = cli(root, 'hook', 'post', env=env, stdin=json.dumps({'toolName': 'read_file', 'toolInput': {'target_file': 'x'}, 'cwd': str(root)}))
    out = json.loads(r.stdout)
    assert out['decision'] == 'block' and 'stop and rebase first' in out['reason']
    stop = json.loads(cli(root, 'hook', 'stop', env=env, stdin='{}').stdout)
    assert stop['decision'] == 'block' and 'unacknowledged' in stop['reason']
    (root/'m.py').write_text('a = 1\n')
    edit = {'toolName': 'search_replace', 'toolInput': {'file_path': str(root/'m.py')}, 'cwd': str(root)}
    assert cli(root, 'hook', 'pre', env=env, stdin=json.dumps(edit)).returncode == 0
    (root/'m.py').write_text('a = 2\n')
    cli(root, 'hook', 'post', env=env, stdin=json.dumps(edit))
    v = h.db.one("SELECT v,origin,agent FROM vers WHERE path='m.py' ORDER BY v DESC LIMIT 1")
    assert (v.v, v.origin, v.agent) == (2, 'sync', h.agents.named('hooky').id)
    assert cli(root, 'hook', 'post', stdin='{}', env={'HIVE_AGENT': ''}).returncode == 0
    h.close()


def testCliInitPlanStatusTreeInsights(tmp_path):
    ws = tmp_path/'proj'
    ws.mkdir()
    run = lambda *a: subprocess.run([sys.executable, '-m', 'hive', *a], cwd=ws, capture_output=True, text=True, timeout=60)
    assert run('init').returncode == 0 and (ws/'.hive'/'config.toml').exists()
    (ws/'plan.json').write_text(json.dumps({'tasks': [{'key': 'x', 'title': 'first'}, {'title': 'second', 'after': ['x']}]}))
    assert json.loads(run('plan', 'plan.json').stdout)['created'][1]['state'] == 'pending'
    st = run('status').stdout
    assert 'operator' in st and 'pending=1' in st and 'ready=1' in st
    assert 'operator · coordinator' in run('tree').stdout
    assert run('insights').returncode == 0
    assert run('tasks').stdout.count('\n') == 2


@pytest.mark.parametrize('n', [3])
def testManyProcessesShareOneSessionThroughMcp(root, tmp_path, n):
    (root/'notes.txt').write_text(''.join(f'SLOT{i}: todo\n' for i in range(n)))
    script = tmp_path/'writer.py'
    script.write_text(textwrap.dedent('''
        import asyncio, json, os, sys
        from mcp.client import Client
        from mcp.client.stdio import StdioServerParameters
        db, root, i = sys.argv[1:4]
        async def main():
            p = StdioServerParameters(command=sys.executable, args=['-m', 'hive', '--db', db, '--root', root, 'mcp', '--agent', f'w{i}'], env=dict(os.environ))
            async with Client(p) as c:
                await c.call_tool('read', {'path': 'notes.txt'})
                r = await c.call_tool('edit', {'path': 'notes.txt', 'edits': [{'old': f'SLOT{i}: todo', 'new': f'SLOT{i}: w{i}'}]})
                assert not r.is_error, r.content[0].text
        asyncio.run(main())
    '''))
    procs = [subprocess.Popen([sys.executable, str(script), str(root/'.hive'/'hive.db'), str(root), str(i)], stderr=subprocess.PIPE, text=True) for i in range(n)]
    errs = [p.communicate(timeout=120)[1] for p in procs]
    assert all(p.returncode == 0 for p in procs), errs
    assert (root/'notes.txt').read_text() == ''.join(f'SLOT{i}: w{i}\n' for i in range(n))
