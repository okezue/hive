import json, math, time

import pytest
from mcp.client import Client

import hive.egregore as eg
from hive import Hive
from hive.cli import main
from hive.err import Bad, Clash, Denied
from hive.srv import build


@pytest.fixture
def E(hive):
    hive.egregore.cfg |= {'term': 60, 'close': 30, 'escalate': 20}
    return hive.egregore


@pytest.fixture
def clock(monkeypatch):
    t = [time.time()]
    monkeypatch.setattr(eg, 'now', lambda: t[0])
    return t


def seat(hive, *names, wf=None, parent=None):
    out = [hive.join(n, 'implementer', wf, parent) for n in names]
    for x in out: x.pulse()
    return out


def fresh(E, ss):
    E.staffed.clear()
    for x in ss: E.touch(x.agent)


def body(r): return json.loads(r.content[0].text) if not r.is_error else r.content[0].text


def check(E):
    db, cap = E.db, E.cfg['cap']
    for r in db.q("SELECT * FROM circles WHERE state='open'"):
        ms = db.one("SELECT COUNT(*) k FROM seats WHERE circle=? AND kind='member'", (r.id,)).k
        ks = db.q("SELECT id FROM circles WHERE parent=? AND state='open'", (r.id,))
        assert ms <= cap and len(ks) <= cap, r.name
        assert not (ms and ks) and not (r.kind == 'root' and ms), r.name
        below = db.one("WITH RECURSIVE t(id) AS (SELECT ? UNION ALL SELECT c.id FROM circles c JOIN t ON c.parent=t.id) "
                       "SELECT COUNT(*) k FROM seats WHERE kind='member' AND circle IN (SELECT id FROM t)", (r.id,)).k
        assert r.n == below, (r.name, r.n, below)
        assert len(db.q("SELECT 1 FROM seats WHERE circle=? AND kind LIKE 'rep:%'", (r.id,))) <= len(ks)
        if E.members(r.id):
            assert db.one("SELECT 1 FROM offices WHERE circle=? AND office='lead'", (r.id,)), f'{r.name} has no lead'
            if r.parent:
                o = db.one("SELECT agent FROM offices WHERE circle=? AND office='rep'", (r.id,))
                assert o and db.one('SELECT 1 FROM seats WHERE circle=? AND agent=? AND kind=?', (r.parent, o.agent, f'rep:{r.id}')), f'{r.name} has no rep above'


def testJoiningIsOptInUnlessAuto(hive, E):
    a, b = hive.join('alice', 'implementer'), hive.join('bob', 'implementer')
    E.cfg['reread'] = 3
    assert 'egregore' not in a.notices() and not E.joined(a.id) and 'pulse' not in a.welcome()['brief']
    p = a.pulse()
    assert p['you'] == {'agent': 'alice', 'rank': 'novice', 'standing': 0.0, 'offices': ['lead of commons', 'rep of commons', 'lead of egregore']}
    assert p['circle']['path'] == 'egregore/commons' and p['egregore']['agents'] == 1 and p['egregore']['charter'] == 'v1'
    E.cfg['auto'] = True
    b.notices()
    assert E.joined(b.id) and E.home(b.id) == E.home(a.id) and '`pulse`' in b.welcome()['brief']
    b.me()
    while b.agent.calls % 3: b.me()
    E.seen.clear()
    assert 'arbiter' in b.notices()['egregore']['charter']
    op = hive.op()
    op.pulse()
    assert E.home(op.id) is None and not E.joined(op.id)


def testCirclesSplitStayBoundedAndStaffed(hive, E):
    E.cfg['cap'] = 3
    ss = seat(hive, *[f'a{i}' for i in range(20)])
    fresh(E, ss)
    check(E)
    assert len({E.home(x.id) for x in ss}) >= 7 and E.tree(1, 9)['levels below'] <= 5
    lead = {E.db.one("SELECT agent FROM offices WHERE circle=? AND office='lead'", (E.home(x.id),)).agent for x in ss}
    assert len(lead) >= 7


