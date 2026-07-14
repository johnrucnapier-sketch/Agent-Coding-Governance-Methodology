from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
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
            return True, (2, 1, 143)
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

        self.assertEqual(report["status"], "READY_FOR_RC_TEST")
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

    def test_json_cli_emits_only_structured_report(self) -> None:
        fixture = {
            "schema_version": 1,
            "acgm_version": "fixture",
            "status": "READY_FOR_RC_TEST",
            "read_only": True,
            "platform": {"system": "Darwin", "profile": "posix_supported"},
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
