import os, stat
from pathlib import Path

import pytest

from hive import Hive
from hive.err import Bad, Missing


@pytest.fixture
def org(hive):
    lead = hive.join('lead', 'coordinator')
    [t] = lead.plan([{'title': 'investigate'}])['created']
    lead.take(t['id'])
    a, b = (hive.sess(lead.spawn(g, 'researcher')['token']) for g in ('db layer', 'api layer'))
    for x in (a, b): x.take()
    return lead, a, b


def testConfidenceNeedsIndependentWork(hive, org):
    lead, a, b = org
    dis, cmp = hive.join('dis', 'distiller'), hive.join('cmp', 'composer')
    fa = a.note('caches are cold at boot')['finding']
    fd = dis.note('caches are cold at boot, I agree')['finding']
    i = dis.distill('Cold caches at boot', 'Caches start cold after deploys.', 'observed', [fa, fd])['insight']
    assert hive.know.show(hive.know.lib('project'), 1)['support'] == 1
    [t] = lead.plan([{'title': 'never done'}])['created']
    with pytest.raises(Bad, match='no result'): dis.weigh(i, evidence=[t['id']])
    for n in ('r1', 'r2'): hive.join(n, 'researcher').weigh(i, note='agree')
    assert dis.recall('cold caches boot')['insights'][0]['support'] == 1
    with pytest.raises(Bad, match='nothing to compose'): cmp.compose('cmp', 'made up')
    assert hive.join('doubter', 'researcher').weigh(i, 'against', note='caches were warm in staging')['against'] == 1


def testRootResultIsNotIndependent(hive, org):
    lead, a, b = org
    a.done(a.agent.deleg, 'db done')
    b.done(b.agent.deleg, 'api done')
    lead.done('t1', 'all layers done')
    fs = {x['by']: x['id'] for x in lead.findings('lead')['findings']}
    r = hive.join('dis', 'distiller').distill('Layers done', 'Every layer finished.', 'observed', [fs['lead.rese1'], fs['lead']])
    assert r['support'] == 1 and r['state'] == 'proposed'


def testComposerHelpersMakeNoFindingsOrNewWork(hive, org):
    lead, a, b = org
    cmp = hive.join('cmp', 'composer')
    for x in (a, b): x.done(x.agent.deleg, 'mapped')
    lead.done('t1', 'mapped')
    task = cmp.take()['task']
    before = hive.db.one('SELECT COUNT(*) n FROM findings').n
    sub = hive.sess(cmp.spawn(f'compose {a.name}', 'composer')['token'])
    sub.take()
    sub.done(sub.agent.deleg, 'composed the db branch')
    assert hive.db.one('SELECT COUNT(*) n FROM findings').n == before
    assert [t['id'] for t in lead.tasks('ready,running')['tasks'] if t['kind'] == 'compose'] == [task['id']]
    assert lead.task(task['id'])['task']['creator'] is None


def testTipsOnlyShowEstablishedAndRelevant(hive, org):
    lead, a, b = org
    dis = hive.join('dis', 'distiller')
    fa, fb = a.note('pool limit ten')['finding'], b.note('pool limit ten too')['finding']
    good = dis.distill('Pool limit is ten', 'The connection pool is limited to ten.', 'observed', [fa, fb])['insight']
    for i in range(6): dis.distill(f'alpha beta gamma {i}', f'alpha beta gamma pool {i}', 'observed', [fa], force=True)
    tips = hive.know.tips('alpha beta gamma pool limit')
    assert len(tips) == 1 and tips[0].startswith(good)
    assert hive.know.tips('do it') == []
    uses = {r.id: r.uses for r in hive.know.lib('project').db.q('SELECT id,uses FROM insights')}
    assert uses[1] == 1 and sum(uses.values()) == 1


def testReadOnlyGlobalLibraryNeverBreaksWork(hive, org, tmp_path):
    lead, a, b = org
    dis = hive.join('dis', 'distiller')
    fa, fb = a.note('x ok')['finding'], b.note('x ok here')['finding']
    dis.distill('X is ok', 'X works.', 'observed', [fa, fb], scope='global')
    g = Path(os.environ['HIVE_GLOBAL'])
    other = Hive.open(hive.cfg.db, hive.root)
    other.know.libs.clear()
    os.chmod(g, stat.S_IRUSR)
    os.chmod(g.parent, stat.S_IRUSR | stat.S_IXUSR)
    try:
        boss = other.sess(lead.token)
        assert boss.spawn('check x', 'researcher')['agent']
        boss.recall('x')
    finally:
        os.chmod(g.parent, stat.S_IRWXU)
        os.chmod(g, stat.S_IRUSR | stat.S_IWUSR)
        other.close()


def testCoverageFollowsCitedSources(hive, org):
    lead, a, b = org
    cmp = hive.join('cmp', 'composer')
    a1 = hive.sess(a.spawn('sub')['token'])
    f1, f0 = a.note('one')['finding'], a1.note('zero')['finding']
    cpa = cmp.compose(a.name, 'db', [f1, f0])['composition']
    f2 = b.note('two')['finding']
    a.note('three')
    r = cmp.compose('lead', 'all', [cpa, f2])
    assert r['notCovered'] == ['f4'] and not lead.gist('lead')['fresh']
    assert {x['node'] for x in cmp.stale('lead')['stale']} == {a.name, 'lead'}


def testSessionIdSurvivesPathReuse(hive, org, root):
    lead, a, b = org
    dis = hive.join('dis', 'distiller')
    i = dis.distill('Thing', 'A thing holds.', 'observed', [a.note('thing holds')['finding']])['insight']
    hive.close()
    for f in root.joinpath('.hive').glob('hive.db*'): f.unlink()
    h = Hive.open(root/'.hive'/'hive.db', root)
    lead2 = h.join('lead', 'coordinator')
    x = h.sess(lead2.spawn('again', 'researcher')['token'])
    r = h.join('dis', 'distiller').distill('t', 'b', 'observed', [x.note('thing holds again')['finding']], into=i)
    assert r['support'] == 2
    h.close()


def testComposeTriggersFollowTheTree(hive):
    boss = hive.join('boss', 'coordinator')
    hive.join('cmp', 'composer')
    kids = [hive.sess(boss.spawn(f'part {i}', 'researcher')['token']) for i in range(2)]
    for k in kids:
        k.take()
        k.done(k.agent.deleg, 'part done')
    assert [t['title'] for t in boss.tasks('ready')['tasks'] if t['kind'] == 'compose'] == ["Compose what boss's subtree found"]


def testLoneRootGetsNoDistillTask(hive):
    hive.join('dis', 'distiller')
    v, cmp = hive.join('solo', 'researcher'), hive.join('cmp', 'composer')
    v.note('a lone observation')
    v.note('another lone observation')
    cmp.compose('solo', 'two lone observations', ['f1', 'f2'])
    assert [t for t in cmp.tasks()['tasks'] if t['kind'] == 'distill'] == []


def testMissingGlobalLibraryIsNotCreatedByLookups(hive, org):
    with pytest.raises(Missing): org[1].weigh('ig7', note='x')
    assert not Path(os.environ['HIVE_GLOBAL']).exists()


async def testHttpNeedsKeyForSynthesisRoles(hive):
    from mcp.client import Client

    from hive.srv import build
    async with Client(build(hive, strict=True)) as c:
        for r in ('composer', 'distiller'): assert (await c.call_tool('join', {'name': f'x{r}', 'role': r})).is_error