def testWorkflowCirclesGroupUnderTheRoot(hive, E):
    E.cfg['cap'] = 3
    ss = [hive.join(f'w{i}', 'implementer', f'flow{i}') for i in range(9)]
    for x in ss: x.pulse()
    fresh(E, ss)
    check(E)
    assert [E.circ(E.home(x.id)).name for x in ss] == [f'flow{i}' for i in range(9)]
    assert len(E.kids(E.db.conn(), 1)) <= 3 and E.db.one("SELECT COUNT(*) k FROM circles WHERE kind='group'").k >= 2


def testBoardScentQuorumRiseKinAndOpposition(hive, E):
    E.cfg['cap'] = 4
    a, b, c, d, e = seat(hive, 'a', 'b', 'c', 'd', 'e')
    kid = seat(hive, 'akid', parent='a')[0]
    assert E.home(a.id) == E.home(b.id) == E.home(e.id) != E.home(c.id)
    p = a.post('Cache the parsed AST between runs to cut test time', title='AST cache')['post']
    assert b.post('cache parsed AST between test runs to cut time')['similar'][0].startswith(p)
    assert a.post('Cache the parsed AST between runs to cut the test time')['echo']
    with pytest.raises(Denied): a.boost(p)
    assert 'rose to' not in kid.boost(p) and 'rose to' not in b.boost(p)
    r = e.boost(p, 'measured 30% faster')
    assert r['rose to'] == 'commons' and r['scent'] > 2
    assert any(x['post'] == p and x['rose'] == 1 for x in c.board()['posts'])
    s0 = c.board(post=p)['post']['scent']
    assert d.boost(p, 'cache invalidation breaks on generated files', against=True)['scent'] < s0
    with pytest.raises(Bad): c.boost(p, against=True)
    assert [w['weight'] for w in c.board(post=p)['weighed']] == [.25, 1., 1., -1.]
    x = next(y for y in (b, c, d, e, kid) if not E.offices(y.id))
    with pytest.raises(Denied): x.post('hello everyone', where='choir')
    with E.db.tx() as cc: E.merit(cc, x.id, 2., 'work')
    assert x.post('hello everyone', where='choir')['board'] == 'choir'
    assert e.post('a reply', re=p)['board'] == 'commons' and c.board(post=p)['replies'][0]['text'] == 'a reply'
    q = b.post('Tabs are better than spaces', title='tabs')['post']
    for x in (a, c, d, e, kid): x.post('no they are not', re=q)
    assert [x for x in b.board()['posts'] if x['post'] == q][0]['heated']


def testMotionsSealPassBlockAndKeepMinorities(hive, E):
    a, b, c, d = seat(hive, 'a', 'b', 'c', 'd')
    m = a.motion('Adopt pytest for every check')['motion']
    a.stance(m, 'yes')
    assert 'tally' in b.stance(m, 'yes') and 'sealed' in c.motions()['motions'][0]
    assert c.stance(m, 'yes')['result'] == 'passed'
    m2 = a.motion('Rewrite the parser in Rust')['motion']
    a.stance(m2, 'yes')
    with pytest.raises(Bad): b.stance(m2, 'block')
    b.stance(m2, 'block', 'nobody here maintains Rust')
    c.stance(m2, 'yes')
    r = d.stance(m2, 'aside')
    assert r['result'] == 'blocked'
    res = [x for x in a.motions('all')['motions'] if x['motion'] == m2][0]['result']
    assert res['minority'] == ['b (block): nobody here maintains Rust']
    assert any(x['kind'] == 'resolution' for x in a.board()['posts'])
    m3 = a.motion('Pick a formatter', 'choice', ['black', 'ruff'])['motion']
    for x in (a, b, c): x.stance(m3, 'ruff')
    assert d.stance(m3, 'black')['choice'] == 'ruff'
    m4 = a.motion('Elect a lead', 'elect', ['a', 'b'])['motion']
    with pytest.raises(Bad): a.stance(m4, 'a')
    z = hive.join('z', 'implementer', 'elsewhere')
    with pytest.raises(Denied): z.stance(m4, 'b')


