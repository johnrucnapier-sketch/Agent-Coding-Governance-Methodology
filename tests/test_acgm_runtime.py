from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
RUNTIME_PATH = REPO_ROOT / "scripts" / "acgm_runtime.py"

SPEC = importlib.util.spec_from_file_location("acgm_runtime", RUNTIME_PATH)
assert SPEC and SPEC.loader
acgm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acgm)


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def capture_json(function, *args, **kwargs):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        function(*args, **kwargs)
    value = output.getvalue().strip()
    return json.loads(value) if value else None


class RuntimeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="acgm tests 中文 ")
        self.base = Path(self.temp.name)
        self.data_dir = self.base / "plugin data"
        self.config_dir = self.base / "claude config"
        self.environment = mock.patch.dict(
            os.environ,
            {
                "ACGM_DATA_DIR": str(self.data_dir),
                "CLAUDE_CONFIG_DIR": str(self.config_dir),
                "HOME": str(self.base / "home"),
            },
            clear=False,
        )
        self.environment.start()
        for key in ("CLAUDE_PLUGIN_DATA", "CLAUDE_PROJECT_DIR", "XDG_DATA_HOME"):
            os.environ.pop(key, None)
        for key in ("CLAUDE_CODE_GIT_BASH_PATH", "CLAUDE_CODE_USE_POWERSHELL_TOOL"):
            os.environ.pop(key, None)
        if os.name == "nt":
            # Windows runtime tests exercise the documented RC4 profile. Tests
            # that verify settings.json discovery explicitly remove this value.
            os.environ["CLAUDE_CODE_USE_POWERSHELL_TOOL"] = "0"
        self.store = acgm.Store(self.data_dir)

    def tearDown(self) -> None:
        self.environment.stop()
        self.temp.cleanup()

    def make_git_project(self, name: str = "项目 with spaces") -> Path:
        root = self.base / name
        root.mkdir(parents=True)
        subprocess.run(
            ["git", "init", "-q", str(root)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return root

    def make_governed_project(self, name: str = "项目 with spaces") -> Path:
        root = self.make_git_project(name)
        (root / "CLAUDE.md").write_text(
            "# Rules\nRead CONSTITUTION.md and current code before acting.\n",
            encoding="utf-8",
        )
        (root / "CONSTITUTION.md").write_text(
            "# Constitution\nOnly the human owner amends this file.\n",
            encoding="utf-8",
        )
        (root / ".governance" / "decisions").mkdir(parents=True)
        (root / ".governance" / "snapshots").mkdir(parents=True)
        (root / ".governance" / "decisions" / "INDEX.md").write_text(
            "# Decision index\n",
            encoding="utf-8",
        )
        (root / ".governance" / "snapshots" / "current.md").write_text(
            "# Current-state snapshot\n\nSource: fixture commit\n",
            encoding="utf-8",
        )
        (root / ".governance" / "scope.yml").write_text(
            "in:\n  - src/**\nout:\n  - business/**\n",
            encoding="utf-8",
        )
        return root

    def materialize_fixture(self, name: str, **replacements: str) -> dict[str, object]:
        value = fixture(name)

        def replace(item):
            if isinstance(item, str):
                for source, target in replacements.items():
                    item = item.replace(f"__{source}__", target)
                return item
            if isinstance(item, list):
                return [replace(child) for child in item]
            if isinstance(item, dict):
                return {key: replace(child) for key, child in item.items()}
            return item

        return replace(value)


class ProjectAndSessionTests(RuntimeTestCase):
    def test_resolve_project_root_from_nested_unicode_space_path(self) -> None:
        root = self.make_git_project()
        nested = root / "src" / "深层 目录"
        nested.mkdir(parents=True)
        resolved = acgm.resolve_project_root({"cwd": str(nested)})
        self.assertEqual(resolved, root.resolve())

    def test_run_git_decodes_utf8_output_independent_of_locale(self) -> None:
        expected = "/tmp/项目 with spaces"
        completed = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout=expected.encode("utf-8") + b"\n"
        )
        with mock.patch.object(acgm.subprocess, "run", return_value=completed):
            self.assertEqual(acgm.run_git(self.base, "rev-parse", "--show-toplevel"), expected)

    def test_hook_json_wire_is_independent_of_windows_code_page(self) -> None:
        payload = {"cwd": "C:/项目 with spaces", "session_id": "会话"}
        stream = io.TextIOWrapper(
            io.BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
            encoding="cp1252",
        )
        with mock.patch("sys.stdin", stream):
            self.assertEqual(acgm.read_hook_input(), payload)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            acgm.json_print(payload)
        output.getvalue().encode("ascii")
        self.assertEqual(json.loads(output.getvalue()), payload)

    def test_project_state_lifecycle(self) -> None:
        root = self.make_git_project()
        state, components, errors, _ = acgm.assess_project(root, self.store)
        self.assertEqual(state, "INSTALLED_NOT_BOOTSTRAPPED")
        self.assertFalse(components["constitution"])
        self.assertEqual(errors, [])

        (root / "CLAUDE.md").write_text("# Rules\n", encoding="utf-8")
        state, _, _, _ = acgm.assess_project(root, self.store)
        self.assertEqual(state, "PARTIALLY_GOVERNED")

        (root / "CONSTITUTION.md").write_text("# Constitution\nStable.\n", encoding="utf-8")
        (root / ".governance" / "decisions").mkdir(parents=True)
        (root / ".governance" / "snapshots").mkdir(parents=True)
        (root / ".governance" / "decisions" / "INDEX.md").write_text(
            "# Decision index\n", encoding="utf-8"
        )
        (root / ".governance" / "snapshots" / "current.md").write_text(
            "# Snapshot\n", encoding="utf-8"
        )
        (root / ".governance" / "scope.yml").write_text(
            "in:\n  - src/**\nout:\n  - business/**\n", encoding="utf-8"
        )
        state, _, _, _ = acgm.assess_project(root, self.store)
        self.assertEqual(state, "GOVERNED")

        (root / ".governance" / "scope.yml").unlink()
        state, _, _, _ = acgm.assess_project(root, self.store)
        self.assertEqual(state, "DRIFTED")
        state, _, _, _ = acgm.assess_project(root, self.store)
        self.assertEqual(state, "DRIFTED")

    def test_explicit_missing_or_file_project_path_never_falls_back_to_cwd(self) -> None:
        missing = self.base / "does not exist"
        with self.assertRaises(FileNotFoundError):
            acgm.resolve_project_root(explicit=str(missing))

        file_path = self.base / "not a project directory.txt"
        file_path.write_text("fixture\n", encoding="utf-8")
        with self.assertRaises(NotADirectoryError):
            acgm.resolve_project_root(explicit=str(file_path))

    def test_empty_governance_directories_do_not_claim_governed(self) -> None:
        root = self.make_git_project()
        (root / "CLAUDE.md").write_text("# Rules\n", encoding="utf-8")
        (root / "CONSTITUTION.md").write_text("# Constitution\nStable.\n", encoding="utf-8")
        (root / ".governance" / "decisions").mkdir(parents=True)
        (root / ".governance" / "snapshots").mkdir(parents=True)
        (root / ".governance" / "scope.yml").write_text("in:\n  - src/**\n", encoding="utf-8")

        state, components, _, _ = acgm.assess_project(root, self.store)

        self.assertEqual(state, "PARTIALLY_GOVERNED")
        self.assertFalse(components["decisions"])
        self.assertFalse(components["snapshots"])
        self.assertFalse(components["scope"])

    def test_session_start_sources_are_explicit(self) -> None:
        root = self.make_governed_project()
        expected = {
            "startup": "project state: GOVERNED",
            "resume": "resumed or compacted",
            "compact": "resumed or compacted",
            "clear": "Context was cleared",
        }
        for source, phrase in expected.items():
            with self.subTest(source=source):
                data = self.materialize_fixture(
                    "session_start.json",
                    PROJECT_ROOT=str(root),
                )
                data["source"] = source
                data["session_id"] = f"session-{source}"
                result = capture_json(acgm.hook_session_start, data, self.store)
                context = result["hookSpecificOutput"]["additionalContext"]
                self.assertIn(phrase, context)
                self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_session_start_health_event_is_once_per_session(self) -> None:
        root = self.make_governed_project()
        data = {"cwd": str(root), "source": "startup", "session_id": "same-session"}
        capture_json(acgm.hook_session_start, data, self.store)
        capture_json(acgm.hook_session_start, data, self.store)
        health = [event for event in self.store.events() if event["event_type"] == "health"]
        self.assertEqual(len(health), 1)

    def test_transcript_reader_uses_a_bounded_tail(self) -> None:
        transcript = self.base / "large transcript.jsonl"
        prefix_line = b'{"type":"progress","payload":"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}\n'
        transcript.write_bytes(
            prefix_line * 40000 + (FIXTURES / "gate_complete.jsonl").read_bytes()
        )

        items = acgm.transcript_objects(str(transcript), max_bytes=256 * 1024)

        self.assertLessEqual(len(items), 500)
        self.assertIn("ACGM-VERIFY-AFTER:", acgm.assistant_text(items))


class ScaffoldAndPlatformTests(RuntimeTestCase):
    def test_python_scaffold_is_idempotent_and_never_overwrites(self) -> None:
        root = self.make_git_project()
        existing = root / "CLAUDE.md"
        existing.write_text("human-owned fixture\n", encoding="utf-8")

        with contextlib.redirect_stdout(io.StringIO()):
            first = acgm.scaffold_project(root)
            first_bytes = {name: (root / name).read_bytes() for name in ("CONSTITUTION.md", "AGENTS.md", "CLAUDE.md")}
            second = acgm.scaffold_project(root)

        self.assertEqual(first, (2, 1))
        self.assertEqual(second, (0, 3))
        self.assertEqual(existing.read_text(encoding="utf-8"), "human-owned fixture\n")
        self.assertEqual(
            first_bytes,
            {name: (root / name).read_bytes() for name in ("CONSTITUTION.md", "AGENTS.md", "CLAUDE.md")},
        )

    def test_python_and_posix_fallback_scaffolds_match(self) -> None:
        python_target = self.base / "python scaffold"
        shell_target = self.base / "shell scaffold"
        python_target.mkdir()
        shell_target.mkdir()

        with contextlib.redirect_stdout(io.StringIO()):
            acgm.scaffold_project(python_target)
        subprocess.run(
            ["sh", str(REPO_ROOT / "scripts" / "governance-init.sh"), str(shell_target)],
            check=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for name in ("CONSTITUTION.md", "AGENTS.md", "CLAUDE.md"):
            with self.subTest(name=name):
                self.assertEqual((python_target / name).read_bytes(), (shell_target / name).read_bytes())

    def test_interrupted_exclusive_create_removes_only_its_partial_file(self) -> None:
        partial = self.base / "partial.txt"
        original_write = os.write
        call_count = 0

        def fail_after_prefix(descriptor, content):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return original_write(descriptor, bytes(content[:1]))
            raise OSError("fixture interruption")

        with mock.patch.object(acgm.os, "write", side_effect=fail_after_prefix):
            with self.assertRaises(OSError):
                acgm.create_file_exclusive(partial, b"fixture content")
        self.assertFalse(partial.exists())

        existing = self.base / "existing.txt"
        existing.write_bytes(b"human owned")
        self.assertFalse(acgm.create_file_exclusive(existing, b"replacement"))
        self.assertEqual(existing.read_bytes(), b"human owned")

    @unittest.skipIf(os.name == "nt", "POSIX permission error contract")
    def test_posix_fchmod_failure_is_not_silenced(self) -> None:
        descriptor = os.open(self.base / "permission.txt", os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            with mock.patch.object(acgm.os, "fchmod", side_effect=OSError("fixture")):
                with self.assertRaises(OSError):
                    acgm.restrict_descriptor(descriptor)
        finally:
            os.close(descriptor)

    def test_git_bash_path_and_powershell_setting_can_come_from_claude_settings(self) -> None:
        os.environ.pop("CLAUDE_CODE_USE_POWERSHELL_TOOL", None)
        git_bash = self.base / "Git" / "bin" / "bash.exe"
        git_bash.parent.mkdir(parents=True)
        git_bash.write_bytes(b"fixture")
        self.config_dir.mkdir(parents=True)
        (self.config_dir / "settings.json").write_text(
            json.dumps(
                {
                    "env": {
                        "CLAUDE_CODE_GIT_BASH_PATH": str(git_bash),
                        "CLAUDE_CODE_USE_POWERSHELL_TOOL": "0",
                    }
                }
            ),
            encoding="utf-8",
        )

        self.assertEqual(acgm.effective_claude_env("CLAUDE_CODE_USE_POWERSHELL_TOOL"), "0")
        self.assertEqual(acgm.windows_git_bash_status(), (True, "configured_path"))

    def test_package_integrity_uses_running_python_not_python3_command_name(self) -> None:
        with mock.patch.object(acgm.shutil, "which", return_value=None):
            errors, _ = acgm.package_integrity()
        self.assertNotIn("python3_missing", errors)
        self.assertNotIn("python_too_old", errors)


class BashGateTests(RuntimeTestCase):
    def test_safe_and_destructive_command_inventory(self) -> None:
        destructive = {
            "rm important.db": "file_delete",
            "rm -r /tmp/fixture": "file_delete",
            "rm -rf /tmp/fixture": "file_delete",
            "/bin/rm -rf /tmp/fixture": "file_delete",
            "git push --force-with-lease origin topic": "git_history",
            "git reset --hard HEAD~1": "git_history",
            "git restore --worktree important.py": "git_history",
            "systemctl restart worker.service": "service_state",
            "DROP TABLE audit_log": "database_state",
            "docker prune": "container_state",
            "kubectl delete pod fixture": "container_state",
            "kill -9 123": "process_or_power",
        }
        for command, category in destructive.items():
            with self.subTest(command=command):
                self.assertEqual(acgm.destructive_category(command), category)

        for command in ("git status --short", "pytest -q", "ls -la", "docker ps", "systemctl status worker"):
            with self.subTest(command=command):
                self.assertIsNone(acgm.destructive_category(command))

    def test_safe_bash_is_silent(self) -> None:
        root = self.make_git_project()
        data = self.materialize_fixture("safe_bash.json", PROJECT_ROOT=str(root))
        self.assertEqual(capture_json(acgm.hook_pretool_bash, data, self.store), {})
        self.assertEqual(self.store.events(), [])

    def test_bash_cannot_bypass_human_owned_constitution(self) -> None:
        root = self.make_git_project()
        mutation = {
            "cwd": str(root),
            "session_id": "constitution-bash-session",
            "tool_name": "Bash",
            "tool_use_id": "constitution-bash-tool",
            "tool_input": {"command": "printf replacement > CONSTITUTION.md"},
        }
        blocked = capture_json(acgm.hook_pretool_bash, mutation, self.store)
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.store.events()[-1]["detail_code"], "constitution_bash_write")

        read_only = dict(mutation)
        read_only["tool_input"] = {"command": "cat CONSTITUTION.md"}
        self.assertEqual(capture_json(acgm.hook_pretool_bash, read_only, self.store), {})

    def test_destructive_bash_without_transcript_is_denied(self) -> None:
        root = self.make_git_project()
        data = self.materialize_fixture(
            "destructive_bash.json",
            PROJECT_ROOT=str(root),
            TRANSCRIPT_PATH=str(self.base / "missing.jsonl"),
        )
        result = capture_json(acgm.hook_pretool_bash, data, self.store)
        output = result["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("ACGM-EVIDENCE", output["permissionDecisionReason"])
        self.assertEqual(self.store.events()[-1]["detail_code"], "gate_transcript_unavailable")

    def test_compound_high_risk_bash_is_denied_before_permission(self) -> None:
        root = self.make_git_project()
        data = self.materialize_fixture(
            "destructive_bash.json",
            PROJECT_ROOT=str(root),
            TRANSCRIPT_PATH=str(FIXTURES / "gate_complete.jsonl"),
        )
        data["tool_input"]["command"] = (
            "rm -rf /tmp/acgm-fixture-target && printf deletion-complete"
        )

        result = capture_json(acgm.hook_pretool_bash, data, self.store)

        output = result["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("standalone", output["permissionDecisionReason"])
        self.assertEqual(self.store.events()[-1]["detail_code"], "compound_high_risk_command")
        session_id = self.store.session_id(str(data["session_id"]))
        self.assertEqual(self.store.load_obligations(session_id), [])

    def test_gate_transitions_from_deny_to_human_ask(self) -> None:
        root = self.make_git_project()
        incomplete = FIXTURES / "gate_incomplete.jsonl"
        data = self.materialize_fixture(
            "destructive_bash.json",
            PROJECT_ROOT=str(root),
            TRANSCRIPT_PATH=str(incomplete),
        )
        denied = capture_json(acgm.hook_pretool_bash, data, self.store)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

        data["transcript_path"] = str(FIXTURES / "gate_complete.jsonl")
        asked = capture_json(acgm.hook_pretool_bash, data, self.store)
        self.assertEqual(asked["hookSpecificOutput"]["permissionDecision"], "ask")
        session_id = self.store.session_id(str(data["session_id"]))
        obligations = self.store.load_obligations(session_id)
        self.assertEqual(len(obligations), 1)
        self.assertEqual(obligations[0]["status"], "awaiting_execution")

    def test_source_check_from_wrong_category_cannot_open_gate(self) -> None:
        root = self.make_git_project()
        data = self.materialize_fixture(
            "destructive_bash.json",
            PROJECT_ROOT=str(root),
            TRANSCRIPT_PATH=str(FIXTURES / "gate_wrong_category.jsonl"),
        )
        result = capture_json(acgm.hook_pretool_bash, data, self.store)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.store.events()[-1]["detail_code"], "gate_missing_source_check")

    def test_unbound_gate_fields_have_precise_denial_code(self) -> None:
        root = self.make_git_project()
        data = self.materialize_fixture(
            "destructive_bash.json",
            PROJECT_ROOT=str(root),
            TRANSCRIPT_PATH=str(FIXTURES / "gate_unbound_fields.jsonl"),
        )

        result = capture_json(acgm.hook_pretool_bash, data, self.store)

        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.store.events()[-1]["detail_code"], "gate_unbound_fields")

    def test_source_check_must_bind_command_or_output_to_target(self) -> None:
        root = self.make_git_project()
        data = self.materialize_fixture(
            "destructive_bash.json",
            PROJECT_ROOT=str(root),
            TRANSCRIPT_PATH=str(FIXTURES / "gate_wrong_source_target.jsonl"),
        )

        result = capture_json(acgm.hook_pretool_bash, data, self.store)

        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.store.events()[-1]["detail_code"], "gate_missing_source_check")

    def open_verification_obligation(self) -> tuple[Path, dict[str, object], str]:
        root = self.make_git_project()
        data = self.materialize_fixture(
            "destructive_bash.json",
            PROJECT_ROOT=str(root),
            TRANSCRIPT_PATH=str(FIXTURES / "gate_complete.jsonl"),
        )
        asked = capture_json(acgm.hook_pretool_bash, data, self.store)
        self.assertEqual(asked["hookSpecificOutput"]["permissionDecision"], "ask")
        post = dict(data)
        post["tool_name"] = "Bash"
        context = capture_json(acgm.hook_posttool, post, self.store)
        self.assertIn("still open", context["hookSpecificOutput"]["additionalContext"])
        return root, data, self.store.session_id(str(data["session_id"]))

    def test_verification_obligation_blocks_stop_then_caps(self) -> None:
        root, data, session_id = self.open_verification_obligation()
        stop = {"cwd": str(root), "session_id": data["session_id"], "stop_hook_active": True}
        first = capture_json(acgm.hook_stop, stop, self.store)
        second = capture_json(acgm.hook_stop, stop, self.store)
        third = capture_json(acgm.hook_stop, stop, self.store)
        self.assertEqual(first["decision"], "block")
        self.assertEqual(second["decision"], "block")
        self.assertEqual(third, {})
        self.assertEqual(self.store.load_obligations(session_id)[0]["status"], "unresolved")

    def test_verification_command_resolves_obligation(self) -> None:
        root, data, session_id = self.open_verification_obligation()
        transcript = acgm.transcript_objects(str(FIXTURES / "gate_complete.jsonl"))
        declared_verification = acgm.gate_field(
            acgm.assistant_text(transcript),
            "ACGM-VERIFY-AFTER:",
        )
        self.assertTrue(acgm.is_single_shell_command(declared_verification))
        verification = {
            "cwd": str(root),
            "session_id": data["session_id"],
            "tool_name": "Bash",
            "tool_use_id": "tool-verify-1",
            "tool_input": {"command": declared_verification},
        }
        result = capture_json(acgm.hook_posttool, verification, self.store)
        self.assertIn("resolved", result["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.store.load_obligations(session_id)[0]["status"], "verified")
        self.assertEqual(
            capture_json(
                acgm.hook_stop,
                {"cwd": str(root), "session_id": data["session_id"]},
                self.store,
            ),
            {},
        )

    def test_unrelated_same_category_check_cannot_close_declared_obligation(self) -> None:
        root, data, session_id = self.open_verification_obligation()
        unrelated = {
            "cwd": str(root),
            "session_id": data["session_id"],
            "tool_name": "Bash",
            "tool_use_id": "tool-unrelated-check",
            "tool_input": {"command": "test ! -e /tmp/a-different-target"},
        }
        result = capture_json(acgm.hook_posttool, unrelated, self.store)
        self.assertIn("does not exactly match", result["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(
            self.store.load_obligations(session_id)[0]["status"],
            "awaiting_verification",
        )

    def test_stop_accounts_for_all_pending_obligations(self) -> None:
        root, data, session_id = self.open_verification_obligation()
        with self.store.obligations_lock(session_id):
            obligations = self.store.load_obligations(session_id)
            duplicate = dict(obligations[0])
            duplicate["obligation_id"] = "obl_second"
            duplicate["event_id"] = self.store.append_event(
                project_id=duplicate["project_id"],
                session_id=session_id,
                event_type="verification_obligation",
                initiator="acgm_hook",
                phase="pre_action",
                rule_id="truth_first.post_action_verification",
                action="opened",
                status="pending_human_approval",
                outcome="evidence_present",
                confidence="medium",
                detail_code="file_delete",
            )
            duplicate["tool_id"] = "tool_second"
            obligations.append(duplicate)
            self.store.save_obligations(session_id, obligations)

        stop = {"cwd": str(root), "session_id": data["session_id"], "stop_hook_active": True}
        self.assertEqual(capture_json(acgm.hook_stop, stop, self.store)["decision"], "block")
        self.assertEqual(capture_json(acgm.hook_stop, stop, self.store)["decision"], "block")
        self.assertEqual(capture_json(acgm.hook_stop, stop, self.store), {})
        self.assertEqual(
            [item["status"] for item in self.store.load_obligations(session_id)],
            ["unresolved", "unresolved"],
        )

    def test_failed_destructive_call_keeps_verification_obligation_open(self) -> None:
        root = self.make_git_project()
        data = self.materialize_fixture(
            "destructive_bash.json",
            PROJECT_ROOT=str(root),
            TRANSCRIPT_PATH=str(FIXTURES / "gate_complete.jsonl"),
        )
        capture_json(acgm.hook_pretool_bash, data, self.store)
        result = capture_json(acgm.hook_posttool_failure, data, self.store)
        self.assertIn("remains mandatory", result["hookSpecificOutput"]["additionalContext"])
        session_id = self.store.session_id(str(data["session_id"]))
        self.assertEqual(
            self.store.load_obligations(session_id)[0]["status"],
            "awaiting_verification",
        )
        event = self.store.events()[-1]
        self.assertEqual(event["status"], "pending_verification")
        self.assertEqual(event["outcome"], "execution_failed_state_unknown")

    def test_persistent_obligation_state_does_not_store_raw_target_or_command(self) -> None:
        _, _, session_id = self.open_verification_obligation()
        persisted = self.store.obligations_path(session_id).read_text(encoding="utf-8")

        self.assertNotIn("/tmp/acgm-fixture-target", persisted)
        self.assertNotIn("rm -rf", persisted)
        self.assertNotIn("test ! -e", persisted)
        self.assertIn("vfy_", persisted)


class WriteAndLedgerTests(RuntimeTestCase):
    def test_constitution_write_is_denied_before_action(self) -> None:
        root = self.make_governed_project()
        for file_path in (str(root / "CONSTITUTION.md"), "CONSTITUTION.md"):
            with self.subTest(file_path=file_path):
                data = {
                    "cwd": str(root),
                    "session_id": f"constitution-session-{file_path}",
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": file_path,
                        "content": "Agent-authored amendment",
                    },
                }
                result = capture_json(acgm.hook_pretool_write, data, self.store)
                self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_posttool_advises_without_mutating_governance_file(self) -> None:
        root = self.make_governed_project()
        governed_file = root / "CLAUDE.md"
        before = governed_file.read_bytes()
        data = self.materialize_fixture(
            "posttool_governance_write.json",
            PROJECT_ROOT=str(root),
            GOVERNANCE_FILE=str(governed_file),
        )
        result = capture_json(acgm.hook_posttool, data, self.store)
        self.assertIn("did not modify", result["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(governed_file.read_bytes(), before)
        self.assertEqual(self.store.events()[-1]["detail_code"], "unsourced_governance_claim")

    def test_ledger_never_contains_raw_hook_material(self) -> None:
        root = self.make_git_project()
        data = {
            "cwd": str(root),
            "session_id": "raw-secret-session",
            "tool_name": "Bash",
            "tool_use_id": "tool-secret",
            "tool_input": {
                "command": "rm -rf /Users/example/private/sk-SECRET https://gateway.invalid ProviderSecretName"
            },
            "transcript_path": str(self.base / "missing transcript.jsonl"),
        }
        capture_json(acgm.hook_pretool_bash, data, self.store)
        ledger = (self.data_dir / "events.jsonl").read_text(encoding="utf-8")
        for forbidden in (
            "/Users/example",
            "sk-SECRET",
            "https://gateway.invalid",
            "ProviderSecretName",
            str(root),
            "rm -rf",
        ):
            self.assertNotIn(forbidden, ledger)
        mode = stat.S_IMODE((self.data_dir / "events.jsonl").stat().st_mode)
        if os.name != "nt":
            self.assertEqual(mode, 0o600)

    def test_ledger_rejects_path_like_enum_values(self) -> None:
        with self.assertRaises(ValueError):
            self.store.append_event(
                project_id="prj_0123456789abcdef",
                session_id="ses_0123456789abcdef",
                event_type="health/path",
                initiator="acgm_hook",
                phase="session_start",
                rule_id="runtime.health",
                action="checked",
                status="healthy",
                outcome="visible",
                confidence="high",
                detail_code="governed",
            )

    def test_crashed_python_runtime_makes_wrapper_fail_closed_for_bash(self) -> None:
        wrapper_dir = self.base / "broken wrapper"
        wrapper_dir.mkdir()
        wrapper = wrapper_dir / "acgm-hook.sh"
        shutil.copy2(REPO_ROOT / "scripts" / "acgm-hook.sh", wrapper)
        runtime = wrapper_dir / "acgm_runtime.py"
        runtime.write_text("raise SystemExit(7)\n", encoding="utf-8")
        result = subprocess.run(
            ["sh", str(wrapper), "pretool-bash"],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}}),
            encoding="utf-8",
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output = json.loads(result.stdout)
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("runtime", output["hookSpecificOutput"]["permissionDecisionReason"])

    def test_corrupt_obligation_store_makes_stop_fail_closed(self) -> None:
        root = self.make_git_project()
        raw_session_id = "corrupt-obligation-session"
        session_id = self.store.session_id(raw_session_id)
        path = self.store.obligations_path(session_id)
        path.parent.mkdir(parents=True)
        path.write_text("{broken", encoding="utf-8")
        hook_input = json.dumps({"cwd": str(root), "session_id": raw_session_id})

        with mock.patch("sys.stdin", io.StringIO(hook_input)):
            payload = capture_json(acgm.main, ["hook-stop"])

        self.assertEqual(payload["decision"], "block")
        self.assertIn("cannot read or persist", payload["reason"])


class DoctorReportAndExportTests(RuntimeTestCase):
    def configure_healthy_claude_home(self) -> None:
        plugins = self.config_dir / "plugins"
        plugins.mkdir(parents=True)
        (plugins / "installed_plugins.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        acgm.PLUGIN_ID: [
                            {
                                "scope": "user",
                                "installPath": str(REPO_ROOT),
                                "version": acgm.ACGM_VERSION,
                                "gitCommitSha": "fixture-commit",
                            }
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.config_dir / "settings.json").write_text(
            json.dumps(
                {
                    "cleanupPeriodDays": 90,
                    "enabledPlugins": {acgm.PLUGIN_ID: True},
                }
            ),
            encoding="utf-8",
        )
        transcripts = self.config_dir / "projects" / "fixture"
        transcripts.mkdir(parents=True)
        (transcripts / "recent.jsonl").write_text("{}\n", encoding="utf-8")

    def append_session_start_health(self, root: Path, *, version: str) -> None:
        with mock.patch.object(acgm, "ACGM_VERSION", version):
            self.store.append_event(
                project_id=self.store.project_id(root),
                session_id="ses_0123456789abcdef",
                event_type="health",
                initiator="acgm_hook",
                phase="session_start",
                rule_id="runtime.health",
                action="checked",
                status="healthy",
                outcome="visible",
                confidence="high",
                detail_code="governed",
            )

    def test_doctor_reports_healthy_governed_project(self) -> None:
        root = self.make_governed_project()
        self.configure_healthy_claude_home()
        with mock.patch.object(
            acgm, "running_from_source_checkout", return_value=True
        ):
            report = acgm.doctor_report(str(root), update=False)
        self.assertEqual(report["project_state"], "GOVERNED")
        self.assertTrue(report["installation"]["registered"])
        self.assertEqual(report["installation"]["installed_version"], acgm.ACGM_VERSION)
        self.assertTrue(report["runtime"]["healthy"])
        self.assertEqual(report["continuity"]["status"], "READY")
        self.assertEqual(
            report["activation"]["status"],
            "SOURCE_CHECKOUT_NOT_RUNTIME_PROOF",
        )
        self.assertFalse(
            report["activation"]["current_version_session_start_observed"]
        )

    def test_doctor_observes_only_current_version_session_start_evidence(self) -> None:
        root = self.make_governed_project()
        self.configure_healthy_claude_home()
        self.append_session_start_health(root, version=acgm.ACGM_VERSION)

        with mock.patch.object(
            acgm, "running_from_source_checkout", return_value=False
        ):
            report = acgm.doctor_report(str(root), update=False)

        activation = report["activation"]
        self.assertEqual(
            activation["status"],
            "HISTORICAL_CURRENT_VERSION_SESSION_START_OBSERVED",
        )
        self.assertTrue(activation["current_version_session_start_observed"])
        self.assertTrue(activation["current_project_session_start_observed"])
        self.assertTrue(activation["historical_observation_only"])
        self.assertFalse(activation["sufficient_for_active_verified"])
        self.assertIsNotNone(activation["latest_observed_at"])
        self.assertEqual(
            activation["evidence_scope"],
            "historical_session_start_health_event_only",
        )

    def test_doctor_does_not_promote_retained_event_when_plugin_is_disabled(self) -> None:
        root = self.make_governed_project()
        self.configure_healthy_claude_home()
        settings_path = self.config_dir / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["enabledPlugins"][acgm.PLUGIN_ID] = False
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        self.append_session_start_health(root, version=acgm.ACGM_VERSION)

        with mock.patch.object(
            acgm, "running_from_source_checkout", return_value=False
        ):
            report = acgm.doctor_report(str(root), update=False)

        self.assertFalse(report["installation"]["explicitly_enabled_for_project"])
        self.assertFalse(report["installation"]["registration_consistent"])
        self.assertIn(
            "plugin_not_explicitly_enabled_for_project",
            report["installation"]["error_codes"],
        )
        self.assertEqual(
            report["activation"]["status"], "CURRENT_INSTALLATION_NOT_CONFIRMED"
        )
        self.assertFalse(
            report["activation"]["current_version_session_start_observed"]
        )

    def test_doctor_does_not_choose_last_duplicate_install_record(self) -> None:
        root = self.make_governed_project()
        self.configure_healthy_claude_home()
        registry_path = self.config_dir / "plugins" / "installed_plugins.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        records = registry["plugins"][acgm.PLUGIN_ID]
        records.append(dict(records[0]))
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        self.append_session_start_health(root, version=acgm.ACGM_VERSION)

        with mock.patch.object(
            acgm, "running_from_source_checkout", return_value=False
        ):
            report = acgm.doctor_report(str(root), update=False)

        self.assertEqual(report["installation"]["record_count"], 2)
        self.assertFalse(report["installation"]["registration_consistent"])
        self.assertIn(
            "multiple_installed_plugin_records",
            report["installation"]["error_codes"],
        )
        self.assertEqual(
            report["activation"]["status"], "CURRENT_INSTALLATION_NOT_CONFIRMED"
        )

    def test_doctor_does_not_promote_inconsistent_install_path(self) -> None:
        root = self.make_governed_project()
        self.configure_healthy_claude_home()
        registry_path = self.config_dir / "plugins" / "installed_plugins.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["plugins"][acgm.PLUGIN_ID][0]["installPath"] = str(
            self.base / "different install"
        )
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        self.append_session_start_health(root, version=acgm.ACGM_VERSION)

        with mock.patch.object(
            acgm, "running_from_source_checkout", return_value=False
        ):
            report = acgm.doctor_report(str(root), update=False)

        self.assertFalse(report["installation"]["registration_consistent"])
        self.assertIn(
            "installed_plugin_path_differs_from_running_source",
            report["installation"]["error_codes"],
        )
        self.assertEqual(
            report["activation"]["status"], "CURRENT_INSTALLATION_NOT_CONFIRMED"
        )

    def test_doctor_does_not_promote_old_registered_version(self) -> None:
        root = self.make_governed_project()
        self.configure_healthy_claude_home()
        registry_path = self.config_dir / "plugins" / "installed_plugins.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["plugins"][acgm.PLUGIN_ID][0]["version"] = "0.2.0"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        self.append_session_start_health(root, version=acgm.ACGM_VERSION)

        with mock.patch.object(
            acgm, "running_from_source_checkout", return_value=False
        ):
            report = acgm.doctor_report(str(root), update=False)

        self.assertFalse(report["installation"]["registration_consistent"])
        self.assertIn(
            "installed_version_differs_from_running_source",
            report["installation"]["error_codes"],
        )
        self.assertEqual(
            report["activation"]["status"], "CURRENT_INSTALLATION_NOT_CONFIRMED"
        )

    def test_doctor_does_not_count_old_version_session_start_evidence(self) -> None:
        root = self.make_governed_project()
        self.configure_healthy_claude_home()
        self.append_session_start_health(root, version="0.2.0")

        with mock.patch.object(
            acgm, "running_from_source_checkout", return_value=False
        ):
            report = acgm.doctor_report(str(root), update=False)

        activation = report["activation"]
        self.assertEqual(
            activation["status"], "CURRENT_VERSION_SESSION_START_NOT_OBSERVED"
        )
        self.assertFalse(activation["current_version_session_start_observed"])
        self.assertFalse(activation["current_project_session_start_observed"])
        self.assertIsNone(activation["latest_observed_at"])

    def test_source_checkout_does_not_claim_activation_from_shared_ledger(self) -> None:
        root = self.make_governed_project()
        self.configure_healthy_claude_home()
        self.append_session_start_health(root, version=acgm.ACGM_VERSION)

        with mock.patch.object(
            acgm, "running_from_source_checkout", return_value=True
        ):
            report = acgm.doctor_report(str(root), update=False)

        activation = report["activation"]
        self.assertTrue(report["installation"]["source_mode"])
        self.assertEqual(
            activation["status"], "SOURCE_CHECKOUT_NOT_RUNTIME_PROOF"
        )
        self.assertFalse(activation["current_version_session_start_observed"])

    def test_doctor_marks_corrupt_event_ledger_broken(self) -> None:
        root = self.make_governed_project()
        self.store.ensure()
        (self.data_dir / "events.jsonl").write_text("not-json\n", encoding="utf-8")

        report = acgm.doctor_report(str(root), update=False)

        self.assertEqual(report["project_state"], "BROKEN")
        self.assertIn("local_state_corrupt_or_unwritable", report["runtime"]["error_codes"])
        self.assertEqual(report["activation"]["status"], "EVIDENCE_UNAVAILABLE")
        self.assertFalse(
            report["activation"]["current_version_session_start_observed"]
        )

    def test_report_and_export_are_sanitized(self) -> None:
        event_id = self.store.append_event(
            project_id="prj_0123456789abcdef",
            session_id="ses_0123456789abcdef",
            event_type="drift_intervention",
            initiator="acgm_hook",
            phase="pre_action",
            rule_id="truth_first.high_risk_gate",
            action="blocked",
            status="unresolved",
            outcome="prevented_pending_evidence",
            confidence="high",
            detail_code="gate_missing_fields",
        )
        args = argparse.Namespace(project="all", limit=20, json=True)
        payload = capture_json(acgm.command_report, args)
        self.assertEqual(payload["summary"]["potential_drift_events"], 1)
        self.assertEqual(payload["summary"]["operations_blocked_before_action"], 1)

        output = self.base / "exports" / "case.md"
        export_args = argparse.Namespace(event_id=event_id, output=str(output))
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = acgm.command_export_case(export_args)
        self.assertEqual(status, 0)
        exported = output.read_text(encoding="utf-8")
        self.assertIn("Project-A", exported)
        self.assertIn("Nothing was uploaded", exported)
        self.assertNotIn("prj_0123456789abcdef", exported)
        self.assertNotIn(str(self.base), exported)

    def test_related_lifecycle_records_count_once(self) -> None:
        root_event = self.store.append_event(
            project_id="prj_0123456789abcdef",
            session_id="ses_0123456789abcdef",
            event_type="verification_obligation",
            initiator="acgm_hook",
            phase="pre_action",
            rule_id="truth_first.post_action_verification",
            action="opened",
            status="pending_human_approval",
            outcome="evidence_present",
            confidence="medium",
            detail_code="file_delete",
        )
        self.store.append_event(
            project_id="prj_0123456789abcdef",
            session_id="ses_0123456789abcdef",
            event_type="verification_obligation",
            initiator="acgm_hook",
            phase="post_action",
            rule_id="truth_first.post_action_verification",
            action="executed",
            status="unresolved",
            outcome="verification_pending",
            confidence="high",
            detail_code="file_delete",
            related_event_id=root_event,
        )
        self.store.append_event(
            project_id="prj_0123456789abcdef",
            session_id="ses_0123456789abcdef",
            event_type="verification_obligation",
            initiator="acgm_hook",
            phase="post_action",
            rule_id="truth_first.post_action_verification",
            action="verified",
            status="verified",
            outcome="declared_check_succeeded",
            confidence="medium",
            detail_code="file_delete",
            related_event_id=root_event,
        )
        payload = capture_json(
            acgm.command_report,
            argparse.Namespace(project="all", limit=20, json=True),
        )
        self.assertEqual(payload["summary"]["verified_obligations"], 1)
        self.assertEqual(payload["summary"]["unresolved"], 0)


if __name__ == "__main__":
    unittest.main()
