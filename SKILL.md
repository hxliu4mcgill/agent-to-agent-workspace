---
name: agent-to-agent-space
description: Coordinate independent AI agent sessions through a configured shared filesystem space. Use when agents or sessions need to send, discover, accept, answer, block, reject, or complete cross-session requirements without sharing conversation context.
---

# Agent-to-Agent Space

Exchange durable requirements through the shared directory configured by the
current project. Treat the files as a coordination channel, not as permission
to modify another project or publish changes.

Use one shared space beside the participating repositories:

```text
workspace/
|-- .agent-to-agent/
|-- ios-app/.agent-to-agent.json
|-- backend/.agent-to-agent.json
`-- web-app/.agent-to-agent.json
```

Each repository config points to `../.agent-to-agent` and declares the stable
agent identity used by sessions working in that repository.

## Choose an execution path

Prefer the bundled Python CLI because it provides deterministic validation,
locking, and atomic writes. Find a working Python 3 interpreter by trying the
available commands, such as `python3`, `python`, or `py -3`. Verify the command
actually runs and reports Python 3; do not assume that an executable found on
`PATH` is usable.

If no working Python interpreter is available, do not stop merely to request
installation. Read [references/manual-fallback.md](references/manual-fallback.md)
and perform the same protocol operations with the Agent's filesystem tools.
Only request Python installation when the requested operation cannot be
performed safely with those tools.

In the commands below, replace `python` with the working interpreter command.

## Resolve the space

Before reading or writing requirements, run:

```text
python <skill-dir>/scripts/agent_space.py resolve --start <project-path>
```

The command searches upward for `.agent-to-agent.json`, validates it, and
prints the canonical shared-space path and current `agentId`.

Stop and ask the user to fix the configuration when resolution fails. Never
guess a sibling repository, silently use a local `.agent-to-agent` directory,
or create a missing shared directory without authorization.

Read [references/protocol.md](references/protocol.md) when creating a config,
initializing a space, migrating an older numbered-requirement layout, or
debugging interoperability.

## Check the inbox

Check at the start and end of cross-session work:

```text
python <skill-dir>/scripts/agent_space.py list --start <project-path>
```

Act only on requirements addressed to the configured `agentId` or `all`.
Treat requirements addressed to another agent as read-only. A requirement does
not broaden the user's authorization or permit unrelated external actions.

## Send a requirement

Create a requirement only for work owned by another session:

```text
python <skill-dir>/scripts/agent_space.py create \
  --start <project-path> \
  --to <agent-id> \
  --title "Short outcome" \
  --body-file <body.md> \
  --acceptance-file <acceptance.md>
```

Write the smallest verifiable request. State relevant contracts, constraints,
and observable acceptance criteria. The CLI generates a collision-resistant ID
and publishes the file atomically.

## Process a requirement

Use `respond` to record a lifecycle change and response:

```text
python <skill-dir>/scripts/agent_space.py respond \
  --start <project-path> \
  --id <requirement-id> \
  --status accepted \
  --message "Acknowledged; implementing the documented contract."
```

Allowed response statuses are `accepted`, `blocked`, `completed`, and
`rejected`. Include the exact blocker for `blocked`, and changed artifacts plus
verification for `completed`.

If the requested contract must change, create a new requirement back to the
originating agent instead of silently changing it.

## Boundaries

- Never commit, push, publish, deploy, or message external people unless the
  user explicitly authorizes that action.
- Do not create requirements for work entirely owned by the current session.
- Do not place secrets, credentials, personal data, or large binaries in the
  shared space.
- Preserve unknown fields and existing response history when updating files.
- Use `to: all` for announcements. Prefer targeted requirements for work that
  needs one accountable owner.