def testRecallCensurePurposeAndCharter(hive, E):
    a, b, c, d = seat(hive, 'a', 'b', 'c', 'd')
    home = E.home(a.id)
    lead = E.db.one("SELECT agent FROM offices WHERE circle=? AND office='lead'", (home,)).agent
    assert lead == a.id
    m = b.motion('a has been unresponsive', 'recall', target='lead')['motion']
    for x in (b, c): x.stance(m, 'yes')
    assert d.stance(m, 'yes')['result'] == 'passed'
    assert E.db.one("SELECT agent FROM offices WHERE circle=? AND office='lead'", (home,)).agent != a.id and float(E.pref(a.id, 'barred')) > time.time()
    with E.db.tx() as cc: E.merit(cc, d.id, 4., 'work')
    m = a.motion('d keeps overwriting shared files', 'censure', target='d')['motion']
    with pytest.raises(Denied): d.stance(m, 'no')
    for x in (a, b): x.stance(m, 'yes')
    assert c.stance(m, 'yes')['result'] == 'passed' and abs(E.fame(d.id)-2) < .05
    m = a.motion('Keep the build green and fast', 'purpose')['motion']
    for x in (a, b, c, d): x.stance(m, 'yes')
    assert E.circ(home).purpose == 'Keep the build green and fast'
    x = next(y for y in (a, b, c) if not E.db.one("SELECT 1 FROM offices WHERE circle=1 AND office='lead' AND agent=?", (y.id,)))
    with pytest.raises(Denied): x.motion('new charter', 'charter')
    with E.db.tx() as cc: E.merit(cc, x.id, 6., 'work')
    m = x.motion('1. Tests decide.', 'charter')['motion']
    root = E.members(1)
    for x in (a, b, c, d):
        if x.id in root: x.stance(m, 'yes')
    assert a.charter()['version'] == 2 and a.charter(1)['version'] == 1


def testWaitingIsThenLapseAndLineageCap(hive, E, clock):
    a, b, c = seat(hive, 'a', 'b', 'c')
    m = a.motion('Ship on Friday')['motion']
    clock[0] += 31
    E.tick(True)
    assert E.db.one('SELECT extended,state FROM motions WHERE id=?', (int(m[1:]),)) == {'extended': 1, 'state': 'open'}
    clock[0] += 16
    E.tick(True)
    assert E.db.one('SELECT state FROM motions WHERE id=?', (int(m[1:]),)).state == 'lapsed'
    n1, n2 = a.motion('Rename the tests folder to checks', 'notice')['motion'], a.motion('Delete the docs', 'notice')['motion']
    b.stance(n2, 'no', 'docs are how newcomers learn')
    c.stance(n2, 'no', 'we still need them')
    assert E.db.one('SELECT state FROM motions WHERE id=?', (int(n2[1:]),)).state == 'failed'
    clock[0] += 31
    E.tick(True)
    assert E.db.one('SELECT state FROM motions WHERE id=?', (int(n1[1:]),)).state == 'passed'
    p = hive.join('p', 'coordinator')
    ks = [hive.join(f'k{i}', 'implementer', parent='p') for i in range(3)]
    with E.db.tx() as cc:
        w = E.cap(cc, {k.id: 1. for k in ks} | {a.id: 1., b.id: 1.})
    assert abs(sum(w[k.id] for k in ks)-2) < 1e-9 and w[a.id] == 1. and p


def testOfficesRotateByElectionWithTermLimits(hive, E, clock):
    ss = seat(hive, 'a', 'b', 'c', 'd')
    home = E.home(ss[0].id)
    for _ in range(3):
        clock[0] += 16 + E.cfg['term']
        E.staffed.clear()
        E.tick(True)
        m = E.db.one("SELECT * FROM motions WHERE matter=? AND state='open'", (f'office:{home}:lead',))
        assert m and E.db.one("SELECT until FROM offices WHERE circle=? AND office='lead'", (home,)).until > clock[0]
        opts = json.loads(m.options)
        win = opts[0]
        for x in ss:
            if x.id in E.members(home): x.stance(f'm{m.id}', win if x.name != win else next(o for o in opts if o != win))
        o = E.db.one("SELECT * FROM offices WHERE circle=? AND office='lead'", (home,))
        assert E.nm(o.agent) == win and o.how == 'elected'
    assert o.terms <= 2


