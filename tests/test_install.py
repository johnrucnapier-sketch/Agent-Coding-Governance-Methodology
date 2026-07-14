from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("acgm_installer", SCRIPTS / "install.py")
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


REVISION = "a" * 40
FIXTURE_ROOT = Path(tempfile.gettempdir()).resolve() / "acgm-installer-fixture"
CLAUDE = FIXTURE_ROOT / ("claude.exe" if os.name == "nt" else "claude")
SNAPSHOT = FIXTURE_ROOT / "verified-snapshot"
OLD_SNAPSHOT = FIXTURE_ROOT / "0.3.0-rc.3-bbbbbbbbbbbb-cccccccccccc"


def ready_report() -> dict[str, object]:
    return {
        "schema_version": 2,
        "acgm_version": "0.3.0-rc.4",
        "status": "READY_FOR_AUTOMATED_INSTALL",
        "surface": {
            "requested": "auto",
            "resolved": "claude-code-cli",
            "install_route": "claude_plugin_cli",
        },
        "actions": [],
        "error_codes": [],
    }


def command_json(value) -> installer.CommandResult:
    return installer.CommandResult(0, stdout=json.dumps(value))


def fixture_source(
    version: str = "0.3.0-rc.4", revision: str = REVISION
) -> installer.VerifiedSource:
    plugin = {
        "name": installer.PLUGIN_NAME,
        "version": version,
    }
    marketplace = {
        "name": installer.MARKETPLACE_NAME,
        "plugins": [{"name": installer.PLUGIN_NAME, "source": "./"}],
    }
    files = {
        "VERSION": f"{version}\n".encode(),
        "bin/acgm": b"#!/bin/sh\nexit 0\n",
        "README.md": b"fixture\n",
        ".claude-plugin/plugin.json": json.dumps(plugin, sort_keys=True).encode(),
        ".claude-plugin/marketplace.json": json.dumps(
            marketplace, sort_keys=True
        ).encode(),
    }
    manifest = {
        "schema_version": 1,
        "version": version,
        "files": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(files.items())
        },
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    return installer.VerifiedSource(
        revision=revision,
        version=version,
        manifest_bytes=manifest_bytes,
        manifest_digest=hashlib.sha256(manifest_bytes).hexdigest(),
        files=files,
        modes={
            "VERSION": 0o100644,
            "bin/acgm": 0o100755,
            "README.md": 0o100644,
            ".claude-plugin/plugin.json": 0o100644,
            ".claude-plugin/marketplace.json": 0o100644,
        },
    )


class UpgradeCliFixture:
    def __init__(self, *, fail_new_install: bool = False, become_unknown: bool = False):
        self.state = "old_full"
        self.fail_new_install = fail_new_install
        self.become_unknown = become_unknown
        self.calls: list[list[str]] = []
        self.cwds: list[Path | None] = []

    @staticmethod
    def marketplace(path: Path) -> list[dict[str, object]]:
        return [
            {
                "name": installer.MARKETPLACE_NAME,
                "source": "directory",
                "path": str(path),
            }
        ]

    @staticmethod
    def plugin(version: str) -> list[dict[str, object]]:
        return [
            {
                "id": installer.PLUGIN_ID,
                "enabled": True,
                "scope": "user",
                "version": version,
                "errors": [],
                "installPath": "/private/cache/acgm",
            }
        ]

    def user_declaration(self, path: Path) -> tuple[str, None]:
        if self.state == "empty":
            return "absent", None
        if self.state in {"old_full", "old_marketplace_only"}:
            return ("exact" if path == OLD_SNAPSHOT else "conflict"), None
        if self.state in {"new_full", "new_marketplace_only"}:
            return ("exact" if path == SNAPSHOT else "conflict"), None
        return "conflict", None

    def run(self, argv, *, timeout, env=None, cwd=None) -> installer.CommandResult:
        del timeout, env
        command = list(argv)
        self.calls.append(command)
        self.cwds.append(cwd)
        if command[-1:] == ["--help"]:
            return installer.CommandResult(
                0, stdout="  --scope <scope>\n  --keep-data\n"
            )
        if command[1:4] == ["plugin", "marketplace", "list"]:
            if self.state in {"old_full", "old_marketplace_only"}:
                return command_json(self.marketplace(OLD_SNAPSHOT))
            if self.state in {"new_full", "new_marketplace_only"}:
                return command_json(self.marketplace(SNAPSHOT))
            if self.state == "empty":
                return command_json([])
            return command_json(self.marketplace(FIXTURE_ROOT / "unknown"))
        if command[1:3] == ["plugin", "list"]:
            if self.state == "old_full":
                return command_json(self.plugin("0.3.0-rc.3"))
            if self.state == "new_full":
                return command_json(self.plugin("0.3.0-rc.4"))
            if self.state == "unknown":
                return command_json(self.plugin("9.9.9"))
            return command_json([])
        if command[1:4] == ["plugin", "marketplace", "remove"]:
            self.state = "empty"
            return installer.CommandResult(0)
        if command[1:4] == ["plugin", "marketplace", "add"]:
            self.state = (
                "old_marketplace_only"
                if OLD_SNAPSHOT == Path(command[4])
                else "new_marketplace_only"
            )
            return installer.CommandResult(0)
        if command[1:3] == ["plugin", "uninstall"]:
            if self.state == "old_full":
                self.state = "old_marketplace_only"
            elif self.state == "new_full":
                self.state = "new_marketplace_only"
            return installer.CommandResult(0)
        if command[1:3] == ["plugin", "install"]:
            if self.state == "new_marketplace_only" and self.fail_new_install:
                self.fail_new_install = False
                self.state = "unknown" if self.become_unknown else self.state
                return installer.CommandResult(1)
            if self.state == "new_marketplace_only":
                self.state = "new_full"
            elif self.state == "old_marketplace_only":
                self.state = "old_full"
            return installer.CommandResult(0)
        raise AssertionError(f"unexpected command: {command}")


