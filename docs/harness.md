# Harness setup

Every agent needs the Hive MCP server. Hooks are optional and add three things MCP cannot: interrupts delivered between tool calls that do not touch Hive, automatic adoption of edits made with the harness's own edit tools, and a stop gate that keeps an agent working while an interrupt or merge request is waiting on it.

All examples assume `hive init` was run in the project, so `hive` finds `.hive/hive.db` from the working directory. Set `HIVE_DB` and `HIVE_ROOT` when agents run elsewhere.

## Identity

Hive needs to know which agent is calling.

- One MCP server per agent: pass `--agent <name> --role <role>` (or set `HIVE_AGENT` and `HIVE_ROLE`). The agent is created on first use and resumed afterwards.
- One connection shared by several agents, as with subagents of one host: each agent calls `join` (or receives a token from a coordinator's `dispatch` or `spawn`) and passes `agent="<token>"` on every call. The token is in the brief Hive returns.
- Hooks read the same identity from `HIVE_AGENT` / `HIVE_ROLE` or `HIVE_AGENT_TOKEN` in the harness's environment, so start the harness with them set, for example `HIVE_AGENT=alice HIVE_ROLE=implementer claude`. Hooks skip events that come from subagents, whose identity the hook cannot tell apart.

## Claude Code

```sh
claude mcp add hive -- hive mcp --agent alice --role implementer
```

`.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "command": "hive hook start"}]}],
    "PreToolUse": [{"matcher": "Edit|Write|MultiEdit|NotebookEdit", "hooks": [{"type": "command", "command": "hive hook pre"}]}],
    "PostToolUse": [{"hooks": [{"type": "command", "command": "hive hook post"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "hive hook stop"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "hive hook end"}]}]
  }
}
```

## Grok Build

`~/.grok/config.toml` (or the project's `.grok/config.toml`):

```toml
[mcp_servers.hive]
command = "hive"
args = ["mcp", "--agent", "grok-1", "--role", "implementer"]
```

Grok Build reads the Claude Code hook file above, or put the same JSON in `.grok/hooks/hive.json`; the `Edit|Write` matcher also matches Grok's `search_replace`. Grok loads project hooks only inside a git repository, so run `git init` in a scratch workspace or the hooks silently never fire (`grok inspect` lists what it loaded). Headless runs (`grok -p`) need a trusted folder (`--trust`) or `GROK_FOLDER_TRUST=0` before they read the project's `.grok/config.toml`. Grok truncates large MCP results (20,000 bytes by default), so read big files in ranges with `read(path, start, end)`.

## Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.hive]
command = "hive"
args = ["mcp", "--agent", "codex-1", "--role", "implementer"]
```

## Cursor and other MCP clients

```json
{"mcpServers": {"hive": {"command": "hive", "args": ["mcp", "--agent", "cursor-1", "--role", "implementer"]}}}
```

`hive mcp-config --agent <name> --role <role>` prints this entry with the hive's paths filled in.

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
command = ["claude", "-p", "{prompt}", "--mcp-config", "{mcp}"]

[runner.roles.verifier]
command = ["codex", "exec", "{prompt}"]

[runner.roles.composer]
command = ["claude", "-p", "{prompt}", "--mcp-config", "{mcp}"]

[runner.roles.distiller]
command = ["claude", "-p", "{prompt}", "--mcp-config", "{mcp}"]
```

```sh
hive plan plan.json && hive run
```

With commands for `composer` and `distiller`, the compose and distill tasks Hive files as work finishes are picked up automatically. The runner starts agents as their tasks become ready, up to `max` at a time, passes each one `HIVE_AGENT_TOKEN`, `HIVE_TASK`, `HIVE_DB`, and `HIVE_ROOT`, writes an MCP config for it to `{mcp}`, logs its output under `.hive/run/`, and retries or fails tasks whose agent exits without finishing.
