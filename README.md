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

Plug Hive into the agent CLIs you use, once:

```sh
hive install              # every harness on your PATH: claude, codex, grok, gemini, cursor, opencode
hive install grok codex   # or name them; --project writes the project's config files instead of your user's
hive doctor               # checks each one: config, hooks, a handshake with the server, and the harness's own mcp list
```

`hive install` adds the Hive MCP server to each harness's own config and, where the harness supports them, the hooks. It leaves everything else in those files as it was, keeps a backup of user-level files it changes, and refuses to touch a file it cannot parse. From then on any session of those harnesses can use Hive: an agent calls `join` and the project's hive is created on first use (in the git root, with its own `.gitignore`).

Or start agents from Hive, in any harness, all in the same hive:

```sh
hive start claude                         # an interactive Claude Code session that is already a member of this hive
hive start codex --role verifier          # a Codex session next to it, as a verifier
hive start grok -p "tidy the changelog"   # a headless Grok run that prints its output and leaves when done
hive start gemini --task t3               # a Gemini session working on task t3
hive ls                                   # every hive on this machine, with who is in it and in which harness
```

[docs/harness.md](docs/harness.md) has the details for each harness, and manual setups for MCP clients Hive does not know.

## One hive across harnesses

A project has one hive, and every agent in it shares it whatever it runs in: sessions you start yourself that call `join`, sessions started with `hive start`, and agents the runner launches. Hive keeps a registry of hives and agent processes in `~/.hive/hives.db`, so `hive ls` shows hives started from inside any harness, and `hive -H <name|number> status` (or any other command) reaches one from anywhere.

Agents are identified by the harness process they run in. When Hive starts a harness it records that process; when a session joins by itself, its MCP server records the harness it runs under. The MCP server and the hooks then find their agent by looking up their own process ancestry. This works even for harnesses that strip environment variables from MCP servers and hooks, as Gemini and Codex do.

Work can be placed in a particular harness: a plan task or a `spawn` takes `harness="codex"`, a runner role takes `harness = "claude"` in `.hive/config.toml`, and `hive run --harness gemini` sets the default. Without any, `hive run` uses the first harness it finds installed. Your own agent CLI can be added as a harness under `[harness.<name>]` with a headless `run` command and an interactive `chat` command.

**Sharing MCP servers.** `hive mount <name> -- <command> [args]` (or `--url` for HTTP servers) makes an MCP server's tools available to every agent in the hive as `<name>.<tool>`, called through Hive's `call`, so a Codex agent can use a server that only your Grok config has. `hive mount --from grok` imports the servers from a harness's config, and agents with the `exec` capability can `mount` servers themselves. Each agent's Hive server keeps its own live connection to a mounted server and reconnects if it dies; mount an HTTP server when every agent should share one instance. Environment values written as `${VAR}` are read from each caller when it connects, so secrets stay out of the hive.

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

**Trees of agents.** Any agent whose role has the `fork` capability can `spawn` helpers, and those helpers can spawn their own, so orchestration gets as deep as the work needs. A spawn is a delegation: the child gets a goal, a deliverable, its own task filed under the parent's current task, a slice of the parent's budget, and capabilities no wider than the parent's (a verifier's helpers cannot write files). Budgets are escrowed: a child costs one plus what it receives, and whatever it leaves unspent returns up the tree, so a subtree can never create more agents than its root was given. Depth and live children per agent are capped. Children start in the caller's own subagent tool (`launch='host'` returns a prompt and token), or as separate processes started by `hive run` (`launch='runner'`), which gives real depth even in harnesses that limit nested subagents; the runner counts only agents that are working against its concurrency cap, so parents waiting on children never starve them, and it restarts a child that fails under the same identity (see Failures and recovery). `gather` collects children's results as a fork-join. A parent cannot finish its task while subtasks under it are unsettled, cancelling a task cancels the work below it and interrupts those agents, and a failed or abandoned delegation interrupts the parent.

Lineage is permanent: `path` shows the chain from the root with every ancestor's goal, which answers why any agent exists. Custody can move: when an agent leaves, its children's keeper becomes the nearest live ancestor, open issues and unspent budget go with them, and their lineage, inherited context, and history stay intact. A blocked agent calls `escalate` with the decision it needs (and optionally a budget request); the issue goes to its keeper, who answers with `decide` or passes it further up.

