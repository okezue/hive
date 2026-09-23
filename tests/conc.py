import multiprocessing as mp

from hive import Hive

from .conftest import nums

N, EDITS = 4, 6


def editor(db, root, i, q):
    h = Hive.open(db, root)
    me = h.join(f'p{i}')
    me.read('shared.py')
    out = []
    for k in range(EDITS):
        line = 1 + i*10 + k
        out.append(me.edit('shared.py', [{'old': f'line {line}\n', 'new': f'p{i} edit {k}\n'}])['status'])
    q.put(out)
    h.close()


def taker(db, root, i, q):
    h = Hive.open(db, root)
    me, got = h.join(f'w{i}'), []
    while (t := me.take()['task']) is not None:
        got.append(t['id'])
        me.done(t['id'], 'ok')
    q.put(got)
    h.close()


def spawn(fn, db, root):
    ctx = mp.get_context('spawn')
    q = ctx.Queue()
    ps = [ctx.Process(target=fn, args=(str(db), str(root), i, q)) for i in range(N)]
    for p in ps: p.start()
    res = [q.get(timeout=60) for _ in ps]
    for p in ps: p.join(30)
    return res


def testProcessesEditOneFileWithoutLosingChanges(hive, root):
    (root/'shared.py').write_text(nums(N*10))
    res = spawn(editor, hive.cfg.db, root)
    assert all(s in ('applied', 'merged') for r in res for s in r)
    text = (root/'shared.py').read_text()
    assert all(f'p{i} edit {k}\n' in text for i in range(N) for k in range(EDITS))
    assert hive.db.one("SELECT head FROM files WHERE path='shared.py'").head == 1 + N*EDITS


def testProcessesTakeEachTaskOnce(hive, root):
    hive.op().plan([{'title': f'job {i}'} for i in range(20)])
    got = [t for r in spawn(taker, hive.cfg.db, root) for t in r]
    assert sorted(got) == sorted(set(got)) and len(got) == 20 and hive.tasks.counts() == {'done': 20}
