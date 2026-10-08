import json, os, subprocess, sys, textwrap, threading, time
from pathlib import Path

import pytest

from hive.build import Worker, ask, detect, diags, home, project, queue, recent
from hive.cli import main
from hive.reg import alive

CC = textwrap.dedent('''
    import os, pathlib, sys, time
    cache = pathlib.Path(sys.argv[1])
    (cache/'obj').mkdir(parents=True, exist_ok=True)
    n, bad, srcs = 0, [], sorted(pathlib.Path('src').rglob('*.txt'))
    for f in srcs:
        o = cache/'obj'/(str(f).replace('/', '_')+'.o')
        if not o.exists() or o.stat().st_mtime_ns < f.stat().st_mtime_ns:
            n += 1
            o.write_text(f.read_text())
        bad += [f'{f}:{i}:3: error: bad token here' for i, ln in enumerate(f.read_text().splitlines(), 1) if 'ERR' in ln]
    time.sleep(float(os.environ.get('NAP', '0')))
    for b in bad: print(b, file=sys.stderr)
    (cache/'app.bin').write_text(f'compiled {n}\\n' + ''.join(f.read_text() for f in srcs))
    print(f'compiled {n} of {len(srcs)}')
    sys.exit(1 if bad else 0)
''')


def sh(d, *a): return subprocess.run(['git', '-C', str(d), *a], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def proj(tmp_path):
    d = tmp_path/'proj'
    (d/'src'/'deep').mkdir(parents=True)
    for i in range(6): (d/'src'/f'f{i}.txt').write_text(f'file {i}\n')
    (d/'src'/'deep'/'x.txt').write_text('deep\n')
    (d/'cc.py').write_text(CC)
    (d/'.gitignore').write_text('.hive/\nout/\n')
    (d/'.hive').mkdir()
    (d/'.hive'/'config.toml').write_text(f'[build]\nslots = 2\npriority = "normal"\nlinger = 4\n\n[build.kinds.build]\ncmd = [{json.dumps(sys.executable)}, "cc.py", "{{cache}}"]\n'
                                         'outputs = ["{cache}/app.bin"]\n\n[build.kinds.slow]\ncmd = ["sh", "-c", "sleep 30"]\n')
    sh(d, 'init', '-q')
    sh(d, '-c', 'user.email=t@t', '-c', 'user.name=t', 'add', '-A')
    sh(d, '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'init')
    yield d
    h, end = home(project(d)[2]), time.time()+20
    while (r := queue(h).one("SELECT val FROM meta WHERE key='worker'")) and (p := json.loads(r.val)['pid']) != os.getpid() and alive(p) and time.time() < end:
        time.sleep(.3)


def made(d, kind='build'): return (d/'.hive'/'out'/kind/'app.bin').read_text()


def testBuildsIncrementallyAtAStablePathAndAnswersRepeatsFromCache(proj):
    r = ask(proj, wait=120)
    assert r['state'] == 'done' and r['ok'] and r['synced'] == 9 and made(proj).startswith('compiled 7'), r
    (proj/'src'/'f2.txt').write_text('file 2 edited\n')
    r2 = ask(proj, wait=120)
    assert r2['ok'] and r2['synced'] == 1 and r2['slot'] == r['slot'] and made(proj).startswith('compiled 1') and 'edited' in made(proj)
    t = time.time()
    r3 = ask(proj, wait=120)
    assert r3['cached'] and r3['build'] == r2['build'] and time.time()-t < 5
    (proj/'src'/'deep'/'x.txt').unlink()
    (proj/'src'/'new.txt').write_text('new\n')
    r4 = ask(proj, wait=120)
    src = home(project(proj)[2])/'slots'/str(r4['slot'])/'src'
    assert r4['ok'] and not (src/'src'/'deep'/'x.txt').exists() and (src/'src'/'new.txt').exists() and r4['synced'] == 2


def testBuildsTheSnapshotTakenAtRequestTime(proj):
    ask(proj, wait=120)
    (proj/'src'/'f1.txt').write_text('version A\n')
    r = ask(proj, 'build', wait=0)
    (proj/'src'/'f1.txt').write_text('version B\n')
    r = ask(proj, rid=r['build'], wait=120)
    assert r['ok'] and 'version A' in made(proj) and 'version B' not in made(proj)


def testWorktreesOfOneRepoShareTheWarmSlot(proj, tmp_path):
    a = ask(proj, wait=120)
    sh(proj, 'worktree', 'add', '-q', str(w := tmp_path/'wt'), '-b', 'feature')
    (w/'.hive').mkdir(exist_ok=True)
    (w/'.hive'/'config.toml').write_text((proj/'.hive'/'config.toml').read_text())
    (w/'src'/'f4.txt').write_text('feature work\n')
    assert project(w)[2] == project(proj)[2]
    b = ask(w, wait=120)
    assert b['ok'] and b['slot'] == a['slot'] and b['synced'] == 1 and made(w).startswith('compiled 1') and 'feature work' in made(w)
    assert not (proj/'.hive'/'out'/'build'/'app.bin').read_text().count('feature work')


def testSimultaneousRequestsForOneStateShareOneBuild(proj, tmp_path):
    ask(proj, wait=120)
    (proj/'src'/'f0.txt').write_text('shared change\n')
    got = []
    ts = [threading.Thread(target=lambda: got.append(ask(proj, wait=120))) for _ in range(3)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert len({g['build'] for g in got}) == 1 and all(g['ok'] for g in got)
    assert queue(home(project(proj)[2])).one('SELECT COUNT(*) n FROM runs').n == 2


def testErrorsComeBackMappedToTheProjectsFiles(proj):
    (proj/'src'/'f3.txt').write_text('fine\nhas ERR here\n')
    r = ask(proj, wait=120)
    assert not r['ok'] and r['state'] == 'done' and r['errors'] == [{'file': 'src/f3.txt', 'line': 2, 'col': 3, 'severity': 'error', 'message': 'bad token here'}]
    assert ask(proj, wait=120)['cached'], 'a deterministic failure is answered from cache too'


def testParallelBuildsUseSeparateSlotsOnceMemoryIsKnown(proj, tmp_path):
    ask(proj, wait=120)
    sh(proj, 'worktree', 'add', '-q', str(w := tmp_path/'wt2'), '-b', 'other')
    (w/'.hive').mkdir(exist_ok=True)
    (w/'.hive'/'config.toml').write_text((proj/'.hive'/'config.toml').read_text())
    for d in (proj, w): (d/'.hive'/'config.toml').write_text((d/'.hive'/'config.toml').read_text() + '\n[build.env]\nNAP = "3"\n')
    (proj/'src'/'f5.txt').write_text('main side\n')
    (w/'src'/'f5.txt').write_text('other side\n')
    got = {}
    ts = [threading.Thread(target=lambda d=d: got.__setitem__(d, ask(d, wait=120))) for d in (proj, w)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert {got[proj]['slot'], got[w]['slot']} == {1, 2} and all(x['ok'] for x in got.values())


def testCrashedSyncNeverLeavesStaleSourcesBehind(proj):
    r = ask(proj, wait=120)
    d = home(project(proj)[2])/'slots'/str(r['slot'])
    os.replace(d/'manifest.json', d/'manifest.syncing')
    (d/'src'/'src'/'f0.txt').write_text('half written\n')
    (proj/'src'/'f1.txt').unlink()
    r2 = ask(proj, wait=120)
    assert r2['ok'] and not (d/'src'/'src'/'f1.txt').exists() and (d/'src'/'src'/'f0.txt').read_text() == 'file 0\n'


def testTimeoutsKillTheBuildAndAreNotCached(proj):
    c = proj/'.hive'/'config.toml'
    c.write_text(c.read_text().replace('[build.kinds.slow]', '[build.kinds.slow]\ntimeout = 2\nidle = 0'))
    r = ask(proj, 'slow', wait=120)
    assert r['state'] == 'error' and r['timedOut'] == 2 and not r['ok']
    assert not ask(proj, 'slow', wait=0).get('cached')


def testMemoryPressurePausesTheBuildInsteadOfKillingIt(proj, monkeypatch):
    h = home(project(proj)[2])
    (c := proj/'.hive'/'config.toml').write_text(c.read_text().replace('linger = 4\n', 'linger = 4\npass = ["NAP"]\n'))
    with queue(h).tx() as c: c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('worker', json.dumps({'pid': os.getpid(), 'ts': time.time()+3600})))
    os.environ['NAP'] = '3'
    def fake():
        o = [x for x in h.glob('slots/*/cache/obj') if time.time()-x.stat().st_mtime < 2]
        return 5. if o else 60.
    monkeypatch.setattr('hive.build.free', fake)
    try:
        r = ask(proj, wait=0)
        threading.Thread(target=Worker(h).run, daemon=True).start()
        r = ask(proj, rid=r['build'], wait=60)
    finally: os.environ.pop('NAP')
    assert r['ok'] and r.get('paused', 0) >= 1


def testDiagnosticsUnderstandCommonCompilers(tmp_path):
    src = tmp_path
    text = ('src/a.swift:3:7: error: cannot find \'x\' in scope\n'
            'error[E0425]: cannot find value `y` in this scope\n --> model/src/lib.rs:10:5\n'
            'web/app.ts(4,2): error TS2304: Cannot find name \'z\'.\n'
            '/usr/include/stdio.h:1:1: warning: system header\n')
    d = diags(text, src, src)
    assert [(x['file'], x['line'], x['severity']) for x in d] == [('src/a.swift', 3, 'error'), ('model/src/lib.rs', 10, 'error'), ('web/app.ts', 4, 'error'),
                                                                   ('/usr/include/stdio.h', 1, 'warning')]
    assert d[1]['code'] == 'E0425' and d[2]['code'] == 'TS2304'


def testDetectsCommonProjectKinds(tmp_path):
    (tmp_path/'Cargo.toml').write_text('[package]\nname="x"\n')
    assert set(detect(tmp_path)) == {'check', 'build', 'test'}
    (x := tmp_path/'x').mkdir()
    (x/'App.xcodeproj').mkdir()
    k = detect(x)['build']['cmd']
    assert 'CODE_SIGNING_ALLOWED=NO' in k and '{cache}/dd' in k and 'App' in k


def testAgentsAndTheCliBuildThroughHive(proj, capsys):
    from hive import Hive
    h = Hive.open(proj/'.hive'/'hive.db', proj)
    x = h.join('ann', 'implementer')
    r = x.build(wait=120)
    assert r['ok'] and r['artifacts'] and x.builds()['builds'][0]['build'] == r['build']
    assert main(['--root', str(proj), 'build']) == 0 and 'cached' in capsys.readouterr().out
    (proj/'src'/'f1.txt').write_text('ERR\n')
    assert main(['--root', str(proj), 'build']) == 1 and 'src/f1.txt:1:3: error: bad token here' in capsys.readouterr().out
    assert [b['build'] for b in recent(proj)][:1] and main(['--root', str(proj), 'build', '--kinds']) == 0


def kind(d, name, body):
    (c := d/'.hive'/'config.toml').write_text(c.read_text() + f'\n[build.kinds.{name}]\n{body}\n')


def testBuildsThatEditTrackedFilesDoNotLeakIntoLaterBuilds(proj):
    (proj/'lock.txt').write_text('lock v1\n')
    sh(proj, 'add', 'lock.txt')
    kind(proj, 'lockish', 'cmd = "cat lock.txt > {cache}/seen.txt; echo by-build >> lock.txt"\noutputs = ["{cache}/seen.txt"]')
    ask(proj, 'lockish', wait=120)
    (proj/'src'/'f0.txt').write_text('changed\n')
    ask(proj, 'lockish', wait=120)
    assert (proj/'.hive'/'out'/'lockish'/'seen.txt').read_text() == 'lock v1\n'


def testFailedBuildsDeliverNoOldArtifacts(proj):
    ask(proj, wait=120)
    (proj/'src'/'f0.txt').write_text('fresh\n')
    kind(proj, 'flaky', 'cmd = "test -f src/bad.txt && exit 1; echo good > {cache}/app.bin"\noutputs = ["{cache}/app.bin"]')
    assert ask(proj, 'flaky', wait=120)['artifacts']
    (proj/'src'/'bad.txt').write_text('x\n')
    r = ask(proj, 'flaky', wait=120)
    assert not r['ok'] and 'artifacts' not in r


def testSnapshotsReadWhatIsOnDisk(proj):
    (proj/'.gitattributes').write_text('*.sm filter=rev\n')
    sh(proj, 'config', 'filter.rev.clean', 'tr a-z A-Z')
    sh(proj, 'config', 'filter.rev.smudge', 'tr A-Z a-z')
    (proj/'asset.sm').write_text('real bytes\n')
    sh(proj, 'add', '.gitattributes', 'asset.sm')
    sh(proj, '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'attrs')
    sh(proj, 'update-index', '--skip-worktree', 'src/f1.txt')
    (proj/'src'/'f1.txt').write_text('local override\n')
    kind(proj, 'cat', 'cmd = "cat asset.sm src/f1.txt > {cache}/out.txt"\noutputs = ["{cache}/out.txt"]')
    ask(proj, 'cat', wait=120)
    assert (proj/'.hive'/'out'/'cat'/'out.txt').read_text() == 'real bytes\nlocal override\n'


def testKilledWorkersLeaveNoOrphanBuildsAndPollingRestartsThem(proj):
    kind(proj, 'nap', 'cmd = "n=90; [ -s {slot}/trace ] && n=1; echo start $$ >> {slot}/trace; sleep $n; echo end >> {slot}/trace"')
    r = ask(proj, 'nap', wait=0)
    h, end = home(project(proj)[2]), time.time()+120
    while not list(h.glob('slots/*/trace')) and time.time() < end: time.sleep(.2)
    w = json.loads(queue(h).one("SELECT val FROM meta WHERE key='worker'").val)['pid']
    os.kill(w, 9)
    r = ask(proj, rid=r['build'], wait=120)
    trace = (h/'slots'/str(r['slot'])/'trace').read_text().split('\n')
    assert r['state'] == 'done' and trace.count('end') == 1 and len([x for x in trace if x.startswith('start')]) == 2, trace


def testTheEnvironmentAndRootArePartOfTheCacheKey(proj, monkeypatch, tmp_path):
    (c := proj/'.hive'/'config.toml').write_text(c.read_text().replace('linger = 4\n', 'linger = 4\npass = ["TOOLCHAIN"]\n'))
    kind(proj, 'env', 'cmd = "echo $TOOLCHAIN {root} > {cache}/env.txt"\noutputs = ["{cache}/env.txt"]')
    monkeypatch.setenv('TOOLCHAIN', 'one')
    a = ask(proj, 'env', wait=120)
    monkeypatch.setenv('TOOLCHAIN', 'two')
    b = ask(proj, 'env', wait=120)
    assert a['build'] != b['build'] and not b.get('cached') and (proj/'.hive'/'out'/'env'/'env.txt').read_text().startswith('two')
    sh(proj, 'worktree', 'add', '-q', str(w := tmp_path/'wt3'), '-b', 'w3')
    (w/'.hive').mkdir(exist_ok=True)
    (w/'.hive'/'config.toml').write_text(c.read_text())
    r = ask(w, 'env', wait=120)
    assert not r.get('cached') and str(w) in (w/'.hive'/'out'/'env'/'env.txt').read_text()


def testAgentsCanBuildTheirOwnWorktree(proj, tmp_path):
    from hive import Hive
    sh(proj, 'worktree', 'add', '-q', str(w := tmp_path/'wt4'), '-b', 'w4')
    (w/'.hive').mkdir(exist_ok=True)
    (w/'.hive'/'config.toml').write_text((proj/'.hive'/'config.toml').read_text())
    (w/'src'/'f0.txt').write_text('worktree edit\n')
    x = Hive.open(proj/'.hive'/'hive.db', proj).join('wa', 'implementer')
    r = x.build(path=str(w), wait=120)
    assert r['ok'] and 'worktree edit' in made(w)


def testConcurrentSnapshotsAndDeliveriesDoNotCollide(proj):
    from hive.build import snap
    (proj/'src'/'big.txt').write_bytes(os.urandom(1 << 20))
    h = home(project(proj)[2])
    errs = []

    def go():
        try:
            for _ in range(10): snap(proj, [], h/'cas')
        except Exception as e: errs.append(e)
    ts = [threading.Thread(target=go) for _ in range(4)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert not errs
    kind(proj, 'dir', 'cmd = "mkdir -p {cache}/P && for i in $(seq 200); do echo $i > {cache}/P/f$i; done"\noutputs = ["{cache}/P"]')
    got = []
    ts = [threading.Thread(target=lambda: got.append(ask(proj, 'dir', wait=120))) for _ in range(4)]
    for t in ts: t.start()
    for t in ts: t.join()
    p = proj/'.hive'/'out'/'dir'/'P'
    assert all(g['ok'] for g in got) and sorted(os.listdir(p)) == sorted(f'f{i}' for i in range(1, 201))


def testDamagedSlotFilesAndShapeChangesRecover(proj):
    r = ask(proj, wait=120)
    d = home(project(proj)[2])/'slots'/str(r['slot'])
    (d/'manifest.json').write_text('{"trunc')
    (d/'paths.json').write_text('[')
    (proj/'src'/'deep'/'x.txt').unlink()
    (proj/'src'/'deep').rmdir()
    (proj/'src'/'deep').write_text('now a file\n')
    assert ask(proj, wait=120)['ok']
    (proj/'src'/'deep').unlink()
    (proj/'src'/'deep').symlink_to('f0.txt')
    r = ask(proj, wait=120)
    assert r['ok'] and (d/'src'/'src'/'deep').is_symlink() and not list((d/'src'/'src').glob('.*.hive~'))


def testRepeatedAsksStayCachedAndRelativeOutputsUseTheBuildFolder(proj):
    (proj/'.hive'/'.gitignore').unlink(missing_ok=True)
    (proj/'.gitignore').write_text('out/\n')
    sh(proj, '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qam', 'ignore')
    kind(proj, 'rel', 'cmd = "echo here > out.txt"\noutputs = ["out.txt"]')
    a = ask(proj, 'rel', wait=120)
    assert a['artifacts'] and (proj/'.hive'/'out'/'rel'/'out.txt').read_text() == 'here\n'
    assert ask(proj, 'rel', wait=120).get('cached') and ask(proj, 'rel', wait=120).get('cached')


def testOnlyDeterministicFailuresAreCachedAndForceRebuilds(proj):
    kind(proj, 'missing', 'cmd = ["no-such-tool-xyz"]')
    assert not ask(proj, 'missing', wait=120).get('cached') and not ask(proj, 'missing', wait=120).get('cached')
    a = ask(proj, wait=120)
    b = ask(proj, wait=120, force=True)
    assert b['build'] != a['build'] and not b.get('cached') and b['ok']


def testPlaceholdersAreQuotedAndBadIdsAreRejected(tmp_path):
    from hive.build import fill
    from hive.err import Bad
    assert fill('ls {src}', {'src': tmp_path/'My App$(x)'}, True) == f"ls '{tmp_path}/My App$(x)'"
    with pytest.raises(Bad): ask(Path.cwd(), rid='latest')


def testLongPausesStopTheBuild(proj, monkeypatch):
    h = home(project(proj)[2])
    kind(proj, 'stuck', 'cmd = "sleep 30"\npausemax = 2')
    with queue(h).tx() as c: c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('worker', json.dumps({'pid': os.getpid(), 'ts': time.time()+3600})))
    monkeypatch.setattr('hive.build.free', lambda: 1.)
    monkeypatch.setattr(Worker, 'fits', lambda s, k, c: True)
    r = ask(proj, 'stuck', wait=0)
    threading.Thread(target=Worker(h).run, daemon=True).start()
    r = ask(proj, rid=r['build'], wait=60)
    assert r['state'] == 'error' and 'paused' in r['stopped']


def testDuplicateOutputNamesAndWhoAsked(proj):
    kind(proj, 'two', 'cmd = "mkdir -p {cache}/a {cache}/b && echo A > {cache}/a/app && echo B > {cache}/b/app"\noutputs = ["{cache}/a/app", "{cache}/b/app"]')
    r = ask(proj, 'two', wait=120, by='zed')
    assert sorted(r['artifacts']) == sorted(str(proj/'.hive'/'out'/'two'/x) for x in ('a/app', 'b/app'))
    assert (proj/'.hive'/'out'/'two'/'b'/'app').read_text() == 'B\n' and recent(proj)[0]['by'] == ['zed']


def testOnlyProjectsWithBuildsTellAgentsToUseThem(proj, root):
    from hive import Hive
    assert 'with `build`' in Hive.open(proj/'.hive'/'hive.db', proj).join('b1', 'implementer').welcome()['brief']
    assert 'with `build`' not in Hive.open(root/'.hive'/'hive.db', root).join('b2', 'implementer').welcome()['brief']


def testBuildsWaitForFreeDiskAndSayWhy(proj, monkeypatch):
    h = home(project(proj)[2])
    with queue(h).tx() as c: c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('worker', json.dumps({'pid': os.getpid(), 'ts': time.time()+3600})))
    (c := proj/'.hive'/'config.toml').write_text(c.read_text().replace('linger = 4\n', 'linger = 4\ndisk = 50\n'))
    space = [10.]
    monkeypatch.setattr('hive.build.room', lambda h: space[0])
    r = ask(proj, wait=0)
    threading.Thread(target=Worker(h).run, daemon=True).start()
    r = ask(proj, rid=r['build'], wait=3)
    assert r['state'] == 'queued' and 'waiting for free disk: 10 GB free, builds need 50' in r['hint']
    space[0] = 80.
    assert ask(proj, rid=r['build'], wait=120)['ok']


def testPureKindsShareResultsAcrossCheckouts(proj, tmp_path):
    kind(proj, 'pure', 'cmd = "echo {root} > {cache}/r.txt"\npure = true\noutputs = ["{cache}/r.txt"]')
    a = ask(proj, 'pure', wait=120)
    sh(proj, 'worktree', 'add', '-q', str(w := tmp_path/'wt5'), '-b', 'w5')
    (w/'.hive').mkdir(exist_ok=True)
    (w/'.hive'/'config.toml').write_text((proj/'.hive'/'config.toml').read_text())
    b = ask(w, 'pure', wait=120)
    assert b['cached'] and b['build'] == a['build']


def testHivesOutsideARepoListTheBuildableRepositories(proj, tmp_path):
    from hive import Hive
    from hive.err import Missing
    ask(proj, wait=120)
    (other := tmp_path/'notrepo').mkdir()
    b = Hive.open(other/'.hive'/'hive.db', other).join('far', 'implementer').welcome()['brief']
    assert 'with `build`' in b and f'checkouts of {proj}' in b and 'build(path=<your checkout>)' in b
    with pytest.raises(Missing, match='pass path'): ask(other)


def testAutoDetectedProjectsAreNotAdvertisedInBriefs(tmp_path):
    from hive import Hive
    (d := tmp_path/'rusty').mkdir()
    (d/'Cargo.toml').write_text('[package]\nname = "x"\n')
    sh(d, 'init', '-q')
    assert 'with `build`' not in Hive.open(d/'.hive'/'hive.db', d).join('r', 'implementer').welcome()['brief']


def testTimeoutsCountBuildingNotWaitingAndProgressShows(proj):
    kind(proj, 'queued', 'cmd = "sleep 6; echo ok"\ntimeout = 2\nlimit = 60')
    r = ask(proj, 'queued', wait=4)
    assert r['state'] == 'running' and 'waiting inside its command' in r['hint'], r
    r = ask(proj, rid=r['build'], wait=120)
    assert r['ok'] and r['state'] == 'done'
    kind(proj, 'stuckq', 'cmd = "sleep 30"\nlimit = 3')
    r = ask(proj, 'stuckq', wait=120)
    assert r['state'] == 'error' and 'overall limit' in r['stopped']
