import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_space  # noqa: E402


class AgentSpaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.shared = self.root / ".agent-to-agent"
        self.frontend = self._project("frontend", "frontend")
        self.backend = self._project("backend", "backend")

    def tearDown(self):
        self.temporary.cleanup()

    def _project(self, name: str, agent_id: str) -> Path:
        project = self.root / name
        project.mkdir()
        relative = Path("..") / ".agent-to-agent"
        (project / ".agent-to-agent.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "agentId": agent_id,
                    "spaceDirectory": str(relative),
                }
            ),
            encoding="utf-8",
        )
        return project

    def args(self, **values):
        defaults = {"start": str(self.frontend), "config": None}
        defaults.update(values)
        return type("Args", (), defaults)()

    def setup_args(self, project: Path, **values):
        defaults = {
            "start": str(project),
            "agent_id": None,
            "space": None,
            "force": False,
        }
        defaults.update(values)
        return type("Args", (), defaults)()

    def new_git_project(self, name: str) -> Path:
        project = self.root / name
        project.mkdir()
        (project / ".git").mkdir()
        return project

    def test_setup_creates_config_and_shared_space_from_nested_path(self):
        project = self.new_git_project("api")
        nested = project / "src" / "feature"
        nested.mkdir(parents=True)

        result = agent_space.command_setup(self.setup_args(nested))

        self.assertEqual(result["agentId"], "api")
        self.assertTrue(result["configCreated"])
        self.assertTrue(result["spaceInitialized"])
        self.assertTrue(result["verified"])
        self.assertEqual(Path(result["spaceDirectory"]), self.shared.resolve())
        config = json.loads((project / ".agent-to-agent.json").read_text("utf-8"))
        self.assertEqual(
            config,
            {
                "version": 1,
                "agentId": "api",
                "spaceDirectory": "../.agent-to-agent",
            },
        )
        self.assertTrue((self.shared / "requirements").is_dir())

    def test_setup_is_idempotent_and_rejects_conflicting_values(self):
        project = self.new_git_project("service")
        first = agent_space.command_setup(self.setup_args(project))
        second = agent_space.command_setup(self.setup_args(project))

        self.assertTrue(first["configCreated"])
        self.assertFalse(second["configCreated"])
        self.assertFalse(second["configUpdated"])
        self.assertFalse(second["spaceInitialized"])

        with self.assertRaises(agent_space.SpaceError):
            agent_space.command_setup(
                self.setup_args(project, agent_id="different-backend")
            )

    def test_setup_force_replaces_existing_config(self):
        project = self.new_git_project("worker")
        agent_space.command_setup(self.setup_args(project))

        result = agent_space.command_setup(
            self.setup_args(
                project,
                agent_id="api",
                space="../shared-agent-space",
                force=True,
            )
        )

        self.assertTrue(result["configUpdated"])
        self.assertEqual(result["agentId"], "api")
        self.assertEqual(
            Path(result["spaceDirectory"]),
            (self.root / "shared-agent-space").resolve(),
        )

    def test_resolve_requires_existing_space(self):
        with self.assertRaises(agent_space.SpaceError):
            agent_space.load_config(self.frontend)

        result = agent_space.command_init(self.args())

        self.assertEqual(result["agentId"], "frontend")
        self.assertEqual(Path(result["spaceDirectory"]), self.shared.resolve())

    def test_multiple_repositories_resolve_one_workspace_space(self):
        agent_space.command_init(self.args())
        frontend_config = agent_space.load_config(self.frontend)
        backend_config = agent_space.load_config(self.backend)

        self.assertEqual(frontend_config.space_directory, self.shared.resolve())
        self.assertEqual(backend_config.space_directory, self.shared.resolve())
        self.assertNotEqual(frontend_config.agent_id, backend_config.agent_id)

    def test_create_list_and_respond(self):
        agent_space.command_init(self.args())
        created = agent_space.command_create(
            self.args(
                to="backend",
                title="Define the capture contract",
                body="Return a structured proposal.",
                body_file=None,
                acceptance="The response validates against v1.",
                acceptance_file=None,
            )
        )

        frontend_items = agent_space.command_list(self.args(all=False))
        self.assertEqual(frontend_items, [])

        backend_args = self.args(start=str(self.backend), all=False)
        backend_items = agent_space.command_list(backend_args)
        self.assertEqual([item["id"] for item in backend_items], [created["id"]])

        agent_space.command_respond(
            self.args(
                start=str(self.backend),
                id=created["id"],
                status="accepted",
                message="Accepted for implementation.",
            )
        )
        response = agent_space.command_respond(
            self.args(
                start=str(self.backend),
                id=created["id"],
                status="completed",
                message="Implemented and verified with contract tests.",
            )
        )
        self.assertEqual(response["status"], "completed")
        text = Path(response["path"]).read_text(encoding="utf-8")
        self.assertIn('status: "completed"', text)
        self.assertIn("backend (completed)", text)

    def test_other_agent_cannot_respond(self):
        agent_space.command_init(self.args())
        created = agent_space.command_create(
            self.args(
                to="backend",
                title="Backend-only requirement",
                body="Do the backend work.",
                body_file=None,
                acceptance="Backend reports completion.",
                acceptance_file=None,
            )
        )

        with self.assertRaises(agent_space.SpaceError):
            agent_space.command_respond(
                self.args(
                    id=created["id"],
                    status="accepted",
                    message="Wrong recipient.",
                )
            )

    def test_invalid_config_is_rejected(self):
        config_path = self.frontend / ".agent-to-agent.json"
        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "agentId": "invalid agent",
                    "spaceDirectory": "../shared",
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(agent_space.SpaceError):
            agent_space.load_config(self.frontend, require_space=False)

    def test_cli_accepts_location_after_command(self):
        args = agent_space.build_parser().parse_args(
            ["resolve", "--start", str(self.frontend)]
        )

        self.assertEqual(args.command, "resolve")
        self.assertEqual(args.start, str(self.frontend))

    def test_cli_init_and_resolve_round_trip(self):
        script = ROOT / "scripts" / "agent_space.py"
        initialized = subprocess.run(
            [sys.executable, "-B", str(script), "init", "--start", str(self.frontend)],
            check=False,
            capture_output=True,
            text=True,
        )
        resolved = subprocess.run(
            [
                sys.executable,
                "-B",
                str(script),
                "resolve",
                "--start",
                str(self.frontend),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        payload = json.loads(resolved.stdout)
        self.assertEqual(payload["data"]["agentId"], "frontend")
        self.assertEqual(Path(payload["data"]["spaceDirectory"]), self.shared.resolve())

    def test_cli_setup_round_trip(self):
        project = self.new_git_project("analytics")
        script = ROOT / "scripts" / "agent_space.py"

        completed = subprocess.run(
            [sys.executable, "-B", str(script), "setup", "--start", str(project)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["agentId"], "analytics")
        self.assertTrue(payload["data"]["configCreated"])
        self.assertTrue(payload["data"]["verified"])
        self.assertTrue((project / ".agent-to-agent.json").is_file())
        self.assertTrue((self.shared / "requirements").is_dir())

    def test_concurrent_creates_use_unique_ids(self):
        agent_space.command_init(self.args())

        def create(index):
            return agent_space.command_create(
                self.args(
                    to="backend",
                    title=f"Requirement {index}",
                    body="Coordinate this work.",
                    body_file=None,
                    acceptance="The receiver reports a result.",
                    acceptance_file=None,
                )
            )["id"]

        with ThreadPoolExecutor(max_workers=8) as executor:
            identifiers = list(executor.map(create, range(32)))

        self.assertEqual(len(set(identifiers)), 32)
        self.assertEqual(len(list(self.shared.glob("requirements/req-*.md"))), 32)

    def test_terminal_status_cannot_be_reopened(self):
        agent_space.command_init(self.args())
        created = agent_space.command_create(
            self.args(
                to="backend",
                title="Terminal lifecycle",
                body="Complete this once.",
                body_file=None,
                acceptance="The item stays completed.",
                acceptance_file=None,
            )
        )
        agent_space.command_respond(
            self.args(
                start=str(self.backend),
                id=created["id"],
                status="accepted",
                message="Accepted.",
            )
        )
        agent_space.command_respond(
            self.args(
                start=str(self.backend),
                id=created["id"],
                status="completed",
                message="Completed.",
            )
        )

        with self.assertRaises(agent_space.SpaceError):
            agent_space.command_respond(
                self.args(
                    start=str(self.backend),
                    id=created["id"],
                    status="accepted",
                    message="Reopening is not allowed.",
                )
            )


if __name__ == "__main__":
    unittest.main()
