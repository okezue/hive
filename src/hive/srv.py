import inspect, json, os, sqlite3, threading
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from .err import Anon, Denied, Err, Missing
from .sess import Sess

GROUPS = {
    'core': 'me progress leave overview digest watch roles',
    'msgs': 'send inbox ack ask wait share handoff follow',
    'ctx': 'put get keys drop',
    'files': 'read edit write sync diff release claim files merges propose respond abandon',
    'tasks': 'plan tasks task take done fail verify cancel dispatch define assign retry faults',
    'tree': 'spawn gather tree node walk path find brief fund adopt escalate decide issues',
    'know': 'note findings material compose gist stale harvest distill recall weigh retire',
    'tools': 'offer tools call answer result withdraw',
}

INFO = ('Hive connects you with the other agents in this session. Start with join (or me if your identity is preset) to learn your '
        'role, token, and who else is here. Responses may carry interrupts (handle first, then ack), messages, a queued count, and '
        'updates on what you follow. Change shared files with edit/write (or sync after another editor) so concurrent changes merge; '
        'overlapping changes open a merge request you settle with the other author. Stay in your role.')

DOCS = {
    'join': 'Join the hive. Returns your token, your charter, how to work here, and who else is present.',
    'me': 'Your identity, role, capabilities, current task, follows, and open files.',
    'progress': 'Post a progress line; others see it in overview, digests, and watch.',
    'leave': 'Leave the hive; a task you are running is released for someone else.',
    'overview': 'Everyone with role, state, status, task, and open files; active tasks; open merge requests; recent events.',
    'digest': 'What other agents did since your last digest, summarized to the budget.',
    'watch': "Inspect one agent: 'live' follows new activity (wait blocks for more), 'window' pages back through history (pass "
             "before=older), 'summary' condenses any length of activity.",
    'roles': 'All roles with charters and capabilities.',
    'send': 'Message agents. mode queue: they read it when they choose; steer: shown on their next Hive call; interrupt: shown on '
            'their next tool call and repeated until acknowledged.',
    'inbox': 'Read your messages, most urgent first; marks them read.',
    'ack': 'Acknowledge handled interrupts so they stop reappearing.',
    'ask': 'Ask one agent a question and wait for the reply.',
    'wait': 'Block until a message or an update on something you follow arrives. Use it when idle.',
    'share': 'Share one thing: a context entry (key), a file range (path, lines), a task, a message, or text.',
    'handoff': 'Pass your working context to another agent: task, open files, status, and a summary of your activity.',
    'follow': 'Follow topics (file:src/*, agent:alice, task:t3, context:plan*, kind:task.*) or stop following them.',
    'put': 'Publish or update a shared context entry (findings, plans, decisions). Versioned; expect gives compare-and-swap.',
    'get': 'Read a shared context entry, optionally with history.',
    'keys': 'List shared context entries with previews.',
    'drop': 'Delete a shared context entry.',
    'read': 'Read a shared file and follow it. Shows who else has it open and what changed since your last read.',
    'edit': 'Replace exact text in a shared file. Concurrent changes elsewhere are kept; overlapping ones open a merge request.',
    'write': 'Create a file or replace its content, three-way merged with changes made since your base version.',
    'sync': 'Record a change you made to a file with another tool, merging it with concurrent changes and telling others.',
    'diff': 'Diffs of a file since a version (default: since your last read), with authors.',
    'release': 'Stop following a file and drop your claims on it.',
    'claim': 'Announce a region you are about to change; others are warned and you hear if they edit it.',
    'files': 'Who has a file open, its claims, and merge requests; without a path, all tracked files.',
    'merges': 'Show a merge request (both sides of each conflict, the proposal, the thread), or list them.',
    'propose': "Propose a resolution: picks has one entry per conflict ('requester', 'current', 'base', 'both', 'current+requester', "
               "or {'text': ...}), or give the whole resolved content. Every other author must accept.",
    'respond': 'Accept or reject the proposed resolution of a merge request (rejecting needs a note).',
    'abandon': 'Drop your conflicting change; the current version stands.',
    'plan': 'Create tasks with dependencies (after). Tasks with no dependency path between them run concurrently; verify sends '
            'finished work to an independent verifier before dependents start.',
    'tasks': 'List tasks and counts by state.',
    'task': 'One task in full, with the results of the tasks it depends on.',
    'take': 'Take a ready task (omit id for the next one your role can do). Returns it with its dependencies\' results.',
    'done': 'Finish your task with a result: what changed, where, and how you checked it.',
    'fail': 'Give up on a task; retry puts it back for another agent, otherwise dependents are blocked.',
    'verify': 'Approve or reject work under review with evidence (verifier roles, never your own work).',
    'cancel': 'Cancel a task you created (coordinators: any); dependents are blocked.',
    'dispatch': 'Coordinators: create an agent for a ready task and get the prompt to start it with.',
    'spawn': "Spawn a helper below you with a goal and a deliverable. It gets its own task under yours, a slice of your budget, capabilities "
             "no wider than yours, and can spawn helpers of its own. launch 'host' returns a prompt for your own subagent tool, 'runner' has "
             "Hive start it as a separate process, 'none' only registers it.",
    'gather': 'Wait for your children (or the listed agents or tasks) to settle and collect their results; any returns at the first.',
    'tree': 'Show the agent tree around one node (default: your cursor, else you) to a depth, with +N more for wide levels.',
    'node': 'One node in full: goal, task, budget, keeper, children, an exact rollup of its subtree, and which descendant needs attention.',
    'walk': "Move your view cursor: up, down, down:<name>, next, prev, root, me, or a name. Returns the node there. Moving never changes who you act as.",
    'path': 'The lineage from the root to a node with each ancestor\'s goal: why this agent exists.',
    'find': 'Search a subtree for agents by name, goal, status, or task, optionally by state or role.',
    'brief': "Summarize a subtree: exact blockers first, then each child's work condensed along the tree to fit the budget.",
    'fund': 'Give some of your budget to an agent below you.',
    'adopt': 'Take custody of an agent below you (or any, for coordinators): its escalations come to you.',
    'escalate': 'Ask your keeper for a decision (options, or extra budget via fund) instead of guessing; it moves up the tree if they pass it on.',
    'decide': "Answer an issue raised to you: a choice (and optionally budget), or choice='up' to pass it to your own keeper.",
    'issues': 'Open issues you raised or hold (all=true for every open issue).',
    'retry': 'Reopen a failed, cancelled, or blocked task (or skip its retry wait); a runner restarts it with a brief of every earlier attempt. '
             'Without an id, coordinators resume agent commands the runner paused after authentication, setup, or long rate-limit failures.',
    'faults': 'How agent commands are doing (ok, cooling down, probing, paused), recent agent failures and restarts, tasks waiting to '
              'retry, and open issues about them.',
    'note': "Record a finding as you work: a fact, decision, problem, method, or result, with refs to evidence (files, tasks, messages; "
            "'against:f12' marks a contradiction). Composers and distillers build on findings.",
    'findings': 'Findings recorded by an agent and (deep) everyone below it, newest first, with where each came from.',
    'material': "A composer's input for one node: its own findings, each child's composition (or raw findings if uncomposed), and flagged contradictions.",
    'compose': 'Composers: record the combined account of a node and its subtree, citing the findings (f..) and child compositions (cp..) it uses. '
               'Reports findings and branches left out.',
    'gist': "The latest composition of a node's subtree and whether new findings have arrived since.",
    'stale': 'Nodes below one whose compositions are missing or out of date, deepest first: the composing worklist.',
    'harvest': "A distiller's input: each independent branch's composition or findings, echoes (terms that recur across branches, with the "
               'findings they came from), and saved insights that look related.',
    'distill': "Distillers: save an insight, 'observed' (a pattern in the work) or 'reusable' (a lesson for future work), citing evidence. "
               'Similar saved insights are shown first so you add evidence instead of duplicating (into=<id>).',
    'recall': 'Search insights saved in this project (and the global library) by relevance and confidence.',
    'weigh': 'Add evidence for or against a saved insight. Support from independent branches raises its confidence; counter-evidence contests it.',
    'retire': 'Distillers and coordinators: retire an insight that no longer holds.',
    'define': 'Coordinators: define a role with a charter and capabilities.',
    'assign': "Coordinators: change an agent's role; it is interrupted with its new charter.",
    'offer': "Share a tool. kind 'agent': calls come to you and you reply with answer; 'command': Hive runs argv with the arguments "
             'as JSON on stdin.',
    'tools': 'Tools other agents share, with owners and schemas.',
    'call': 'Call a shared tool; waits up to wait seconds, else returns a call id for result.',
    'answer': 'Reply to a call of a tool you share.',
    'result': 'Check or wait for the result of a shared tool call.',
    'withdraw': 'Stop sharing a tool.',
}

