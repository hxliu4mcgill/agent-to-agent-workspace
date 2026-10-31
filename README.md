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

## Configure each project

The intended deployment is one parent workspace containing several related
repositories and one shared coordination directory:

```text
workspace/
├── .agent-to-agent/          # shared inbox and requirement history
├── ios-app/
│   └── .agent-to-agent.json
├── backend/
│   └── .agent-to-agent.json
└── web-app/
    └── .agent-to-agent.json
```

Every agent Session keeps working inside its own repository. The small config
file in that repository points upward to the same workspace-level directory.

Create `.agent-to-agent.json` in every participating project:

```json
{
  "version": 1,
  "agentId": "ios-app",
  "spaceDirectory": "../.agent-to-agent"
}
```

Each project uses its own stable `agentId`. All participants resolve
`spaceDirectory` to the same directory. Relative paths are resolved from the
configuration file, not from the current shell directory.

`agentId` normally identifies the repository or responsibility, such as
`ios-app`, `backend`, or `web-app`. Multiple Sessions working for the same
repository share that identity and inbox. Use separate IDs only when those
Sessions need independently addressable ownership.

Initialize the shared directory once:

```bash
python scripts/agent_space.py init --start /path/to/project
```

Then inspect or exchange requirements:

```bash
python scripts/agent_space.py resolve --start /path/to/project
python scripts/agent_space.py list --start /path/to/project
python scripts/agent_space.py create --start /path/to/project \
  --to backend --title "Add article enrichment" \
  --body "Enrich public article URLs during capture preview." \
  --acceptance "A public article produces a useful title and summary."
python scripts/agent_space.py respond --start /path/to/backend \
  --id req-... --status accepted --message "Starting implementation."
```

See [references/protocol.md](references/protocol.md) for the complete file
format and lifecycle rules.

A complete three-repository layout is available under
[`examples/workspace`](examples/workspace).

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
