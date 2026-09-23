import contextlib, sqlite3, threading
from pathlib import Path

from .util import row

SCHEMA = '''
CREATE TABLE IF NOT EXISTS wfs(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,creator INTEGER,ts REAL);
CREATE TABLE IF NOT EXISTS roles(name TEXT PRIMARY KEY,charter TEXT NOT NULL,caps TEXT NOT NULL,builtin INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS agents(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,role TEXT NOT NULL,token TEXT UNIQUE NOT NULL,
  wf INTEGER,parent INTEGER,about TEXT DEFAULT '',state TEXT DEFAULT 'active',status TEXT DEFAULT '',task INTEGER,
  calls INTEGER DEFAULT 0,joined REAL,seen REAL);
CREATE INDEX IF NOT EXISTS agentParent ON agents(parent);
CREATE TABLE IF NOT EXISTS issues(id INTEGER PRIMARY KEY,src INTEGER,holder INTEGER,need TEXT,options TEXT DEFAULT '[]',state TEXT DEFAULT 'open',
  choice TEXT,note TEXT DEFAULT '',fund INTEGER DEFAULT 0,ts REAL,doneAt REAL);
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,ts REAL,agent INTEGER,wf INTEGER,kind TEXT,topic TEXT,text TEXT,data TEXT);
CREATE INDEX IF NOT EXISTS evAgent ON events(agent,seq);
CREATE TABLE IF NOT EXISTS subs(agent INTEGER,topic TEXT,PRIMARY KEY(agent,topic));
CREATE TABLE IF NOT EXISTS cursors(agent INTEGER,name TEXT,seq INTEGER,PRIMARY KEY(agent,name));
CREATE TABLE IF NOT EXISTS msgs(id INTEGER PRIMARY KEY,src INTEGER,dst INTEGER NOT NULL,kind TEXT DEFAULT 'chat',mode TEXT DEFAULT 'queue',
  body TEXT NOT NULL,data TEXT,thread TEXT,re INTEGER,ts REAL,seenAt REAL,readAt REAL,ackAt REAL);
CREATE INDEX IF NOT EXISTS msgDst ON msgs(dst,readAt);
CREATE INDEX IF NOT EXISTS msgThread ON msgs(thread);
CREATE TABLE IF NOT EXISTS ctx(scope TEXT,key TEXT,val TEXT,v INTEGER,agent INTEGER,tags TEXT DEFAULT '[]',ts REAL,PRIMARY KEY(scope,key));
CREATE TABLE IF NOT EXISTS ctxLog(scope TEXT,key TEXT,v INTEGER,val TEXT,agent INTEGER,ts REAL,PRIMARY KEY(scope,key,v));
CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,head INTEGER NOT NULL,ts REAL);
CREATE TABLE IF NOT EXISTS vers(path TEXT,v INTEGER,body TEXT NOT NULL,sha TEXT,agent INTEGER,origin TEXT,what TEXT,ts REAL,PRIMARY KEY(path,v));
CREATE TABLE IF NOT EXISTS views(agent INTEGER,path TEXT,v INTEGER,ts REAL,pend REAL,PRIMARY KEY(agent,path));
CREATE TABLE IF NOT EXISTS claims(id INTEGER PRIMARY KEY,agent INTEGER,path TEXT,lo INTEGER,hi INTEGER,note TEXT,until REAL);
CREATE TABLE IF NOT EXISTS mrs(id INTEGER PRIMARY KEY,path TEXT,state TEXT DEFAULT 'open',src INTEGER,parties TEXT,base INTEGER,head INTEGER,
  body TEXT,hunks TEXT,prop TEXT,oks TEXT DEFAULT '[]',note TEXT DEFAULT '',ts REAL,doneAt REAL,v INTEGER);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,wf INTEGER,title TEXT NOT NULL,about TEXT DEFAULT '',role TEXT,kind TEXT DEFAULT 'work',
  state TEXT NOT NULL,prio INTEGER DEFAULT 0,creator INTEGER,owner INTEGER,parent INTEGER,verify TEXT,checks INTEGER,paths TEXT DEFAULT '[]',
  result TEXT,notes TEXT DEFAULT '[]',tries INTEGER DEFAULT 0,ts REAL,startAt REAL,doneAt REAL);
CREATE TABLE IF NOT EXISTS deps(task INTEGER,dep INTEGER,PRIMARY KEY(task,dep));
CREATE INDEX IF NOT EXISTS depOn ON deps(dep);
CREATE TABLE IF NOT EXISTS tools(name TEXT PRIMARY KEY,owner INTEGER,about TEXT,schema TEXT,kind TEXT,argv TEXT,timeout REAL,ts REAL);
CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY,tool TEXT,src INTEGER,owner INTEGER,args TEXT,state TEXT,result TEXT,err TEXT,
  waitUntil REAL DEFAULT 0,ts REAL,doneAt REAL);
CREATE TABLE IF NOT EXISTS summs(key TEXT PRIMARY KEY,text TEXT,ts REAL)
'''
ADD = (('agents', 'keeper', 'INTEGER'), ('agents', 'depth', 'INTEGER DEFAULT 0'), ('agents', 'budget', 'INTEGER DEFAULT 0'),
       ('agents', 'goal', "TEXT DEFAULT ''"), ('agents', 'launch', 'TEXT'), ('agents', 'deleg', 'INTEGER'), ('agents', 'grants', 'TEXT'),
       ('tasks', 'deliver', "TEXT DEFAULT ''"))


