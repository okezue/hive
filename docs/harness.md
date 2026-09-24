# Harness setup

Every agent needs the Hive MCP server. Hooks are optional and add three things MCP cannot: interrupts delivered between tool calls that do not touch Hive, automatic adoption of edits made with the harness's own edit tools, and a stop gate that keeps an agent working while an interrupt or merge request is waiting on it.

## hive install

`hive install [harness ...] [--project] [--no-hooks] [--dry-run]` writes the server (and hooks) into each harness's own files, for your user by default or for the project with `--project`. It changes only Hive's entries, backs up user-level files before changing them, validates what it wrote by parsing it back, and stops with an error instead of rewriting a file it cannot parse. `hive uninstall` removes exactly those entries. Afterwards it runs `hive doctor`, which starts the configured server and lists its tools, and asks the harness itself (`<harness> mcp list`) whether it loads Hive.

| Harness | MCP server | Hooks | Notes |
|---|---|---|---|
| Claude Code | `~/.claude.json`, or `.mcp.json` | `~/.claude/settings.json`, or `.claude/settings.json` | A project install pre-approves the server in `.claude/settings.local.json` |
| Codex | `~/.codex/config.toml`, or `.codex/config.toml` | `~/.codex/hooks.json`, or `.codex/hooks.json` | Codex runs project files only in trusted projects, and asks once to trust new hooks (`/hooks`) |
| Grok Build | `~/.grok/config.toml`, or `.grok/config.toml` | `~/.grok/hooks/hive.json`, or `.grok/hooks/hive.json` | Project files need a trusted folder (`/hooks-trust`), and project hooks load only inside a git repository |
| Gemini CLI | `~/.gemini/settings.json`, or `.gemini/settings.json` | the same file | Gemini turns off every MCP server, user ones included, in folders it does not trust; headless agents Hive starts pass `--skip-trust` for their session |
| Cursor CLI | `~/.cursor/mcp.json`, or `.cursor/mcp.json` | none | |
| opencode | `~/.config/opencode/opencode.json`, or `opencode.json` | none | |

The server entry is only `hive mcp` (plus `--dir <project>` for a project install): it carries no identity and no paths, so one entry serves every project and every agent. The server opens nothing until an agent uses it, and then finds its hive from the agent's identity, the environment, or the working directory.

## Identity

Hive needs to know which agent is calling, and finds out in this order:

1. Explicit settings: `--agent <name> --role <role>` on `hive mcp`, or `HIVE_AGENT` / `HIVE_ROLE` / `HIVE_AGENT_TOKEN` in the environment.
2. The harness process. `hive start` and `hive run` record every harness process they launch in `~/.hive/hives.db`, and a session that calls `join` records the harness it runs under. The MCP server and the hooks look up their own process ancestry there, so they know their agent even when the harness hands them no environment (Gemini removes variables that look like secrets, and Codex passes MCP servers only a short list).
3. A `join` call. Several agents sharing one connection, as subagents of one host do, each pass their token as `agent` on every call; the token is in the brief Hive returns.

Hooks skip events that come from subagents, whose identity the hook cannot tell apart. Installed hook commands start with a shell check, so in a session that is not part of any hive (no Hive identity in its environment and no agent bound anywhere on the machine) they exit before starting Python, and they never print anything when Hive has nothing to say.

## hive start

`hive start <harness> [prompt] [--name n] [--role r] [--task t3] [--model m] [-p] [-- extra harness args]` joins a new agent to the project's hive and runs the harness as it: interactively in your terminal, or headless with `-p`. The agent gets the hive's brief (its role, charter, token, and how to work here) as its first prompt, or through the SessionStart hook when the harness has one. When the harness exits the agent leaves the hive, and a task it had not finished goes back to ready. If Hive is not yet installed for that harness, `hive start` installs it for your user first and says so.

