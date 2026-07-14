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
CLAUDE = Path("/native/claude")
SNAPSHOT = Path("/private/acgm/verified-snapshot")


def ready_report() -> dict[str, object]:
    return {
        "schema_version": 1,
        "acgm_version": "0.3.0-rc.3",
        "status": "READY_FOR_RC_TEST",
        "error_codes": [],
    }


def command_json(value) -> installer.CommandResult:
    return installer.CommandResult(0, stdout=json.dumps(value))


def fixture_source() -> installer.VerifiedSource:
    files = {
        "VERSION": b"0.3.0-rc.3\n",
        "bin/acgm": b"#!/bin/sh\nexit 0\n",
        "README.md": b"fixture\n",
    }
    manifest = {
        "schema_version": 1,
        "version": "0.3.0-rc.3",
        "files": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(files.items())
        },
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    return installer.VerifiedSource(
        revision=REVISION,
        version="0.3.0-rc.3",
        manifest_bytes=manifest_bytes,
        manifest_digest=hashlib.sha256(manifest_bytes).hexdigest(),
        files=files,
        modes={"VERSION": 0o100644, "bin/acgm": 0o100755, "README.md": 0o100644},
    )


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
        version="0.3.0-rc.3",
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

    def test_preflight_blocked_never_captures_or_mutates(self) -> None:
        report = ready_report()
        report["status"] = "BLOCKED"
        report["error_codes"] = ["git_missing_or_unusable"]
        with (
            mock.patch.object(installer.preflight, "build_report", return_value=report),
            mock.patch.object(installer, "checkout_revision", return_value=REVISION),
            mock.patch.object(installer, "checkout_clean", return_value=True),
            mock.patch.object(installer, "capture_verified_source") as capture,
            mock.patch.object(installer, "run_command") as runner,
        ):
            exit_code, result = installer.install()
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "PREFLIGHT_BLOCKED")
        capture.assert_not_called()
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
        self.assertEqual(result["status"], "DRY_RUN_READY")
        self.assertFalse(result["changed"])
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
        self.assertEqual(result["status"], "INSTALLED")
        self.assertTrue(result["ok"])
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
        self.assertEqual(result["status"], "INSTALLED")
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
        self.assertEqual(result["status"], "INSTALLED")
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
        self.assertEqual(result["status"], "ALREADY_INSTALLED_VERIFIED")
        self.assertTrue(result["ok"])
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
        self.assertEqual(result["status"], "INSTALLED")
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
        self.assertEqual(result["status"], "INSTALLED")
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
            "VERSION": b"0.3.0-rc.3\n",
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
            "version": "0.3.0-rc.3",
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
                "0.3.0-rc.3", REVISION, True
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
                (root / "VERSION").write_text("0.3.0-rc.3\n", encoding="utf-8")
                original_tool = b"print('committed')\n"
                (root / "scripts" / "tool.py").write_bytes(original_tool)
                original_manifest = {
                    "schema_version": 1,
                    "version": "0.3.0-rc.3",
                    "files": {
                        "VERSION": hashlib.sha256(b"0.3.0-rc.3\n").hexdigest(),
                        "scripts/tool.py": hashlib.sha256(original_tool).hexdigest(),
                    },
                }
                (root / installer.PACKAGE_MANIFEST_NAME).write_text(
                    json.dumps(original_manifest, sort_keys=True), encoding="utf-8"
                )
                for argv in (
                    ["git", "init", "-q"],
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
                        "0.3.0-rc.3", revision, bool(clean)
                    )
                self.assertIsNone(source)
                self.assertEqual(errors, ["checkout_differs_from_git_index"])

    def test_git_replace_cannot_substitute_index_blob_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            version_bytes = b"0.3.0-rc.3\n"
            original_tool = b"print('committed')\n"
            (root / "VERSION").write_bytes(version_bytes)
            (root / "scripts" / "tool.py").write_bytes(original_tool)
            original_manifest = {
                "schema_version": 1,
                "version": "0.3.0-rc.3",
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
                    "0.3.0-rc.3", revision, bool(clean)
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
                version_bytes = b"0.3.0-rc.3\n"
                (root / "VERSION").write_bytes(version_bytes)
                (root / "scripts" / "tool.py").write_bytes(tool_bytes)
                manifest = {
                    "schema_version": 1,
                    "version": "0.3.0-rc.3",
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
                "version": "0.3.0-rc.3",
                "files": {
                    "VERSION": hashlib.sha256(b"0.3.0-rc.3\n").hexdigest(),
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
                    "0.3.0-rc.3", checkout_revision, True
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


class SchemaAndCommandTests(unittest.TestCase):
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
                        "version": "0.3.0-rc.3",
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
