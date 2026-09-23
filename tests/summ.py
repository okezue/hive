import httpx, pytest

from hive.summ import Extract, Fail, Llm, Summ, backend, chunks, size
from hive.util import toks


class Fake:
    name = 'fake'

    def __init__(s): s.calls = []

    def __call__(s, text, focus, target):
        s.calls.append(text)
        return f'S{len(s.calls)}[{len(text.splitlines())} lines]'


def log(n): return [f'#{i} alice file.changed: app.py v{i} line {i} changed with some detail text' for i in range(n)]


def testShortInputIsVerbatim():
    r = Summ(Fake())(['a', 'b'], 100, 'x')
    assert r.text == 'a\nb' and r.method == 'verbatim'


def testSingleChunkOneCall():
    f = Fake()
    r = Summ(f, chunk=3000)(log(40), 50, 'x')
    assert len(f.calls) == 1 and r.levels == 1 and r.method == 'fake'


def testHierarchicalReduction():
    f = Fake()
    r = Summ(f, chunk=200)(log(400), 100, 'x')
    assert r.chunks > 10 and r.levels >= 2 and toks(r.text) <= 100


def testCacheReusesStableChunks(hive):
    f = Fake()
    s = Summ(f, hive.db, chunk=200)
    s(log(300), 100, 'x')
    first = len(f.calls)
    r = s(log(310), 100, 'x')
    assert r.cached > 0 and len(f.calls)-first < first


def testFallbackOnFailure():
    def bad(text, focus, target): raise Fail('down')
    r = Summ(bad, chunk=200)(log(100), 80, 'x')
    assert r.method == 'extractive' and r.text


def testChunksRespectCap():
    cs = chunks(log(100) + ['x'*5000], 200)
    assert all(size(c) <= 200 for c in cs) and sum(len(c) for c in cs) > 100


def testExtractKeepsImportantLines():
    ls = [f'#{i} bob file.read: read a.py' for i in range(50)] + ['#99 bob task.failed: t3 failed: tests broke']
    out = Extract()('\n'.join(ls), 'x', 40)
    assert 'task.failed' in out and 'omitted' in out and toks(out) <= 60


def testBackendChoice(monkeypatch):
    for k in ('XAI_API_KEY', 'HIVE_LLM_API_KEY', 'HIVE_SUMMARIZER'): monkeypatch.delenv(k, raising=False)
    assert isinstance(backend({}), Extract)
    with pytest.raises(Fail): backend({'backend': 'llm'})
    monkeypatch.setenv('XAI_API_KEY', 'k')
    b = backend({})
    assert isinstance(b, Llm) and b.url == 'https://api.x.ai/v1' and b.model == 'grok-4.5'
    monkeypatch.setenv('HIVE_SUMMARIZER', 'extractive')
    assert isinstance(backend({}), Extract)


def testLlmBackendRequest(monkeypatch):
    seen = {}

    def post(url, headers, timeout, json):
        seen.update(url=url, auth=headers['Authorization'], body=json)
        return httpx.Response(200, json={'choices': [{'message': {'content': ' short '}}]}, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', post)
    assert Llm('https://x/v1/', 'key', 'm')('text', 'focus', 100) == 'short'
    assert seen['url'] == 'https://x/v1/chat/completions' and seen['auth'] == 'Bearer key' and seen['body']['model'] == 'm'
    monkeypatch.setattr(httpx, 'post', lambda *a, **k: httpx.Response(500, request=httpx.Request('POST', 'https://x')))
    with pytest.raises(Fail): Llm('https://x', 'k', 'm')('t', 'f', 10)