class InstallerFlowTests(unittest.TestCase):
    def local_marketplace(self):
        return [
            {
                "name": installer.MARKETPLACE_NAME,
                "source": "directory",
                "path": str(SNAPSHOT),
            }
        ]

    def installed_plugin(
        self,
        *,
        enabled=True,
        version="0.3.0-rc.4",
        scope="user",
        errors=None,
    ):
        return [
            {
                "id": installer.PLUGIN_ID,
                "enabled": enabled,
                "scope": scope,
                "version": version,
                "errors": [] if errors is None else errors,
                "installPath": "/private/cache/acgm",
            }
        ]

    def run_install(
        self,
        side_effect,
        *,
        dry_run=False,
        user_declared=False,
        snapshot_created=True,
        installed_verification=(True, []),
        reverification=(True, None),
    ):
        source = fixture_source()
        user_scope_answers = (
            [("exact", None)]
            if user_declared
            else [("absent", None), ("exact", None)]
        )
        with (
            mock.patch.object(
                installer.preflight, "build_report", return_value=ready_report()
            ),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(
                installer,
                "capture_verified_source",
                return_value=(source, []),
            ),
            mock.patch.object(
                installer.preflight,
                "resolve_claude_executable",
                return_value=(CLAUDE, None),
            ),
            mock.patch.object(installer, "snapshot_path", return_value=SNAPSHOT),
            mock.patch.object(
                installer,
                "create_or_verify_snapshot",
                return_value=(SNAPSHOT, snapshot_created, None),
            ) as snapshot_creator,
            mock.patch.object(
                installer,
                "user_marketplace_declaration",
                side_effect=user_scope_answers,
            ) as user_scope,
            mock.patch.object(
                installer,
                "reverify_source_and_snapshot",
                return_value=reverification,
            ) as reverify,
            mock.patch.object(
                installer,
                "verify_installed_plugin",
                return_value=installed_verification,
            ),
            mock.patch.object(installer, "run_command", side_effect=side_effect) as runner,
        ):
            exit_code, result = installer.install(dry_run=dry_run)
        return exit_code, result, runner, snapshot_creator, user_scope, reverify

    def run_upgrade(
        self,
        cli: UpgradeCliFixture,
        *,
        dry_run: bool = False,
        old_plugin_verification=(True, []),
        scoped_remove_available: bool = True,
        keep_data_uninstall_available: bool = True,
        plugin_in_use: bool = False,
        plugin_in_use_results=None,
        backup_present: bool = False,
        cleanup_result=(True, None),
    ):
        old_source = fixture_source("0.3.0-rc.3", "b" * 40)
        if backup_present:
            transaction_root = Path(
                tempfile.mkdtemp(prefix="acgm-upgrade-retained-test-")
            )
            self.addCleanup(shutil.rmtree, transaction_root, True)
            backup_path = transaction_root / "data"
            backup_path.mkdir(mode=0o700)
            if os.name != "nt":
                backup_path.chmod(0o700)
            data_backup = installer.PluginDataBackup(
                FIXTURE_ROOT / "plugin-data",
                True,
                installer.PrivateDataTree({}, {}, {".": 0o700}),
                backup_path,
            )
        else:
            data_backup = installer.PluginDataBackup(
                FIXTURE_ROOT / "plugin-data", False, None, None
            )

        def verify_plugin(record, source):
            if source.version == old_source.version and cli.state == "old_full":
                return old_plugin_verification
            if source.version == "0.3.0-rc.4" and cli.state == "new_full":
                return True, []
            if source.version == old_source.version and cli.state == "old_full":
                return True, []
            return False, ["fixture_plugin_state_mismatch"]

        original_run = cli.run

        def run_with_capability(argv, *, timeout, env=None, cwd=None):
            command = list(argv)
            scoped_remove_missing = (
                command[-1:] == ["--help"]
                and command[1:4] == ["plugin", "marketplace", "remove"]
                and not scoped_remove_available
            )
            keep_data_missing = (
                command[-1:] == ["--help"]
                and command[1:3] == ["plugin", "uninstall"]
                and not keep_data_uninstall_available
            )
            if scoped_remove_missing or keep_data_missing:
                cli.calls.append(list(argv))
                cli.cwds.append(cwd)
                return installer.CommandResult(
                    0,
                    stdout=(
                        "command help\n"
                        if scoped_remove_missing
                        else "command help --scope\n"
                    ),
                )
            return original_run(argv, timeout=timeout, env=env, cwd=cwd)

        in_use_patch = (
            mock.patch.object(
                installer,
                "installed_plugin_in_use",
                side_effect=list(plugin_in_use_results),
            )
            if plugin_in_use_results is not None
            else mock.patch.object(
                installer,
                "installed_plugin_in_use",
                return_value=(plugin_in_use, None),
            )
        )
        cleanup_patch = (
            mock.patch.object(
                installer,
                "cleanup_plugin_data_backup",
                side_effect=cleanup_result,
            )
            if callable(cleanup_result)
            else mock.patch.object(
                installer,
                "cleanup_plugin_data_backup",
                return_value=cleanup_result,
            )
        )

        with (
            mock.patch.object(
                installer.preflight, "build_report", return_value=ready_report()
            ),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(
                installer,
                "capture_verified_source",
                return_value=(fixture_source(), []),
            ),
            mock.patch.object(
                installer.preflight,
                "resolve_claude_executable",
                return_value=(CLAUDE, None),
            ),
            mock.patch.object(installer, "snapshot_path", return_value=SNAPSHOT),
            mock.patch.object(
                installer,
                "capture_verified_snapshot",
                return_value=(old_source, []),
            ),
            mock.patch.object(
                installer,
                "create_or_verify_snapshot",
                return_value=(SNAPSHOT, True, None),
            ) as snapshot_creator,
            mock.patch.object(
                installer,
                "user_marketplace_declaration",
                side_effect=cli.user_declaration,
            ),
            mock.patch.object(
                installer,
                "verify_installed_plugin",
                side_effect=verify_plugin,
            ),
            in_use_patch,
            mock.patch.object(
                installer,
                "reverify_source_and_snapshot",
                return_value=(True, None),
            ),
            mock.patch.object(
                installer,
                "verify_materialized_tree",
                return_value=(True, None),
            ),
            mock.patch.object(
                installer,
                "prepare_plugin_data_backup",
                return_value=(data_backup, None),
            ),
            mock.patch.object(
                installer,
                "plugin_data_transition_safe",
                return_value=(True, None),
            ),
            mock.patch.object(
                installer,
                "plugin_data_unchanged",
                return_value=(True, None),
            ),
            mock.patch.object(
                installer,
                "restore_plugin_data",
                return_value=(True, None),
            ),
            cleanup_patch,
            mock.patch.object(installer, "run_command", side_effect=run_with_capability),
        ):
            exit_code, result = installer.install(
                dry_run=dry_run,
                upgrade_verified_snapshot=True,
            )
        return exit_code, result, cli, snapshot_creator

    def run_legacy_detection(
        self,
        *,
        upgrade_verified_snapshot: bool = False,
        marketplace_source=None,
        declaration=None,
        marketplace_overrides=None,
        plugin_overrides=None,
        preflight_report=None,
    ):
        source_shape = (
            marketplace_source
            if marketplace_source is not None
            else {
                "source": "github",
                "repo": installer.PUBLIC_GITHUB_REPO,
                "ref": "v0.3.0-rc.1",
            }
        )
        user_shape = (
            declaration
            if declaration is not None
            else {"source": dict(source_shape)}
        )
        plugin = {
            "id": installer.PLUGIN_ID,
            "enabled": True,
            "scope": "user",
            "version": "0.3.0-rc.1",
            "errors": [],
            "installPath": "/private/cache/legacy-acgm",
        }
        plugin.update(plugin_overrides or {})
        marketplace = {
            "name": installer.MARKETPLACE_NAME,
            "source": source_shape,
        }
        marketplace.update(marketplace_overrides or {})
        prepared_report = preflight_report or ready_report()
        with (
            mock.patch.object(
                installer.preflight, "build_report", return_value=prepared_report
            ),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(
                installer,
                "capture_verified_source",
                return_value=(fixture_source(), []),
            ),
            mock.patch.object(
                installer.preflight,
                "resolve_claude_executable",
                return_value=(CLAUDE, None),
            ),
            mock.patch.object(installer, "snapshot_path", return_value=SNAPSHOT),
            mock.patch.object(
                installer,
                "raw_user_marketplace_declaration",
                return_value=(user_shape, "present", None),
            ),
            mock.patch.object(installer, "create_or_verify_snapshot") as snapshot,
            mock.patch.object(
                installer,
                "run_command",
                side_effect=[command_json([marketplace]), command_json([plugin])],
            ) as runner,
        ):
            exit_code, result = installer.install(
                upgrade_verified_snapshot=upgrade_verified_snapshot
            )
        return exit_code, result, runner, snapshot

    def test_preflight_blocked_never_captures_or_mutates(self) -> None:
        report = ready_report()
        report["status"] = "BLOCKED"
        report["error_codes"] = [
            "claude_code_plugin_trust_contract_too_old_or_unverified"
        ]
        report["actions"] = [
            {
                "id": "update_claude_code_for_plugin_trust_contract",
                "kind": "decision",
                "instruction": "Update Claude Code only with explicit approval.",
                "mutates_state": True,
                "requires_explicit_install_intent": True,
            }
        ]
        with (
            mock.patch.object(installer.preflight, "build_report", return_value=report),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(installer, "capture_verified_source") as capture,
            mock.patch.object(installer, "run_command") as runner,
        ):
            exit_code, result = installer.install()
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["requires_user_action"])
        self.assertTrue(result["actions"][0]["requires_explicit_install_intent"])
        self.assertFalse(result["operation_ok"])
        self.assertFalse(result["ok"])
        self.assertFalse(result["ready_for_use"])
        self.assertFalse(result["mutation_attempted"])
        capture.assert_not_called()
        runner.assert_not_called()

    def test_manual_desktop_route_verifies_source_without_snapshot_or_mutation(self) -> None:
        report = ready_report()
        report["status"] = "MANUAL_INSTALL_PLAN_AVAILABLE"
        report["surface"] = {
            "requested": "desktop-code-local",
            "resolved": "desktop-code-local",
            "install_route": "desktop_plugin_manager",
        }
        report["actions"] = [
            {
                "id": "desktop_ui",
                "kind": "ui",
                "instruction": "Use the Desktop plugin manager and verify in the same Code surface.",
                "mutates_state": True,
                "requires_explicit_install_intent": True,
            }
        ]
        with (
            mock.patch.object(installer.preflight, "build_report", return_value=report),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(
                installer,
                "capture_verified_source",
                return_value=(fixture_source(), []),
            ),
            mock.patch.object(installer.preflight, "resolve_claude_executable") as resolve,
            mock.patch.object(installer, "create_or_verify_snapshot") as snapshot,
            mock.patch.object(installer, "run_command") as runner,
        ):
            exit_code, result = installer.install(surface="desktop-code-local")

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "SOURCE_VERIFIED_MANUAL_INSTALL_REQUIRED")
        self.assertTrue(result["operation_ok"])
        self.assertFalse(result["ok"])
        self.assertFalse(result["ready_for_use"])
        self.assertTrue(result["verification"]["source"])
        self.assertFalse(result["verification"]["configuration"])
        self.assertFalse(result["verification"]["runtime_activation"])
        self.assertTrue(result["requires_user_action"])
        self.assertTrue(result["actions"][0]["requires_explicit_install_intent"])
        self.assertTrue(result["actions"][0]["mutates_state"])
        self.assertIsNone(result["scope"])
        self.assertEqual(result["suggested_scope"], "user")
        self.assertEqual(result["installation_shape"], "github_tag_desktop_ui")
        resolve.assert_not_called()
        snapshot.assert_not_called()
        runner.assert_not_called()

    def test_unsupported_surface_stops_before_source_or_mutation(self) -> None:
        report = ready_report()
        report["status"] = "UNSUPPORTED_SURFACE"
        report["surface"] = {
            "requested": "desktop-code-cloud",
            "resolved": "desktop-code-cloud",
            "install_route": "none",
        }
        report["error_codes"] = [
            "full_acgm_plugins_unavailable_on_desktop-code-cloud"
        ]
        with (
            mock.patch.object(installer.preflight, "build_report", return_value=report),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(installer, "capture_verified_source") as capture,
            mock.patch.object(installer, "create_or_verify_snapshot") as snapshot,
            mock.patch.object(installer, "run_command") as runner,
        ):
            exit_code, result = installer.install(surface="desktop-code-cloud")

        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "UNSUPPORTED_SURFACE")
        self.assertFalse(result["operation_ok"])
        self.assertFalse(result["ok"])
        self.assertFalse(result["ready_for_use"])
        capture.assert_not_called()
        snapshot.assert_not_called()
        runner.assert_not_called()

    def test_missing_revision_blocks_before_source_capture(self) -> None:
        with (
            mock.patch.object(
                installer.preflight, "build_report", return_value=ready_report()
            ),
            mock.patch.object(installer, "checkout_revision", return_value=None),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(installer, "capture_verified_source") as capture,
        ):
            exit_code, result = installer.install()
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "CHECKOUT_REVISION_BLOCKED")
        self.assertTrue(result["requires_user_action"])
        self.assertTrue(result["next_steps"])
        self.assertFalse(result["operation_ok"])
        self.assertFalse(result["ok"])
        self.assertFalse(result["ready_for_use"])
        self.assertFalse(result["mutation_attempted"])
        capture.assert_not_called()

    def test_dirty_checkout_blocks_before_source_capture(self) -> None:
        with (
            mock.patch.object(
                installer.preflight, "build_report", return_value=ready_report()
            ),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=False),
            mock.patch.object(installer, "capture_verified_source") as capture,
        ):
            exit_code, result = installer.install()
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "CHECKOUT_DIRTY_BLOCKED")
        capture.assert_not_called()

    def test_source_integrity_failure_blocks_before_snapshot_or_claude(self) -> None:
        with (
            mock.patch.object(
                installer.preflight, "build_report", return_value=ready_report()
            ),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(
                installer,
                "capture_verified_source",
                return_value=(None, ["package_manifest_git_inventory_mismatch"]),
            ),
            mock.patch.object(installer, "create_or_verify_snapshot") as snapshot_creator,
            mock.patch.object(installer, "run_command") as runner,
        ):
            exit_code, result = installer.install()
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "SOURCE_INTEGRITY_BLOCKED")
        snapshot_creator.assert_not_called()
        runner.assert_not_called()

    def test_dry_run_creates_no_snapshot_and_calls_no_plugin_cli(self) -> None:
        exit_code, result, runner, snapshot_creator, user_scope, _ = self.run_install(
            [], dry_run=True
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "SOURCE_VERIFIED_AUTOMATED_INSTALL_READY")
        self.assertTrue(result["operation_ok"])
        self.assertFalse(result["ok"])
        self.assertFalse(result["ready_for_use"])
        self.assertFalse(result["changed"])
        self.assertTrue(result["verification"]["source"])
        self.assertFalse(result["verification"]["configuration"])
        self.assertEqual(result["scope"], "user")
        self.assertEqual(result["installation_shape"], "verified_snapshot_user")
        runner.assert_not_called()
        snapshot_creator.assert_not_called()
        user_scope.assert_not_called()
        serialized = json.dumps(result)
        self.assertIn("VERIFIED_SNAPSHOT", serialized)
        self.assertNotIn(str(SNAPSHOT), serialized)
        self.assertNotIn(str(CLAUDE), serialized)

    def test_fresh_install_adds_user_marketplace_and_verifies_twice(self) -> None:
        exit_code, result, runner, _, user_scope, reverify = self.run_install(
            [
                command_json([]),
                command_json([]),
                installer.CommandResult(0),
                command_json(self.local_marketplace()),
                installer.CommandResult(0),
                command_json(self.installed_plugin()),
            ],
            user_declared=False,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "CONFIGURATION_VERIFIED_NEW")
        self.assertTrue(result["operation_ok"])
        self.assertTrue(result["ok"])
        self.assertTrue(result["verification"]["configuration"])
        self.assertFalse(result["verification"]["runtime_activation"])
        self.assertFalse(result["ready_for_use"])
        self.assertTrue(result["changed"])
        self.assertEqual(runner.call_count, 6)
        self.assertEqual(reverify.call_count, 2)
        self.assertEqual(user_scope.call_count, 2)
        mutation_calls = [
            call.args[0]
            for call in runner.call_args_list
            if "add" in call.args[0] or "install" in call.args[0]
        ]
        self.assertEqual(len(mutation_calls), 2)

    def test_exact_user_marketplace_skips_duplicate_add(self) -> None:
        exit_code, result, runner, _, user_scope, reverify = self.run_install(
            [
                command_json(self.local_marketplace()),
                command_json([]),
                installer.CommandResult(0),
                command_json(self.installed_plugin()),
            ],
            user_declared=True,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "CONFIGURATION_VERIFIED_NEW")
        self.assertEqual(runner.call_count, 4)
        self.assertFalse(any("add" in call.args[0] for call in runner.call_args_list))
        self.assertEqual(user_scope.call_count, 1)
        self.assertEqual(reverify.call_count, 1)
        self.assertEqual(result["planned_commands"][0][0:3], ["claude", "plugin", "install"])

    def test_project_only_marketplace_is_redeclared_at_user_scope(self) -> None:
        exit_code, result, runner, _, user_scope, _ = self.run_install(
            [
                command_json(self.local_marketplace()),
                command_json([]),
                installer.CommandResult(0),
                command_json(self.local_marketplace()),
                installer.CommandResult(0),
                command_json(self.installed_plugin()),
            ],
            user_declared=False,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "CONFIGURATION_VERIFIED_NEW")
        self.assertTrue(any("add" in call.args[0] for call in runner.call_args_list))
        self.assertEqual(user_scope.call_count, 2)

    def test_conflicting_marketplace_is_never_replaced(self) -> None:
        conflict = [
            {
                "name": installer.MARKETPLACE_NAME,
                "source": "directory",
                "path": "/different/source",
            }
        ]
        exit_code, result, runner, snapshot_creator, _, _ = self.run_install(
            [command_json(conflict), command_json([])]
        )
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "MARKETPLACE_CONFLICT")
        self.assertFalse(result["changed"])
        self.assertEqual(runner.call_count, 2)
        snapshot_creator.assert_not_called()

    def test_legacy_public_github_shape_is_diagnosed_without_mutation(self) -> None:
        exit_code, result, runner, snapshot = self.run_legacy_detection()

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            result["status"],
            "LEGACY_PUBLIC_GITHUB_INSTALL_REQUIRES_EXPLICIT_MIGRATION",
        )
        self.assertFalse(result["operation_ok"])
        self.assertFalse(result["ok"])
        self.assertFalse(result["ready_for_use"])
        self.assertTrue(result["requires_user_action"])
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(result["installation_shape"], "legacy_public_github_user")
        self.assertTrue(result["legacy_detection"]["detected"])
        self.assertEqual(
            result["legacy_detection"]["repo"], installer.PUBLIC_GITHUB_REPO
        )
        self.assertEqual(result["legacy_detection"]["ref"], "v0.3.0-rc.1")
        self.assertEqual(result["legacy_detection"]["version"], "0.3.0-rc.1")
        self.assertEqual(result["legacy_detection"]["scope"], "user")
        self.assertFalse(
            result["legacy_detection"]["publisher_authenticity_proven"]
        )
        self.assertFalse(result["legacy_detection"]["installed_content_verified"])
        self.assertEqual(runner.call_count, 2)
        snapshot.assert_not_called()

    def test_legacy_machine_migration_plan_is_ordered_and_non_executable(self) -> None:
        exit_code, result, runner, snapshot = self.run_legacy_detection()

        self.assertEqual(exit_code, 2)
        plan = result["manual_migration_plan"]
        self.assertIsInstance(plan, dict)
        self.assertFalse(plan["automatic_execution_allowed"])
        self.assertTrue(plan["requires_separate_authorization"])
        expected_order = [
            "review_legacy_evidence_limits",
            "close_all_acgm_sessions",
            "preserve_privacy_safe_acgm_report",
            "authorize_legacy_migration_mutations",
            "uninstall_legacy_plugin_keep_data_user_scope",
            "verify_legacy_plugin_absent_and_data_retained",
            "remove_legacy_marketplace_user_scope",
            "select_and_install_one_rc4_target_shape",
            "reload_and_verify_same_surface",
        ]
        self.assertEqual(plan["step_order"], expected_order)
        self.assertEqual(
            [action["id"] for action in result["actions"]], expected_order
        )
        for action in result["actions"]:
            self.assertIn("mutates_state", action)
            self.assertIn("requires_explicit_install_intent", action)
            self.assertNotIn("mutating", action)
            self.assertFalse(action["automatic_execution_allowed"])
            if action["mutates_state"]:
                self.assertTrue(action["requires_explicit_install_intent"])

        actions = {action["id"]: action for action in result["actions"]}
        report_argv = [
            "python3",
            "scripts/acgm_runtime.py",
            "report",
            "--project",
            "all",
            "--limit",
            installer.FULL_LEDGER_REPORT_LIMIT,
            "--json",
        ]
        self.assertEqual(
            actions["preserve_privacy_safe_acgm_report"]["command_argv"],
            report_argv,
        )
        self.assertEqual(
            actions["preserve_privacy_safe_acgm_report"]["cwd_token"],
            "LOCAL_CHECKOUT",
        )
        before_evidence = actions["preserve_privacy_safe_acgm_report"][
            "stdout_evidence"
        ]
        self.assertEqual(
            before_evidence["fingerprint_alias"],
            "LEGACY_DATA_REPORT_BEFORE_SHA256",
        )
        self.assertEqual(before_evidence["algorithm"], "sha256")
        self.assertEqual(before_evidence["input"], "exact_stdout_bytes")
        self.assertEqual(
            before_evidence["coverage"], "full_sanitized_event_ledger"
        )
        self.assertEqual(before_evidence["event_count_expression"], "len($.events)")
        self.assertEqual(
            actions["uninstall_legacy_plugin_keep_data_user_scope"][
                "command_argv"
            ],
            [
                "claude",
                "plugin",
                "uninstall",
                installer.PLUGIN_ID,
                "--scope",
                "user",
                "--keep-data",
            ],
        )
        self.assertEqual(
            plan["verification_gate"],
            {
                "after_step_id": "uninstall_legacy_plugin_keep_data_user_scope",
                "gate_step_id": "verify_legacy_plugin_absent_and_data_retained",
                "before_step_id": "remove_legacy_marketplace_user_scope",
                "must_pass_before_next_mutation": True,
            },
        )
        gate = actions["verify_legacy_plugin_absent_and_data_retained"]
        self.assertEqual(
            gate["commands"][0]["command_argv"],
            ["claude", "plugin", "list", "--json"],
        )
        self.assertEqual(gate["commands"][1]["command_argv"], report_argv)
        self.assertEqual(gate["commands"][1]["cwd_token"], "LOCAL_CHECKOUT")
        self.assertEqual(
            gate["evidence_comparison"],
            {
                "before_fingerprint_alias": "LEGACY_DATA_REPORT_BEFORE_SHA256",
                "after_fingerprint_alias": "LEGACY_DATA_REPORT_AFTER_SHA256",
                "algorithm": "sha256",
                "input": "exact_stdout_bytes",
                "coverage": "full_sanitized_event_ledger",
                "event_count_relation": "equal",
                "required_relation": "equal",
                "must_pass_before_step_id": "remove_legacy_marketplace_user_scope",
            },
        )
        self.assertEqual(
            actions["remove_legacy_marketplace_user_scope"]["command_argv"],
            [
                "claude",
                "plugin",
                "marketplace",
                "remove",
                installer.MARKETPLACE_NAME,
                "--scope",
                "user",
            ],
        )
        choices = actions["select_and_install_one_rc4_target_shape"]
        self.assertEqual(choices["selection_cardinality"], "exactly_one")
        self.assertEqual(
            [option["installation_shape"] for option in choices["target_options"]],
            ["verified_snapshot_user", "github_tag_desktop_ui"],
        )
        self.assertTrue(
            all(
                option["version"] == "0.3.0-rc.4"
                and option["automatic_execution_allowed"] is False
                for option in choices["target_options"]
            )
        )
        self.assertEqual(
            choices["target_options"][0]["command_argv"],
            [
                "python3",
                "scripts/install.py",
                "--surface",
                "claude-code-cli",
                "--json",
            ],
        )
        self.assertEqual(
            choices["target_options"][1]["ref"], "v0.3.0-rc.4"
        )
        same_surface = actions["reload_and_verify_same_surface"][
            "same_surface_checks"
        ]
        self.assertEqual(
            [
                check.get("value")
                or check.get("command_argv")
                or check.get("kind")
                for check in same_surface
            ],
            [
                "/reload-plugins",
                "/hooks",
                "/skills",
                ["acgm", "version"],
                "controlled_hook_probe",
                ["acgm", "doctor", "--json"],
            ],
        )
        self.assertFalse(result["mutation_attempted"])
        self.assertFalse(result["state_change_possible"])
        self.assertEqual(result["planned_commands"], [])
        self.assertEqual(runner.call_count, 2)
        snapshot.assert_not_called()

    def test_legacy_machine_plan_uses_windows_py3_launcher_consistently(self) -> None:
        report = ready_report()
        report["checks"] = {"python_hook_launcher": {"kind": "py-3"}}
        exit_code, result, runner, snapshot = self.run_legacy_detection(
            preflight_report=report
        )

        self.assertEqual(exit_code, 2)
        actions = {action["id"]: action for action in result["actions"]}
        before = actions["preserve_privacy_safe_acgm_report"]
        after = actions["verify_legacy_plugin_absent_and_data_retained"][
            "commands"
        ][1]
        self.assertEqual(before["command_argv"][:2], ["py", "-3"])
        self.assertEqual(after["command_argv"], before["command_argv"])
        self.assertEqual(before["cwd_token"], "LOCAL_CHECKOUT")
        self.assertEqual(after["cwd_token"], "LOCAL_CHECKOUT")
        choices = actions["select_and_install_one_rc4_target_shape"]
        self.assertEqual(
            choices["target_options"][0]["command_argv"][:2], ["py", "-3"]
        )
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(runner.call_count, 2)
        snapshot.assert_not_called()

    def test_upgrade_flag_never_mutates_legacy_public_github_shape(self) -> None:
        exit_code, result, runner, snapshot = self.run_legacy_detection(
            upgrade_verified_snapshot=True,
            marketplace_source={
                "source": "github",
                "repo": installer.PUBLIC_GITHUB_REPO,
            },
            declaration={
                "source": {
                    "source": "github",
                    "repo": installer.PUBLIC_GITHUB_REPO,
                }
            },
            plugin_overrides={"version": "0.1.0"},
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            result["status"],
            "LEGACY_PUBLIC_GITHUB_INSTALL_REQUIRES_EXPLICIT_MIGRATION",
        )
        self.assertIsNone(result["legacy_detection"]["ref"])
        self.assertEqual(result["legacy_detection"]["version"], "0.1.0")
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(runner.call_count, 2)
        snapshot.assert_not_called()

    def test_flat_legacy_github_cli_record_is_diagnosed(self) -> None:
        exit_code, result, runner, snapshot = self.run_legacy_detection(
            marketplace_overrides={
                "source": "github",
                "repo": installer.PUBLIC_GITHUB_REPO,
                "ref": "v0.3.0-rc.1",
                "path": "/private/cache/marketplace",
                "installLocation": "/private/cache/marketplace",
            }
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            result["status"],
            "LEGACY_PUBLIC_GITHUB_INSTALL_REQUIRES_EXPLICIT_MIGRATION",
        )
        self.assertTrue(result["legacy_detection"]["detected"])
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(runner.call_count, 2)
        snapshot.assert_not_called()

    def test_legacy_detection_rejects_duplicate_records(self) -> None:
        source = {
            "source": "github",
            "repo": installer.PUBLIC_GITHUB_REPO,
            "ref": "v0.3.0-rc.1",
        }
        marketplace = {"name": installer.MARKETPLACE_NAME, "source": source}
        plugin = {
            "id": installer.PLUGIN_ID,
            "enabled": True,
            "scope": "user",
            "version": "0.3.0-rc.1",
            "errors": [],
        }
        with mock.patch.object(
            installer,
            "raw_user_marketplace_declaration",
            return_value=({"source": source}, "present", None),
        ):
            self.assertIsNone(
                installer.detect_legacy_public_github_install(
                    [marketplace, marketplace], [plugin]
                )
            )
            self.assertIsNone(
                installer.detect_legacy_public_github_install(
                    [marketplace], [plugin, plugin]
                )
            )

    def test_similar_but_unproven_github_shapes_remain_plain_conflicts(self) -> None:
        variants = [
            {
                "marketplace_source": {
                    "source": "github",
                    "repo": "someone-else/Agent-Coding-Governance-Methodology",
                    "ref": "v0.3.0-rc.1",
                }
            },
            {
                "marketplace_source": {
                    "source": "github",
                    "repo": installer.PUBLIC_GITHUB_REPO,
                    "ref": "v9.9.9",
                }
            },
            {"plugin_overrides": {"version": "0.3.0-rc.2"}},
            {"plugin_overrides": {"scope": "project"}},
            {"plugin_overrides": {"errors": ["broken"]}},
            {
                "declaration": {
                    "source": "github",
                    "repo": installer.PUBLIC_GITHUB_REPO,
                    "ref": "v0.3.0-rc.1",
                }
            },
            {
                "marketplace_overrides": {
                    "repo": installer.PUBLIC_GITHUB_REPO,
                    "ref": "v0.3.0-rc.1",
                }
            },
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                exit_code, result, runner, snapshot = self.run_legacy_detection(
                    **variant
                )
                self.assertEqual(exit_code, 2)
                self.assertEqual(result["status"], "MARKETPLACE_CONFLICT")
                self.assertFalse(result["legacy_detection"]["detected"])
                self.assertFalse(result["mutation_attempted"])
                self.assertEqual(runner.call_count, 2)
                snapshot.assert_not_called()

    def test_verified_snapshot_upgrade_succeeds_with_scoped_fixed_argv(self) -> None:
        exit_code, result, cli, snapshot_creator = self.run_upgrade(
            UpgradeCliFixture()
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "CONFIGURATION_VERIFIED_UPGRADED")
        self.assertTrue(result["upgrade"]["preconditions_verified"])
        self.assertEqual(result["upgrade"]["from_version"], "0.3.0-rc.3")
        self.assertEqual(result["upgrade"]["to_version"], "0.3.0-rc.4")
        self.assertFalse(result["upgrade"]["rollback_attempted"])
        self.assertTrue(result["verification"]["configuration"])
        self.assertFalse(result["verification"]["runtime_activation"])
        self.assertEqual(cli.state, "new_full")
        self.assertEqual(result["installation_shape"], "verified_snapshot_user")
        snapshot_creator.assert_called_once()
        uninstall_calls = [
            call
            for call in cli.calls
            if call[1:3] == ["plugin", "uninstall"]
            and call[-1:] != ["--help"]
        ]
        self.assertEqual(len(uninstall_calls), 1)
        self.assertIn("--keep-data", uninstall_calls[0])
        self.assertEqual(
            uninstall_calls[0][-3:], ["--scope", "user", "--keep-data"]
        )
        remove_calls = [
            call
            for call in cli.calls
            if call[1:4] == ["plugin", "marketplace", "remove"]
            and call[-1:] != ["--help"]
        ]
        self.assertEqual(len(remove_calls), 1)
        self.assertEqual(remove_calls[0][-2:], ["--scope", "user"])
        self.assertTrue(cli.cwds)
        self.assertTrue(all(cwd is not None for cwd in cli.cwds))
        self.assertEqual(len({str(cwd) for cwd in cli.cwds}), 1)
        self.assertNotEqual(cli.cwds[0], installer.REPO_ROOT)
        self.assertFalse(cli.cwds[0].exists())

    def test_verified_upgrade_dry_run_proves_old_state_without_mutation(self) -> None:
        exit_code, result, cli, snapshot_creator = self.run_upgrade(
            UpgradeCliFixture(), dry_run=True
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "VERIFIED_UPGRADE_READY")
        self.assertTrue(result["upgrade"]["preconditions_verified"])
        self.assertEqual(cli.state, "old_full")
        snapshot_creator.assert_not_called()
        self.assertFalse(
            any(
                call[1:4] == ["plugin", "marketplace", "remove"]
                and call[-1:] != ["--help"]
                for call in cli.calls
            )
        )

    def test_verified_upgrade_rejects_old_cache_mismatch_without_mutation(self) -> None:
        exit_code, result, cli, snapshot_creator = self.run_upgrade(
            UpgradeCliFixture(),
            old_plugin_verification=(False, ["verified_tree_content_mismatch"]),
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "VERIFIED_UPGRADE_PRECONDITIONS_BLOCKED")
        self.assertIn("verified_tree_content_mismatch", result["error_codes"])
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(cli.state, "old_full")
        snapshot_creator.assert_not_called()

    def test_verified_upgrade_requires_scoped_marketplace_remove(self) -> None:
        exit_code, result, cli, snapshot_creator = self.run_upgrade(
            UpgradeCliFixture(), scoped_remove_available=False
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            result["status"], "VERIFIED_UPGRADE_SCOPED_REMOVE_UNAVAILABLE"
        )
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(cli.state, "old_full")
        snapshot_creator.assert_not_called()

    def test_verified_upgrade_requires_keep_data_uninstall_capability(self) -> None:
        exit_code, result, cli, snapshot_creator = self.run_upgrade(
            UpgradeCliFixture(), keep_data_uninstall_available=False
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            result["status"],
            "VERIFIED_UPGRADE_KEEP_DATA_UNINSTALL_UNAVAILABLE",
        )
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(cli.state, "old_full")
        snapshot_creator.assert_not_called()

    def test_verified_upgrade_blocks_active_plugin_cache_before_mutation(self) -> None:
        exit_code, result, cli, snapshot_creator = self.run_upgrade(
            UpgradeCliFixture(), plugin_in_use=True
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "VERIFIED_UPGRADE_PLUGIN_IN_USE")
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(cli.state, "old_full")
        snapshot_creator.assert_not_called()

    def test_second_in_use_gate_cleans_present_backup_and_clears_token(self) -> None:
        exit_code, result, cli, _ = self.run_upgrade(
            UpgradeCliFixture(),
            plugin_in_use_results=[(False, None), (True, None)],
            backup_present=True,
            cleanup_result=(True, None),
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "VERIFIED_UPGRADE_PLUGIN_IN_USE")
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(cli.state, "old_full")
        self.assertEqual(result["upgrade"]["data"]["source_state"], "present")
        self.assertTrue(result["upgrade"]["data"]["backup_verified"])
        self.assertFalse(result["upgrade"]["data"]["backup_retained"])
        self.assertIsNone(result["upgrade"]["data"]["backup_location_token"])
        self.assertFalse(
            result["upgrade"]["data"]["retained_backup_verified"]
        )
        self.assertTrue(result["upgrade"]["data"]["backup_cleanup_verified"])

    def test_second_in_use_gate_retains_backup_when_cleanup_fails(self) -> None:
        exit_code, result, cli, _ = self.run_upgrade(
            UpgradeCliFixture(),
            plugin_in_use_results=[(False, None), (True, None)],
            backup_present=True,
            cleanup_result=(False, "plugin_data_backup_cleanup_failed"),
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "VERIFIED_UPGRADE_PLUGIN_IN_USE")
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(cli.state, "old_full")
        self.assertTrue(result["upgrade"]["data"]["backup_retained"])
        self.assertEqual(
            result["upgrade"]["data"]["backup_location_token"],
            "UPGRADE_DATA_BACKUP",
        )
        self.assertTrue(
            result["upgrade"]["data"]["retained_backup_verified"]
        )
        self.assertFalse(result["upgrade"]["data"]["backup_cleanup_verified"])
        self.assertIn("plugin_data_backup_cleanup_failed", result["error_codes"])
        self.assertTrue(
            any(
                "UPGRADE_DATA_BACKUP" in step and "manual" in step
                for step in result["next_steps"]
            )
        )

    def test_second_in_use_gate_marks_partial_cleanup_artifact_unverified(self) -> None:
        def partial_cleanup(backup):
            assert backup.backup_path is not None
            shutil.rmtree(backup.backup_path)
            return False, "plugin_data_backup_cleanup_failed"

        exit_code, result, cli, _ = self.run_upgrade(
            UpgradeCliFixture(),
            plugin_in_use_results=[(False, None), (True, None)],
            backup_present=True,
            cleanup_result=partial_cleanup,
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "VERIFIED_UPGRADE_PLUGIN_IN_USE")
        self.assertFalse(result["mutation_attempted"])
        self.assertEqual(cli.state, "old_full")
        self.assertTrue(result["upgrade"]["data"]["backup_retained"])
        self.assertEqual(
            result["upgrade"]["data"]["backup_location_token"],
            "UPGRADE_DATA_BACKUP",
        )
        self.assertFalse(
            result["upgrade"]["data"]["retained_backup_verified"]
        )
        self.assertFalse(result["upgrade"]["data"]["backup_cleanup_verified"])
        self.assertIn(
            "retained_plugin_data_backup_not_verified", result["error_codes"]
        )
        self.assertTrue(
            any(
                "not a verified recoverable backup" in step
                and "live ledger" in step
                and "manually" in step
                for step in result["next_steps"]
            )
        )

    def test_failed_upgrade_restores_exact_old_verified_state(self) -> None:
        exit_code, result, cli, _ = self.run_upgrade(
            UpgradeCliFixture(fail_new_install=True)
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "VERIFIED_UPGRADE_FAILED_ROLLED_BACK")
        self.assertTrue(result["upgrade"]["rollback_attempted"])
        self.assertTrue(result["upgrade"]["rollback_verified"])
        self.assertFalse(result["state_change_possible"])
        self.assertEqual(cli.state, "old_full")

    def test_unknown_partial_upgrade_stops_without_guessing(self) -> None:
        exit_code, result, cli, _ = self.run_upgrade(
            UpgradeCliFixture(fail_new_install=True, become_unknown=True),
            backup_present=True,
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(
            result["status"],
            "VERIFIED_UPGRADE_PARTIAL_STATE_REQUIRES_MANUAL_REPAIR",
        )
        self.assertTrue(result["upgrade"]["rollback_attempted"])
        self.assertFalse(result["upgrade"]["rollback_verified"])
        self.assertTrue(result["state_change_possible"])
        self.assertEqual(cli.state, "unknown")
        self.assertTrue(result["upgrade"]["data"]["backup_retained"])
        self.assertTrue(
            result["upgrade"]["data"]["retained_backup_verified"]
        )
        self.assertEqual(
            result["upgrade"]["data"]["backup_location_token"],
            "UPGRADE_DATA_BACKUP",
        )

    def test_upgrade_cannot_claim_closed_when_backup_cleanup_fails(self) -> None:
        exit_code, result, _cli, _ = self.run_upgrade(
            UpgradeCliFixture(),
            backup_present=True,
            cleanup_result=(False, "plugin_data_backup_cleanup_failed"),
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(
            result["status"],
            "VERIFIED_UPGRADE_PARTIAL_STATE_REQUIRES_MANUAL_REPAIR",
        )
        self.assertIn("plugin_data_backup_cleanup_failed", result["error_codes"])
        self.assertTrue(result["upgrade"]["data"]["backup_retained"])
        self.assertTrue(
            result["upgrade"]["data"]["retained_backup_verified"]
        )

    def test_existing_exact_install_is_idempotently_verified(self) -> None:
        exit_code, result, runner, _, _, _ = self.run_install(
            [
                command_json(self.local_marketplace()),
                command_json(self.installed_plugin()),
            ],
            user_declared=True,
            snapshot_created=False,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "CONFIGURATION_VERIFIED_EXISTING")
        self.assertTrue(result["operation_ok"])
        self.assertTrue(result["ok"])
        self.assertTrue(result["verification"]["configuration"])
        self.assertFalse(result["verification"]["runtime_activation"])
        self.assertFalse(result["changed"])
        self.assertEqual(runner.call_count, 2)

    def test_existing_install_with_wrong_scope_never_mutates(self) -> None:
        exit_code, result, runner, _, _, _ = self.run_install(
            [
                command_json(self.local_marketplace()),
                command_json(self.installed_plugin(scope="project")),
            ],
            user_declared=True,
            installed_verification=(False, ["installed_plugin_scope_not_user"]),
        )
        self.assertEqual(exit_code, 2)
        self.assertEqual(
            result["status"], "ALREADY_INSTALLED_REQUIRES_RUNTIME_VERIFICATION"
        )
        self.assertIn("installed_plugin_scope_not_user", result["error_codes"])
        self.assertEqual(runner.call_count, 2)

    def test_unknown_json_object_blocks_all_mutations(self) -> None:
        exit_code, result, runner, snapshot_creator, _, _ = self.run_install(
            [command_json({"error": "future"}), command_json([])]
        )
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "STATE_INSPECTION_BLOCKED")
        self.assertEqual(runner.call_count, 2)
        snapshot_creator.assert_not_called()

    def test_user_scope_inspection_failure_blocks_snapshot(self) -> None:
        source = fixture_source()
        with (
            mock.patch.object(
                installer.preflight, "build_report", return_value=ready_report()
            ),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(
                installer, "capture_verified_source", return_value=(source, [])
            ),
            mock.patch.object(
                installer.preflight,
                "resolve_claude_executable",
                return_value=(CLAUDE, None),
            ),
            mock.patch.object(installer, "snapshot_path", return_value=SNAPSHOT),
            mock.patch.object(
                installer,
                "user_marketplace_declaration",
                return_value=(None, "user_settings_invalid_json"),
            ),
            mock.patch.object(installer, "create_or_verify_snapshot") as creator,
            mock.patch.object(
                installer,
                "run_command",
                side_effect=[command_json([]), command_json([])],
            ),
        ):
            exit_code, result = installer.install()
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "USER_SCOPE_INSPECTION_BLOCKED")
        creator.assert_not_called()

    def test_every_mutation_requires_fresh_source_reverification(self) -> None:
        exit_code, result, _, _, _, reverify = self.run_install(
            [
                command_json([]),
                command_json([]),
                installer.CommandResult(0),
                command_json(self.local_marketplace()),
                installer.CommandResult(0),
                command_json(self.installed_plugin()),
            ],
            user_declared=False,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "CONFIGURATION_VERIFIED_NEW")
        self.assertEqual(reverify.call_count, 2)

    def test_source_change_before_first_mutation_stops_install(self) -> None:
        exit_code, result, runner, _, _, _ = self.run_install(
            [command_json([]), command_json([])],
            user_declared=False,
            reverification=(False, "checkout_identity_changed_before_mutation"),
        )
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "PRE_MUTATION_SOURCE_VERIFICATION_FAILED")
        self.assertEqual(runner.call_count, 2)

    def test_post_add_user_scope_verification_is_required(self) -> None:
        source = fixture_source()
        with (
            mock.patch.object(
                installer.preflight, "build_report", return_value=ready_report()
            ),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(
                installer, "capture_verified_source", return_value=(source, [])
            ),
            mock.patch.object(
                installer.preflight,
                "resolve_claude_executable",
                return_value=(CLAUDE, None),
            ),
            mock.patch.object(installer, "snapshot_path", return_value=SNAPSHOT),
            mock.patch.object(
                installer,
                "create_or_verify_snapshot",
                return_value=(SNAPSHOT, True, None),
            ),
            mock.patch.object(
                installer,
                "user_marketplace_declaration",
                side_effect=[("absent", None), ("absent", None)],
            ),
            mock.patch.object(
                installer,
                "reverify_source_and_snapshot",
                return_value=(True, None),
            ),
            mock.patch.object(
                installer,
                "run_command",
                side_effect=[
                    command_json([]),
                    command_json([]),
                    installer.CommandResult(0),
                    command_json(self.local_marketplace()),
                ],
            ),
        ):
            exit_code, result = installer.install()
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "MARKETPLACE_VERIFICATION_FAILED")

    def test_content_verification_failure_is_not_success(self) -> None:
        exit_code, result, _, _, _, _ = self.run_install(
            [
                command_json(self.local_marketplace()),
                command_json([]),
                installer.CommandResult(0),
                command_json(self.installed_plugin()),
            ],
            user_declared=True,
            installed_verification=(
                False,
                ["verified_tree_content_mismatch"],
            ),
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "PLUGIN_CONTENT_VERIFICATION_FAILED")
        self.assertFalse(result["ok"])

    def test_user_scope_conflict_never_runs_marketplace_add(self) -> None:
        source = fixture_source()
        with (
            mock.patch.object(
                installer.preflight, "build_report", return_value=ready_report()
            ),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(
                installer, "capture_verified_source", return_value=(source, [])
            ),
            mock.patch.object(
                installer.preflight,
                "resolve_claude_executable",
                return_value=(CLAUDE, None),
            ),
            mock.patch.object(installer, "snapshot_path", return_value=SNAPSHOT),
            mock.patch.object(
                installer,
                "user_marketplace_declaration",
                return_value=("conflict", None),
            ),
            mock.patch.object(installer, "create_or_verify_snapshot") as creator,
            mock.patch.object(
                installer,
                "run_command",
                side_effect=[command_json([]), command_json([])],
            ) as runner,
        ):
            exit_code, result = installer.install()
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "MARKETPLACE_CONFLICT")
        self.assertEqual(runner.call_count, 2)
        creator.assert_not_called()
        self.assertFalse(result["mutation_attempted"])

    def test_preexisting_snapshot_install_success_still_reports_changed(self) -> None:
        exit_code, result, _, _, _, _ = self.run_install(
            [
                command_json(self.local_marketplace()),
                command_json([]),
                installer.CommandResult(0),
                command_json(self.installed_plugin()),
            ],
            user_declared=True,
            snapshot_created=False,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "CONFIGURATION_VERIFIED_NEW")
        self.assertTrue(result["changed"])
        self.assertTrue(result["mutation_attempted"])
        self.assertFalse(result["state_change_possible"])

    def test_install_failure_reports_possible_partial_state(self) -> None:
        exit_code, result, _, _, _, _ = self.run_install(
            [
                command_json(self.local_marketplace()),
                command_json([]),
                installer.CommandResult(
                    124, timed_out=True, error_code="command_timeout"
                ),
            ],
            user_declared=True,
            snapshot_created=False,
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "PLUGIN_INSTALL_FAILED")
        self.assertFalse(result["changed"])
        self.assertTrue(result["mutation_attempted"])
        self.assertTrue(result["state_change_possible"])


