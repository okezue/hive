import pytest

from hive.err import Bad, Clash, Denied, Missing

from .conftest import nums


@pytest.fixture
def app(root):
    (root/'app.py').write_text(nums(20))
    return root/'app.py'


def testDisjointEditsBothLandAndOthersAreTold(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    r = a.edit('app.py', [{'old': 'line 3\n', 'new': 'line 3 a\n'}])
    assert r['status'] == 'applied' and r['version'] == 2 and r['openBy'][0]['agent'] == 'bob'
    r = b.write('app.py', nums(20, l15='line 15 b'))
    assert r['status'] == 'merged' and r['mergedWith'][0]['author'] == 'alice'
    assert app.read_text() == nums(20, l3='line 3 a', l15='line 15 b')
    up = a.notices()['updates']
    assert len(up) == 1 and 'bob file.changed' in up[0] and '+line 15 b' in up[0]
    assert 'line 3 a' in b.notices()['updates'][0]


def testStringEditAppliesOnTopOfNewerHead(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 1\n', 'new': 'first\n'}])
    r = a.edit('app.py', [{'old': 'line 9\n', 'new': 'ninth\n'}])
    assert r['status'] == 'applied' and r['keptNewer'][0]['author'] == 'bob'
    assert app.read_text() == nums(20, l1='first', l9='ninth')


def testEditFallsBackToViewAndMerges(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 4\nline 5\n', 'new': 'four\nfive\n'}])
    r = a.edit('app.py', [{'old': 'line 5\nline 6\n', 'new': 'line 5\nsix\n'}])
    assert r['status'] == 'merged' and app.read_text() == nums(20, l4='four', l5='five', l6='six')


def testOverlapOpensMergeRequestAndBlocks(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 7\n', 'new': 'bob 7\n'}])
    r = a.edit('app.py', [{'old': 'line 7\n', 'new': 'alice 7\n'}], base=1)
    assert r['status'] == 'conflict' and r['with'] == ['bob'] and r['conflicts'][0]['requester'] == 'alice 7\n'
    assert app.read_text() == nums(20, l7='bob 7')
    mr = r['mr']
    n = b.notices()
    assert n['interrupts'][0]['kind'] == 'merge' and n['mergesWaitingOnYou'] == [mr]
    with pytest.raises(Clash, match='waits in merge request'): a.edit('app.py', [{'old': 'line 1', 'new': 'x'}])
    assert b.blockers() and a.blockers()
    b.send('alice', 'keep both lines?', thread=mr)
    with pytest.raises(Bad): a.propose(mr, ' ', ['both'])
    assert a.propose(mr, 'keep both, mine first', ['both'])['status'] == 'proposed'
    with pytest.raises(Clash): a.respond(mr, True)
    shown = b.merges(mr)
    assert shown['proposal']['by'] == 'alice' and 'keep both lines?' in [m['body'] for m in shown['thread']]
    r = b.respond(mr, True, 'ok')
    assert r['status'] == 'resolved'
    assert app.read_text() == nums(20, l7='alice 7\nbob 7')
    assert not a.blockers() and a.edit('app.py', [{'old': 'line 1\n', 'new': 'one\n'}])['status'] == 'applied'


def testRejectThenCustomResolution(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 2\n', 'new': 'B\n'}])
    mr = a.write('app.py', nums(20, l2='A'))['mr']
    b.propose(mr, 'mine is right', ['current'])
    with pytest.raises(Bad): a.respond(mr, False)
    assert a.respond(mr, False, 'no, combine them')['status'] == 'rejected'
    assert 'rejected' in b.notices()['interrupts'][-1]['body']
    b.propose(mr, 'combined', [{'text': 'AB\n'}])
    assert a.respond(mr, True)['status'] == 'resolved' and app.read_text() == nums(20, l2='AB')


def testResolutionReopensWhenHeadMovedIntoIt(team, app, hive):
    a, b, c = team['alice'], team['bob'], hive.join('carl')
    for x in (a, b, c): x.read('app.py')
    b.edit('app.py', [{'old': 'line 5\n', 'new': 'B5\n'}])
    mr = a.edit('app.py', [{'old': 'line 5\n', 'new': 'A5\n'}], base=1)['mr']
    b.propose(mr, 'take alice', ['requester'])
    c.edit('app.py', [{'old': 'B5\n', 'new': 'C5\n'}])
    r = a.respond(mr, True)
    assert r['status'] == 'reopened' and 'carl' in hive.files.mrs.show(a, mr)['with']


def testResolutionMergesWithUnrelatedLaterEdit(team, app, hive):
    a, b, c = team['alice'], team['bob'], hive.join('carl')
    for x in (a, b, c): x.read('app.py')
    b.edit('app.py', [{'old': 'line 5\n', 'new': 'B5\n'}])
    mr = a.edit('app.py', [{'old': 'line 5\n', 'new': 'A5\n'}], base=1)['mr']
    b.propose(mr, 'take alice', ['requester'])
    c.edit('app.py', [{'old': 'line 18\n', 'new': 'C18\n'}])
    assert a.respond(mr, True)['status'] == 'resolved' and app.read_text() == nums(20, l5='A5', l18='C18')


def testAbandon(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 2\n', 'new': 'B\n'}])
    mr = a.write('app.py', nums(20, l2='A'))['mr']
    with pytest.raises(Denied): b.abandon(mr)
    assert a.abandon(mr, 'fine')['status'] == 'abandoned' and app.read_text() == nums(20, l2='B')
    assert a.merges()['merges'] == [] and a.merges(state='all')['merges'][0]['state'] == 'abandoned'


def testWriteNeedsRead(team, app):
    a = team['alice']
    with pytest.raises(Clash, match='have not read'): a.write('app.py', 'x\n')
    assert a.write('app.py', 'x\n', base=1)['status'] == 'applied'
    assert a.write('new/mod.py', 'print(1)\n')['status'] == 'created' and (app.parent/'new/mod.py').exists()


def testOutsideEditsAreAdopted(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    app.write_text(nums(20, l10='human'))
    r = b.read('app.py')
    assert r['version'] == 2 and 'outside' in r
    assert a.read('app.py')['changedSince'][0]['author'] == 'outside Hive'


def testSyncMergesStaleFullRewrite(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 2\n', 'new': 'B2\n'}])
    app.write_text(nums(20, l19='A19'))
    r = a.sync('app.py')
    assert r['status'] == 'merged' and app.read_text() == nums(20, l2='B2', l19='A19')


def testSyncConflictRestoresDiskAndOpensRequest(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 2\n', 'new': 'B2\n'}])
    app.write_text(nums(20, l2='A2'))
    r = a.sync('app.py')
    assert r['status'] == 'conflict' and app.read_text() == nums(20, l2='B2') and 'restored' in r['note']


def testSyncOfInPlaceEditIsPlainCommit(team, app):
    a = team['alice']
    a.read('app.py')
    app.write_text(nums(20, l4='four'))
    assert a.sync('app.py')['status'] == 'committed' and a.sync('app.py')['status'] == 'unchanged'


def testClaims(team, app):
    a, b = team['alice'], team['bob']
    r = a.claim('app.py', 5, 9, 'refactor loop')
    assert r['lines'] == '5-9'
    assert b.claim('app.py', 8, 12, 'mine')['overlaps'][0]['agent'] == 'alice'
    b.read('app.py')
    r = b.edit('app.py', [{'old': 'line 6\n', 'new': 'six\n'}])
    assert any('alice' in w for w in r['warnings'])
    assert 'claimed region' in a.notices()['messages'][0]['body']
    b.edit('app.py', [{'old': 'line 1\n', 'new': 'x\ny\n'}])
    assert any(c['lines'] == '6-10' for c in b.files('app.py')['claims'] if c['agent'] == 'alice')
    with pytest.raises(Bad): a.claim('app.py', 5, 2, 'x')


def testScopeWarning(team, app, root):
    (root/'docs').mkdir()
    (root/'docs/a.md').write_text('a\n')
    c, a = team['coord'], team['alice']
    c.plan([{'title': 'only src', 'paths': ['src/*'], 'role': 'implementer'}])
    a.take()
    a.read('docs/a.md')
    assert 'outside the paths' in a.edit('docs/a.md', [{'old': 'a', 'new': 'b'}])['warnings'][0]


def testDiffAndStatus(team, app):
    a, b = team['alice'], team['bob']
    a.read('app.py')
    b.read('app.py')
    b.edit('app.py', [{'old': 'line 2\n', 'new': 'two\n'}])
    d = a.diff('app.py')
    assert d['since'] == 1 and d['versions'][0]['author'] == 'bob' and '+two' in d['versions'][0]['diff']
    s = a.files('app.py')
    assert {x['agent'] for x in s['openBy']} == {'alice', 'bob'}
    assert a.files()['files'][0]['path'] == 'app.py'
    a.release('app.py')
    assert 'file:app.py' not in a.me()['follows']


def testPathSafety(team, root):
    a = team['alice']
    for p in ('../x', '/etc/passwd', '.hive/hive.db', ''):
        with pytest.raises(Bad): a.read(p)
    with pytest.raises(Missing): a.read('nope.txt')
    (root/'bin.dat').write_bytes(b'\xff\xfe\x00')
    with pytest.raises(Bad, match='UTF-8'): a.read('bin.dat')


def testUnchangedEditKeepsVersion(team, app):
    a = team['alice']
    a.read('app.py')
    assert a.edit('app.py', [{'old': 'line 1\n', 'new': 'line 1\n'}])['status'] == 'unchanged'
    assert a.read('app.py')['version'] == 1


def testReadRange(team, app):
    r = team['alice'].read('app.py', 3, 4)
    assert r['content'] == 'line 3\nline 4\n' and r['lines'] == 20