ARGS = {
    'agent': 'Your token from join; needed only when several agents share this connection',
    'to': 'Agent name, role:<role>, workflow:<name>, parent, keeper, children, siblings, subtree, ancestors, or *',
    'scope': 'auto (reads walk your lineage, then workflow, then session), node (yours, visible to your subtree), team (your parent\'s), workflow, or session',
    'base': 'Version your change is based on; defaults to your last read',
    'thread': 'Thread name, e.g. mr3',
    're': 'Message id you are answering, e.g. m12',
    'id': 'Id like t3, m12, mr2, or c5',
    'since': 'Start after this event number (watch) or version (diff)',
    'budget': 'Maximum length in tokens',
    'expect': 'Fail unless the entry is still at this version',
    'wait': 'Seconds to wait',
    'secs': 'Seconds to wait',
    'retry.note': 'Why it is being retried, or what changed',
    'tasks.state': 'Comma-separated: pending, ready, running, in_review, done, failed, blocked, cancelled',
    'progress.state': 'active, idle, or done',
    'merges.state': 'open, resolved, abandoned, or all',
    'workflow': 'Workflow name for scoping tasks, broadcasts, and context',
    'of': 'Agent name (or a path like coord/alice/bob); empty means your cursor, else you',
    'spawn.budget': 'Agents the child may create below it; it costs you this plus one',
    'spawn.role': 'The child role; defaults to yours. Its capabilities are cut down to what you have',
    'spawn.grants': 'Narrow the child to these capabilities (a subset of yours and its role)',
    'spawn.deliver': 'What the child must hand back, e.g. "a patch to src/x.py and passing tests"',
    'spawn.launch': 'host, runner, or none',
    'gather.of': 'Agent names or task ids; default all your children',
    'gather.budget': 'Maximum length of returned results in tokens',
    'tree.depth': 'Levels below the node to show',
    'tree.after': 'Continue a wide level after this child',
    'fund.amount': 'Budget to hand down',
    'note.kind': 'fact, decision, problem, method, or result',
    'note.refs': "Evidence such as 'src/a.py:40', 't3', 'm12', or 'against:f7' for a contradiction",
    'compose.sources': 'The findings (f12) and child compositions (cp3) you combined',
    'compose.gaps': 'What is unknown or unresolved',
    'distill.kind': 'observed or reusable',
    'distill.evidence': 'Findings (f..), compositions (cp..), or tasks (t..); cite one from each branch that shows it',
    'distill.scope': 'project (this repository) or global (every project on this machine)',
    'distill.into': 'Add your evidence to this existing insight instead of saving a new one',
    'weigh.stance': 'support or against',
    'recall.state': 'proposed, established, or contested',
    'dispatch.budget': 'Budget to give the new agent out of yours (default 0)',
    'chain': 'Run the tasks in order, each after the previous',
}


