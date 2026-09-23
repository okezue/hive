import pytest

from hive import Hive
from hive.err import Bad, Denied


@pytest.fixture
def org(hive):
    lead = hive.join('lead', 'coordinator')
    [t] = lead.plan([{'title': 'investigate the service'}])['created']
    lead.take(t['id'])
    a, b = (hive.sess(lead.spawn(g, 'researcher')['token']) for g in ('map the database layer', 'map the api layer'))
    for x in (a, b): x.take()
    return lead, a, b


def testNotesCarryProvenance(org):
    lead, a, b = org
    f = a.note('the connection pool is capped at 10', refs=['db/pool.py:12'])
    assert f['finding'] == 'f1' and f['path'] == 'lead/lead.rese1'
    b.note('handlers retry three times', 'method')
    assert [x['by'] for x in lead.findings()['findings']] == ['lead.rese2', 'lead.rese1']
    assert [x['text'] for x in a.findings('me', deep=False)['findings']] == ['the connection pool is capped at 10']
    with pytest.raises(Bad): a.note('x', 'rumor')
    with pytest.raises(Bad): a.note('   ')


def testResultsAndVerdictsBecomeFindings(hive, org):
    lead, a, b = org
    a.done(a.agent.deleg, 'database layer mapped: 3 pools, 1 replica')
    imp, ver = hive.join('imp'), hive.join('ver', 'verifier')
    [t] = lead.plan([{'title': 'patch', 'verify': True}])['created']
    imp.take(t['id'])
    imp.done(t['id'], 'patched')
    ver.take()
    ver.verify(t['id'], True, 'tests pass on the patch')
    kinds = {(x['by'], x['kind']) for x in hive.know.findings(lead.agent, 'lead')['findings']}
    assert ('lead.rese1', 'result') in kinds
    allf = hive.db.q('SELECT agent,kind,text FROM findings ORDER BY id')
    names = hive.agents.names()
    assert ('ver', 'verdict') in {(names[r.agent], r.kind) for r in allf} and ('imp', 'result') in {(names[r.agent], r.kind) for r in allf}


def testMaterialComposeGistStale(hive, org):
    lead, a, b = org
    fa = a.note('queries use an ORM with lazy loading')['finding']
    fb = b.note('the api layer caches nothing')['finding']
    fc = b.note('the ORM loads eagerly in hot paths', refs=[f'against:{fa}'])['finding']
    cmp = hive.join('cmp', 'composer')
    m = cmp.material('lead')
    assert {c['node'] for c in m['children']} == {a.name, b.name} and all('uncomposed' in c for c in m['children'])
    assert fc in m['contradictions'][0] and fa in m['contradictions'][0]
    with pytest.raises(Bad, match='cite'): cmp.compose('lead', 'summary')
    outsider = hive.join('out', 'researcher')
    fo = outsider.note('unrelated')['finding']
    with pytest.raises(Bad, match='not a finding under lead'): cmp.compose('lead', 'x', [fo])
    r = cmp.compose('lead', 'ORM loading is disputed (f1 vs f3); the api caches nothing (f2).', [fa, fb])
    assert r['notCovered'] == [fc]
    r = cmp.compose('lead', 'ORM loading is disputed (f1 vs f3); the api caches nothing (f2).', [fa, fb, fc])
    assert r['composition'] == 'cp2' and r['version'] == 2 and 'notCovered' not in r
    g = lead.gist('me')
    assert g['fresh'] and g['sources'] == [fa, fb, fc]
    fr = a.note('there is also a read replica')['finding']
    assert lead.gist('me')['notCovered'] == 1
    assert lead.stale('me')['stale'][0]['why'] == '1 finding(s) not covered'
    assert cmp.compose('lead', 'v3', [fa, fb, fc, fr])['version'] == 3


def testTopDownWithSubComposers(hive, org):
    lead, a, b = org
    a1, a2 = (hive.sess(a.spawn(g)['token']) for g in ('pools', 'replicas'))
    for x, t in ((a1, 'pool max is 10'), (a2, 'one replica, async'), (b, 'api has 12 routes')): x.note(t)
    cmp = hive.join('cmp', 'composer')
    order = [x['node'] for x in cmp.stale('lead')['stale']]
    assert order.index(a.name) < order.index('lead')
    sub = hive.sess(cmp.spawn(f'compose {a.name}', 'composer')['token'])
    fs = [f['id'] for f in sub.findings(a.name)['findings']]
    cpa = sub.compose(a.name, 'db: pool max 10, one async replica', fs)['composition']
    m = cmp.material('lead')
    child = next(c for c in m['children'] if c['node'] == a.name)
    assert child['composition'] == cpa and child['fresh']
    fb = b.findings('me')['findings'][0]['id']
    assert 'notCovered' not in cmp.compose('lead', 'service map', [cpa, fb])
    assert cmp.stale('lead')['stale'] == []
    with pytest.raises(Bad): cmp.compose(a.name, 'self-cite', [cpa])


def testAutomaticComposeAndDistillTasks(hive, org):
    lead, a, b = org
    cmp, dis = hive.join('cmp', 'composer'), hive.join('dis', 'distiller')
    a.done(a.agent.deleg, 'db mapped')
    b.done(b.agent.deleg, 'api mapped')
    lead.done('t1', 'service mapped')
    t = cmp.take()['task']
    assert t['kind'] == 'compose' and t['role'] == 'composer' and "stale('lead')" in t['about']
    fs = [f['id'] for f in cmp.findings('lead')['findings']]
    cmp.compose('lead', 'the service in one page', fs)
    d = dis.take()['task']
    assert d['kind'] == 'distill' and "harvest('lead')" in d['about']


