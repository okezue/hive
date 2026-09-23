# Hive

Hive lets several coding agents work in the same workspace at the same time and actually cooperate. Each agent joins a shared session, gets a role with a charter it is held to, and from then on can see who else is present and what they are doing, message them with the right urgency, share context and specific artifacts, call tools other agents expose, take tasks from a dependency graph, and edit the same files concurrently without overwriting each other.

It works with any harness that speaks MCP (Claude Code, Grok Build, Codex, Cursor, and others), and harness hooks add the parts MCP alone cannot do, such as interrupting an agent between two unrelated tool calls. Everything is stored in one SQLite file, so there is no daemon to run: every agent's MCP server process opens the same hive.

## Install

```sh
uv tool install git+https://github.com/okezue/hive
# or: pip install git+https://github.com/okezue/hive
```

Python 3.11 or newer.

## Start

```sh
cd your-project
hive init          # creates .hive/ and prints an MCP config entry
```

Give each agent the MCP server, naming the agent and its role:

```sh
claude mcp add hive -- hive mcp --agent alice --role implementer
```

or in any MCP client config:

```json
{"mcpServers": {"hive": {"command": "hive", "args": ["mcp", "--agent", "alice", "--role", "implementer"]}}}
```

An agent can also start unnamed and call `join`. Subagents that share one host connection each get a token from `join`, `spawn`, or `dispatch` and pass it as `agent` on every call. [docs/harness.md](docs/harness.md) has setups for each harness, including the hooks.

## How agents work together

**Roles.** Every agent has a role: `coordinator`, `implementer`, `verifier`, `reviewer`, `researcher`, `composer`, `distiller`, `observer`, or one a coordinator defines. A role is a charter plus capabilities, and every operation checks one. When an agent reaches outside its role the refusal restates its charter and points it at the agent whose job it is, and the charter is repeated to each agent every twenty calls. Verifiers cannot edit files or verify their own work, and tasks can only be taken by the role they name.

**Messages.** `send` reaches an agent, a role (`role:verifier`), a workflow, an agent's parent or children, or everyone, in one of three modes:

| mode | when the recipient sees it |
|---|---|
| `queue` | a count appears on each of its Hive calls; it reads the messages with `inbox` at a stopping point |
| `steer` | in full on its next Hive call |
| `interrupt` | in full on its next tool call of any kind (through hooks), repeated until it calls `ack`, and its turn cannot end while one is open |

`ask` sends a question and waits for the reply, `wait` blocks an idle agent until something arrives, `share` hands over one specific thing (a file range, a context entry, a task and its result, a message), and `handoff` passes an agent's whole working context, with a summary of its activity, to another agent.

**Co-editing.** Hive versions every shared file and remembers which version each agent last saw. When two agents change different parts of a file, both changes are kept (lines next to each other count as different parts) and everyone who has the file open is told what changed, with the diff. When changes overlap, Hive applies neither: it opens a merge request, interrupts the authors involved, and blocks the requester from that file. The authors talk it through in the request's thread; one proposes a resolution with a note (per conflict or as a whole file), and every other author must accept it before Hive applies it, re-merging if the file moved meanwhile. Edits made with an agent's own tools are adopted through `sync` or the hooks, and a stale full-file rewrite is merged instead of silently reverting someone else's work. `claim` announces a region an agent is about to change so others are warned.

**Tasks.** `plan` creates tasks with `after` dependencies. Tasks with no dependency path between them run concurrently, and a task becomes ready when everything it depends on is done; whoever takes it receives the results of those tasks, summarized if they are long. A task created with `verify` goes to review when finished and spawns a verification task for an independent verifier; dependents wait for approval, and a rejection returns the work to its author as an interrupt. A coordinator can `dispatch` a ready task to get a new agent's token and a complete prompt for starting it as a subagent, or run `hive run` to launch agent processes for ready tasks automatically.