PRIV = {'exec', 'define', 'spawn', 'manage', 'compose', 'distill'}


class Who:
    def __init__(s, hive, strict=False):
        s.hive, s.strict, s.lock, s.joined, s.default, s.env = hive, strict, threading.Lock(), [], None, strict

    def bind(s, x):
        with s.lock:
            if x.id not in s.joined: s.joined.append(x.id)

    def fromEnv(s):
        if s.env: return
        h = s.hive
        if t := os.environ.get('HIVE_AGENT_TOKEN'): s.default = h.sess(t).id
        elif n := os.environ.get('HIVE_AGENT'):
            try: a = h.agents.named(n)
            except Missing: a = None
            s.default = a.id if a and a.state != 'left' else h.join(n, os.environ.get('HIVE_ROLE', 'implementer'),
                                                                    os.environ.get('HIVE_WORKFLOW') or None).id
        s.env = True

    def __call__(s, agent):
        if agent:
            try: return s.hive.sess(agent)
            except Anon:
                if s.strict: raise
                with s.lock:
                    if x := next((i for i in s.joined if s.hive.agents.get(i).name == agent), None): return Sess(s.hive, x)
                raise
        if s.strict: raise Anon('pass your token as agent', 'join returns it')
        with s.lock:
            s.fromEnv()
            if s.default: return Sess(s.hive, s.default)
            if len(s.joined) == 1: return Sess(s.hive, s.joined[0])
            if not s.joined: raise Anon('you have not joined the hive', 'call join(name=..., role=...) first')
        raise Anon('several agents joined through this connection, so Hive cannot tell who is calling', 'pass your token as agent')


