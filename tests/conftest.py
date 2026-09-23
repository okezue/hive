import pytest

from hive import Hive
from hive.summ import Extract, Summ


@pytest.fixture
def root(tmp_path):
    (d := tmp_path/'ws').mkdir()
    return d


@pytest.fixture(autouse=True)
def lib(monkeypatch, tmp_path): monkeypatch.setenv('HIVE_GLOBAL', str(tmp_path/'global'/'insights.db'))


@pytest.fixture
def hive(root, monkeypatch):
    for k in ('XAI_API_KEY', 'HIVE_LLM_API_KEY', 'HIVE_AGENT', 'HIVE_AGENT_TOKEN', 'HIVE_DB', 'HIVE_ROOT'): monkeypatch.delenv(k, raising=False)
    h = Hive.open(root/'.hive'/'hive.db', root, summ=Summ(Extract(), chunk=400))
    yield h
    h.close()


@pytest.fixture
def team(hive):
    return {n: hive.join(n, r) for n, r in (('coord', 'coordinator'), ('alice', 'implementer'), ('bob', 'implementer'), ('vera', 'verifier'))}


def nums(n, **ch): return ''.join(ch.get(f'l{i}', f'line {i}')+'\n' for i in range(1, n+1))