| Harness | Interactive | Headless (`-p` and `hive run`) |
|---|---|---|
| claude | `claude <prompt>` | `claude -p <prompt> --permission-mode bypassPermissions` |
| codex | `codex -C <root> <prompt>` | `codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check -C <root> <prompt>` |
| grok | `grok --cwd <root> <prompt>` | `grok --prompt-file <file> --cwd <root> --permission-mode bypassPermissions --no-auto-update` |
| gemini | `gemini -i <prompt>` | `gemini -p <prompt> --yolo --skip-trust` |
| cursor | `cursor-agent <prompt>` | `cursor-agent -p <prompt> --force --approve-mcps` |
| opencode | `opencode --prompt <prompt>` | `opencode run <prompt>` |

Override any of these, or add your own agent CLI, in `.hive/config.toml`:

```toml
[harness.grok]
run = ["grok", "--prompt-file", "{promptFile}", "--cwd", "{root}", "-m", "grok-4.7-build-fast", "--permission-mode", "bypassPermissions"]

[harness.mine]
run = ["mine", "--headless", "{prompt}"]
chat = ["mine", "{prompt}"]
```

## Manual setup

For MCP clients Hive does not know, add the server yourself:

```json
{"mcpServers": {"hive": {"command": "hive", "args": ["mcp"]}}}
```

`hive mcp-config --agent <name> --role <role>` prints an entry with this hive's paths and an identity filled in. Hooks take the event on stdin in Claude Code's format (`hive hook pre|post|prompt|stop|start|end`), Gemini's (`--format gemini`), or return plain text (`--format text`). Grok truncates large MCP results (20,000 bytes by default), so read big files in ranges with `read(path, start, end)`.

## Agents on other machines

Run one HTTP server next to the hive and point clients at it:

```sh
HIVE_KEY=<secret> hive mcp --http --host 0.0.0.0 --port 8765
```

Clients connect to `http://<host>:8765/mcp`. Over HTTP every call must carry the caller's `join` token as `agent`, and joining with a role that can run commands, manage agents, or write compositions and insights (`coordinator`, `composer`, `distiller`, or a custom role with `exec`, `define`, `spawn`, `manage`, `compose`, or `distill`) requires `key=<secret>`. The server refuses to listen beyond localhost unless `HIVE_KEY` is set. Put it behind TLS when it crosses an untrusted network.

## Starting agents for a plan, and recursive spawning

A coordinator can start each agent itself: `dispatch('t3')` returns a new agent's token and a complete prompt (charter, protocol, task, and dependency results) to hand to a subagent. Any agent with `fork` can do the same for a piece of its own work with `spawn(goal, deliver=...)`: with `launch='host'` it gets a prompt (its lineage, goal, deliverable, budget, and token) for its harness's subagent tool, and with `launch='runner'` Hive starts the child as its own harness process. Runner children can spawn further runner children, so depth does not depend on whether the harness allows nested subagents (Claude Code caps nesting with `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`). Keep `hive run --watch` running so children spawned later are picked up. Or let Hive launch processes for every ready task:

```toml
# .hive/config.toml
[runner]
max = 3

[runner.roles.default]
harness = "claude"
fallback = ["codex"]   # takes over while claude is rate limited, down, or out of retries for a task

[runner.roles.verifier]
harness = "codex"

[runner.roles.composer]
command = ["my-agent", "--prompt", "{prompt}", "--mcp-config", "{mcp}"]   # any command works too
```

```sh
hive plan plan.json && hive run
```

With a default command or harness (or ones for `composer` and `distiller`), the compose and distill tasks Hive files as work finishes are picked up automatically. The runner starts agents as their tasks become ready, up to `max` at a time, records each process in the registry, passes it `HIVE_AGENT_TOKEN`, `HIVE_TASK`, `HIVE_DB`, and `HIVE_ROOT`, writes an MCP config for it to `{mcp}`, and logs its output under `.hive/run/`. When an agent stops without finishing, the runner reads the reason from its exit code and last lines of output (Claude Code's `API Error: 429` or `usage limit reached|<reset time>`, Codex's `exceeded retry limit` or `ran out of room in the model's context window`, Grok's `max turns reached`, Gemini's quota and `max session turns` messages, plus timeouts, hangs, and crashes) and acts on it as described in the README under Failures and recovery: it cools a rate-limited command for as long as the provider asks, switches to a `fallback`, restarts the same agent with a brief of its progress, or, when nothing is left to try, fails the task with a diagnosis you can act on and `hive retry`.