class Db:
    def __init__(s, path, seed=32):
        s.path = Path(path)
        s.path.parent.mkdir(parents=True, exist_ok=True)
        s.loc, s.lock, s.conns, s.added = threading.local(), threading.Lock(), [], set()
        with s.tx() as c:
            for q in SCHEMA.split(';'): c.execute(q)
            for t, col, decl in ADD:
                if col not in {r.name for r in c.execute(f'PRAGMA table_info({t})')}:
                    c.execute(f'ALTER TABLE {t} ADD COLUMN {col} {decl}')
                    s.added.add(col)
            if 'budget' in s.added:
                c.execute('UPDATE agents SET budget=CASE WHEN parent IS NULL THEN ? ELSE 0 END,keeper=parent', (seed,))
                c.execute('WITH RECURSIVE d(id,n) AS (SELECT id,0 FROM agents WHERE parent IS NULL UNION ALL SELECT a.id,d.n+1 FROM agents a '
                          'JOIN d ON a.parent=d.id) UPDATE agents SET depth=COALESCE((SELECT n FROM d WHERE d.id=agents.id),0)')

    def conn(s):
        if (c := getattr(s.loc, 'c', None)) is None:
            c = sqlite3.connect(s.path, timeout=30, isolation_level=None, check_same_thread=False)
            c.row_factory = row
            for p in ('busy_timeout=30000', 'journal_mode=WAL', 'synchronous=NORMAL'): c.execute('PRAGMA '+p)
            s.loc.c, s.loc.depth = c, 0
            with s.lock: s.conns.append(c)
        return c

    @contextlib.contextmanager
    def tx(s):
        c = s.conn()
        if s.loc.depth:
            s.loc.depth += 1
            try: yield c
            finally: s.loc.depth -= 1
            return
        # IMMEDIATE takes the write lock up front, so read-modify-write sequences serialize across processes
        c.execute('BEGIN IMMEDIATE')
        s.loc.depth = 1
        try: yield c
        except BaseException:
            s.loc.depth = 0
            c.execute('ROLLBACK')
            raise
        s.loc.depth = 0
        try: c.execute('COMMIT')
        except BaseException:
            if c.in_transaction: c.execute('ROLLBACK')
            raise

    def q(s, sql, p=()): return s.conn().execute(sql, p).fetchall()

    def one(s, sql, p=()): return s.conn().execute(sql, p).fetchone()

    def close(s):
        with s.lock:
            for c in s.conns:
                with contextlib.suppress(sqlite3.Error): c.close()
            s.conns.clear()
        s.loc = threading.local()