The tree is meant to be walked, one neighborhood at a time. `tree` renders a node and a few levels below it with `+N more` for wide levels, `node` shows one agent's goal, task, budget, children, an exact rollup of its whole subtree (agents and tasks by state, open issues, merge requests, unacknowledged interrupts, stale agents), and which descendant needs attention first. `walk` moves a personal cursor (`up`, `down`, `down:<name>`, `next`, `prev`, `root`) without changing who the agent acts as, `find` searches a subtree, and `brief` summarizes a subtree along its own shape: exact blockers first, then each child's work condensed recursively within the token budget. Context follows lineage too: `put(key, value, scope='node')` is visible to the whole subtree below the writer, `scope='team'` writes to the parent's frame for siblings to share, and reads look up the nearest frame on the way to the root before falling back to the workflow and the session. The design draws on ADK agent hierarchies, OpenAI's agents-as-tools, Claude Code's nested subagents, LangGraph subgraphs, and a design review by GPT 6 Astra; lineage-scoped memory, escrowed budgets, narrowing capabilities, custody transfer, and structured completion are what set it apart.

**Insights.** Individual agents record findings as they work with `note` (facts, decisions, problems, methods, each with references to evidence, and `against:f12` to mark a contradiction); finished tasks and verification verdicts become findings automatically. Two dedicated roles turn them into knowledge. A `composer` combines what a subtree found, top down: `stale` lists the nodes whose compositions are missing or out of date, deepest first, so the composer handles big branches by spawning sub-composers and gathering them; `material` gives one node's own findings, each child's composition (or its raw findings if nobody has composed it), and the flagged contradictions; `compose` records the account with its sources, refusing findings from outside the subtree. A composition covers exactly what it cites (directly, or through the child compositions it cites), so a node stays stale until every finding below it is covered, and `gist` shows a node's current composition and what it does not yet cover. A `distiller` turns the combined knowledge of many agents into insights: `harvest` lays out each independent branch next to the saved insights that look related, and `distill` saves an insight as `observed` (a pattern in the work) or `reusable` (a lesson for future work) with its evidence. A near-duplicate is shown instead of being saved twice, so evidence accumulates on one insight. Confidence counts independent branches of the tree: findings from the same line of delegation count once; a root's own results, whole-tree compositions, and anything composers or distillers write add no independent support; `weigh` adds evidence for or against, where support must cite findings but a note is enough to contest; and insights move between proposed, established, and contested as evidence arrives. Insights live in a library outside the session (`.hive/insights.db` for the project, or `~/.hive/insights.db` with `scope='global'`), so later sessions can `recall` them, and the most relevant established ones are written into the prompts of newly spawned and dispatched agents. When a task with several finished subtasks completes, or all of an agent's delegated children settle, Hive files a compose task for that part of the tree (work done by composers and distillers never triggers more), and composing a root with two or more branches files a distill task, whenever an agent or runner command exists for those roles.

**Shared context and tools.** `put` and `get` maintain a versioned board of findings, plans, and decisions, scoped to the session or a workflow, with compare-and-swap for co-edited entries. `offer` shares a tool: calls to an agent tool arrive in the owner's inbox and it replies with `answer`, which lets one agent expose something only it has; a command tool runs a fixed program with the arguments as JSON.

**Scope.** One hive database is one session. Workflows group agents and tasks inside it, and broadcasts, context, task lists, and overviews can be limited to a workflow.

**Failures and recovery.** `hive run` watches every agent it starts and reads why it stopped from its exit code and the end of its output: a rate limit, a network or server error, failed authentication, a command that cannot run, a full context, a turn limit, an early exit, or a crash. It also stops agents that work past `timeout` (time spent waiting on children or messages does not count, up to four times the limit in all) or go `idle` seconds without a Hive call or output. Each cause gets its own response:

- **Rate limits and network errors** cool down that command for every task that uses it. The runner waits as long as the provider asks (`Retry-After`, "try again in 2 hours", reset timestamps) or backs off exponentially, and halves the command's concurrency, which recovers by one slot for each agent that succeeds. A configured `fallback` command takes over at once. These waits don't use up a task's retries, so a long outage never fails work; `patience` and probing handle it. They count against a task only when other agents succeed on the same command in the meantime, which points at the task itself, and then only up to `waits` times.
- **Turn limits, full contexts, timeouts, hangs, and early exits** restart the agent immediately. A restart after an attempt that saved progress (files, progress, findings, finished steps) is free, so long work keeps going as long as it advances; only attempts that saved nothing count against `resumes`, with a hard cap of five times that in all.
- **Crashes** restart it after a backoff, up to `tries` attempts per command.
- **Repeated authentication or setup failures** pause the command and keep its tasks queued, so a bad key costs nothing but time.