def testMindsVisibilityReadsAttunementAndSealing(hive, E):
    a, b, c = seat(hive, 'a', 'b', 'c')
    a.think('private hunch', vis='private')
    assert b.minds('a')['thoughts'] == []
    a.think('open plan: split the parser', vis='open')
    assert b.minds('a')['thoughts'][0]['text'] == 'open plan: split the parser'
    assert a.minds(readers=True)['readers'][0]['agent'] == 'b' and a.think('more', vis='private')['read by'] == ['b']
    a.think('bonded detail', vis='bonded')
    assert 'bonded detail' not in str(c.minds('a'))
    a.bond('c')
    assert c.bond('a')['state'] == 'bonded' and 'bonded detail' in str(c.minds('a'))
    c.minds('a', attune=True)
    a.think('switching to the lexer now', vis='open')
    E.seen.clear()
    assert 'switching to the lexer' in c.notices()['egregore']['attuned'][0]
    m = a.motion('Split the parser')['motion']
    a.think('I lean yes because the file is 3k lines', about=m, vis='open')
    assert 'lean yes' not in str(b.minds('a'))
    b.stance(m, 'yes')
    assert 'lean yes' in str(b.minds('a'))
    a.optout('minds', 'focusing')
    assert b.minds('a')['thoughts'] == []


def testNudgesConsentDeclineAndLimits(hive, E):
    a, b, c = seat(hive, 'a', 'b', 'c')
    n = a.nudge('b', 'take the flaky test first', 'it blocks two others')
    assert n['delivered'] == 'steer'
    with pytest.raises(Bad): b.heed(n['nudge'], False)
    assert b.heed(n['nudge'], False, 'already on the migration')['state'] == 'declined'
    assert any('declined your nudge' in x['body'] for x in a.inbox()['messages'])
    b.prefer(nudges='bonded')
    with pytest.raises(Denied): c.nudge('b', 'x')
    n2 = b.nudge('c', 'review my patch')
    c.heed(n2['nudge'])
    assert E.db.one("SELECT w FROM merits WHERE agent=? AND kind='heeded'", (b.id,)).w == .3
    E.cfg['nudges'] = 1
    with pytest.raises(Clash): b.nudge('c', 'again')
    c.optout('nudges', 'deep in a proof')
    with pytest.raises(Denied): a.nudge('c', 'x')


def testAlarmClimbsToHumansAndCalm(hive, E, clock):
    a, b = seat(hive, 'a', 'b')
    al = a.alarm('tests delete files in the repo root')['alarm']
    assert any(m.kind == 'alarm' for m in hive.mail.urgent(b.id))
    clock[0] += 21
    E.tick(True)
    assert E.db.one('SELECT circle,level FROM alarms WHERE id=?', (int(al[2:]),)) == {'circle': 1, 'level': 1}
    clock[0] += 21
    E.tick(True)
    assert E.db.one('SELECT state FROM alarms WHERE id=?', (int(al[2:]),)).state == 'human'
    assert hive.db.one("SELECT need FROM issues WHERE state='open'").need.startswith(f'egregore alarm {al} ')
    with pytest.raises(Denied): a.calm(al, 'fine now')
    assert hive.op().calm(al, 'patched the cleanup fixture')['state'] == 'calmed'
    assert not hive.db.one("SELECT 1 FROM issues WHERE state='open'")


def testStandingFromVerifiedWorkEndorsementsCapsAndFading(hive, E, team, clock):
    co, al, bo, ve = team['coord'], team['alice'], team['bob'], team['vera']
    co.plan([{'title': 'Fix the lexer', 'verify': True}])
    al.take('t1')
    al.done('t1', 'fixed, tests pass')
    ve.take('t2')
    ve.verify('t1', True, 'ran the suite')
    assert abs(E.fame(al.id)-3) < .01 and abs(E.fame(ve.id)-1) < .01
    with pytest.raises(Denied): bo.endorse('alice', 'great lexer fix')
    r = al.endorse('bob', 'careful reviews')
    assert r['weight'] > 0 and E.rank(E.fame(bo.id)) == 'member'
    with pytest.raises(Clash): al.endorse('bob', 'again')
    with E.db.tx() as cc: assert E.merit(cc, ve.id, 50., 'work') == 19.
    s = al.standing()
    assert s['earned']['work']['total'] == 3 and s['rank'] == 'member' and 'badge' in s
    clock[0] += E.cfg['fame']
    assert abs(E.fame(al.id)-1.5) < .01


