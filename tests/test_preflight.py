from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("acgm_preflight", SCRIPTS / "preflight.py")
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def command_versions(self, argv):
        if argv[0] == "git":
            return True, (2, 50, 1)
        if Path(argv[0]).name.casefold() in {"claude", "claude.exe"}:
            return True, (2, 1, 200)
        raise AssertionError(argv)

    def test_windows_git_bash_profile_requires_both_explicit_controls(self) -> None:
        with (
            mock.patch.object(preflight.platform, "system", return_value="Windows"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "py-3", (3, 10, 14))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(Path("C:/Users/test/.local/bin/claude.exe"), None),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
            mock.patch.object(preflight, "command_succeeds", return_value=True),
            mock.patch.object(
                preflight.runtime, "windows_git_bash_status", return_value=(True, "configured_path")
            ),
            mock.patch.object(
                preflight.runtime,
                "effective_claude_env",
                return_value="0",
            ),
        ):
            report = preflight.build_report()

        self.assertEqual(report["status"], "READY_FOR_AUTOMATED_INSTALL")
        self.assertEqual(report["platform"]["profile"], "windows_git_bash_candidate")
        self.assertTrue(report["checks"]["git_bash"]["ok"])
        self.assertTrue(report["checks"]["powershell_tool_disabled"]["ok"])
        self.assertIn("powershell_native_unsupported", report["warning_codes"])

    def test_windows_native_powershell_profile_is_blocked(self) -> None:
        with (
            mock.patch.object(preflight.platform, "system", return_value="Windows"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(Path("C:/Users/test/.local/bin/claude.exe"), None),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
            mock.patch.object(preflight, "command_succeeds", return_value=True),
            mock.patch.object(
                preflight.runtime, "windows_git_bash_status", return_value=(False, "configured_path_invalid")
            ),
            mock.patch.object(preflight.runtime, "effective_claude_env", return_value="1"),
        ):
            report = preflight.build_report()

        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("windows_git_bash_missing_or_invalid", report["error_codes"])
        self.assertIn("windows_powershell_tool_must_be_disabled", report["error_codes"])

    def test_windows_batch_launcher_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory) / "claude.cmd"
            launcher.write_text("@echo off\n", encoding="utf-8")
            with (
                mock.patch.object(preflight.platform, "system", return_value="Windows"),
                mock.patch.object(preflight.shutil, "which", return_value=str(launcher)),
            ):
                resolved, error = preflight.resolve_claude_executable()
        self.assertIsNone(resolved)
        self.assertEqual(error, "windows_claude_batch_launcher_unsupported")

    def test_windows_non_pe_launcher_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory) / "claude.exe"
            launcher.write_bytes(b"not-a-native-binary")
            with (
                mock.patch.object(preflight.platform, "system", return_value="Windows"),
                mock.patch.object(preflight.shutil, "which", return_value=str(launcher)),
            ):
                resolved, error = preflight.resolve_claude_executable()
        self.assertIsNone(resolved)
        self.assertEqual(error, "windows_claude_launcher_not_native")

    def test_windows_pe_launcher_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory) / "claude.exe"
            launcher.write_bytes(b"MZfixture")
            with (
                mock.patch.object(preflight.platform, "system", return_value="Windows"),
                mock.patch.object(preflight.shutil, "which", return_value=str(launcher)),
            ):
                resolved, error = preflight.resolve_claude_executable()
        self.assertEqual(resolved, launcher.resolve())
        self.assertIsNone(error)

    def test_claude_capability_probe_uses_private_neutral_cwd(self) -> None:
        observed: dict[str, object] = {}

        def fake_run(argv, **kwargs):
            observed["argv"] = argv
            observed["cwd"] = kwargs.get("cwd")
            cwd = Path(str(kwargs.get("cwd")))
            self.assertNotEqual(cwd, REPO_ROOT)
            self.assertFalse((cwd / ".claude" / "settings.json").exists())
            if os.name != "nt":
                self.assertEqual(cwd.stat().st_mode & 0o077, 0)
            return subprocess.CompletedProcess(argv, 0)

        with mock.patch.object(preflight.subprocess, "run", side_effect=fake_run):
            self.assertTrue(preflight.command_succeeds(["/opt/claude", "plugin", "list", "--help"]))

        self.assertIsNotNone(observed["cwd"])
        self.assertFalse(Path(str(observed["cwd"])).exists())
        self.assertFalse(preflight.neutral_cwd_is_safe(REPO_ROOT / "tests"))

    def test_cli_version_without_plugin_management_is_blocked(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(Path("/opt/claude"), None),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
            mock.patch.object(preflight, "command_succeeds", return_value=False),
        ):
            report = preflight.build_report()

        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["surface"]["install_route"], "claude_plugin_cli")
        self.assertIn("claude_plugin_cli_missing_or_unusable", report["error_codes"])

    def test_cli_below_documented_plugin_trust_contract_is_blocked(self) -> None:
        def old_claude_version(argv):
            if argv[0] == "git":
                return True, (2, 50, 1)
            if Path(argv[0]).name.casefold() in {"claude", "claude.exe"}:
                return True, (2, 1, 194)
            raise AssertionError(argv)

        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(Path("/opt/claude"), None),
            ),
            mock.patch.object(preflight, "command_version", side_effect=old_claude_version),
            mock.patch.object(preflight, "command_succeeds", return_value=True),
        ):
            report = preflight.build_report("claude-code-cli")

        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["checks"]["plugin_trust_contract"]["ok"])
        self.assertEqual(
            report["checks"]["plugin_trust_contract"]["minimum_claude_code_version"],
            "2.1.195",
        )
        self.assertIn(
            "claude_code_plugin_trust_contract_too_old_or_unverified",
            report["error_codes"],
        )
        self.assertEqual(
            report["actions"][0]["id"],
            "update_claude_code_for_plugin_trust_contract",
        )

    def test_auto_without_cli_requires_explicit_surface(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(None, "claude_code_missing_or_unusable"),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
        ):
            report = preflight.build_report()

        self.assertEqual(report["status"], "TARGET_SURFACE_REQUIRED")
        self.assertEqual(report["surface"]["resolved"], "unknown")
        self.assertEqual(report["identity_inference"], "not_performed")

    def test_desktop_code_local_without_cli_gets_manual_plan(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(None, "claude_code_missing_or_unusable"),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
        ):
            report = preflight.build_report("desktop-code-local")

        self.assertEqual(report["status"], "MANUAL_INSTALL_PLAN_AVAILABLE")
        self.assertEqual(report["surface"]["install_route"], "desktop_plugin_manager")
        self.assertTrue(report["surface"]["hooks_expected"])
        self.assertTrue(any(action["kind"] == "ui" for action in report["actions"]))
        self.assertTrue(
            any(
                action["id"] == "verify_plugin_trust_contract_version"
                for action in report["actions"]
            )
        )

    def test_explicit_desktop_stays_on_ui_route_when_cli_is_present(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(Path("/opt/claude"), None),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
            mock.patch.object(preflight, "command_succeeds", return_value=True),
        ):
            report = preflight.build_report("desktop-code-local")

        self.assertEqual(report["status"], "MANUAL_INSTALL_PLAN_AVAILABLE")
        self.assertEqual(report["surface"]["install_route"], "desktop_plugin_manager")
        self.assertFalse(
            any(
                action.get("id") == "install_verified_configuration"
                for action in report["actions"]
            )
        )

    def test_claude_code_subprocess_without_cli_routes_to_manual_code_plan(self) -> None:
        with (
            mock.patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(None, "claude_code_missing_or_unusable"),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
        ):
            report = preflight.build_report()

        self.assertEqual(report["status"], "MANUAL_INSTALL_PLAN_AVAILABLE")
        self.assertEqual(
            report["surface"]["resolved"], "desktop-code-local-or-ssh"
        )
        self.assertEqual(
            report["surface"]["confidence"], "claude_code_subprocess_capability"
        )

    def test_claude_subprocess_with_cli_requires_exact_surface(self) -> None:
        with (
            mock.patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(Path("/opt/claude"), None),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
            mock.patch.object(preflight, "command_succeeds", return_value=True),
        ):
            report = preflight.build_report()

        self.assertEqual(report["status"], "TARGET_SURFACE_REQUIRED")
        self.assertEqual(
            report["surface"]["resolved"], "claude-code-cli-or-desktop"
        )
        self.assertEqual(report["surface"]["install_route"], "none")
        self.assertIn(
            "target_surface_required_inside_claude_code", report["error_codes"]
        )

    def test_official_cloud_signal_overrides_local_cli_candidate(self) -> None:
        with (
            mock.patch.dict(os.environ, {"CLAUDE_CODE_REMOTE": "true"}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(Path("/opt/claude"), None),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
            mock.patch.object(preflight, "command_succeeds", return_value=True),
        ):
            report = preflight.build_report()

        self.assertEqual(report["status"], "UNSUPPORTED_SURFACE")
        self.assertEqual(report["surface"]["resolved"], "desktop-code-cloud")

    def test_explicit_cli_cannot_override_official_cloud_signal(self) -> None:
        with (
            mock.patch.dict(os.environ, {"CLAUDE_CODE_REMOTE": "true"}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(Path("/opt/claude"), None),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
            mock.patch.object(preflight, "command_succeeds", return_value=True),
        ):
            report = preflight.build_report("claude-code-cli")

        self.assertEqual(report["status"], "SURFACE_SIGNAL_CONFLICT")
        self.assertEqual(report["surface"]["resolved"], "desktop-code-cloud")
        self.assertEqual(report["surface"]["install_route"], "none")
        self.assertEqual(report["actions"][0]["id"], "use_observed_runtime_surface")
        self.assertIn(
            "requested_surface_conflicts_with_observed_runtime",
            report["error_codes"],
        )

    def test_explicit_local_cannot_override_wsl_runtime_signal(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Linux"),
            mock.patch.object(preflight, "is_wsl", return_value=True),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(Path("/opt/claude"), None),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
            mock.patch.object(preflight, "command_succeeds", return_value=True),
        ):
            report = preflight.build_report("desktop-code-local")

        self.assertEqual(report["status"], "SURFACE_SIGNAL_CONFLICT")
        self.assertEqual(report["surface"]["resolved"], "desktop-code-wsl")
        self.assertEqual(report["surface"]["install_route"], "none")
        self.assertEqual(report["actions"][0]["id"], "use_observed_runtime_surface")
        self.assertIn(
            "requested_surface_conflicts_with_observed_runtime",
            report["error_codes"],
        )

    def test_chat_cowork_cloud_and_wsl_are_not_full_ready(self) -> None:
        common = (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(None, "claude_code_missing_or_unusable"),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
        )
        with contextlib.ExitStack() as stack:
            for manager in common:
                stack.enter_context(manager)
            chat = preflight.build_report("desktop-chat")
            cowork = preflight.build_report("cowork")
            cloud = preflight.build_report("desktop-code-cloud")
            wsl = preflight.build_report("desktop-code-wsl")

        self.assertEqual(chat["status"], "ADVISORY_ONLY")
        self.assertFalse(chat["surface"]["hooks_expected"])
        self.assertEqual(cowork["status"], "EXPERIMENTAL_SURFACE_UNVERIFIED")
        self.assertEqual(cloud["status"], "UNSUPPORTED_SURFACE")
        self.assertEqual(wsl["status"], "UNSUPPORTED_SURFACE")

    def test_host_managed_provider_is_boolean_signal_not_identity(self) -> None:
        secret_value = "compatible-endpoint-secret-model-label"
        with (
            mock.patch.dict(
                os.environ,
                {"CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST": secret_value},
                clear=True,
            ),
            mock.patch.object(preflight.platform, "system", return_value="Darwin"),
            mock.patch.object(preflight, "is_wsl", return_value=False),
            mock.patch.object(preflight, "python_launcher", return_value=(True, "python3", (3, 12, 4))),
            mock.patch.object(
                preflight,
                "resolve_claude_executable",
                return_value=(None, "claude_code_missing_or_unusable"),
            ),
            mock.patch.object(preflight, "command_version", side_effect=self.command_versions),
        ):
            report = preflight.build_report("desktop-code-local")

        serialized = json.dumps(report)
        self.assertNotIn(secret_value, serialized)
        self.assertTrue(report["observable_signals"]["provider_managed_by_host"])
        self.assertIn(
            "provider_route_managed_by_host_identity_not_inferred",
            report["warning_codes"],
        )

    def test_json_cli_emits_only_structured_report(self) -> None:
        fixture = {
            "schema_version": 2,
            "acgm_version": "fixture",
            "status": "READY_FOR_AUTOMATED_INSTALL",
            "read_only": True,
            "platform": {"system": "Darwin", "profile": "posix_supported"},
            "surface": {
                "resolved": "claude-code-cli",
                "install_route": "claude_plugin_cli",
            },
            "checks": {},
            "error_codes": [],
            "warning_codes": [],
        }
        output = io.StringIO()
        with mock.patch.object(preflight, "build_report", return_value=fixture), contextlib.redirect_stdout(output):
            status = preflight.main(["--json"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue()), fixture)


if __name__ == "__main__":
    unittest.main()
