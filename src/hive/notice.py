from .log import match
from .mail import show
from .util import an, line

CAP, SCAN = 8, 500


class Notice:
    def __init__(s, mail, log, agents, roles, mrs, every):
        s.mail, s.log, s.agents, s.roles, s.mrs, s.every = mail, log, agents, roles, mrs, every

    def __call__(s, a, eat=True):
        names, out = s.agents.names(), {}
        if urgent := s.mail.urgent(a.id):
            fresh = [m for m in urgent if m.seenAt is None]
            out['interrupts'] = [show(m, names) for m in fresh] + [
                {'id': f'm{m.id}', 'from': names.get(m.src, 'hive'), 'body': line(m.body, 140), 'reminder': 'still unacknowledged'}
                for m in urgent if m.seenAt is not None]
            out['interruptsHint'] = 'handle these first, then ack them'
            if eat: s.mail.mark([m.id for m in fresh])
        if steers := s.mail.steers(a.id):
            out['messages'] = [show(m, names) for m in steers]
            if eat: s.mail.mark([m.id for m in steers])
        if q := s.mail.queued(a.id): out['queued'] = f'{q} queued message(s); read them with inbox at a stopping point'
        if ups := s.updates(a, names, eat): out['updates'] = ups
        if mrs := [f'mr{m.id}' for m in s.mrs.involving(a.id) if a.id in s.mrs.waiting(m)]: out['mergesWaitingOnYou'] = mrs
        if iss := s.log.db.q("SELECT id FROM issues WHERE holder=? AND state='open' ORDER BY id", (a.id,)):
            out['issuesWaitingOnYou'] = [f'i{x.id}' for x in iss]
        if s.every and a.calls and a.calls % s.every == 0:
            r = s.roles.get(a.role)
            out['roleReminder'] = f"You are {a.name}, {an(r.name)}. {r.charter}" + (f' Your task is t{a.task}.' if a.task else '')
        return out

    def scan(s, a, names, stop=False):
        cur, pats, hit = s.log.cur(a.id, 'notices'), s.log.topics(a.id), []
        if cur is None or not pats: return cur, hit
        while page := s.log.find(after=cur, notBy=a.id, limit=SCAN):
            hit += [e for e in page if match(pats, e, names.get(e.agent))]
            cur = page[-1].seq
            if len(page) < SCAN or (stop and hit): break
        return cur, hit

    def updates(s, a, names, eat):
        was = s.log.cur(a.id, 'notices')
        cur, hit = s.scan(a, names)
        if eat and cur is not None and cur != was:
            with s.log.db.tx() as c: s.log.setCur(c, a.id, 'notices', cur, True)
        out = []
        for e in hit[:CAP]:
            x = f"{names.get(e.agent, 'hive')} {e.kind}: {e.text}"
            if e.kind == 'file.changed' and isinstance(e.data, dict) and e.data.get('diff'): x += '\n' + '\n'.join(e.data['diff'].splitlines()[:30])
            out.append(x)
        return out + ([f'... {len(hit)-CAP} more; digest has the rest'] if len(hit) > CAP else [])

    def pending(s, a): return bool(s.mail.unread(a.id) or s.scan(a, s.agents.names(), True)[1])
