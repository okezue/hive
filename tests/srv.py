import json, os

import pytest
from mcp.client import Client

from hive.srv import DOCS, GROUPS, build, groups, render


def body(r):
    t = r.content[0].text
    return json.loads(t.split('\n-----')[0]) if not r.is_error else t


async def testToolSurface(hive):
    async with Client(build(hive)) as c:
        ts = {t.name: t for t in (await c.list_tools()).tools}
    assert set(ts) == {'join', *' '.join(GROUPS.values()).split()} and set(ts) == set(DOCS)
    edit = ts['edit'].input_schema
    assert edit['required'] == ['path', 'edits'] and 'agent' in edit['properties']
    assert 'token' in edit['properties']['agent']['description']
    async with Client(build(hive, ('core',))) as c:
        assert {t.name for t in (await c.list_tools()).tools} == {'join', *GROUPS['core'].split()}


async def testSharedConnectionNeedsTokens(hive, root):
    (root/'a.txt').write_text('one\ntwo\n')
    async with Client(build(hive)) as c:
        a = body(await c.call_tool('join', {'name': 'alice'}))
        assert a['token'] and 'charter' in a['brief'].lower()
        assert body(await c.call_tool('me', {}))['name'] == 'alice'
        b = body(await c.call_tool('join', {'name': 'bob'}))
        r = await c.call_tool('me', {})
        assert r.is_error and 'several agents' in r.content[0].text
        r = await c.call_tool('read', {'path': 'a.txt', 'agent': a['token']})
        assert '----- a.txt v1 (lines 1-2) -----\none\ntwo\n' in r.content[0].text
        r = body(await c.call_tool('edit', {'path': 'a.txt', 'edits': [{'old': 'two', 'new': 'TWO'}], 'agent': 'bob'}))
        assert r['status'] == 'applied'
        await c.call_tool('send', {'to': 'alice', 'body': 'look', 'mode': 'interrupt', 'agent': b['token']})
        o = body(await c.call_tool('overview', {'agent': a['token']}))
        assert list(o)[0] == 'interrupts' and o['interrupts'][0]['body'] == 'look' and 'updates' in o['notices']


async def testErrorsCarryNotices(hive):
    async with Client(build(hive)) as c:
        a = body(await c.call_tool('join', {'name': 'alice', 'role': 'observer'}))
        hive.join('bob').send('alice', 'ping', 'interrupt')
        r = await c.call_tool('put', {'key': 'k', 'value': 1, 'agent': a['token']})
        assert r.is_error and 'observer' in r.content[0].text and 'ping' in r.content[0].text


async def testPlanAndTaskFlowOverMcp(hive):
    async with Client(build(hive)) as c:
        co = body(await c.call_tool('join', {'name': 'co', 'role': 'coordinator'}))['token']
        im = body(await c.call_tool('join', {'name': 'im'}))['token']
        r = body(await c.call_tool('plan', {'agent': co, 'tasks': [{'key': 'a', 'title': 'A', 'verify': True}, {'title': 'B', 'after': ['a']}]}))
        assert [t['state'] for t in r['created']] == ['ready', 'pending']
        t = body(await c.call_tool('take', {'agent': im}))['task']['id']
        assert body(await c.call_tool('done', {'id': t, 'result': 'ok', 'agent': im}))['task']['state'] == 'in_review'


async def testEnvIdentity(hive, monkeypatch):
    monkeypatch.setenv('HIVE_AGENT', 'envy')
    monkeypatch.setenv('HIVE_ROLE', 'researcher')
    async with Client(build(hive)) as c:
        assert body(await c.call_tool('me', {}))['role'] == 'researcher'
    async with Client(build(hive)) as c:
        assert body(await c.call_tool('me', {}))['name'] == 'envy'


def testRender():
    assert json.loads(render({'a': 1}, {'queued': '1'})) == {'a': 1, 'notices': {'queued': '1'}}
    assert list(json.loads(render({'a': 1}, {'interrupts': [1], 'interruptsHint': 'h'})))[:2] == ['interrupts', 'interruptsHint']
    assert json.loads(render([1])) == {'result': [1]}


def testGroups(monkeypatch):
    assert groups('core,files') == ('core', 'files') and groups() == tuple(GROUPS)
    with pytest.raises(SystemExit): groups('nope')


async def testStdioProcess(root):
    import sys

    from mcp.client.stdio import StdioServerParameters
    (root/'s.txt').write_text('hi\n')
    p = StdioServerParameters(command=sys.executable, args=['-m', 'hive', '--db', str(root/'.hive'/'hive.db'), '--root', str(root), 'mcp',
                                                            '--agent', 'stdio', '--role', 'implementer'], env=dict(os.environ))
    async with Client(p) as c:
        assert body(await c.call_tool('me', {}))['name'] == 'stdio'
        assert body(await c.call_tool('read', {'path': 's.txt'}))['version'] == 1
