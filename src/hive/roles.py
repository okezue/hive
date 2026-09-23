from .err import Bad, Denied, Missing
from .util import R, J, an, dumps, name

CAPS = frozenset('read write plan claim verify manage spawn fork send broadcast post use offer exec define'.split())
BASE = {'read', 'send', 'use', 'post'}

ROLES = {
    'coordinator': ('Plan the work, split it into tasks with clear owners and dependencies, start or dispatch agents, watch '
                    'progress, and settle disputes. Leave implementation and verification to the agents whose roles cover them.', CAPS),
    'implementer': ('Implement the task you took, inside the paths it names. Edit shared files through Hive so concurrent '
                    'changes merge, post progress, and hand finished work to verification with done. Ask the owner of a '
                    'region before changing it.', BASE | {'write', 'claim', 'plan', 'offer', 'fork'}),
    'verifier': ('Independently check work others finished: read the change, run the tests or checks, and approve or reject '
                 'it with verify and concrete evidence. Report defects to the implementer; do not fix them yourself.',
                 BASE | {'claim', 'verify', 'offer', 'fork'}),
    'reviewer': ('Review designs and changes for correctness, clarity, and fit. Send findings to the author and approve or '
                 'reject review tasks; the author makes the edits.', BASE | {'claim', 'verify', 'fork'}),
    'researcher': ('Investigate questions, read code and sources, and publish findings with put so others can build on them. '
                   'Leave code changes to implementers.', BASE | {'claim', 'offer', 'fork'}),
    'observer': ('Watch the hive and answer questions about it. Observers read and message only.', {'read', 'send'}),
}


class Roles:
    def __init__(s, db):
        s.db = db
        with db.tx() as c:
            c.executemany('INSERT OR REPLACE INTO roles VALUES(?,?,?,1)', [(k, ch, dumps(sorted(cp))) for k, (ch, cp) in ROLES.items()])

    def _r(s, r): return R(name=r.name, charter=r.charter, caps=frozenset(J(r.caps, [])), builtin=bool(r.builtin))

    def get(s, n):
        if (r := s.db.one('SELECT * FROM roles WHERE name=?', (n,))) is None:
            raise Missing(f'unknown role {n!r}', 'known: ' + ', '.join(x.name for x in s.all()))
        return s._r(r)

    def all(s): return [s._r(r) for r in s.db.q('SELECT * FROM roles ORDER BY builtin DESC,name')]

    def define(s, n, charter, caps):
        name(n, 'role name')
        if not charter.strip(): raise Bad('a role needs a charter that states its job')
        if bad := set(caps) - CAPS: raise Bad('unknown capabilities: ' + ', '.join(sorted(bad)), 'known: ' + ' '.join(sorted(CAPS)))
        with s.db.tx() as c:
            if (r := c.execute('SELECT builtin FROM roles WHERE name=?', (n,)).fetchone()) and r.builtin:
                raise Bad(f'{n} is built in')
            c.execute('INSERT OR REPLACE INTO roles VALUES(?,?,?,0)', (n, charter.strip(), dumps(sorted(set(caps)))))
        return s.get(n)

    def caps(s, a): return frozenset(J(a.grants)) if a.get('grants') else s.get(a.role).caps

    def can(s, a, cap): return cap in s.caps(a)

    def need(s, a, cap, act):
        if not s.can(a, cap):
            r = s.get(a.role)
            raise Denied(f"{a.name} is {an(r.name)}{' with narrowed grants' if a.get('grants') else ''}, and cannot {act} (needs {cap})",
                         f'your charter: {r.charter} Ask an agent whose role covers it, or a coordinator to reassign you')
