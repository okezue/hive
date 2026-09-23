from pathlib import Path

from .agents import Agents
from .aware import Aware
from .board import Board
from .cfg import load
from .db import Db
from .disk import Disk
from .err import Missing
from .files import Files
from .log import Log
from .mail import Mail
from .notice import Notice
from .roles import Roles
from .sess import Sess
from .summ import Summ, backend
from .tasks import Tasks
from .tools import Tools
from .tree import Tree


class Hive:
    def __init__(s, cfg, summ=None):
        s.cfg, s.db, s.root = cfg, Db(cfg.db, cfg.budget), Path(cfg.root)
        s.disk, s.roles, s.log = Disk(s.root), Roles(s.db), Log(s.db)
        s.agents = Agents(s.db, s.log, s.roles, cfg.stale, cfg.budget)
        s.mail = Mail(s.db, s.log, s.agents)
        s.summ = summ or Summ(backend(cfg.summ), chunk=int(cfg.summ.get('chunk', 3000)))
        s.summ.db = s.summ.db or s.db
        s.board = Board(s.db, s.log, s.agents)
        s.files = Files(s.db, s.log, s.mail, s.agents, s.roles, s.disk)
        s.tasks = Tasks(s.db, s.log, s.mail, s.agents, s.roles, lambda ls, b, f: s.summ(ls, b, f).text, cfg.tries)
        s.tools = Tools(s.db, s.log, s.mail, s.agents, s.roles, s.root)
        s.aware = Aware(s.db, s.log, s.agents, s.tasks, s.files, s.summ, cfg.stale)
        s.notice = Notice(s.mail, s.log, s.agents, s.roles, s.files.mrs, cfg.reminder)
        s.tree = Tree(s.db, s.log, s.mail, s.agents, s.roles, s.tasks, s.summ, cfg)

    @classmethod
    def open(cls, db=None, root=None, session=None, summ=None): return cls(load(db, root, session), summ)

    def join(s, name, role='implementer', workflow=None, parent=None, about='', takeover=False):
        return Sess(s, s.agents.join(name, role, workflow, parent and s.agents.named(parent).id, about, takeover).id)

    def sess(s, token): return Sess(s, s.agents.byToken(token).id)

    def op(s, name='operator'):
        try: a = s.agents.named(name)
        except Missing: a = None
        return Sess(s, a.id) if a and a.state != 'left' else s.join(name, 'coordinator', about='the human at the CLI')

    def close(s): s.db.close()