class SourceCaptureTests(unittest.TestCase):
    def make_checkout(
        self,
        *,
        bad_hash=False,
        omit_tracked=False,
        unsafe_entry=False,
    ):
        root = Path(tempfile.mkdtemp(prefix="acgm-source-test-"))
        self.addCleanup(shutil.rmtree, root, True)
        files = {
            "VERSION": b"0.3.0-rc.4\n",
            "scripts/tool.py": b"print('ok')\n",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest_files = {
            relative: hashlib.sha256(content).hexdigest()
            for relative, content in files.items()
        }
        if bad_hash:
            manifest_files["scripts/tool.py"] = "0" * 64
        if unsafe_entry:
            manifest_files["../escape"] = "0" * 64
        manifest = {
            "schema_version": 1,
            "version": "0.3.0-rc.4",
            "files": manifest_files,
        }
        (root / installer.PACKAGE_MANIFEST_NAME).write_text(
            json.dumps(manifest, sort_keys=True), encoding="utf-8"
        )
        modes = {
            "VERSION": 0o100644,
            "scripts/tool.py": 0o100644,
            installer.PACKAGE_MANIFEST_NAME: 0o100644,
        }
        if omit_tracked:
            (root / "tracked-extra.txt").write_text("tracked", encoding="utf-8")
            modes["tracked-extra.txt"] = 0o100644
        blobs: dict[str, bytes] = {}
        index: dict[str, tuple[int, str]] = {}
        for relative, mode in modes.items():
            content = (root / relative).read_bytes()
            object_id = hashlib.sha1(relative.encode() + b"\0" + content).hexdigest()
            blobs[object_id] = content
            index[relative] = (mode, object_id)
        return root, index, blobs

    def capture(
        self,
        root: Path,
        index: dict[str, tuple[int, str]],
        blobs: dict[str, bytes],
        **extra_patches,
    ):
        revision = extra_patches.pop("final_revision", REVISION)
        clean = extra_patches.pop("final_clean", True)
        def blob_result(object_id: str):
            content = blobs.get(object_id)
            return (
                (content, None)
                if content is not None
                else (None, "git_blob_read_failed")
            )
        with (
            mock.patch.object(installer, "REPO_ROOT", root),
            mock.patch.object(installer, "git_index_entries", return_value=(index, None)),
            mock.patch.object(installer, "read_git_blob", side_effect=blob_result),
            mock.patch.object(installer, "checkout_revision", return_value=revision),
            mock.patch.object(installer, "checkout_clean", return_value=clean),
        ):
            return installer.capture_verified_source(
                "0.3.0-rc.4", REVISION, True
            )

    def test_manifest_and_git_inventory_capture_exact_bytes(self) -> None:
        root, index, blobs = self.make_checkout()
        source, errors = self.capture(root, index, blobs)
        self.assertEqual(errors, [])
        assert source is not None
        self.assertEqual(set(source.files), {"VERSION", "scripts/tool.py"})
        self.assertEqual(source.modes, {"VERSION": 0o100644, "scripts/tool.py": 0o100644})

    def test_missing_manifest_is_fatal(self) -> None:
        root, index, blobs = self.make_checkout()
        (root / installer.PACKAGE_MANIFEST_NAME).unlink()
        source, errors = self.capture(root, index, blobs)
        self.assertIsNone(source)
        self.assertEqual(errors, ["checkout_differs_from_git_index"])

    def test_bad_hash_is_fatal(self) -> None:
        root, index, blobs = self.make_checkout(bad_hash=True)
        source, errors = self.capture(root, index, blobs)
        self.assertIsNone(source)
        self.assertEqual(errors, ["package_manifest_hash_mismatch"])

    def test_manifest_omitting_tracked_publishable_file_is_fatal(self) -> None:
        root, index, blobs = self.make_checkout(omit_tracked=True)
        source, errors = self.capture(root, index, blobs)
        self.assertIsNone(source)
        self.assertEqual(errors, ["package_manifest_git_inventory_mismatch"])

    def test_manifest_unsafe_path_is_fatal(self) -> None:
        root, index, blobs = self.make_checkout(unsafe_entry=True)
        source, errors = self.capture(root, index, blobs)
        self.assertIsNone(source)
        self.assertEqual(errors, ["package_manifest_entry_invalid"])

    def test_ignored_or_untracked_file_is_never_captured(self) -> None:
        root, index, blobs = self.make_checkout()
        (root / "ignored-secret.txt").write_text("do not copy", encoding="utf-8")
        source, errors = self.capture(root, index, blobs)
        self.assertEqual(errors, [])
        assert source is not None
        self.assertNotIn("ignored-secret.txt", source.files)

    def test_checkout_change_during_capture_is_fatal(self) -> None:
        root, index, blobs = self.make_checkout()
        source, errors = self.capture(
            root, index, blobs, final_revision="b" * 40
        )
        self.assertIsNone(source)
        self.assertEqual(errors, ["checkout_changed_during_source_capture"])

    def test_symlink_mode_in_publishable_inventory_is_fatal(self) -> None:
        root, index, blobs = self.make_checkout()
        _mode, object_id = index["scripts/tool.py"]
        index["scripts/tool.py"] = (0o120000, object_id)
        source, errors = self.capture(root, index, blobs)
        self.assertIsNone(source)
        self.assertEqual(errors, ["package_source_unsupported_git_mode"])

    def test_assume_unchanged_and_skip_worktree_cannot_hide_modified_bytes(self) -> None:
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "scripts").mkdir()
                (root / "VERSION").write_text("0.3.0-rc.4\n", encoding="utf-8")
                original_tool = b"print('committed')\n"
                (root / "scripts" / "tool.py").write_bytes(original_tool)
                original_manifest = {
                    "schema_version": 1,
                    "version": "0.3.0-rc.4",
                    "files": {
                        "VERSION": hashlib.sha256(b"0.3.0-rc.4\n").hexdigest(),
                        "scripts/tool.py": hashlib.sha256(original_tool).hexdigest(),
                    },
                }
                (root / installer.PACKAGE_MANIFEST_NAME).write_text(
                    json.dumps(original_manifest, sort_keys=True), encoding="utf-8"
                )
                for argv in (
                    ["git", "init", "-q"],
                    ["git", "config", "core.autocrlf", "false"],
                    ["git", "config", "user.name", "ACGM Test"],
                    ["git", "config", "user.email", "acgm-test@example.invalid"],
                    ["git", "add", "."],
                    ["git", "commit", "-q", "-m", "fixture"],
                    [
                        "git",
                        "update-index",
                        flag,
                        installer.PACKAGE_MANIFEST_NAME,
                        "scripts/tool.py",
                    ],
                ):
                    subprocess.run(argv, cwd=root, check=True)

                modified_tool = b"print('uncommitted')\n"
                (root / "scripts" / "tool.py").write_bytes(modified_tool)
                modified_manifest = {
                    **original_manifest,
                    "files": {
                        **original_manifest["files"],
                        "scripts/tool.py": hashlib.sha256(modified_tool).hexdigest(),
                    },
                }
                (root / installer.PACKAGE_MANIFEST_NAME).write_text(
                    json.dumps(modified_manifest, sort_keys=True), encoding="utf-8"
                )
                status = subprocess.run(
                    ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                    cwd=root,
                    check=True,
                    stdout=subprocess.PIPE,
                    encoding="utf-8",
                )
                self.assertEqual(status.stdout, "")

                with mock.patch.object(installer, "REPO_ROOT", root):
                    revision = installer.checkout_revision()
                    clean = installer.checkout_clean()
                    assert revision is not None
                    source, errors = installer.capture_verified_source(
                        "0.3.0-rc.4", revision, bool(clean)
                    )
                self.assertIsNone(source)
                self.assertEqual(errors, ["checkout_differs_from_git_index"])

    def test_git_replace_cannot_substitute_index_blob_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            version_bytes = b"0.3.0-rc.4\n"
            original_tool = b"print('committed')\n"
            (root / "VERSION").write_bytes(version_bytes)
            (root / "scripts" / "tool.py").write_bytes(original_tool)
            original_manifest = {
                "schema_version": 1,
                "version": "0.3.0-rc.4",
                "files": {
                    "VERSION": hashlib.sha256(version_bytes).hexdigest(),
                    "scripts/tool.py": hashlib.sha256(original_tool).hexdigest(),
                },
            }
            manifest_path = root / installer.PACKAGE_MANIFEST_NAME
            manifest_path.write_text(
                json.dumps(original_manifest, sort_keys=True), encoding="utf-8"
            )
            for argv in (
                ["git", "init", "-q"],
                ["git", "config", "core.autocrlf", "false"],
                ["git", "config", "user.name", "ACGM Test"],
                ["git", "config", "user.email", "acgm-test@example.invalid"],
                ["git", "add", "."],
                ["git", "commit", "-q", "-m", "fixture"],
            ):
                subprocess.run(argv, cwd=root, check=True)

            def git_text(*args: str) -> str:
                return subprocess.run(
                    ["git", *args],
                    cwd=root,
                    check=True,
                    stdout=subprocess.PIPE,
                    encoding="utf-8",
                ).stdout.strip()

            def write_blob(content: bytes) -> str:
                return subprocess.run(
                    ["git", "hash-object", "-w", "--stdin"],
                    cwd=root,
                    check=True,
                    input=content,
                    stdout=subprocess.PIPE,
                ).stdout.decode("ascii").strip()

            original_tool_object = git_text("rev-parse", ":scripts/tool.py")
            original_manifest_object = git_text(
                "rev-parse", f":{installer.PACKAGE_MANIFEST_NAME}"
            )
            replacement_tool = b"print('replacement')\n"
            replacement_manifest = {
                **original_manifest,
                "files": {
                    **original_manifest["files"],
                    "scripts/tool.py": hashlib.sha256(replacement_tool).hexdigest(),
                },
            }
            replacement_manifest_bytes = json.dumps(
                replacement_manifest, sort_keys=True
            ).encode()
            subprocess.run(
                ["git", "replace", original_tool_object, write_blob(replacement_tool)],
                cwd=root,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "replace",
                    original_manifest_object,
                    write_blob(replacement_manifest_bytes),
                ],
                cwd=root,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "update-index",
                    "--assume-unchanged",
                    installer.PACKAGE_MANIFEST_NAME,
                    "scripts/tool.py",
                ],
                cwd=root,
                check=True,
            )
            (root / "scripts" / "tool.py").write_bytes(replacement_tool)
            manifest_path.write_bytes(replacement_manifest_bytes)
            self.assertEqual(git_text("status", "--porcelain=v1"), "")

            with mock.patch.object(installer, "REPO_ROOT", root):
                revision = installer.checkout_revision()
                clean = installer.checkout_clean()
                assert revision is not None
                source, errors = installer.capture_verified_source(
                    "0.3.0-rc.4", revision, bool(clean)
                )
            self.assertIsNone(source)
            self.assertEqual(errors, ["checkout_differs_from_git_index"])

    def test_inherited_git_environment_cannot_redirect_repository_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            checkout = base / "checkout"
            decoy = base / "decoy"

            def initialize_repository(root: Path, tool_bytes: bytes) -> str:
                (root / "scripts").mkdir(parents=True)
                version_bytes = b"0.3.0-rc.4\n"
                (root / "VERSION").write_bytes(version_bytes)
                (root / "scripts" / "tool.py").write_bytes(tool_bytes)
                manifest = {
                    "schema_version": 1,
                    "version": "0.3.0-rc.4",
                    "files": {
                        "VERSION": hashlib.sha256(version_bytes).hexdigest(),
                        "scripts/tool.py": hashlib.sha256(tool_bytes).hexdigest(),
                    },
                }
                (root / installer.PACKAGE_MANIFEST_NAME).write_text(
                    json.dumps(manifest, sort_keys=True), encoding="utf-8"
                )
                for argv in (
                    ["git", "init", "-q"],
                    ["git", "config", "core.autocrlf", "false"],
                    ["git", "config", "user.name", "ACGM Test"],
                    ["git", "config", "user.email", "acgm-test@example.invalid"],
                    ["git", "add", "."],
                    ["git", "commit", "-q", "-m", "fixture"],
                ):
                    subprocess.run(argv, cwd=root, check=True)
                return subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=root,
                    check=True,
                    stdout=subprocess.PIPE,
                    encoding="ascii",
                ).stdout.strip()

            committed_tool = b"print('checkout')\n"
            decoy_tool = b"print('decoy')\n"
            checkout_revision = initialize_repository(checkout, committed_tool)
            decoy_revision = initialize_repository(decoy, decoy_tool)
            self.assertNotEqual(checkout_revision, decoy_revision)

            # Make the real checkout's working tree look exactly like the decoy.
            # An inherited GIT_DIR/GIT_WORK_TREE pair would otherwise make all
            # identity and index reads silently target the decoy repository.
            (checkout / "scripts" / "tool.py").write_bytes(decoy_tool)
            decoy_manifest = {
                "schema_version": 1,
                "version": "0.3.0-rc.4",
                "files": {
                    "VERSION": hashlib.sha256(b"0.3.0-rc.4\n").hexdigest(),
                    "scripts/tool.py": hashlib.sha256(decoy_tool).hexdigest(),
                },
            }
            (checkout / installer.PACKAGE_MANIFEST_NAME).write_text(
                json.dumps(decoy_manifest, sort_keys=True), encoding="utf-8"
            )

            hostile_environment = {
                "GIT_DIR": str(decoy / ".git"),
                "GIT_WORK_TREE": str(checkout),
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.ignorecase",
                "GIT_CONFIG_VALUE_0": "true",
            }
            with (
                mock.patch.dict(os.environ, hostile_environment, clear=False),
                mock.patch.object(installer, "REPO_ROOT", checkout),
            ):
                environment = installer.git_identity_environment()
                self.assertNotIn("GIT_DIR", environment)
                self.assertNotIn("GIT_WORK_TREE", environment)
                self.assertNotIn("GIT_CONFIG_COUNT", environment)
                self.assertNotIn("GIT_CONFIG_KEY_0", environment)
                self.assertNotIn("GIT_CONFIG_VALUE_0", environment)
                self.assertEqual(environment["GIT_NO_REPLACE_OBJECTS"], "1")
                revision = installer.checkout_revision()
                clean = installer.checkout_clean()
                source, errors = installer.capture_verified_source(
                    "0.3.0-rc.4", checkout_revision, True
                )

            self.assertEqual(revision, checkout_revision)
            self.assertFalse(clean)
            self.assertIsNone(source)
            self.assertEqual(errors, ["checkout_differs_from_git_index"])


