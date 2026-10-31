# Agent-to-Agent Space

English | [简体中文](README.zh-CN.md)

Agent-to-Agent Space is a small, filesystem-based coordination protocol for
independent AI agent sessions. It lets sessions exchange requirements and
status updates without sharing a conversation, running a server, or assuming
that all agents work in the same Git repository.

The repository is both a Codex Skill and a reference implementation of the
protocol.

## Why

Two agents working in related repositories often need to coordinate an API,
schema, design decision, or follow-up task. Chat history is session-local, and
Git commits are the wrong transport for transient coordination. A shared space
provides a durable inbox that both sessions can inspect directly.

## Use case: one developer, multiple repositories

This tool is especially useful for independent developers and small teams
building products composed of multiple modules. A single workspace may contain
separate repositories for the frontend, backend, data, infrastructure, and
even operations. Each repository can be opened as its own Project in an agent
tool such as Codex, Claude Code, or Cursor, with a separate Session for each.

Every Session understands the code and context of its own repository, but it
cannot naturally see discussions held in other Sessions. When cross-module
coordination relies on manually relaying messages or copying text between
windows, context, acceptance criteria, and progress are easily lost.

Agent-to-Agent Space places a shared `.agent-to-agent/` directory in the
repositories' common parent directory. It acts as a requirement inbox and
coordination history that every Session can access. For example:

1. The frontend discovers that it needs a new backend endpoint.
2. In the frontend Session, say: "Send the backend a requirement for an article
   bookmarking endpoint, including its request parameters and acceptance criteria."
3. The frontend Agent writes a structured requirement addressed to `backend`
   into the shared `.agent-to-agent/` directory.
4. Switch to the backend Project and say: "The frontend has a new requirement.
   Take a look."
5. The backend Agent reads its inbox, accepts the requirement, asks follow-up
   questions, or implements it, then writes its status and result back to the
   same space.
6. When you return to the frontend Session, its Agent can inspect the result
   without reconstructing the context.

The same pattern works when the backend requests a schema migration from the
data repository, the data team asks the frontend or backend to add analytics
events, or operations requests a campaign page or content configuration from
the product repositories.

> Agent-to-Agent Space does not automatically wake another Session. It makes
> cross-Session communication durable, structured, and traceable. The developer
> only needs to switch to the target Session and ask it to check its inbox.

## Install the Skill

Clone or copy this repository into your Codex skills directory:

```text
~/.codex/skills/agent-to-agent-space/
```

The directory must contain `SKILL.md`, `scripts/`, `references/`, and
`agents/openai.yaml` at its root.

Python 3.10 or newer is the preferred executor for the bundled CLI, but it is
not a protocol requirement. The Skill checks for a working Python 3 command
and falls back to direct filesystem operations when Python is unavailable. See
[`references/manual-fallback.md`](references/manual-fallback.md) for the safe
fallback procedure.

## User guide: connect multiple projects

The following walkthrough connects an iOS app, a backend, and a web app. Replace
the example names and paths with your own repositories.

### Step 1: place the repositories in one workspace

Keep the participating repositories under a common parent directory. They
remain independent Git repositories and can still be opened as separate
Projects in Codex or another Agent tool.

```text
workspace/
├── ios-app/
├── backend/
└── web-app/
```

The common parent must be readable and writable by every participating
Session. The shared `.agent-to-agent/` directory will be created there in a
later step.

### Step 2: give every project an identity

Create `.agent-to-agent.json` at the root of each repository. Give every
project a stable, unique `agentId`, while pointing all of them to the same
workspace-level directory.

For `ios-app/.agent-to-agent.json`:

```json
{
  "version": 1,
  "agentId": "ios-app",
  "spaceDirectory": "../.agent-to-agent"
}
```

For `backend/.agent-to-agent.json`, use the same shared path and change only
the identity:

```json
{
  "version": 1,
  "agentId": "backend",
  "spaceDirectory": "../.agent-to-agent"
}
```

