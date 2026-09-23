import random, shutil, subprocess

import pytest

from hive.err import Bad
from hive.merge import Diff, NoMatch, apply, merge, say

from .conftest import nums


def testDisjoint():
    m = merge(nums(10), nums(10, l2='ours'), nums(10, l8='theirs'))
    assert m.clean and m.text() == nums(10, l2='ours', l8='theirs')


def testAdjacentLinesMerge():
    assert merge(nums(6), nums(6, l3='three'), nums(6, l4='four')).text() == nums(6, l3='three', l4='four')


def testOverlapConflicts():
    m = merge(nums(5), nums(5, l3='ours'), nums(5, l3='theirs'))
    [h] = m.hunks
    assert not m.clean and (h.base, h.ours, h.theirs) == (('line 3\n',), ('ours\n',), ('theirs\n',)) and h.where() == 'base line 3'
    assert '<<<<<<< a\nours\n||||||| base\nline 3\n=======\ntheirs\n>>>>>>> b\n' in m.marked('a', 'b')
    with pytest.raises(ValueError): m.text()


def testSameChangeTwice():
    same = nums(5, l2='same')
    assert merge(nums(5), same, same).text() == same
    assert merge(nums(5), nums(5, l2='same', l4='x'), same).text() == nums(5, l2='same', l4='x')


def testInsertions():
    assert not merge('a\nb\nc\n', 'a\nX\nb\nc\n', 'a\nY\nb\nc\n').clean
    assert merge('a\nb\nc\n', 'X\na\nb\nc\n', 'a\nb\nc\nY\n').text() == 'X\na\nb\nc\nY\n'


def testInsertIntoDeletedRange():
    assert not merge('a\nb\nc\nd\n', 'a\nd\n', 'a\nb\nNEW\nc\nd\n').clean


def testDeleteBesideEdit():
    assert merge('a\nb\nc\nd\n', 'a\nd\n', 'a\nb\nc\nD\n').text() == 'a\nD\n'


def testUnchangedSide():
    x = nums(3, l1='x')
    assert merge(nums(3), nums(3), x).text() == x == merge(nums(3), x, nums(3)).text()


def testPick():
    m = merge(nums(4), nums(4, l2='A', l4='C'), nums(4, l2='B', l4='D'))
    assert len(m.hunks) == 2
    assert m.pick(['ours', 'theirs']) == nums(4, l2='A', l4='D')
    assert m.pick([{'take': 'ours+theirs'}, {'text': 'custom'}]) == 'line 1\nA\nB\nline 3\ncustom'
    assert m.pick(['base', 'theirs+ours']) == 'line 1\nline 2\nline 3\nD\nC\n'
    for bad in (['ours'], ['ours', 'nope']):
        with pytest.raises(Bad): m.pick(bad)


def testCustomTextGetsNewline():
    assert merge(nums(3), nums(3, l2='A'), nums(3, l2='B')).pick([{'text': 'Z'}]) == 'line 1\nZ\nline 3\n'


def testNoTrailingNewlineAndCrlf():
    assert merge('a\nb', 'A\nb', 'a\nB').text() == 'A\nB'
    assert merge('a\r\nb\r\nc\r\n', 'A\r\nb\r\nc\r\n', 'a\r\nb\r\nC\r\n').text() == 'A\r\nb\r\nC\r\n'


def mutate(rng, ls, tag):
    out = list(ls)
    for _ in range(rng.randint(1, 3)):
        op, i = rng.choice('rid') if out else 'i', rng.randrange(len(out)) if out else 0
        if op == 'r': out[i] = f'{tag} {rng.random():.6f}\n'
        elif op == 'i': out.insert(i, f'{tag}+ {rng.random():.6f}\n')
        else: del out[i]
    return out