class SnapshotTests(unittest.TestCase):
    def make_snapshot_root(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="acgm-snapshot-test-"))
        self.addCleanup(shutil.rmtree, root, True)
        self.addCleanup(installer._make_tree_writable, root)
        return root / "snapshots"

    def materialize_cache(self, root: Path, source: installer.VerifiedSource) -> None:
        for relative, content in source.expected_files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            os.chmod(path, installer._expected_mode(source, relative))

    def test_snapshot_is_exact_persistent_and_reusable(self) -> None:
        source = fixture_source()
        base = self.make_snapshot_root()
        with mock.patch.object(installer, "snapshot_base_directory", return_value=base):
            path, created, error = installer.create_or_verify_snapshot(source)
            self.assertIsNone(error)
            self.assertTrue(created)
            assert path is not None
            self.assertFalse((path / "ignored-secret.txt").exists())
            reused, created_again, second_error = installer.create_or_verify_snapshot(source)
        self.assertEqual(reused, path)
        self.assertFalse(created_again)
        self.assertIsNone(second_error)

    def test_legacy_snapshot_capture_reconstructs_verified_acgm_identity(self) -> None:
        source = fixture_source("0.3.0-rc.3", "b" * 40)
        base = self.make_snapshot_root()
        with mock.patch.object(installer, "snapshot_base_directory", return_value=base):
            path, _, error = installer.create_or_verify_snapshot(source)
            self.assertIsNone(error)
            assert path is not None
            captured, errors = installer.capture_verified_snapshot(path)

        self.assertEqual(errors, [])
        self.assertIsNotNone(captured)
        assert captured is not None
        self.assertEqual(captured.version, "0.3.0-rc.3")
        self.assertEqual(captured.expected_files, source.expected_files)

    def test_legacy_snapshot_capture_rejects_tampered_bytes(self) -> None:
        source = fixture_source("0.3.0-rc.3", "b" * 40)
        base = self.make_snapshot_root()
        with mock.patch.object(installer, "snapshot_base_directory", return_value=base):
            path, _, _ = installer.create_or_verify_snapshot(source)
            assert path is not None
            os.chmod(path / "README.md", 0o600)
            (path / "README.md").write_text("tampered", encoding="utf-8")
            captured, errors = installer.capture_verified_snapshot(path)

        self.assertIsNone(captured)
        self.assertIn("legacy_snapshot_content_hash_mismatch", errors)

    def test_upgrade_version_order_is_strict_semver(self) -> None:
        self.assertTrue(
            installer.version_is_strictly_older("0.3.0-rc.3", "0.3.0-rc.4")
        )
        self.assertTrue(installer.version_is_strictly_older("0.3.0-rc.4", "0.3.0"))
        self.assertFalse(
            installer.version_is_strictly_older("0.3.0-rc.4", "0.3.0-rc.4")
        )
        self.assertFalse(
            installer.version_is_strictly_older("0.4.0", "0.3.0-rc.4")
        )

    def test_tampered_snapshot_is_rejected_not_overwritten(self) -> None:
        source = fixture_source()
        base = self.make_snapshot_root()
        with mock.patch.object(installer, "snapshot_base_directory", return_value=base):
            path, _, _ = installer.create_or_verify_snapshot(source)
            assert path is not None
            os.chmod(path / "README.md", 0o600)
            (path / "README.md").write_text("tampered", encoding="utf-8")
            reused, created, error = installer.create_or_verify_snapshot(source)
        self.assertIsNone(reused)
        self.assertFalse(created)
        self.assertEqual(error, "verified_tree_content_mismatch")

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows")
    def test_symlink_snapshot_target_is_rejected(self) -> None:
        source = fixture_source()
        base = self.make_snapshot_root()
        base.mkdir(parents=True)
        destination = base / source.snapshot_name
        destination.symlink_to(base)
        with mock.patch.object(installer, "snapshot_base_directory", return_value=base):
            path, created, error = installer.create_or_verify_snapshot(source)
        self.assertIsNone(path)
        self.assertFalse(created)
        self.assertEqual(error, "snapshot_target_unsafe")

    def test_cache_allows_only_known_management_directory(self) -> None:
        source = fixture_source()
        root = self.make_snapshot_root() / "cache"
        root.mkdir(parents=True)
        self.materialize_cache(root, source)
        (root / ".in_use").mkdir()
        (root / ".in_use" / "lock").write_text("runtime", encoding="utf-8")
        verified, error = installer.verify_materialized_tree(
            root, source, allow_cache_management=True
        )
        self.assertTrue(verified)
        self.assertIsNone(error)
        (root / "unexpected.txt").write_text("unexpected", encoding="utf-8")
        verified, error = installer.verify_materialized_tree(
            root, source, allow_cache_management=True
        )
        self.assertFalse(verified)
        self.assertEqual(error, "verified_tree_inventory_mismatch")

    def test_verified_installed_plugin_requires_scope_version_enabled_and_cache(self) -> None:
        source = fixture_source()
        cache = self.make_snapshot_root() / "cache"
        cache.mkdir(parents=True)
        self.materialize_cache(cache, source)
        record = {
            "_key": installer.PLUGIN_ID,
            "scope": "user",
            "version": source.version,
            "enabled": True,
            "errors": [],
            "installPath": str(cache),
        }
        verified, errors = installer.verify_installed_plugin(record, source)
        self.assertTrue(verified)
        self.assertEqual(errors, [])

        record["scope"] = "project"
        verified, errors = installer.verify_installed_plugin(record, source)
        self.assertFalse(verified)
        self.assertIn("installed_plugin_scope_not_user", errors)

        record["scope"] = "user"
        record["marketplace"] = "different-marketplace"
        verified, errors = installer.verify_installed_plugin(record, source)
        self.assertFalse(verified)
        self.assertIn("installed_plugin_marketplace_identity_mismatch", errors)

    def test_missing_install_path_or_wrong_cached_bytes_is_fatal(self) -> None:
        source = fixture_source()
        record = {
            "_key": installer.PLUGIN_ID,
            "scope": "user",
            "version": source.version,
            "enabled": True,
            "errors": [],
        }
        verified, errors = installer.verify_installed_plugin(record, source)
        self.assertFalse(verified)
        self.assertIn("installed_plugin_cache_path_missing", errors)

        cache = self.make_snapshot_root() / "cache"
        cache.mkdir(parents=True)
        self.materialize_cache(cache, source)
        (cache / "README.md").write_text("wrong", encoding="utf-8")
        record["installPath"] = str(cache)
        verified, errors = installer.verify_installed_plugin(record, source)
        self.assertFalse(verified)
        self.assertIn("verified_tree_content_mismatch", errors)

    def test_installed_cache_in_use_marker_blocks_upgrade_gate(self) -> None:
        cache = self.make_snapshot_root() / "cache-in-use"
        cache.mkdir(parents=True)
        record = {"installPath": str(cache)}
        in_use, error = installer.installed_plugin_in_use(record)
        self.assertFalse(in_use)
        self.assertIsNone(error)
        (cache / ".in_use").mkdir()
        in_use, error = installer.installed_plugin_in_use(record)
        self.assertTrue(in_use)
        self.assertIsNone(error)


