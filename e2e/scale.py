import argparse, math, random, shutil, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'tests'))
from egregore import check  # noqa: E402

from hive import Hive  # noqa: E402


def main():
    p = argparse.ArgumentParser(description='Seat many agents in one egregore, check its invariants, and time the common calls.')
    p.add_argument('n', type=int, nargs='?', default=20000)
    a = p.parse_args()
    d = Path(tempfile.mkdtemp(prefix='egregore-scale-'))
    try:
        h = Hive.open(d/'.hive'/'hive.db', d)
        e, n = h.egregore, a.n
        t0 = time.monotonic()
        rows = [h.agents.join(f'x{i}', 'implementer', None if i % 3 == 0 else 'big' if i % 3 == 1 else f'wf{i % 300}') for i in range(n)]
        t1 = time.monotonic()
        for r in rows: e.place(r)
        t2 = time.monotonic()
        check(e)
        print(f'{n} agents: join {(t1-t0)/n*1e3:.2f} ms, seat {(t2-t1)/n*1e3:.2f} ms each; {e.stats()["circles"]} circles, '
              f'{e.tree(1, 1)["levels below"]} levels below the root (log7 n = {math.log(n, 7):.1f})')
        print('most seats in a circle', e.db.one('SELECT MAX(k) m FROM (SELECT COUNT(*) k FROM seats GROUP BY circle)').m,
              '; most sub-circles', e.db.one("SELECT MAX(k) m FROM (SELECT COUNT(*) k FROM circles WHERE state='open' GROUP BY parent)").m)
        pick = random.sample(rows, 20)
        for r in pick: e.enter(r)
        xs = [h.sess(r.token) for r in pick]
        e.tick(True)
        for name, f in (('pulse', lambda x: x.pulse()), ('board', lambda x: x.board()), ('post', lambda x: x.post('try caching the lexer tables')),
                        ('flock', lambda x: x.flock()), ('think', lambda x: x.think('a thought')), ('notices', lambda x: (e.seen.clear(), x.notices()))):
            t = time.monotonic()
            for x in xs: f(x)
            print(f'  {name}: {(time.monotonic()-t)/len(xs)*1e3:.1f} ms per call')
        t = time.monotonic()
        with e.db.tx() as c:
            for r in random.sample(rows, n*3//10): h.agents.set(c, r.id, state='left')
        check(e)
        print(f'{n*3//10} agents left in {time.monotonic()-t:.1f} s; {e.circ(1).n} remain in {e.stats()["circles"]} circles, invariants hold')
        h.close()
    finally: shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__': main()
