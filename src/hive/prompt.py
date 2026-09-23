from .util import an, dumps

PROTOCOL = '''How to work in the hive (MCP server "hive"):
- Hive responses may carry `interrupts` (handle first, then `ack`), `messages` that arrived since your last call, a `queued` count (read with `inbox` at a stopping point), and `updates` on files and tasks you follow.
- Shared files: `read`, then `edit` or `write`; after changing a file with another tool, call `sync`. Changes by others to other parts of a file merge automatically and you are told what changed. If your change overlaps someone else's, Hive opens a merge request: agree with that agent in its thread, then `propose` and `respond`.
- Talk with `send` (mode queue, steer, or interrupt when it cannot wait), `ask` (waits for the answer), `share` (a file range, context entry, task, or message), and `handoff` (pass on your context).
- Stay aware with `overview`, `digest`, and `watch` (view live, window, or summary). The agents form a tree: `tree`, `node`, `walk`, `path`, `find`, and `brief` navigate it one neighborhood at a time.
- When part of your work splits off cleanly, `spawn` a helper with a goal and a deliverable, then `gather` its result. Escalate decisions you cannot make with `escalate`.
- Record what you learn as you go with `note` (facts, decisions, problems, methods; `against:f12` in refs marks a contradiction). Composers combine findings up the tree and distillers keep the insights; `recall` searches insights saved from earlier work.
- Post `progress` at milestones and publish findings with `put`.
- Stay within your role and your task's paths; ask the agent whose job it is when something is outside them.'''


def brief(n, role, charter, tok=None):
    parts = [f'You are {n}, {an(role)} in a Hive: a shared workspace where several agents work at once.', f'Your charter: {charter}']
    if tok: parts.append(f'Your Hive token is "{tok}". Pass agent="{tok}" on every Hive call (required when agents share a connection).')
    return '\n\n'.join(parts+[PROTOCOL])


def tipText(tips): return 'Insights saved from earlier work that may apply (weigh them if they help or mislead):\n' + '\n'.join(f'- {x}' for x in tips)


def task(b, t, deps=None, tips=None):
    parts = [b, f"Your task: {t['id']} {t['title']}"] + ([t['about']] if t.get('about') else [])
    if t.get('paths'): parts.append('Work only in: ' + ', '.join(t['paths']))
    if deps:
        parts.append('Results of the tasks this one depends on:\n' + '\n'.join(
            f"- {d['id']} {d['title']} ({d['state']}, by {d.get('by')}):\n{d.get('result') or d.get('summary') or ''}" for d in deps))
    parts += [tipText(tips)] if tips else []
    parts.append(f"Start with take('{t['id']}'). Check the work independently, then call verify('{t.get('checks')}', ok=true|false, notes=...) "
                 'with concrete evidence.' if t.get('kind') == 'verify' else
                 f"Start with take('{t['id']}'). When finished call done('{t['id']}', result=...) saying what changed, where, and how you "
                 f"checked it; if you cannot finish, fail('{t['id']}', reason=...).")
    return '\n\n'.join(parts)


def lineage(b, chain, t, budget, room, grants=None, tips=None):
    why = '\n'.join(f"{'  '*i}{x.name} ({x.role})" + (f': {x.goal}' if x.goal else '') for i, x in enumerate(chain))
    parts = [b, f'Why you exist (root first):\n{why}', f'Your delegation, t{t.id}:\n{t.about}']
    parts += [f'Deliver: {t.deliver}'] if t.deliver else []
    parts += ['Work only in: ' + ', '.join(t.paths)] if t.paths else []
    parts += ['Your capabilities are narrowed to: ' + ', '.join(grants)] if grants else []
    parts += [tipText(tips)] if tips else []
    parts.append(f"You may spawn helpers below you (budget {budget}, {room} more level(s)); gather collects their results, and you cannot finish "
                 f"t{t.id} while they are unsettled. If you are blocked, escalate to your keeper instead of guessing.")
    parts.append(f"Start with take('t{t.id}'). Finish with done('t{t.id}', result=...) covering what the delivery asks for; if you cannot, "
                 f"fail('t{t.id}', reason=...).")
    return '\n\n'.join(parts)


def mcp(cmd, env): return dumps({'mcpServers': {'hive': {'command': cmd[0], 'args': cmd[1:], 'env': env}}})