def testNoComposeTaskWithoutComposers(hive, org):
    lead, a, b = org
    for x in (a, b): x.done(x.agent.deleg, 'mapped')
    lead.done('t1', 'done')
    assert [t for t in lead.tasks()['tasks'] if t['kind'] == 'compose'] == []


def testDistillCorroborateContestPersist(hive, org, root):
    lead, a, b = org
    dis = hive.join('dis', 'distiller')
    fa = a.note('blind retries in the db client hide timeouts')['finding']
    fb = b.note('blind retries in the http client hide timeouts')['finding']
    r = dis.distill('Blind retries mask timeouts', 'Retrying without logging the first failure hides timeout root causes.', 'reusable', [fa])
    i = r['insight']
    assert r['status'] == 'saved' and r['state'] == 'proposed' and r['support'] == 1 and r['conf'] == .67
    dup = dis.distill('Retries mask timeouts', 'Blind retries hide timeout root causes.', 'reusable', [fb])
    assert dup['status'] == 'similar' and dup['candidates'][0]['insight'] == i
    r = dis.distill('x', 'y', 'reusable', [fb], into=i)
    assert r['status'] == 'merged' and r['support'] == 2 and r['state'] == 'established'
    fa2 = a.note('db retries again')['finding']
    assert dis.weigh(i, evidence=[fa2])['support'] == 2
    r = b.weigh(i, 'against', note='in the cache client retries surfaced timeouts fine')
    assert r['against'] == 1 and r['state'] == 'proposed'
    with pytest.raises(Bad): dis.distill('t', 'b', 'reusable', [])
    other = Hive.open(root/'.hive'/'sessions'/'other.db', root)
    got = other.join('fresh').recall('timeouts retries')['insights']
    assert got[0]['insight'] == i and got[0]['support'] == 2
    g = dis.distill('Keep a first-failure log', 'Log the first failure before any retry.', 'reusable', [fa], scope='global', force=True)
    assert g['insight'] == 'ig1' and g['scope'] == 'global'
    assert {x['insight'] for x in other.join('fresh2').recall('failure retry')['insights']} >= {'ig1'}
    other.close()


def testRecallRanksAndPromptsCarryInsights(hive, org):
    lead, a, b = org
    dis = hive.join('dis', 'distiller')
    fa, fb = a.note('pool exhaustion under load')['finding'], b.note('pool exhaustion in api tests')['finding']
    dis.distill('Pool exhaustion under load', 'The connection pool of 10 runs out under concurrent tests; raise it or queue.', 'observed', [fa, fb])
    dis.distill('Routes are documented', 'Every api route has a docstring.', 'observed', [fb], force=True)
    top = lead.recall('connection pool load')['insights']
    assert top[0]['title'] == 'Pool exhaustion under load' and top[0]['state'] == 'established'
    p = lead.spawn('fix connection pool exhaustion under load', 'researcher')['prompt']
    assert 'Insights saved from earlier work' in p and 'Pool exhaustion under load' in p
    h = dis.harvest('lead')
    assert {a.name, b.name} <= {x['branch'] for x in h['branches']} and h['related']


def testRolesStayInTheirLane(hive, org):
    lead, a, b = org
    cmp, dis, obs = hive.join('cmp', 'composer'), hive.join('dis', 'distiller'), hive.join('obs', 'observer')
    f = a.note('fact')['finding']
    with pytest.raises(Denied): a.compose('lead', 'x', [f])
    with pytest.raises(Denied): a.distill('t', 'b', 'observed', [f])
    with pytest.raises(Denied): cmp.distill('t', 'b', 'observed', [f])
    with pytest.raises(Denied): dis.compose('lead', 'x', [f])
    with pytest.raises(Denied): obs.note('x')
    i = dis.distill('Fact holds', 'A fact holds.', 'observed', [f])['insight']
    with pytest.raises(Denied): a.retire(i, 'nah')
    dis.retire(i, 'superseded')
    assert obs.recall('fact holds')['insights'] == []


async def testKnowToolsOverMcp(hive):
    from mcp.client import Client

    from hive.srv import build
    async with Client(build(hive)) as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert {'note', 'findings', 'material', 'compose', 'gist', 'stale', 'harvest', 'distill', 'recall', 'weigh', 'retire'} <= names


def testWholeTreeCompositionIsNotIndependentSupport(hive, org):
    lead, a, b = org
    dis, cmp = hive.join('dis', 'distiller'), hive.join('cmp', 'composer')
    fa, fb = a.note('x is slow')['finding'], b.note('y is slow')['finding']
    cp = cmp.compose('lead', 'x and y are slow', [fa, fb])['composition']
    r = dis.distill('Things are slow', 'Several components are slow.', 'observed', [cp, fa])
    assert r['support'] == 1 and r['state'] == 'proposed'


def testHarvestEchoesCrossBranchTerms(hive, org):
    lead, a, b = org
    fa, fb = a.note('the scheduler starves writers')['finding'], b.note('writers wait on the scheduler lock')['finding']
    b.note('unrelated api detail')
    e = {x['term']: x['in'] for x in hive.join('dis', 'distiller').harvest('lead')['echoes']}
    assert e['scheduler'] == {a.name: [fa], b.name: [fb]} and 'writers' in e and 'unrelated' not in e
