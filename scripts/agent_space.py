#!/usr/bin/env python3
"""Filesystem coordination CLI for independent agent sessions."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


CONFIG_NAME = ".agent-to-agent.json"
AGENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REQUIREMENT_ID_RE = re.compile(
    r"^req-[0-9]{8}T[0-9]{12}Z-[A-Za-z0-9._-]+-[a-f0-9]{8}$"
)
STATUSES = {"pending", "accepted", "blocked", "completed", "rejected"}
RESPONSE_STATUSES = STATUSES - {"pending"}
STATUS_TRANSITIONS = {
    "pending": {"accepted", "blocked", "rejected"},
    "accepted": {"blocked", "completed", "rejected"},
    "blocked": {"accepted", "rejected"},
    "completed": set(),
    "rejected": set(),
}


class SpaceError(RuntimeError):
    """Raised for invalid configuration or protocol operations."""


@dataclass(frozen=True)
class SpaceConfig:
    config_path: Path
    agent_id: str
    space_directory: Path

    @property
    def requirements_directory(self) -> Path:
        return self.space_directory / "requirements"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def discover_config(start: Path, explicit: Path | None = None) -> Path:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.is_file():
            raise SpaceError(f"Config does not exist: {path}")
        return path

    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_NAME
        if candidate.is_file():
            return candidate
    raise SpaceError(f"No {CONFIG_NAME} found from {current} or its parents")


def discover_project_root(start: Path) -> Path:
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        if (directory / ".git").exists():
            return directory
    raise SpaceError(f"No Git repository root found from {current}")


def load_config(
    start: Path, explicit: Path | None = None, *, require_space: bool = True
) -> SpaceConfig:
    path = discover_config(start, explicit)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SpaceError(f"Cannot read valid JSON config {path}: {error}") from error

    if not isinstance(value, dict) or value.get("version") != 1:
        raise SpaceError("Config version must be 1")
    agent_id = value.get("agentId")
    if not isinstance(agent_id, str) or not AGENT_ID_RE.fullmatch(agent_id):
        raise SpaceError("agentId must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}")
    raw_space = value.get("spaceDirectory")
    if not isinstance(raw_space, str) or not raw_space.strip():
        raise SpaceError("spaceDirectory must be a non-empty string")

    candidate = Path(raw_space).expanduser()
    if not candidate.is_absolute():
        candidate = path.parent / candidate
    space = candidate.resolve()
    if require_space and not space.is_dir():
        raise SpaceError(f"Shared space does not exist: {space}")
    return SpaceConfig(path, agent_id, space)


def quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise SpaceError("Requirement is missing frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SpaceError("Requirement frontmatter is not terminated")
    metadata: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, separator, raw = line.partition(":")
        if not separator:
            raise SpaceError(f"Invalid frontmatter line: {line}")
        raw = raw.strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        metadata[key.strip()] = str(parsed)
    return metadata, text[end + 5 :]


def render_frontmatter(metadata: dict[str, str]) -> str:
    preferred = [
        "id",
        "title",
        "from",
        "to",
        "status",
        "created_at",
        "updated_at",
    ]
    keys = [key for key in preferred if key in metadata]
    keys.extend(sorted(set(metadata) - set(keys)))
    lines = ["---", *(f"{key}: {quote(metadata[key])}" for key in keys), "---"]
    return "\n".join(lines) + "\n"


def validate_metadata(metadata: dict[str, str], expected_id: str | None = None) -> None:
    missing = {
        "id",
        "title",
        "from",
        "to",
        "status",
        "created_at",
        "updated_at",
    } - set(metadata)
    if missing:
        raise SpaceError(f"Requirement is missing fields: {', '.join(sorted(missing))}")
    if expected_id is not None and metadata["id"] != expected_id:
        raise SpaceError("Requirement ID does not match its filename")
    if metadata["status"] not in STATUSES:
        raise SpaceError(f"Invalid requirement status: {metadata['status']}")
    for field in ("from", "to"):
        if metadata[field] != "all" and not AGENT_ID_RE.fullmatch(metadata[field]):
            raise SpaceError(f"Invalid {field} agent ID")


def read_value(value: str | None, file_path: str | None, label: str) -> str:
    if value is not None and file_path is not None:
        raise SpaceError(f"Use either --{label} or --{label}-file, not both")
    if file_path is not None:
        return Path(file_path).read_text(encoding="utf-8").strip()
    if value is not None:
        return value.strip()
    raise SpaceError(f"Missing --{label} or --{label}-file")


def requirement_id(agent_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"req-{stamp}-{agent_id}-{secrets.token_hex(4)}"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def exclusive_lock(path: Path, timeout: float = 5.0) -> Iterator[None]:
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise SpaceError(f"Timed out waiting for lock: {path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def requirement_path(config: SpaceConfig, item_id: str) -> Path:
    if not REQUIREMENT_ID_RE.fullmatch(item_id):
        raise SpaceError("Invalid requirement ID")
    return config.requirements_directory / f"{item_id}.md"


def command_setup(args: argparse.Namespace) -> dict[str, object]:
    project_root = discover_project_root(Path(args.start))
    config_path = project_root / CONFIG_NAME
    config_existed = config_path.exists()

    if config_existed and not args.force:
        config = load_config(project_root, config_path, require_space=False)
        if args.agent_id is not None and args.agent_id != config.agent_id:
            raise SpaceError(
                f"Config already uses agentId {config.agent_id}; use --force to replace it"
            )
        if args.space is not None:
            requested = Path(args.space).expanduser()
            if not requested.is_absolute():
                requested = project_root / requested
            if requested.resolve() != config.space_directory:
                raise SpaceError(
                    "Config already uses a different spaceDirectory; "
                    "use --force to replace it"
                )
    else:
        agent_id = args.agent_id or project_root.name
        if not AGENT_ID_RE.fullmatch(agent_id):
            raise SpaceError(
                "Cannot infer a valid agentId from the project name; "
                "provide --agent-id"
            )
        raw_space = args.space or "../.agent-to-agent"
        if not raw_space.strip():
            raise SpaceError("--space must be a non-empty path")
        candidate = Path(raw_space).expanduser()
        if not candidate.is_absolute():
            candidate = project_root / candidate
        config = SpaceConfig(config_path, agent_id, candidate.resolve())
        content = json.dumps(
            {
                "version": 1,
                "agentId": agent_id,
                "spaceDirectory": raw_space,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        atomic_write(config_path, content)

    requirements_existed = config.requirements_directory.is_dir()
    config.requirements_directory.mkdir(parents=True, exist_ok=True)
    verified = load_config(project_root, config_path)
    return {
        **_config_result(verified),
        "projectRoot": str(project_root),
        "configCreated": not config_existed,
        "configUpdated": config_existed and args.force,
        "spaceInitialized": not requirements_existed,
        "verified": True,
    }


def command_init(args: argparse.Namespace) -> dict[str, object]:
    config = load_config(Path(args.start), _optional_path(args.config), require_space=False)
    config.requirements_directory.mkdir(parents=True, exist_ok=True)
    return _config_result(config)


def command_resolve(args: argparse.Namespace) -> dict[str, object]:
    return _config_result(load_config(Path(args.start), _optional_path(args.config)))


def _config_result(config: SpaceConfig) -> dict[str, object]:
    return {
        "version": 1,
        "agentId": config.agent_id,
        "configPath": str(config.config_path),
        "spaceDirectory": str(config.space_directory),
        "requirementsDirectory": str(config.requirements_directory),
    }


def command_create(args: argparse.Namespace) -> dict[str, object]:
    config = load_config(Path(args.start), _optional_path(args.config))
    if args.to != "all" and not AGENT_ID_RE.fullmatch(args.to):
        raise SpaceError("--to must be a valid agent ID or all")
    title = args.title.strip()
    if not title or "\n" in title:
        raise SpaceError("--title must be one non-empty line")
    body = read_value(args.body, args.body_file, "body")
    acceptance = read_value(args.acceptance, args.acceptance_file, "acceptance")
    item_id = requirement_id(config.agent_id)
    now = utc_now()
    metadata = {
        "id": item_id,
        "title": title,
        "from": config.agent_id,
        "to": args.to,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    content = (
        render_frontmatter(metadata)
        + f"\n# Requirement\n\n{body}\n\n"
        + f"## Acceptance criteria\n\n{acceptance}\n\n## Responses\n"
    )
    path = requirement_path(config, item_id)
    if path.exists():
        raise SpaceError(f"Requirement already exists: {item_id}")
    atomic_write(path, content)
    return {"id": item_id, "path": str(path), "status": "pending"}


def load_requirement(path: Path) -> tuple[dict[str, str], str]:
    if not path.is_file():
        raise SpaceError(f"Requirement does not exist: {path}")
    metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    validate_metadata(metadata, path.stem)
    return metadata, body


def command_list(args: argparse.Namespace) -> list[dict[str, str]]:
    config = load_config(Path(args.start), _optional_path(args.config))
    results: list[dict[str, str]] = []
    if not config.requirements_directory.is_dir():
        return results
    for path in sorted(config.requirements_directory.glob("req-*.md")):
        metadata, _ = load_requirement(path)
        if not args.all:
            if metadata["to"] not in {config.agent_id, "all"}:
                continue
            if metadata["status"] in {"completed", "rejected"}:
                continue
        results.append({**metadata, "path": str(path)})
    return results


def command_respond(args: argparse.Namespace) -> dict[str, object]:
    config = load_config(Path(args.start), _optional_path(args.config))
    if args.status not in RESPONSE_STATUSES:
        raise SpaceError(f"Invalid response status: {args.status}")
    message = args.message.strip()
    if not message:
        raise SpaceError("--message must not be empty")
    path = requirement_path(config, args.id)
    lock_path = path.with_name(f".{path.name}.lock")
    with exclusive_lock(lock_path):
        metadata, body = load_requirement(path)
        if metadata["to"] not in {config.agent_id, "all"}:
            raise SpaceError(
                f"Requirement is addressed to {metadata['to']}, not {config.agent_id}"
            )
        current_status = metadata["status"]
        if args.status not in STATUS_TRANSITIONS[current_status]:
            raise SpaceError(
                f"Invalid status transition: {current_status} -> {args.status}"
            )
        now = utc_now()
        metadata["status"] = args.status
        metadata["updated_at"] = now
        response = f"\n### {now} — {config.agent_id} ({args.status})\n\n{message}\n"
        atomic_write(path, render_frontmatter(metadata) + body.rstrip() + response)
    return {"id": args.id, "path": str(path), "status": args.status}


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    location = argparse.ArgumentParser(add_help=False)
    location.add_argument("--start", default=os.getcwd(), help="Project path")
    location.add_argument("--config", help="Explicit configuration path")

    setup = subparsers.add_parser(
        "setup", help="Configure the current Git project and initialize its shared space"
    )
    setup.add_argument("--start", default=os.getcwd(), help="Project path")
    setup.add_argument("--agent-id", help="Stable project identity; defaults to repo name")
    setup.add_argument(
        "--space",
        help="Shared-space path stored in config; defaults to ../.agent-to-agent",
    )
    setup.add_argument(
        "--force", action="store_true", help="Replace an existing project config"
    )

    subparsers.add_parser(
        "init", parents=[location], help="Create the configured shared space"
    )
    subparsers.add_parser(
        "resolve", parents=[location], help="Resolve and validate configuration"
    )

    list_parser = subparsers.add_parser(
        "list", parents=[location], help="List inbox requirements"
    )
    list_parser.add_argument("--all", action="store_true", help="Include all items")

    create = subparsers.add_parser(
        "create", parents=[location], help="Create a requirement"
    )
    create.add_argument("--to", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--body")
    create.add_argument("--body-file")
    create.add_argument("--acceptance")
    create.add_argument("--acceptance-file")

    respond = subparsers.add_parser(
        "respond", parents=[location], help="Update and answer a requirement"
    )
    respond.add_argument("--id", required=True)
    respond.add_argument("--status", required=True, choices=sorted(RESPONSE_STATUSES))
    respond.add_argument("--message", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "setup": command_setup,
        "init": command_init,
        "resolve": command_resolve,
        "list": command_list,
        "create": command_create,
        "respond": command_respond,
    }
    try:
        result = commands[args.command](args)
    except (OSError, SpaceError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "data": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
