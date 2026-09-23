import os, tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT = '''[hive]
reminder = 20        # restate an agent's charter every N Hive calls, 0 to disable
tries = 2            # times a task may be taken before it fails
stale = 900          # seconds without activity before an agent shows as stale

[summarizer]
backend = "auto"     # auto | llm | extractive; auto uses the LLM when an API key is set
base_url = "https://api.x.ai/v1"
model = "grok-4.5"
api_key_env = "XAI_API_KEY"
chunk = 3000

[tree]
depth = 4            # how many levels below a root agent may spawn
fanout = 8           # live children per agent
budget = 32          # agents a root may create in its whole subtree; spawning hands slices of it down

[insights]
auto = true          # file compose and distill tasks when there are composers or distillers to take them
min = 2              # finished subtasks a task needs before its subtree gets composed
global = "~/.hive/insights.db"   # library for insights saved with scope "global"; project ones live in .hive/insights.db

[runner]
max = 3
poll = 1.0

# Agent command per role ("default" for any). Placeholders: {prompt} {promptFile} {task} {agent} {token} {role} {db} {root} {mcp}
# [runner.roles.default]
# command = ["claude", "-p", "{prompt}", "--mcp-config", "{mcp}"]
'''


@dataclass
class Cfg:
    db: Path
    root: Path
    reminder: int = 20
    tries: int = 2
    stale: float = 900.
    summ: dict = field(default_factory=dict)
    runner: dict = field(default_factory=dict)
    depth: int = 4
    fanout: int = 8
    budget: int = 32
    insights: dict = field(default_factory=dict)

    @property
    def dir(s): return s.db.parent.parent if s.db.parent.name == 'sessions' else s.db.parent


def find(start):
    return next((d/'.hive' for d in [start, *start.parents] if (d/'.hive').is_dir()), None)


def load(db=None, root=None, session=None, cwd=None):
    cwd = cwd or Path.cwd()
    db, session = db or os.environ.get('HIVE_DB'), session or os.environ.get('HIVE_SESSION')
    if db: db = Path(db).expanduser().resolve()
    else:
        d = find(cwd) or cwd/'.hive'
        db = d/'sessions'/f'{session}.db' if session else d/'hive.db'
    d = db.parent.parent if db.parent.name == 'sessions' else db.parent
    root = root or os.environ.get('HIVE_ROOT')
    root = Path(root).expanduser().resolve() if root else d.parent if d.name == '.hive' else cwd
    st = tomllib.loads((d/'config.toml').read_text()) if (d/'config.toml').is_file() else {}
    h, t = st.get('hive', {}), st.get('tree', {})
    return Cfg(db, root, int(h.get('reminder', 20)), int(h.get('tries', 2)), float(h.get('stale', 900)),
               dict(st.get('summarizer', {})), dict(st.get('runner', {})), int(t.get('depth', 4)), int(t.get('fanout', 8)), int(t.get('budget', 32)),
               dict(st.get('insights', {})))


def init(root):
    d = root/'.hive'
    d.mkdir(parents=True, exist_ok=True)
    for f, t in (('config.toml', DEFAULT), ('.gitignore', '*\n!config.toml\n!.gitignore\n')):
        if not (d/f).exists(): (d/f).write_text(t)
    return d