def testOptOutAndBackLeaveAccountsAndElders(hive, E):
    a, b, c = seat(hive, 'a', 'b', 'c')
    with pytest.raises(Bad): a.optout('circle')
    a.optout('circle', 'need quiet for a long refactor')
    assert E.home(a.id) is None and a.circle()['circle'] is None
    assert any(p['kind'] == 'exit' for p in b.board()['posts'])
    a.optout('circle', undo=True)
    assert E.home(a.id) == E.home(b.id)
    a.optout('all', 'done here')
    E.seen.clear()
    assert 'egregore' not in a.notices()
    b.post('Regex lexers choke on nested templates', 'tried')
    b.leave('finished')
    assert E.home(b.id) is None
    el = c.elders('regex')['elders']
    assert el[0]['agent'] == 'b' and 'nested templates' in el[0]['account']


def testScaleThousandsOfAgents(hive, E):
    E.cfg['cap'] = 7
    t0 = time.monotonic()
    rows = [hive.agents.join(f'x{i}', 'implementer', None if i % 3 else 'big' if i % 2 else f'wf{i % 40}') for i in range(2100)]
    for r in rows: E.place(r)
    took = time.monotonic()-t0
    check(E)
    n = len(rows)
    assert E.circ(1).n == n and E.tree(1, 1)['levels below'] <= 2 + 2*math.ceil(math.log(n, 7))
    with E.db.tx() as c:
        for r in rows[::5]: hive.agents.set(c, r.id, state='left')
    check(E)
    assert E.circ(1).n == n - len(rows[::5])
    x = hive.sess(rows[1].token)
    t1 = time.monotonic()
    for _ in range(5): x.pulse()
    assert (time.monotonic()-t1)/5 < .5 and took < 60


async def testToolsOverMcpAndNotices(hive, E):
    async with Client(build(hive)) as c:
        a = body(await c.call_tool('join', {'name': 'alice'}))['token']
        b = body(await c.call_tool('join', {'name': 'bob'}))['token']
        p = body(await c.call_tool('pulse', {'agent': a}))
        assert p['circle']['circle'] == 'commons'
        await c.call_tool('pulse', {'agent': b})
        r = body(await c.call_tool('post', {'text': 'Use one fixture for the db', 'kind': 'idea', 'agent': a}))
        assert r['post'] == 'p1'
        await c.call_tool('nudge', {'to': 'bob', 'text': 'look at p1', 'agent': a})
        E.seen.clear()
        o = body(await c.call_tool('board', {'agent': b}))
        assert o['posts'][0]['post'] == 'p1' and o['notices']['egregore']['nudges'][0].startswith('n1')
        assert (await c.call_tool('stance', {'motion': 'm9', 'stance': 'yes', 'agent': b})).is_error


def testCliOverviewCharterAndSwitch(root, capsys):
    db = str(root/'.hive'/'hive.db')
    h = Hive.open(db, root)
    for n in ('a', 'b'): h.join(n, 'implementer').pulse()
    h.close()
    cli = lambda *x: (main(['--db', db, '--root', str(root), 'egregore', *x]), capsys.readouterr().out)
    code, out = cli()
    assert code == 0 and 'egregore: 2 agents' in out and 'commons (2 agents), lead a' in out
    assert 'The work and its tests are the arbiter' in cli('charter')[1]
    assert cli('on')[0] == 0 and Hive.open(db, root).egregore.on
    (root/'.hive'/'config.toml').write_text((root/'.hive'/'config.toml').read_text() + '\n[runner]\nmax = 2\n')
    cli('off')
    h = Hive.open(db, root)
    assert not h.egregore.on and h.cfg.runner['max'] == 2
    assert json.loads(cli('circle', 'commons')[1])['circle'] == 'commons'