def render(res, note=None):
    note, res = dict(note or {}), res if isinstance(res, dict) else {'result': res}
    raw = res.get('content') if isinstance(res.get('content'), str) and 'version' in res else None
    body = {k: v for k, v in res.items() if raw is None or k != 'content'}
    out = ({'interrupts': note.pop('interrupts'), 'interruptsHint': note.pop('interruptsHint', None)} if 'interrupts' in note else {}) | body
    text = json.dumps(out | ({'notices': note} if note else {}), ensure_ascii=False, indent=1, default=str)
    if raw is None: return text
    return text + f"\n----- {res['path']} v{res['version']} (lines {res.get('start', 1)}-{res.get('end', res.get('lines'))}) -----\n{raw}"


def wrap(name, who):
    ps = list(inspect.signature(getattr(Sess, name), eval_str=True).parameters.values())[1:]
    ps = [p.replace(annotation=Annotated[p.annotation, Field(description=d)]) if (d := ARGS.get(f'{name}.{p.name}', ARGS.get(p.name))) else p
          for p in ps]
    ps.append(inspect.Parameter('agent', inspect.Parameter.KEYWORD_ONLY, default=None,
                                annotation=Annotated[str | None, Field(description=ARGS['agent'])]))

    def tool(**kw):
        try: x = who(kw.pop('agent', None))
        except Err as e: raise ToolError(str(e)) from None
        try: res = getattr(x, name)(**kw)
        except sqlite3.Error as e:
            raise ToolError(f'storage error: {e}' + ('; the store is busy with other agents, so call again in a few seconds' if 'locked' in str(e) or 'busy' in str(e) else '')) from None
        except Err as e:
            n = x.notices()
            raise ToolError(str(e) + (f'\n\n{render({}, n)}' if n else '')) from None
        return render(res, x.notices())

    tool.__name__, tool.__doc__, tool.__signature__ = name, DOCS[name], inspect.Signature(ps, return_annotation=str)
    return tool


def build(hive, groups=tuple(GROUPS), who=None, strict=False):
    srv, who = MCPServer('hive', instructions=INFO), who or Who(hive, strict)

    def join(name: Annotated[str, Field(description='Your agent name, unique in the hive')],
             role: Annotated[str, Field(description='coordinator, implementer, verifier, reviewer, researcher, observer, or custom')] = 'implementer',
             workflow: Annotated[str | None, Field(description=ARGS['workflow'])] = None, about: str = '',
             takeover: Annotated[bool, Field(description='Reclaim your name after a restart')] = False,
             key: Annotated[str | None, Field(description='Admin key, needed over HTTP for roles that can run commands or manage agents')] = None) -> str:
        try:
            if strict and PRIV & hive.roles.get(role).caps and (not key or key != os.environ.get('HIVE_KEY')):
                raise Denied(f'joining as {role} over HTTP needs the admin key', 'pick a role without exec, define, spawn, or manage')
            x = hive.join(name, role, workflow, None, about, takeover)
        except Err as e: raise ToolError(str(e)) from None
        who.bind(x)
        return render(x.welcome())

    srv.tool(description=DOCS['join'], structured_output=False)(join)
    for g in groups:
        for n in GROUPS[g].split(): srv.tool(name=n, description=DOCS[n], structured_output=False)(wrap(n, who))
    return srv


def groups(text=None):
    if not (text := text or os.environ.get('HIVE_TOOLS', '')): return tuple(GROUPS)
    gs = tuple(x.strip() for x in text.split(',') if x.strip())
    if bad := set(gs) - set(GROUPS): raise SystemExit(f"unknown tool groups {', '.join(sorted(bad))}; known: {', '.join(GROUPS)}")
    return gs