Repeat this for any additional repository, such as `web-app`. An `agentId`
normally names a repository or responsibility. Multiple Sessions working in
the same repository should share that identity unless they need separately
addressable inboxes.

Relative `spaceDirectory` values are resolved from the config file, not from
the shell's current directory.

### Step 3: initialize the shared space once

Run `init` from any participating project. Use the path where you installed
this Skill:

```bash
python /path/to/agent-to-agent-space/scripts/agent_space.py init \
  --start /path/to/workspace/ios-app
```

This creates the shared inbox without changing any repository:

```text
workspace/
├── .agent-to-agent/
│   └── requirements/
├── ios-app/
│   └── .agent-to-agent.json
├── backend/
│   └── .agent-to-agent.json
└── web-app/
    └── .agent-to-agent.json
```

If Python is unavailable, follow
[`references/manual-fallback.md`](references/manual-fallback.md) instead.

### Step 4: verify every project

Resolve the configuration once from each repository:

```bash
python /path/to/agent-to-agent-space/scripts/agent_space.py resolve \
  --start /path/to/workspace/ios-app
python /path/to/agent-to-agent-space/scripts/agent_space.py resolve \
  --start /path/to/workspace/backend
```

Both results must report the same `spaceDirectory`. Their `agentId` values must
be different: `ios-app` and `backend` in this example. Fix the configuration
before continuing if either check fails.

### Step 5: open a separate Project and Session for each repository

Open `ios-app`, `backend`, and `web-app` as separate Projects in your Agent
tool. Each Session keeps its own repository context, while the shared inbox
connects them. If the Skill was installed after a Session started, restart or
refresh that Session so the Skill can be discovered.

### Step 6: send the first requirement

In the iOS Session, use natural language:

> Send the backend a requirement to add an article bookmarking endpoint.
> Include the request parameters and acceptance criteria.

The Agent should create a requirement addressed from `ios-app` to `backend`.
The equivalent CLI command is:

```bash
python /path/to/agent-to-agent-space/scripts/agent_space.py create \
  --start /path/to/workspace/ios-app \
  --to backend \
  --title "Add article bookmarking endpoint" \
  --body "Provide an authenticated endpoint that bookmarks an article." \
  --acceptance "A valid request returns the saved bookmark."
```

The command returns a requirement ID such as `req-...`. The request is now
durable, but it does not automatically wake the backend Session.

### Step 7: receive and respond to the requirement

Switch to the backend Session and say:

> The frontend has a new requirement. Check it.

The Agent should inspect the backend inbox, explain the request, and accept,
block, reject, or complete it as appropriate. The equivalent CLI operations
are:

```bash
python /path/to/agent-to-agent-space/scripts/agent_space.py list \
  --start /path/to/workspace/backend
python /path/to/agent-to-agent-space/scripts/agent_space.py respond \
  --start /path/to/workspace/backend \
  --id req-... \
  --status accepted \
  --message "Starting implementation against the documented contract."
```

### Step 8: check the result from the originating Session

Return to the iOS Session and say:

> Check whether the backend has responded to my requirement.

The iOS Agent can now read the updated status and response history without you
copying context between Sessions. Continue using the same flow for follow-up
requirements among frontend, backend, data, infrastructure, or operations
repositories.

You are finished when every project resolves to the same shared directory and
the receiving Session can discover and respond to the first requirement.

See [references/protocol.md](references/protocol.md) for the complete file
format and lifecycle rules. A complete three-repository layout is available
under [`examples/workspace`](examples/workspace).

## Properties

- Generic agent identities; no app/backend assumptions.
- No daemon, database, account, or network dependency.
- Python CLI preferred, with a documented filesystem fallback.
- Collision-resistant requirement IDs.
- Atomic publication and locked updates.
- Human-readable Markdown with YAML-compatible frontmatter.
- No automatic Git commits or pushes.

## Development

Run the standard-library-only test suite:

```bash
python -m unittest discover -s tests -v
```

Validate the Skill structure with Codex's `quick_validate.py` before release.

## License

No license has been selected yet. Add an explicit open-source license before
publishing the repository publicly.