**Awareness.** `overview` shows everyone's role, state, status line, current task, and open files, plus active tasks, open merge requests, and recent events. `digest` summarizes what others did since the caller last asked. `watch` inspects one agent three ways: `live` follows new activity from a cursor and can block until more arrives, `window` slides back through its history page by page, and `summary` condenses any amount of activity to a token budget. Long logs are split into chunks, summarized, and the summaries summarized again until they fit, with each chunk cached so repeated summaries only pay for new activity. Summaries use an OpenAI-compatible model when an API key is present (the xAI API by default) and an extractive summarizer otherwise. `follow` subscribes to files, agents, tasks, context keys, or event kinds.

**Trees of agents.** Any agent whose role has the `fork` capability can `spawn` helpers, and those helpers can spawn their own, so orchestration gets as deep as the work needs. A spawn is a delegation: the child gets a goal, a deliverable, its own task filed under the parent's current task, a slice of the parent's budget, and capabilities no wider than the parent's (a verifier's helpers cannot write files). Budgets are escrowed: a child costs one plus what it receives, and whatever it leaves unspent returns up the tree, so a subtree can never create more agents than its root was given. Depth and live children per agent are capped. Children start in the caller's own subagent tool (`launch='host'` returns a prompt and token), or as separate processes started by `hive run` (`launch='runner'`), which gives real depth even in harnesses that limit nested subagents; the runner counts only agents that are working against its concurrency cap, so parents waiting on children never starve them, and it relaunches a crashed child under the same identity before failing its task. `gather` collects children's results as a fork-join. A parent cannot finish its task while subtasks under it are unsettled, cancelling a task cancels the work below it and interrupts those agents, and a failed or abandoned delegation interrupts the parent.

Lineage is permanent: `path` shows the chain from the root with every ancestor's goal, which answers why any agent exists. Custody can move: when an agent leaves, its children's keeper becomes the nearest live ancestor, open issues and unspent budget go with them, and their lineage, inherited context, and history stay intact. A blocked agent calls `escalate` with the decision it needs (and optionally a budget request); the issue goes to its keeper, who answers with `decide` or passes it further up.

The tree is meant to be walked, one neighborhood at a time. `tree` renders a node and a few levels below it with `+N more` for wide levels, `node` shows one agent's goal, task, budget, children, an exact rollup of its whole subtree (agents and tasks by state, open issues, merge requests, unacknowledged interrupts, stale agents), and which descendant needs attention first. `walk` moves a personal cursor (`up`, `down`, `down:<name>`, `next`, `prev`, `root`) without changing who the agent acts as, `find` searches a subtree, and `brief` summarizes a subtree along its own shape: exact blockers first, then each child's work condensed recursively within the token budget. Context follows lineage too: `put(key, value, scope='node')` is visible to the whole subtree below the writer, `scope='team'` writes to the parent's frame for siblings to share, and reads look up the nearest frame on the way to the root before falling back to the workflow and the session. The design draws on ADK agent hierarchies, OpenAI's agents-as-tools, Claude Code's nested subagents, LangGraph subgraphs, and a design review by GPT 6 Astra; lineage-scoped memory, escrowed budgets, narrowing capabilities, custody transfer, and structured completion are what set it apart.

**Insights.** Individual agents record findings as they work with `note` (facts, decisions, problems, methods, each with references to evidence, and `against:f12` to mark a contradiction); finished tasks and verification verdicts become findings automatically. Two dedicated roles turn them into knowledge. A `composer` combines what a subtree found, top down: `stale` lists the nodes whose compositions are missing or out of date, deepest first, so the composer handles big branches by spawning sub-composers and gathering them; `material` gives one node's own findings, each child's composition (or its raw findings if nobody has composed it), and the flagged contradictions; `compose` records the account with its sources, refusing findings from outside the subtree. A composition covers exactly what it cites (directly, or through the child compositions it cites), so a node stays stale until every finding below it is covered, and `gist` shows a node's current composition and what it does not yet cover. A `distiller` turns the combined knowledge of many agents into insights: `harvest` lays out each independent branch next to the saved insights that look related, and `distill` saves an insight as `observed` (a pattern in the work) or `reusable` (a lesson for future work) with its evidence. A near-duplicate is shown instead of being saved twice, so evidence accumulates on one insight. Confidence counts independent branches of the tree: findings from the same line of delegation count once; a root's own results, whole-tree compositions, and anything composers or distillers write add no independent support; `weigh` adds evidence for or against, where support must cite findings but a note is enough to contest; and insights move between proposed, established, and contested as evidence arrives. Insights live in a library outside the session (`.hive/insights.db` for the project, or `~/.hive/insights.db` with `scope='global'`), so later sessions can `recall` them, and the most relevant established ones are written into the prompts of newly spawned and dispatched agents. When a task with several finished subtasks completes, or all of an agent's delegated children settle, Hive files a compose task for that part of the tree (work done by composers and distillers never triggers more), and composing a root with two or more branches files a distill task, whenever an agent or runner command exists for those roles.