class PluginDataBackupTests(unittest.TestCase):
    def make_roots(self) -> tuple[Path, Path, Path]:
        root = Path(tempfile.mkdtemp(prefix="acgm-plugin-data-test-"))
        self.addCleanup(shutil.rmtree, root, True)
        data = root / "config" / "plugins" / "data" / installer.PLUGIN_DATA_KEY
        backups = root / "backups"
        return root, data, backups

    def make_private_data(self, data: Path) -> bytes:
        marker = b'{"event":"preserve-me"}\n'
        (data / "locks").mkdir(parents=True, mode=0o700)
        os.chmod(data, 0o700)
        os.chmod(data / "locks", 0o700)
        (data / "events.jsonl").write_bytes(marker)
        (data / "locks" / "events.lock").write_bytes(b"")
        os.chmod(data / "events.jsonl", 0o600)
        os.chmod(data / "locks" / "events.lock", 0o600)
        return marker

    def test_private_ledger_backup_survives_removal_and_restores_exactly(self) -> None:
        _root, data, backups = self.make_roots()
        marker = self.make_private_data(data)
        with (
            mock.patch.object(installer, "plugin_data_path", return_value=data),
            mock.patch.object(
                installer,
                "plugin_data_backup_base_directory",
                return_value=backups,
            ),
        ):
            backup, error = installer.prepare_plugin_data_backup()
            self.assertIsNone(error)
            assert backup is not None
            self.assertTrue(backup.existed)
            installer._remove_private_tree(data)
            unchanged, unchanged_error = installer.plugin_data_unchanged(backup)
            self.assertFalse(unchanged)
            self.assertEqual(unchanged_error, "plugin_data_changed_during_upgrade")
            transition_safe, transition_error = installer.plugin_data_transition_safe(
                backup
            )
            self.assertTrue(transition_safe, transition_error)
            restored, restore_error = installer.restore_plugin_data(backup)
            self.assertTrue(restored, restore_error)
            self.assertEqual((data / "events.jsonl").read_bytes(), marker)
            cleanup_ok, cleanup_error = installer.cleanup_plugin_data_backup(backup)

        self.assertTrue(cleanup_ok, cleanup_error)
        self.assertFalse(backups.exists() and any(backups.iterdir()))

    def test_absent_ledger_is_recorded_without_creating_data(self) -> None:
        _root, data, backups = self.make_roots()
        with (
            mock.patch.object(installer, "plugin_data_path", return_value=data),
            mock.patch.object(
                installer,
                "plugin_data_backup_base_directory",
                return_value=backups,
            ),
        ):
            backup, error = installer.prepare_plugin_data_backup()
            self.assertIsNone(error)
            assert backup is not None
            self.assertFalse(backup.existed)
            self.assertIsNone(backup.backup_path)
            restored, restore_error = installer.restore_plugin_data(backup)
        self.assertTrue(restored, restore_error)
        self.assertFalse(data.exists())

    @unittest.skipIf(os.name == "nt", "symlink permissions are platform-specific")
    def test_symlinked_plugin_data_is_rejected_before_backup(self) -> None:
        root, data, backups = self.make_roots()
        target = root / "target"
        target.mkdir()
        data.parent.mkdir(parents=True)
        data.symlink_to(target, target_is_directory=True)
        with (
            mock.patch.object(installer, "plugin_data_path", return_value=data),
            mock.patch.object(
                installer,
                "plugin_data_backup_base_directory",
                return_value=backups,
            ),
        ):
            backup, error = installer.prepare_plugin_data_backup()
        self.assertIsNone(backup)
        self.assertEqual(error, "plugin_data_path_unsafe")

    @unittest.skipIf(os.name == "nt", "POSIX privacy modes are not portable")
    def test_non_private_plugin_data_is_rejected(self) -> None:
        _root, data, backups = self.make_roots()
        self.make_private_data(data)
        os.chmod(data / "events.jsonl", 0o644)
        with (
            mock.patch.object(installer, "plugin_data_path", return_value=data),
            mock.patch.object(
                installer,
                "plugin_data_backup_base_directory",
                return_value=backups,
            ),
        ):
            backup, error = installer.prepare_plugin_data_backup()
        self.assertIsNone(backup)
        self.assertEqual(error, "plugin_data_permissions_not_private")

    def test_changed_restore_target_is_not_overwritten(self) -> None:
        _root, data, backups = self.make_roots()
        self.make_private_data(data)
        with (
            mock.patch.object(installer, "plugin_data_path", return_value=data),
            mock.patch.object(
                installer,
                "plugin_data_backup_base_directory",
                return_value=backups,
            ),
        ):
            backup, error = installer.prepare_plugin_data_backup()
            self.assertIsNone(error)
            assert backup is not None
            (data / "events.jsonl").write_bytes(b"changed concurrently\n")
            os.chmod(data / "events.jsonl", 0o600)
            restored, restore_error = installer.restore_plugin_data(backup)
            installer.cleanup_plugin_data_backup(backup)
        self.assertFalse(restored)
        self.assertEqual(
            restore_error, "plugin_data_restore_target_not_empty_or_exact"
        )

    def test_plugin_data_size_limit_blocks_before_copy(self) -> None:
        _root, data, backups = self.make_roots()
        self.make_private_data(data)
        with (
            mock.patch.object(installer, "plugin_data_path", return_value=data),
            mock.patch.object(
                installer,
                "plugin_data_backup_base_directory",
                return_value=backups,
            ),
            mock.patch.object(installer, "MAX_PLUGIN_DATA_BYTES", 1),
        ):
            backup, error = installer.prepare_plugin_data_backup()
        self.assertIsNone(backup)
        self.assertEqual(error, "plugin_data_size_limit_exceeded")

    def test_backup_cleanup_failure_is_detected(self) -> None:
        _root, data, backups = self.make_roots()
        self.make_private_data(data)
        with (
            mock.patch.object(installer, "plugin_data_path", return_value=data),
            mock.patch.object(
                installer,
                "plugin_data_backup_base_directory",
                return_value=backups,
            ),
        ):
            backup, error = installer.prepare_plugin_data_backup()
            self.assertIsNone(error)
            assert backup is not None
            with mock.patch.object(installer, "_remove_private_tree"):
                cleanup_ok, cleanup_error = installer.cleanup_plugin_data_backup(
                    backup
                )
            installer._remove_private_tree(backup.backup_path.parent)
        self.assertFalse(cleanup_ok)
        self.assertEqual(cleanup_error, "plugin_data_backup_cleanup_failed")


