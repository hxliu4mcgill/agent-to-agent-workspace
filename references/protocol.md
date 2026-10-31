# Agent-to-Agent Space Protocol v1

## Configuration

Each participating project contains `.agent-to-agent.json`:

```json
{
  "version": 1,
  "agentId": "frontend",
  "spaceDirectory": "../.agent-to-agent"
}
```

- `version`: protocol configuration version; currently `1`.
- `agentId`: stable identity matching `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`.
- `spaceDirectory`: absolute path or path relative to the config file.

Configuration discovery walks from `--start` toward the filesystem root and
uses the nearest `.agent-to-agent.json`.

## Workspace topology

Place the shared space at the common parent of the participating repositories:

```text
workspace/
  .agent-to-agent/
    requirements/
  repo-a/
    .agent-to-agent.json
  repo-b/
    .agent-to-agent.json
```

Both project configs use `"spaceDirectory": "../.agent-to-agent"`. An agent
can start anywhere below its repository; config discovery finds the nearest
project config, then path resolution reaches the same workspace-level space.

Do not put the shared directory inside one participant repository unless that
repository is intentionally the owner of the coordination data. A neutral
workspace-level directory prevents one repo from becoming an accidental
transport or authority boundary.

## Space layout

```text
workspace/.agent-to-agent/
  requirements/
    req-20261028T020304123456Z-ios-app-a1b2c3d4.md
```

Temporary and lock files begin with `.` and are not protocol messages.

## Requirement format

```markdown
---
id: "req-20261028T020304123456Z-ios-app-a1b2c3d4"
title: "Add capture-preview endpoint"
from: "ios-app"
to: "backend"
status: "pending"
created_at: "2026-10-28T02:03:04.123456Z"
updated_at: "2026-10-28T02:03:04.123456Z"
---

# Requirement

Describe the requested outcome and relevant constraints.

## Acceptance criteria

- State an observable completion condition.

## Responses

### 2026-10-28T02:05:00.000000Z — backend (accepted)

Acknowledged; beginning implementation.
```

Required frontmatter fields are `id`, `title`, `from`, `to`, `status`,
`created_at`, and `updated_at`. Readers must ignore unknown fields.

`to` is either an agent ID or `all`. Broadcast requirements are best used for
announcements; targeted requirements provide clear ownership.

## Lifecycle

```text
pending -> accepted -> completed
   |           |
   +-> rejected+-> blocked -> accepted
```

Valid statuses are `pending`, `accepted`, `blocked`, `completed`, and
`rejected`. A response appends history rather than replacing earlier entries.

## Concurrency

Writers create a hidden temporary file in `requirements/`, flush it, and rename
it to the final unique ID. Updates acquire an adjacent exclusive lock and use
the same replace pattern. Readers ignore dotfiles.

IDs combine a UTC timestamp, sender ID, and random suffix. They are not ordered
sequence numbers and do not require scanning the directory before creation.

## Trust and authorization

The shared filesystem boundary is the trust boundary. The protocol does not
authenticate writers or sandbox agents. Requirements communicate intent but do
not grant new authority. Agents must still follow user authorization and local
safety rules.

Do not store secrets or sensitive personal data. Use a private, access-controlled
directory when requirements contain proprietary information.

## Legacy migration

Older `requirementNNN/requirement.md` files may be retained as an archive.
Migrate active work by creating new v1 files in `requirements/`; do not rename
live legacy files while another session may be using them.