@pytest.mark.parametrize('seed', range(40))
def testRandomDisjointEditsMerge(seed):
    rng = random.Random(seed)
    n = rng.randint(12, 60)
    base = [f'base {i} {rng.random():.6f}\n' for i in range(n)]
    cut = rng.randint(4, n-4)
    o, t = mutate(rng, base[:cut], 'o'), mutate(rng, base[cut+1:], 't')
    m = merge(''.join(base), ''.join(o+base[cut:]), ''.join(base[:cut+1]+t))
    assert m.clean and m.text() == ''.join(o+[base[cut]]+t)


@pytest.mark.skipif(not shutil.which('git'), reason='needs git')
@pytest.mark.parametrize('seed', range(15))
def testAgreesWithGit(tmp_path, seed):
    rng = random.Random(1000+seed)
    base = [f'row {i} {rng.random():.5f}\n' for i in range(30)]
    o, t = list(base), list(base)
    o[rng.randrange(10)], t[rng.randrange(20, 30)] = 'ours\n', 'theirs\n'
    for n, ls in (('b', base), ('o', o), ('t', t)): (tmp_path/n).write_text(''.join(ls))
    g = subprocess.run(['git', 'merge-file', '-p', tmp_path/'o', tmp_path/'b', tmp_path/'t'], capture_output=True, text=True)
    assert g.returncode == 0 and merge(''.join(base), ''.join(o), ''.join(t)).text() == g.stdout


def testApply():
    t = 'alpha\nbeta\nbeta\n'
    assert apply(t, [{'old': 'alpha', 'new': 'A'}]) == 'A\nbeta\nbeta\n'
    assert apply(t, [{'old': 'beta', 'new': 'B', 'all': True}]) == 'alpha\nB\nB\n'
    assert apply(t, [{'old_string': 'alpha', 'new_string': 'x'}]) == 'x\nbeta\nbeta\n'
    with pytest.raises(Bad, match='2 times'): apply(t, [{'old': 'beta', 'new': 'B'}])
    with pytest.raises(NoMatch): apply(t, [{'old': 'gamma', 'new': 'G'}])
    with pytest.raises(Bad, match='empty'): apply(t, [{'old': '', 'new': 'G'}])


def testDiffHelpers():
    d = Diff(nums(10), nums(10, l3='x', l4='y').replace('line 9\n', ''))
    sp = d.spans()
    assert (sp[0]['start'], sp[0]['end']) == (3, 4) and 'lines 3-4 (+2/-2)' in say(sp) and 'deleted after line 8' in say(sp)
    assert d.size() == 3 and Diff('a\n', 'a\n').size() == 0 and Diff('a\n', 'a\n').text() == ''
    big = Diff(nums(200), nums(200, **{f'l{i}': f'x{i}' for i in range(1, 200, 2)})).text(10)
    assert big.count('\n') == 11 and 'more diff lines' in big


def testDiffTextMatchesDifflib():
    import difflib
    a, b = nums(30), nums(30, l5='five', l20='twenty').replace('line 12\n', '')
    ref = ''.join(list(difflib.unified_diff(a.splitlines(True), b.splitlines(True), n=1))[2:])
    assert Diff(a, b).text(1000) == ref


def testRemap():
    old = nums(10)
    assert Diff(old, 'n1\nn2\n'+old).remap(4, 6) == (6, 8)
    assert Diff(old, old.replace('line 1\nline 2\n', '')).remap(4, 6) == (2, 4)
    assert Diff(old, nums(10, l5='five')).remap(4, 6) == (4, 6)
    assert Diff(old, '').remap(1, 3) == (1, 1)


def testInsertAtEdgeOfDeletionConflicts():
    base = 'a\ndef f():\n    b()\nz\n'
    assert not merge(base, 'a\nz\n', 'a\ndef f():\n    b()\n    c()\nz\n').clean
    assert not merge(base, 'a\nz\n', 'a\n@cache\ndef f():\n    b()\nz\n').clean
    assert merge(base, 'a\ndef g():\n    b()\nz\n', 'a\n@cache\ndef f():\n    b()\nz\n').text() == 'a\n@cache\ndef g():\n    b()\nz\n'