class SchemaAndCommandTests(unittest.TestCase):
    def test_neutral_cwd_allows_user_home_settings_but_rejects_project_ancestors(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="acgm-neutral-cwd-test-"))
        self.addCleanup(shutil.rmtree, root, True)
        home = root / "home"
        neutral = home / "AppData" / "Local" / "Temp" / "isolated"
        neutral.mkdir(parents=True)
        (home / ".claude").mkdir()
        (home / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
        unrelated_repo = root / "repo"
        unrelated_repo.mkdir()

        with (
            mock.patch.object(installer.Path, "home", return_value=home),
            mock.patch.object(installer, "REPO_ROOT", unrelated_repo),
        ):
            self.assertTrue(installer.neutral_claude_cwd_is_safe(neutral))
            project_parent = neutral.parent
            (project_parent / ".claude").mkdir()
            (project_parent / ".claude" / "settings.local.json").write_text(
                "{}", encoding="utf-8"
            )
            self.assertFalse(installer.neutral_claude_cwd_is_safe(neutral))
            (project_parent / ".claude" / "settings.local.json").unlink()
            (project_parent / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
            self.assertFalse(installer.neutral_claude_cwd_is_safe(neutral))

    def test_user_marketplace_declaration_distinguishes_absent_exact_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "settings.json"
            with mock.patch.dict(
                os.environ, {"CLAUDE_CONFIG_DIR": directory}, clear=False
            ):
                state, error = installer.user_marketplace_declaration(SNAPSHOT)
                self.assertEqual(state, "absent")
                self.assertIsNone(error)

                settings.write_text(
                    json.dumps(
                        {
                            "extraKnownMarketplaces": {
                                installer.MARKETPLACE_NAME: {
                                    "source": {
                                        "source": "directory",
                                        "path": str(SNAPSHOT),
                                    }
                                }
                            }
                        }
                    ),
                    encoding="utf-8",
                )
                state, error = installer.user_marketplace_declaration(SNAPSHOT)
                self.assertEqual(state, "exact")
                self.assertIsNone(error)

                settings.write_text(
                    json.dumps(
                        {
                            "extraKnownMarketplaces": {
                                installer.MARKETPLACE_NAME: {
                                    "source": {
                                        "source": "directory",
                                        "path": "/different/source",
                                    }
                                }
                            }
                        }
                    ),
                    encoding="utf-8",
                )
                state, error = installer.user_marketplace_declaration(SNAPSHOT)
                self.assertEqual(state, "conflict")
                self.assertIsNone(error)

    def test_user_marketplace_declaration_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "settings.json"
            settings.write_text(
                (
                    '{"extraKnownMarketplaces":{'
                    f'"{installer.MARKETPLACE_NAME}":{{"source":{{"source":"github","repo":"one/repo"}}}},'
                    f'"{installer.MARKETPLACE_NAME}":{{"source":{{"source":"github","repo":"two/repo"}}}}'
                    "}}"
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ, {"CLAUDE_CONFIG_DIR": directory}, clear=False
            ):
                declaration, state, error = (
                    installer.raw_user_marketplace_declaration()
                )
        self.assertIsNone(declaration)
        self.assertEqual(state, "unknown")
        self.assertEqual(error, "user_settings_duplicate_key")

    def test_full_ledger_report_limit_includes_more_than_default_twenty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_root = Path(directory)
            events = [
                {
                    "schema_version": 1,
                    "event_id": f"evt_{index:032x}",
                    "session_id": f"ses_{index:032x}",
                    "event_type": "health",
                    "status": "healthy",
                }
                for index in range(25)
            ]
            (data_root / "events.jsonl").write_text(
                "".join(
                    json.dumps(event, separators=(",", ":")) + "\n"
                    for event in events
                ),
                encoding="utf-8",
            )
            report_argv = [
                sys.executable,
                str(SCRIPTS / "acgm_runtime.py"),
                "report",
                "--project",
                "all",
                "--limit",
                installer.FULL_LEDGER_REPORT_LIMIT,
                "--json",
            ]
            run_environment = {**os.environ, "ACGM_DATA_DIR": directory}
            completed = subprocess.run(
                report_argv,
                cwd=REPO_ROOT,
                env=run_environment,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
            )
            repeated = subprocess.run(
                report_argv,
                cwd=REPO_ROOT,
                env=run_environment,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(len(payload["events"]), 25)
        self.assertEqual(
            hashlib.sha256(completed.stdout.encode()).hexdigest(),
            hashlib.sha256(repeated.stdout.encode()).hexdigest(),
        )

    def test_marketplace_parser_rejects_error_object(self) -> None:
        records, error = installer.parse_marketplace_payload({"error": "denied"})
        self.assertIsNone(records)
        self.assertEqual(error, "unexpected_marketplace_json_shape")

    def test_marketplace_parser_rejects_mixed_error_envelope(self) -> None:
        records, error = installer.parse_marketplace_payload(
            {"marketplaces": [], "error": "denied"}
        )
        self.assertIsNone(records)
        self.assertEqual(error, "unexpected_marketplace_json_shape")

    def test_plugin_wrapper_and_unknown_version_are_fail_closed(self) -> None:
        payload = {
            "version": 2,
            "plugins": {
                installer.PLUGIN_ID: [
                    {
                        "scope": "user",
                        "version": "0.3.0-rc.4",
                    }
                ]
            },
        }
        records, error = installer.parse_plugin_payload(payload)
        self.assertIsNone(records)
        self.assertEqual(error, "unexpected_plugin_json_shape")
        records, error = installer.parse_plugin_payload(
            {"version": 999, "plugins": {}}
        )
        self.assertIsNone(records)
        self.assertEqual(error, "unexpected_plugin_json_shape")

    def test_plugin_parser_rejects_unknown_root_fields(self) -> None:
        records, error = installer.parse_plugin_payload(
            {"version": 2, "plugins": {}, "error": "future"}
        )
        self.assertIsNone(records)
        self.assertEqual(error, "unexpected_plugin_json_shape")

    def test_marketplace_source_uses_only_authoritative_path_fields(self) -> None:
        wrong_top_level = {
            "name": installer.MARKETPLACE_NAME,
            "source": {"source": "directory", "path": "/different/source"},
            "location": str(SNAPSHOT),
        }
        wrong_nested_metadata = {
            "name": installer.MARKETPLACE_NAME,
            "source": "directory",
            "path": "/different/source",
            "metadata": {"directory": str(SNAPSHOT)},
        }
        self.assertFalse(
            installer.marketplace_source_matches(wrong_top_level, SNAPSHOT)
        )
        self.assertFalse(
            installer.marketplace_source_matches(wrong_nested_metadata, SNAPSHOT)
        )
        self.assertTrue(
            installer.marketplace_source_matches(
                {
                    "name": installer.MARKETPLACE_NAME,
                    "source": "directory",
                    "path": str(SNAPSHOT),
                },
                SNAPSHOT,
            )
        )

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows")
    def test_marketplace_source_does_not_accept_symlink_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "snapshot"
            target.mkdir()
            alias = root / "alias"
            alias.symlink_to(target, target_is_directory=True)
            record = {
                "name": installer.MARKETPLACE_NAME,
                "source": "directory",
                "path": str(alias),
            }
            self.assertFalse(
                installer.marketplace_source_matches(record, target)
            )
        self.assertTrue(
            installer.marketplace_source_matches(
                {
                    "source": {
                        "source": "directory",
                        "path": str(SNAPSHOT),
                    }
                },
                SNAPSHOT,
            )
        )

    def test_command_display_redacts_checkout_snapshot_and_launcher(self) -> None:
        displayed = installer.display_argv(
            [str(CLAUDE), "plugin", "marketplace", "add", str(SNAPSHOT), str(installer.REPO_ROOT)],
            claude_executable=str(CLAUDE),
            materialized=SNAPSHOT,
        )
        self.assertEqual(displayed[0], "claude")
        self.assertIn("VERIFIED_SNAPSHOT", displayed)
        self.assertIn("LOCAL_CHECKOUT", displayed)
        serialized = json.dumps(displayed)
        self.assertNotIn(str(SNAPSHOT), serialized)
        self.assertNotIn(str(CLAUDE), serialized)

    def test_run_command_never_uses_a_shell(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[str(CLAUDE), "--version"],
            returncode=0,
            stdout="2.1.119\n",
            stderr="",
        )
        with mock.patch.object(installer.subprocess, "run", return_value=completed) as run:
            result = installer.run_command([str(CLAUDE), "--version"], timeout=1)
        self.assertEqual(result.returncode, 0)
        _, kwargs = run.call_args
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(run.call_args.args[0], [str(CLAUDE), "--version"])


if __name__ == "__main__":
    unittest.main()