**Shared context and tools.** `put` and `get` maintain a versioned board of findings, plans, and decisions, scoped to the session or a workflow, with compare-and-swap for co-edited entries. `offer` shares a tool: calls to an agent tool arrive in the owner's inbox and it replies with `answer`, which lets one agent expose something only it has; a command tool runs a fixed program with the arguments as JSON.

**Scope.** One hive database is one session. Workflows group agents and tasks inside it, and broadcasts, context, task lists, and overviews can be limited to a workflow.

## Tools

| group | tools |
|---|---|
| core | `join` `me` `progress` `leave` `overview` `digest` `watch` `roles` |
| msgs | `send` `inbox` `ack` `ask` `wait` `share` `handoff` `follow` |
| ctx | `put` `get` `keys` `drop` |
| files | `read` `edit` `write` `sync` `diff` `release` `claim` `files` `merges` `propose` `respond` `abandon` |
| tasks | `plan` `tasks` `task` `take` `done` `fail` `verify` `cancel` `dispatch` `define` `assign` |
| tree | `spawn` `gather` `tree` `node` `walk` `path` `find` `brief` `fund` `adopt` `escalate` `decide` `issues` |
| know | `note` `findings` `material` `compose` `gist` `stale` `harvest` `distill` `recall` `weigh` `retire` |
| tools | `offer` `tools` `call` `answer` `result` `withdraw` |

`hive mcp --tools core,msgs,files` exposes a subset.

## Python

```python
from hive import Hive

h = Hive.open('.hive/hive.db', '.')
lead, dev = h.join('lead', 'coordinator'), h.join('dev')
lead.plan([{'key': 'api', 'title': 'Add the endpoint', 'verify': True},
           {'title': 'Document it', 'after': ['api']}])
t = dev.take()['task']['id']
dev.read('app.py')
dev.edit('app.py', [{'old': 'routes = []', 'new': 'routes = [health]'}])
dev.done(t, 'added /health; tests pass')
```

## CLI

`hive status`, `hive tree [agent] --depth 3`, `hive insights [query]`, `hive tail -f`, `hive history <agent>`, `hive summary [--agent a]`, `hive send <to> <body> --mode interrupt`, `hive tasks`, `hive plan plan.json`, `hive files`, `hive merges`, `hive run`, and `hive hook <event>` for harnesses. The CLI acts as an `operator` coordinator unless given `--as <agent>`.

## Configuration

`.hive/config.toml` holds the reminder interval, task retry limit, staleness threshold, tree limits (depth, fanout, root budget), insight automation and the global library path, summarizer settings, and the runner's agent commands. `HIVE_DB`, `HIVE_ROOT`, and `HIVE_SESSION` choose the hive; `HIVE_KEY` is the admin key for privileged roles over HTTP; `HIVE_AGENT` with `HIVE_ROLE`, or `HIVE_AGENT_TOKEN`, preset an agent's identity; `HIVE_LLM_API_KEY` (or `XAI_API_KEY`), `HIVE_LLM_BASE_URL`, `HIVE_LLM_MODEL`, and `HIVE_SUMMARIZER` control summaries.

## Development

```sh
uv venv && uv pip install -e '.[dev]'
.venv/bin/pytest -q
```

The suite covers composition and insight distillation, recursive spawning three levels deep through the runner, the merge algorithm (including agreement with `git merge-file`), co-editing and merge requests, task graphs and verification, messaging, summaries, the MCP server in process and over stdio, hooks, the runner, and several processes editing one file and racing for tasks.

## License

MIT
