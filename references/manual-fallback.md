# Manual filesystem fallback

Use this procedure only when the bundled Python CLI cannot run. Preserve the
same configuration, file format, routing, and lifecycle rules defined in
[protocol.md](protocol.md).

## Resolve configuration

1. Starting at the current project path, walk toward the filesystem root and
   select the nearest `.agent-to-agent.json`.
2. Parse the JSON and require `version: 1`, a valid `agentId`, and a non-empty
   `spaceDirectory`.
3. Resolve a relative `spaceDirectory` from the config file's directory.
4. Require the resolved shared directory to exist. Never guess a sibling path
   or silently create a different local space.

Valid agent IDs match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`.

## Initialize the space

After resolving a valid config, create `<spaceDirectory>/requirements/` if the
user authorized initialization. Do not move or rename legacy requirements.

## List the inbox

1. Read files matching `requirements/req-*.md`; ignore dotfiles.
2. Parse the frontmatter and require the fields documented in `protocol.md`.
3. By default, return only items whose `to` is the current `agentId` or `all`
   and whose status is not `completed` or `rejected`.
4. Treat requirements addressed to another agent as read-only.

Malformed files must be reported rather than silently ignored or repaired.

## Create a requirement

1. Validate the recipient and generate an ID in this form:
   `req-<UTC timestamp>-<sender agentId>-<8 random hex characters>`.
2. Render the required frontmatter, requirement body, acceptance criteria, and
   an empty `Responses` section exactly as described in `protocol.md`.
3. Never overwrite an existing path. Regenerate the random suffix on collision.
4. Prefer writing a hidden temporary sibling, flushing it, and atomically
   renaming it to the final `.md` path. If the Agent's file API cannot rename
   atomically, use a single create operation on the unique final path and
   verify the complete file immediately afterward.

## Respond to a requirement

1. Acquire an exclusive sibling lock named `.<requirement filename>.lock`.
2. Re-read the requirement after acquiring the lock.
3. Validate its ID, recipient, current status, and requested transition.
4. Update `status` and `updated_at`, then append a timestamped response without
   removing prior response history or unknown frontmatter fields.
5. Replace the file atomically and remove the lock in a `finally`-equivalent
   cleanup step.

If the available tools cannot create a lock exclusively and concurrent writers
may exist, do not perform the update. Report that safe response updates require
the Python CLI or another executor that provides exclusive creation and atomic
replacement. Read-only operations may continue.

Allowed transitions are:

```text
pending  -> accepted | blocked | rejected
accepted -> blocked | completed | rejected
blocked  -> accepted | rejected
```
