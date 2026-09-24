import json

from hive.cli import main


def cli(root, *args, capsys):
    code = main(['--db', str(root/'.hive'/'hive.db'), '--root', str(root), *args])
    return code, capsys.readouterr()


def testInitStatusSendPlan(root, capsys, monkeypatch):
    monkeypatch.chdir(root)
    assert main(['init']) == 0
    out = capsys.readouterr().out
    assert json.loads(out)['mcpServers']['hive']['env']['HIVE_ROOT'] == str(root) and (root/'.hive'/'config.toml').exists()
    (root/'p.json').write_text(json.dumps({'tasks': [{'key': 'a', 'title': 'A'}, {'title': 'B', 'after': ['a']}]}))
    code, o = cli(root, 'plan', str(root/'p.json'), capsys=capsys)
    assert code == 0 and len(json.loads(o.out)['created']) == 2
    code, o = cli(root, 'tasks', capsys=capsys)
    assert 't1' in o.out and 't2' in o.out and '< t1' in o.out
    code, o = cli(root, 'status', capsys=capsys)
    assert 'operator' in o.out and 'ready=1' in o.out
    code, o = cli(root, 'send', 'operator', 'note to self', capsys=capsys)
    assert json.loads(o.out)['to'] == ['operator']
    code, o = cli(root, 'tail', '--limit', '3', capsys=capsys)
    assert 'task.created' in o.out
    code, o = cli(root, 'mcp-config', '--agent', 'alice', '--role', 'verifier', capsys=capsys)
    assert json.loads(o.out)['mcpServers']['hive']['env']['HIVE_ROLE'] == 'verifier'


def testErrorsExitTwo(root, capsys):
    code, o = cli(root, 'status', capsys=capsys)
    assert code == 2 and 'no hive at' in o.err and not (root/'.hive').exists()
    cli(root, 'mcp-config', capsys=capsys)
    code, o = cli(root, 'history', 'ghost', capsys=capsys)
    assert code == 2 and 'ghost' in o.err


def testSummaryAndHistory(hive, root, capsys):
    a = hive.join('alice')
    for i in range(5): a.progress(f'step {i}')
    code, o = cli(root, 'history', 'alice', '--limit', '2', capsys=capsys)
    assert json.loads(o.out)['events'][-1].endswith('step 4')
    code, o = cli(root, 'summary', '--agent', 'alice', capsys=capsys)
    assert 'step 4' in o.out