Every restart keeps the same agent identity, with its claims, file views, and unread messages, and its prompt carries a brief of the earlier attempts: why each stopped, a summary of what it did, the files it changed, its findings and last progress, and its last output. Its edits and records are already in Hive. If the runner itself dies, the next `hive run` adopts agents that are still working (checked against each process's recorded start time, so a reused process id is never mistaken for an agent) and restarts the ones that were lost; a lock keeps a second runner off the same session. When a task has used up its retries on every command, it fails with a diagnosis and a suggested fix, its creator is interrupted, and an issue records it; `retry` reopens it with the full brief and puts its blocked dependents back in line. When a command keeps failing past `patience`, it is paused and reported, and Hive probes it every `probe` seconds so queued work resumes as soon as the command recovers. `hive retry` resumes paused commands. `hive faults` (or the `faults` tool) shows each command's state, recent failures, tasks waiting to retry, and open issues; `hive status` includes the same.

## Tools

| group | tools |
|---|---|
| core | `join` `me` `progress` `leave` `overview` `digest` `watch` `roles` |
| msgs | `send` `inbox` `ack` `ask` `wait` `share` `handoff` `follow` |
| ctx | `put` `get` `keys` `drop` |
| files | `read` `edit` `write` `sync` `diff` `release` `claim` `files` `merges` `propose` `respond` `abandon` |
| tasks | `plan` `tasks` `task` `take` `done` `fail` `verify` `cancel` `dispatch` `define` `assign` `retry` `faults` |
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

`hive install|uninstall|doctor [harness]`, `hive start <harness> [prompt]`, `hive ls`, `hive mount [name] [-- command]`, `hive unmount <name>`, `hive status`, `hive tree [agent] --depth 3`, `hive insights [query]`, `hive tail -f`, `hive history <agent>`, `hive summary [--agent a]`, `hive send <to> <body> --mode interrupt`, `hive tasks`, `hive plan plan.json`, `hive files`, `hive merges`, `hive run [--harness h]`, `hive faults`, `hive retry [task]`, and `hive hook <event>` for harnesses. Commands act on the hive of the current project, or the one `-H <name|number|path>` picks from `hive ls`. The CLI acts as an `operator` coordinator unless given `--as <agent>`.

## Configuration

`.hive/config.toml` holds the reminder interval, task retry limit, staleness threshold, tree limits (depth, fanout, root budget), insight automation and the global library path, summarizer settings, and the runner's agent commands with their fallbacks, time limits, retry budgets, backoff, and rate-limit patience. `HIVE_DB`, `HIVE_ROOT`, and `HIVE_SESSION` choose the hive; `HIVE_KEY` is the admin key for privileged roles over HTTP; `HIVE_AGENT` with `HIVE_ROLE`, or `HIVE_AGENT_TOKEN`, preset an agent's identity; `HIVE_LLM_API_KEY` (or `XAI_API_KEY`), `HIVE_LLM_BASE_URL`, `HIVE_LLM_MODEL`, and `HIVE_SUMMARIZER` control summaries.

## Development

```sh
uv venv && uv pip install -e '.[dev]'
.venv/bin/pytest -q
```

`tests/e2e.py` runs Hive the way agents do, as separate processes over real transports: runner-launched agent processes that talk to `hive mcp` over stdio through the MCP config the runner writes (co-editing, verification, then the automatic compose and distill tasks, and a new agent recalling the saved insight), a shared tool served by one MCP process and called from another while it watches the server's live, window, and summary views, the HTTP server with its admin key, `hive hook` invoked as a subprocess with harness payloads, the CLI from `init` to `insights`, and several MCP processes editing one file at once. `e2e/live.py` drives real Grok agents (`grok` headless, sandboxed to a temporary workspace, with Hive as a project MCP server and hooks) through five scenarios and checks the resulting state: `coedit` (two agents edit one file concurrently and must settle a merge request between themselves), `hooks` (an agent edits with its own tools while the hooks sync its edits and deliver an interrupt), `runner` (a dependent plan with independent verification, every agent started by `hive run`, then one automatic composition once the whole plan has settled), `tree` (runner-launched researchers spawn their own runner child, then automatic compose and distill tasks produce a composition and a saved insight that a later session recalls), and `recover` (an agent whose turn limit is too small for its task keeps hitting it; Hive recognizes Grok's error, restarts the same agent with a brief each time, and the work completes without being redone). Run `python e2e/live.py [scenario ...] --model <model>`; it uses model credits, and results vary from run to run because the agents are real. Grok also starts every MCP server from your own Grok configuration in these workspaces, and on rare runs none of them connect in time for one agent; that agent then works without Hive's tools.

`tests/heal.py` drives scripted agents through every failure path: rate limits with provider wait hints, a fallback taking over, turn limits resumed with their progress, hung and overdue agents, authentication failures that pause a command until it is resumed, exhausted retries followed by `retry`, a runner that is stopped or killed, and a new runner adopting agents that are still working.

The suite covers composition and insight distillation, recursive spawning three levels deep through the runner, the merge algorithm (including agreement with `git merge-file`), co-editing and merge requests, task graphs and verification, messaging, summaries, the MCP server in process and over stdio, hooks, the runner, and several processes editing one file and racing for tasks.

## License

MIT
