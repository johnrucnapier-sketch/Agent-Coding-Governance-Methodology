#!/usr/bin/env python3
"""Conservative, surface-aware installer for a verified ACGM checkout.

The installer uses the documented Claude plugin CLI for Claude configuration
changes. It never edits Claude settings directly, initializes a project,
or treats a command exit code as proof that the requested plugin bytes were
installed. Marketplace replacement is disabled by default and exists only as
an explicit, strictly-forward transaction from a fully verified older ACGM
snapshot with keep-data uninstall, postcondition checks, and verified rollback.
Configuration verification is not reported as runtime hook activation.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Any, Callable, Sequence

import preflight


REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_NAME = "agent-coding-governance-methodology"
PLUGIN_NAME = "agent-coding-governance-methodology"
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"
INSPECT_TIMEOUT_SECONDS = 30
MUTATION_TIMEOUT_SECONDS = 180
GIT_COMMIT_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
GIT_OBJECT_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SAFE_VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
SNAPSHOT_SUFFIX_PATTERN = re.compile(r"^[0-9a-f]{12}$")
PACKAGE_MANIFEST_NAME = "PACKAGE_MANIFEST.json"
EXCLUDED_SOURCE_NAMES = {
    ".DS_Store",
    "BUILD_BRIEF.md",
    "PUBLISHING.md",
    PACKAGE_MANIFEST_NAME,
}
EXCLUDED_SOURCE_PARTS = {".git", ".claude", "__pycache__", "dist"}
CACHE_MANAGEMENT_PARTS = {".in_use"}
PLUGIN_DATA_KEY = re.sub(r"[^A-Za-z0-9_-]", "-", PLUGIN_ID)
PUBLIC_GITHUB_REPO = "johnrucnapier-sketch/Agent-Coding-Governance-Methodology"
LEGACY_PUBLIC_REFS = {None, "v0.3.0-rc.1"}
LEGACY_PUBLIC_VERSIONS = {"0.1.0", "0.3.0-rc.1"}
MAX_PLUGIN_DATA_FILES = 10_000
MAX_PLUGIN_DATA_BYTES = 256 * 1024 * 1024
FULL_LEDGER_REPORT_LIMIT = "9223372036854775807"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error_code: str | None = None


@dataclass(frozen=True)
class VerifiedSource:
    revision: str
    version: str
    manifest_bytes: bytes
    manifest_digest: str
    files: dict[str, bytes]
    modes: dict[str, int]

    @property
    def snapshot_name(self) -> str:
        return f"{self.version}-{self.revision[:12]}-{self.manifest_digest[:12]}"

    @property
    def expected_files(self) -> dict[str, bytes]:
        return {**self.files, PACKAGE_MANIFEST_NAME: self.manifest_bytes}


@dataclass(frozen=True)
class PrivateDataTree:
    files: dict[str, bytes]
    file_modes: dict[str, int]
    directory_modes: dict[str, int]


@dataclass(frozen=True)
class PluginDataBackup:
    data_path: Path
    existed: bool
    tree: PrivateDataTree | None
    backup_path: Path | None


def git_identity_environment() -> dict[str, str]:
    """Return an environment that cannot redirect identity reads to another repo."""

    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
    )
    return environment


def run_command(
    argv: Sequence[str],
    *,
    timeout: int,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> CommandResult:
    """Run one fixed argv without a shell and capture UTF-8 safely."""

    try:
        completed = subprocess.run(
            list(argv),
            check=False,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(cwd) if cwd is not None else None,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(124, timed_out=True, error_code="command_timeout")
    except OSError:
        return CommandResult(127, error_code="command_unavailable")
    return CommandResult(
        completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def checkout_revision() -> str | None:
    completed = run_command(
        ["git", "--no-replace-objects", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        timeout=5,
        env=git_identity_environment(),
    )
    value = completed.stdout.strip().casefold()
    return value if completed.returncode == 0 and GIT_COMMIT_PATTERN.fullmatch(value) else None


def checkout_clean() -> bool | None:
    """Return whether checkout, index, ignored rules, and untracked state agree."""

    completed = run_command(
        [
            "git",
            "--no-replace-objects",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.untrackedCache=false",
            "-C",
            str(REPO_ROOT),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        timeout=10,
        env=git_identity_environment(),
    )
    if completed.returncode != 0:
        return None
    return not bool(completed.stdout.strip())


def _safe_relative_path(value: str) -> PurePosixPath | None:
    if not value or "\\" in value or "\0" in value:
        return None
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        return None
    if candidate.as_posix() != value:
        return None
    return candidate


def _included_source_path(value: str) -> bool:
    candidate = _safe_relative_path(value)
    if candidate is None:
        return False
    if any(part in EXCLUDED_SOURCE_PARTS for part in candidate.parts):
        return False
    if candidate.name in EXCLUDED_SOURCE_NAMES or candidate.suffix == ".pyc":
        return False
    return True


def git_index_entries() -> tuple[dict[str, tuple[int, str]] | None, str | None]:
    """Read the exact stage-zero Git index inventory and executable modes."""

    try:
        completed = subprocess.run(
            [
                "git",
                "--no-replace-objects",
                "-C",
                str(REPO_ROOT),
                "ls-files",
                "--stage",
                "-z",
            ],
            check=False,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=git_identity_environment(),
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return None, "git_index_timeout"
    except OSError:
        return None, "git_index_unavailable"
    if completed.returncode != 0:
        return None, "git_index_command_failed"

    entries: dict[str, tuple[int, str]] = {}
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            metadata, raw_name = raw.split(b"\t", 1)
            mode_text, object_id, stage_text = metadata.decode("ascii").split()
            name = raw_name.decode("utf-8")
            mode = int(mode_text, 8)
            stage = int(stage_text)
        except (UnicodeDecodeError, ValueError):
            return None, "git_index_unexpected_record"
        object_id = object_id.casefold()
        if (
            stage != 0
            or name in entries
            or _safe_relative_path(name) is None
            or not GIT_OBJECT_PATTERN.fullmatch(object_id)
        ):
            return None, "git_index_unsafe_or_unmerged"
        entries[name] = (mode, object_id)
    return entries, None


def read_git_blob(object_id: str) -> tuple[bytes | None, str | None]:
    if not GIT_OBJECT_PATTERN.fullmatch(object_id):
        return None, "git_blob_object_id_invalid"
    try:
        completed = subprocess.run(
            [
                "git",
                "--no-replace-objects",
                "-C",
                str(REPO_ROOT),
                "cat-file",
                "blob",
                object_id,
            ],
            check=False,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=git_identity_environment(),
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return None, "git_blob_timeout"
    except OSError:
        return None, "git_blob_unavailable"
    if completed.returncode != 0:
        return None, "git_blob_read_failed"
    return completed.stdout, None


def read_regular_file(path: Path) -> tuple[bytes | None, str | None]:
    """Read one regular file without following a final-component symlink."""

    try:
        before = path.lstat()
    except OSError:
        return None, "file_unavailable"
    if not stat.S_ISREG(before.st_mode):
        return None, "file_not_regular"

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None, "file_open_failed"
    try:
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode):
            return None, "file_not_regular"
        if before.st_ino and current.st_ino and (
            before.st_dev != current.st_dev or before.st_ino != current.st_ino
        ):
            return None, "file_identity_changed"
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            content = handle.read()
        after = os.fstat(descriptor)
        if (
            current.st_size != after.st_size
            or current.st_mtime_ns != after.st_mtime_ns
            or current.st_ctime_ns != after.st_ctime_ns
        ):
            return None, "file_changed_while_reading"
        return content, None
    except OSError:
        return None, "file_read_failed"
    finally:
        os.close(descriptor)


def capture_verified_source(
    expected_version: str,
    initial_revision: str,
    initial_clean: bool,
) -> tuple[VerifiedSource | None, list[str]]:
    """Capture manifest-listed tracked bytes, then prove source did not drift."""

    if not initial_clean:
        return None, ["checkout_has_uncommitted_or_untracked_files"]
    if not SAFE_VERSION_PATTERN.fullmatch(expected_version):
        return None, ["package_version_unsafe_or_invalid"]

    index, index_error = git_index_entries()
    if index_error or index is None:
        return None, [index_error or "git_index_unavailable"]
    manifest_entry = index.get(PACKAGE_MANIFEST_NAME)
    if manifest_entry is None:
        return None, ["package_manifest_not_tracked"]
    manifest_mode, manifest_object = manifest_entry
    if manifest_mode != 0o100644:
        return None, ["package_manifest_unsupported_git_mode"]
    manifest_bytes, manifest_blob_error = read_git_blob(manifest_object)
    if manifest_blob_error or manifest_bytes is None:
        return None, ["package_manifest_git_blob_unreadable"]
    worktree_manifest, manifest_read_error = read_regular_file(
        REPO_ROOT / PACKAGE_MANIFEST_NAME
    )
    if manifest_read_error or worktree_manifest != manifest_bytes:
        return None, ["checkout_differs_from_git_index"]
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, ["package_manifest_invalid_json"]
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version",
        "version",
        "files",
    }:
        return None, ["package_manifest_unexpected_schema"]
    if manifest.get("schema_version") != 1:
        return None, ["package_manifest_schema_version_unsupported"]
    if manifest.get("version") != expected_version:
        return None, ["package_manifest_version_mismatch"]
    raw_files = manifest.get("files")
    if not isinstance(raw_files, dict) or not raw_files:
        return None, ["package_manifest_files_invalid"]

    hashes: dict[str, str] = {}
    for relative, digest in raw_files.items():
        if (
            not isinstance(relative, str)
            or not _included_source_path(relative)
            or not isinstance(digest, str)
            or not SHA256_PATTERN.fullmatch(digest)
        ):
            return None, ["package_manifest_entry_invalid"]
        hashes[relative] = digest

    publishable_index = {
        name: entry for name, entry in index.items() if _included_source_path(name)
    }
    if set(hashes) != set(publishable_index):
        return None, ["package_manifest_git_inventory_mismatch"]
    if any(
        mode not in {0o100644, 0o100755}
        for mode, _object_id in publishable_index.values()
    ):
        return None, ["package_source_unsupported_git_mode"]

    captured: dict[str, bytes] = {}
    for relative in sorted(hashes):
        _mode, object_id = publishable_index[relative]
        content, blob_error = read_git_blob(object_id)
        if blob_error or content is None:
            return None, ["package_source_git_blob_unreadable"]
        worktree_content, read_error = read_regular_file(REPO_ROOT / relative)
        if read_error or worktree_content != content:
            return None, ["checkout_differs_from_git_index"]
        if hashlib.sha256(content).hexdigest() != hashes[relative]:
            return None, ["package_manifest_hash_mismatch"]
        captured[relative] = content

    version_bytes = captured.get("VERSION")
    try:
        version_from_file = (
            version_bytes.decode("utf-8").strip() if version_bytes is not None else None
        )
    except UnicodeDecodeError:
        version_from_file = None
    if version_from_file != expected_version:
        return None, ["package_version_file_mismatch"]

    final_index, final_index_error = git_index_entries()
    final_revision = checkout_revision()
    final_clean = checkout_clean()
    if (
        final_index_error
        or final_index != index
        or final_revision != initial_revision
        or final_clean is not True
    ):
        return None, ["checkout_changed_during_source_capture"]

    return (
        VerifiedSource(
            revision=initial_revision,
            version=expected_version,
            manifest_bytes=manifest_bytes,
            manifest_digest=hashlib.sha256(manifest_bytes).hexdigest(),
            files=captured,
            modes={
                name: mode for name, (mode, _object_id) in publishable_index.items()
            },
        ),
        [],
    )


def snapshot_base_directory() -> Path:
    return Path.home() / ".acgm" / "marketplace-snapshots"


def snapshot_path(source: VerifiedSource) -> Path:
    return snapshot_base_directory() / source.snapshot_name


def _expected_mode(source: VerifiedSource, relative: str) -> int:
    if relative == PACKAGE_MANIFEST_NAME:
        return 0o644
    return 0o755 if source.modes.get(relative) == 0o100755 else 0o644


def verify_materialized_tree(
    root: Path,
    source: VerifiedSource,
    *,
    allow_cache_management: bool = False,
) -> tuple[bool, str | None]:
    """Verify exact bytes and reject symlinks or unexpected cache content."""

    try:
        root_stat = root.lstat()
    except OSError:
        return False, "verified_tree_missing"
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
        return False, "verified_tree_not_directory"

    actual_files: set[str] = set()
    try:
        for current_root, directory_names, file_names in os.walk(
            root, topdown=True, followlinks=False
        ):
            current = Path(current_root)
            relative_root = current.relative_to(root)
            kept_directories: list[str] = []
            for name in directory_names:
                candidate = current / name
                relative = (relative_root / name).as_posix()
                candidate_stat = candidate.lstat()
                if stat.S_ISLNK(candidate_stat.st_mode):
                    return False, "verified_tree_symlink_detected"
                if allow_cache_management and relative_root == Path(".") and name in CACHE_MANAGEMENT_PARTS:
                    continue
                if not stat.S_ISDIR(candidate_stat.st_mode):
                    return False, "verified_tree_non_directory_component"
                kept_directories.append(name)
            directory_names[:] = kept_directories
            for name in file_names:
                candidate = current / name
                candidate_stat = candidate.lstat()
                if not stat.S_ISREG(candidate_stat.st_mode):
                    return False, "verified_tree_non_regular_file"
                relative = (relative_root / name).as_posix()
                if relative.startswith("./"):
                    relative = relative[2:]
                actual_files.add(relative)
    except (OSError, ValueError):
        return False, "verified_tree_walk_failed"

    expected = source.expected_files
    if actual_files != set(expected):
        return False, "verified_tree_inventory_mismatch"
    for relative, expected_bytes in expected.items():
        content, read_error = read_regular_file(root / relative)
        if read_error or content != expected_bytes:
            return False, "verified_tree_content_mismatch"
        if os.name != "nt":
            try:
                observed_mode = stat.S_IMODE((root / relative).stat().st_mode)
            except OSError:
                return False, "verified_tree_mode_unavailable"
            should_execute = bool(_expected_mode(source, relative) & 0o111)
            if bool(observed_mode & 0o111) != should_execute:
                return False, "verified_tree_executable_mode_mismatch"
    return True, None


def _make_tree_writable(root: Path) -> None:
    if not root.exists():
        return
    for current_root, directories, files in os.walk(root, topdown=False):
        for name in files:
            try:
                os.chmod(Path(current_root) / name, 0o600)
            except OSError:
                pass
        for name in directories:
            try:
                os.chmod(Path(current_root) / name, 0o700)
            except OSError:
                pass
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass


def _remove_private_tree(root: Path) -> None:
    _make_tree_writable(root)
    shutil.rmtree(root, ignore_errors=True)


def plugin_data_path() -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    config_root = Path(configured).expanduser() if configured else Path.home() / ".claude"
    return config_root / "plugins" / "data" / PLUGIN_DATA_KEY


def plugin_data_backup_base_directory() -> Path:
    return Path.home() / ".acgm" / "upgrade-data-backups"


def capture_private_data_tree(
    root: Path,
) -> tuple[PrivateDataTree | None, str, str | None]:
    try:
        root_stat = root.lstat()
    except FileNotFoundError:
        return None, "absent", None
    except OSError:
        return None, "unknown", "plugin_data_path_unavailable"
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
        return None, "unknown", "plugin_data_path_unsafe"

    files: dict[str, bytes] = {}
    file_modes: dict[str, int] = {}
    directory_modes: dict[str, int] = {}
    total_bytes = 0
    try:
        for current_root, directory_names, file_names in os.walk(
            root, topdown=True, followlinks=False
        ):
            current = Path(current_root)
            relative_root = current.relative_to(root)
            root_key = "." if relative_root == Path(".") else relative_root.as_posix()
            current_stat = current.lstat()
            if not stat.S_ISDIR(current_stat.st_mode) or stat.S_ISLNK(current_stat.st_mode):
                return None, "unknown", "plugin_data_directory_unsafe"
            observed_directory_mode = stat.S_IMODE(current_stat.st_mode)
            if os.name != "nt" and observed_directory_mode & 0o077:
                return None, "unknown", "plugin_data_permissions_not_private"
            directory_modes[root_key] = (
                0o700 if os.name == "nt" else observed_directory_mode
            )

            kept_directories: list[str] = []
            for name in directory_names:
                candidate = current / name
                candidate_stat = candidate.lstat()
                if not stat.S_ISDIR(candidate_stat.st_mode) or stat.S_ISLNK(
                    candidate_stat.st_mode
                ):
                    return None, "unknown", "plugin_data_directory_unsafe"
                kept_directories.append(name)
            directory_names[:] = kept_directories

            for name in file_names:
                if len(files) >= MAX_PLUGIN_DATA_FILES:
                    return None, "unknown", "plugin_data_file_count_limit_exceeded"
                candidate = current / name
                candidate_stat = candidate.lstat()
                if not stat.S_ISREG(candidate_stat.st_mode) or stat.S_ISLNK(
                    candidate_stat.st_mode
                ):
                    return None, "unknown", "plugin_data_file_unsafe"
                observed_file_mode = stat.S_IMODE(candidate_stat.st_mode)
                if os.name != "nt" and observed_file_mode & 0o077:
                    return None, "unknown", "plugin_data_permissions_not_private"
                if candidate_stat.st_size > MAX_PLUGIN_DATA_BYTES - total_bytes:
                    return None, "unknown", "plugin_data_size_limit_exceeded"
                relative = (relative_root / name).as_posix()
                if relative.startswith("./"):
                    relative = relative[2:]
                content, read_error = read_regular_file(candidate)
                if read_error or content is None:
                    return None, "unknown", "plugin_data_file_unreadable"
                total_bytes += len(content)
                if total_bytes > MAX_PLUGIN_DATA_BYTES:
                    return None, "unknown", "plugin_data_size_limit_exceeded"
                files[relative] = content
                file_modes[relative] = 0o600 if os.name == "nt" else observed_file_mode
    except (OSError, ValueError):
        return None, "unknown", "plugin_data_tree_walk_failed"
    return PrivateDataTree(files, file_modes, directory_modes), "present", None


def materialize_private_data_tree(root: Path, tree: PrivateDataTree) -> str | None:
    try:
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        directories = sorted(
            (relative for relative in tree.directory_modes if relative != "."),
            key=lambda value: len(PurePosixPath(value).parts),
        )
        for relative in directories:
            destination = root / relative
            destination.mkdir(mode=0o700)
            os.chmod(destination, 0o700)
        for relative, content in sorted(tree.files.items()):
            destination = root / relative
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            descriptor = os.open(destination, flags, tree.file_modes[relative])
            try:
                with os.fdopen(descriptor, "wb", closefd=False) as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                os.close(descriptor)
            os.chmod(destination, tree.file_modes[relative])
        for relative in sorted(
            directories,
            key=lambda value: len(PurePosixPath(value).parts),
            reverse=True,
        ):
            os.chmod(root / relative, tree.directory_modes[relative])
        os.chmod(root, tree.directory_modes.get(".", 0o700))
    except OSError:
        return "plugin_data_materialization_failed"
    return None


def verify_private_data_tree(root: Path, expected: PrivateDataTree) -> tuple[bool, str | None]:
    observed, state, error = capture_private_data_tree(root)
    if error or state != "present" or observed is None:
        return False, error or "plugin_data_tree_missing"
    if observed != expected:
        return False, "plugin_data_tree_content_or_mode_mismatch"
    return True, None


def prepare_plugin_data_backup() -> tuple[PluginDataBackup | None, str | None]:
    data_path = plugin_data_path()
    tree, state, error = capture_private_data_tree(data_path)
    if error:
        return None, error
    if state == "absent":
        return PluginDataBackup(data_path, False, None, None), None
    assert tree is not None

    backup_base = plugin_data_backup_base_directory()
    try:
        backup_base.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup_base_stat = backup_base.lstat()
        if not stat.S_ISDIR(backup_base_stat.st_mode) or stat.S_ISLNK(
            backup_base_stat.st_mode
        ):
            return None, "plugin_data_backup_base_unsafe"
        if os.name != "nt":
            os.chmod(backup_base, 0o700)
        transaction_root = Path(
            tempfile.mkdtemp(prefix=".acgm-upgrade-data-", dir=backup_base)
        )
        if os.name != "nt":
            os.chmod(transaction_root, 0o700)
    except OSError:
        return None, "plugin_data_backup_unavailable"

    backup_data = transaction_root / "data"
    materialization_error = materialize_private_data_tree(backup_data, tree)
    if materialization_error:
        _remove_private_tree(transaction_root)
        return None, materialization_error
    verified, verification_error = verify_private_data_tree(backup_data, tree)
    if not verified:
        _remove_private_tree(transaction_root)
        return None, verification_error or "plugin_data_backup_verification_failed"
    return PluginDataBackup(data_path, True, tree, backup_data), None


def plugin_data_transition_safe(backup: PluginDataBackup) -> tuple[bool, str | None]:
    if backup.existed:
        if backup.tree is None or backup.backup_path is None:
            return False, "plugin_data_backup_contract_invalid"
        backup_ok, backup_error = verify_private_data_tree(
            backup.backup_path, backup.tree
        )
        if not backup_ok:
            return False, backup_error or "plugin_data_backup_verification_failed"
    observed, state, error = capture_private_data_tree(backup.data_path)
    if error:
        return False, error
    if state == "absent":
        return True, None
    if not backup.existed or backup.tree is None or observed != backup.tree:
        return False, "plugin_data_changed_during_upgrade"
    return True, None


def plugin_data_unchanged(backup: PluginDataBackup) -> tuple[bool, str | None]:
    if backup.existed:
        if backup.tree is None or backup.backup_path is None:
            return False, "plugin_data_backup_contract_invalid"
        backup_ok, backup_error = verify_private_data_tree(
            backup.backup_path, backup.tree
        )
        if not backup_ok:
            return False, backup_error or "plugin_data_backup_verification_failed"
        observed, state, error = capture_private_data_tree(backup.data_path)
        if error or state != "present" or observed != backup.tree:
            return False, error or "plugin_data_changed_during_upgrade"
        return True, None
    _observed, state, error = capture_private_data_tree(backup.data_path)
    if error or state != "absent":
        return False, error or "plugin_data_unexpectedly_created"
    return True, None


def restore_plugin_data(backup: PluginDataBackup) -> tuple[bool, str | None]:
    if not backup.existed:
        _observed, state, error = capture_private_data_tree(backup.data_path)
        if error or state != "absent":
            return False, error or "plugin_data_unexpectedly_created"
        return True, None
    if backup.tree is None or backup.backup_path is None:
        return False, "plugin_data_backup_contract_invalid"
    backup_ok, backup_error = verify_private_data_tree(backup.backup_path, backup.tree)
    if not backup_ok:
        return False, backup_error or "plugin_data_backup_verification_failed"

    observed, state, observed_error = capture_private_data_tree(backup.data_path)
    if observed_error:
        return False, observed_error
    if state == "present":
        if observed == backup.tree:
            return True, None
        return False, "plugin_data_restore_target_not_empty_or_exact"

    parent = backup.data_path.parent
    staging_root: Path | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        parent_stat = parent.lstat()
        if not stat.S_ISDIR(parent_stat.st_mode) or stat.S_ISLNK(parent_stat.st_mode):
            return False, "plugin_data_restore_parent_unsafe"
        staging_root = Path(tempfile.mkdtemp(prefix=".acgm-data-restore-", dir=parent))
        if os.name != "nt":
            os.chmod(staging_root, 0o700)
        staged_data = staging_root / "data"
        materialization_error = materialize_private_data_tree(staged_data, backup.tree)
        if materialization_error:
            return False, materialization_error
        staged_ok, staged_error = verify_private_data_tree(staged_data, backup.tree)
        if not staged_ok:
            return False, staged_error or "plugin_data_staging_verification_failed"
        staged_data.rename(backup.data_path)
    except OSError:
        return False, "plugin_data_restore_publish_failed"
    finally:
        if staging_root is not None and staging_root.exists():
            _remove_private_tree(staging_root)
    return verify_private_data_tree(backup.data_path, backup.tree)


def cleanup_plugin_data_backup(backup: PluginDataBackup) -> tuple[bool, str | None]:
    if backup.backup_path is not None:
        transaction_root = backup.backup_path.parent
        _remove_private_tree(transaction_root)
        if transaction_root.exists():
            return False, "plugin_data_backup_cleanup_failed"
    return True, None


def _harden_snapshot(root: Path, source: VerifiedSource) -> None:
    for relative in sorted(source.expected_files):
        try:
            os.chmod(root / relative, 0o555 if _expected_mode(source, relative) & 0o111 else 0o444)
        except OSError:
            if os.name != "nt":
                raise
    directories = sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda value: len(value.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            os.chmod(directory, 0o555)
        except OSError:
            if os.name != "nt":
                raise
    try:
        os.chmod(root, 0o555)
    except OSError:
        if os.name != "nt":
            raise


def create_or_verify_snapshot(
    source: VerifiedSource,
) -> tuple[Path | None, bool, str | None]:
    """Create one persistent, content-addressed, read-only marketplace snapshot."""

    base = snapshot_base_directory()
    target = snapshot_path(source)
    try:
        base.mkdir(parents=True, exist_ok=True)
        base_stat = base.lstat()
    except OSError:
        return None, False, "snapshot_base_unavailable"
    if not stat.S_ISDIR(base_stat.st_mode) or stat.S_ISLNK(base_stat.st_mode):
        return None, False, "snapshot_base_unsafe"

    try:
        target_stat = target.lstat()
    except FileNotFoundError:
        target_stat = None
    except OSError:
        return None, False, "snapshot_target_unavailable"
    if target_stat is not None:
        if stat.S_ISLNK(target_stat.st_mode):
            return None, False, "snapshot_target_unsafe"
        verified, error = verify_materialized_tree(target, source)
        return (target if verified else None), False, error

    temporary = Path(tempfile.mkdtemp(prefix=".acgm-snapshot-", dir=base))
    try:
        for relative, content in sorted(source.expected_files.items()):
            destination = temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            descriptor = os.open(destination, flags, _expected_mode(source, relative))
            try:
                with os.fdopen(descriptor, "wb", closefd=False) as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                os.close(descriptor)
            os.chmod(destination, _expected_mode(source, relative))
        verified, error = verify_materialized_tree(temporary, source)
        if not verified:
            return None, False, error or "snapshot_staging_verification_failed"
        _harden_snapshot(temporary, source)
        verified, error = verify_materialized_tree(temporary, source)
        if not verified:
            return None, False, error or "snapshot_hardening_verification_failed"
        try:
            temporary.rename(target)
        except FileExistsError:
            verified, error = verify_materialized_tree(target, source)
            return (target if verified else None), False, error
        except OSError:
            if target.exists():
                verified, error = verify_materialized_tree(target, source)
                return (target if verified else None), False, error
            return None, False, "snapshot_publish_failed"
        verified, error = verify_materialized_tree(target, source)
        return (target if verified else None), bool(verified), error
    except OSError:
        return None, False, "snapshot_creation_failed"
    finally:
        if temporary.exists():
            _remove_private_tree(temporary)


def reverify_source_and_snapshot(
    source: VerifiedSource, materialized: Path
) -> tuple[bool, str | None]:
    if checkout_revision() != source.revision or checkout_clean() is not True:
        return False, "checkout_identity_changed_before_mutation"
    return verify_materialized_tree(materialized, source)


def parse_json_result(result: CommandResult) -> tuple[Any | None, str | None]:
    if result.returncode != 0:
        return None, result.error_code or "command_failed"
    if not result.stdout.strip():
        return None, "empty_json_output"
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return None, "invalid_json_output"


def _records_from_container(
    container: Any, *, mapping_key_name: str
) -> tuple[list[dict[str, Any]] | None, str | None]:
    if isinstance(container, list):
        if not all(isinstance(item, dict) for item in container):
            return None, "unexpected_record"
        return [dict(item) for item in container], None
    if isinstance(container, dict):
        records: list[dict[str, Any]] = []
        for key, value in container.items():
            values = value if isinstance(value, list) else [value]
            if not values or not all(isinstance(item, dict) for item in values):
                return None, "unexpected_mapping_record"
            for item in values:
                record = dict(item)
                record.setdefault(mapping_key_name, str(key))
                records.append(record)
        return records, None
    return None, "unexpected_container"


def parse_marketplace_payload(
    payload: Any,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not isinstance(payload, list):
        return None, "unexpected_marketplace_json_shape"
    records, error = _records_from_container(payload, mapping_key_name="_key")
    if error or records is None:
        return None, f"unexpected_marketplace_json_{error}"
    for record in records:
        name = record.get("name", record.get("_key"))
        if not isinstance(name, str) or not name:
            return None, "unexpected_marketplace_record_identity"
        source = record.get("source")
        if not isinstance(source, (str, dict)):
            return None, "unexpected_marketplace_record_source"
    return records, None


def parse_plugin_payload(
    payload: Any,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not isinstance(payload, list):
        return None, "unexpected_plugin_json_shape"
    records, error = _records_from_container(payload, mapping_key_name="_key")
    if error or records is None:
        return None, f"unexpected_plugin_json_{error}"
    for record in records:
        identities = record_strings(
            record,
            ("id", "name", "plugin", "fullName", "key", "_key"),
        )
        if not identities:
            return None, "unexpected_plugin_record_identity"
    return records, None


def record_strings(record: dict[str, Any], keys: Sequence[str]) -> set[str]:
    return {
        value
        for key in keys
        if isinstance((value := record.get(key)), str) and value
    }


def matching_marketplaces(
    records: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if MARKETPLACE_NAME
        in record_strings(record, ("name", "id", "marketplace", "_key"))
    ]


def _normalized_path(value: str) -> str | None:
    if value.casefold() in {"directory", "file", "github", "url", "git-subdir"}:
        return None
    candidate = Path(os.path.expandvars(value)).expanduser()
    if not candidate.is_absolute():
        return None
    if candidate.name == "marketplace.json" and candidate.parent.name == ".claude-plugin":
        candidate = candidate.parent.parent
    return os.path.normcase(os.path.abspath(os.path.normpath(str(candidate))))


def marketplace_source_path(record: dict[str, Any]) -> Path | None:
    raw_source = record.get("source")
    raw_path: Any
    if isinstance(raw_source, str):
        source_kind = raw_source.casefold()
        raw_path = record.get("path")
    elif isinstance(raw_source, dict):
        nested_kind = raw_source.get("source")
        source_kind = nested_kind.casefold() if isinstance(nested_kind, str) else ""
        raw_path = raw_source.get("path")
    else:
        return False
    if source_kind not in {"directory", "file"} or not isinstance(raw_path, str):
        return None
    normalized = _normalized_path(raw_path)
    return Path(normalized) if normalized is not None else None


def marketplace_source_matches(record: dict[str, Any], source: Path) -> bool:
    expected = _normalized_path(str(source.absolute()))
    observed = marketplace_source_path(record)
    return expected is not None and observed is not None and str(observed) == expected


def user_settings_path() -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(configured).expanduser() if configured else Path.home() / ".claude"
    return base / "settings.json"


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def raw_user_marketplace_declaration(
) -> tuple[dict[str, Any] | None, str, str | None]:
    path = user_settings_path()
    try:
        content, read_error = read_regular_file(path)
    except OSError:
        return None, "unknown", "user_settings_unavailable"
    if read_error == "file_unavailable":
        return None, "absent", None
    if read_error or content is None:
        return None, "unknown", "user_settings_unreadable"
    try:
        payload = json.loads(
            content.decode("utf-8"), object_pairs_hook=_unique_json_object
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "unknown", "user_settings_invalid_json"
    except ValueError:
        return None, "unknown", "user_settings_duplicate_key"
    if not isinstance(payload, dict):
        return None, "unknown", "user_settings_unexpected_schema"
    marketplaces = payload.get("extraKnownMarketplaces")
    if marketplaces is None:
        return None, "absent", None
    if not isinstance(marketplaces, dict):
        return None, "unknown", "user_marketplaces_unexpected_schema"
    declaration = marketplaces.get(MARKETPLACE_NAME)
    if declaration is None:
        return None, "absent", None
    if not isinstance(declaration, dict):
        return None, "unknown", "user_marketplace_declaration_invalid"
    return declaration, "present", None


def user_marketplace_declaration(
    source: Path,
) -> tuple[str | None, str | None]:
    """Check only the user-scope marketplace declaration documented by Claude."""

    declaration, state, error = raw_user_marketplace_declaration()
    if error:
        return None, error
    if state == "absent":
        return "absent", None
    assert declaration is not None
    return (
        "exact" if marketplace_source_matches(declaration, source) else "conflict"
    ), None


def matching_plugins(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for record in records:
        identities = record_strings(
            record,
            ("id", "name", "plugin", "fullName", "key", "_key"),
        )
        marketplaces = record_strings(record, ("marketplace", "marketplaceName"))
        if PLUGIN_ID in identities or (
            PLUGIN_NAME in identities and MARKETPLACE_NAME in marketplaces
        ):
            matches.append(record)
    return matches


def installed_plugin_has_errors(record: dict[str, Any]) -> bool:
    value = record.get("errors")
    return value not in (None, False, "", [], {})


def verify_installed_plugin(
    record: dict[str, Any],
    source: VerifiedSource,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if record.get("scope") != "user":
        errors.append("installed_plugin_scope_not_user")
    if record.get("version") != source.version:
        errors.append("installed_plugin_version_mismatch_or_missing")
    if record.get("enabled") is not True:
        errors.append("installed_plugin_not_confirmed_enabled")
    if installed_plugin_has_errors(record):
        errors.append("installed_plugin_reports_errors")
    marketplace_values = record_strings(record, ("marketplace", "marketplaceName"))
    identities = record_strings(record, ("id", "name", "plugin", "fullName", "_key"))
    if (
        PLUGIN_ID not in identities
        and MARKETPLACE_NAME not in marketplace_values
    ) or (
        marketplace_values and MARKETPLACE_NAME not in marketplace_values
    ):
        errors.append("installed_plugin_marketplace_identity_mismatch")

    install_path_value = record.get("installPath")
    if not isinstance(install_path_value, str) or not install_path_value:
        errors.append("installed_plugin_cache_path_missing")
    else:
        cache_path = Path(install_path_value).expanduser()
        if not cache_path.is_absolute():
            errors.append("installed_plugin_cache_path_invalid")
        else:
            cache_ok, cache_error = verify_materialized_tree(
                cache_path, source, allow_cache_management=True
            )
            if not cache_ok:
                errors.append(cache_error or "installed_plugin_cache_verification_failed")
    return not errors, errors


def installed_plugin_in_use(record: dict[str, Any]) -> tuple[bool, str | None]:
    install_path_value = record.get("installPath")
    if not isinstance(install_path_value, str) or not install_path_value:
        return False, "installed_plugin_cache_path_missing"
    cache_path = Path(install_path_value).expanduser()
    if not cache_path.is_absolute():
        return False, "installed_plugin_cache_path_invalid"
    marker = cache_path / ".in_use"
    try:
        marker.lstat()
    except FileNotFoundError:
        return False, None
    except OSError:
        return False, "installed_plugin_in_use_state_unavailable"
    return True, None


def legacy_github_source_shape(value: Any) -> dict[str, str | None] | None:
    if not isinstance(value, dict) or set(value) not in (
        {"source", "repo"},
        {"source", "repo", "ref"},
    ):
        return None
    source = value.get("source")
    repo = value.get("repo")
    ref = value.get("ref")
    if (
        source != "github"
        or repo != PUBLIC_GITHUB_REPO
        or ref not in LEGACY_PUBLIC_REFS
    ):
        return None
    return {"source": "github", "repo": repo, "ref": ref}


def legacy_github_settings_shape(
    declaration: Any,
) -> dict[str, str | None] | None:
    """Parse only the exact nested declaration written to user settings."""

    if not isinstance(declaration, dict) or set(declaration) != {"source"}:
        return None
    return legacy_github_source_shape(declaration.get("source"))


def legacy_github_cli_record_shape(
    record: Any,
) -> dict[str, str | None] | None:
    """Normalize the documented nested or observed flat CLI record shape."""

    if not isinstance(record, dict):
        return None
    raw_source = record.get("source")
    if isinstance(raw_source, dict):
        if "repo" in record or "ref" in record:
            return None
        return legacy_github_source_shape(raw_source)
    if raw_source != "github" or "repo" not in record:
        return None
    candidate: dict[str, Any] = {
        "source": raw_source,
        "repo": record.get("repo"),
    }
    if "ref" in record:
        candidate["ref"] = record.get("ref")
    return legacy_github_source_shape(candidate)


def detect_legacy_public_github_install(
    marketplaces: Sequence[dict[str, Any]],
    plugins: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    if len(marketplaces) != 1 or len(plugins) != 1:
        return None
    marketplace_shape = legacy_github_cli_record_shape(marketplaces[0])
    if marketplace_shape is None:
        return None
    declaration, declaration_state, declaration_error = (
        raw_user_marketplace_declaration()
    )
    if declaration_error or declaration_state != "present" or declaration is None:
        return None
    declaration_shape = legacy_github_settings_shape(declaration)
    if declaration_shape != marketplace_shape:
        return None

    plugin = plugins[0]
    version = plugin.get("version")
    if (
        plugin.get("scope") != "user"
        or plugin.get("enabled") is not True
        or version not in LEGACY_PUBLIC_VERSIONS
        or installed_plugin_has_errors(plugin)
    ):
        return None
    return {
        "detected": True,
        "installation_shape": "legacy_public_github_user",
        "repo": PUBLIC_GITHUB_REPO,
        "ref": marketplace_shape["ref"],
        "version": version,
        "scope": "user",
        "publisher_authenticity_proven": False,
        "installed_content_verified": False,
    }


def _python_launcher_argv(report: dict[str, Any]) -> list[str]:
    checks = report.get("checks")
    launcher = checks.get("python_hook_launcher") if isinstance(checks, dict) else None
    kind = launcher.get("kind") if isinstance(launcher, dict) else None
    if kind == "py-3":
        return ["py", "-3"]
    if kind in {"python", "python3"}:
        return [kind]
    return ["python3"]


def legacy_public_migration_plan(
    *, target_version: str, report: dict[str, Any]
) -> dict[str, Any]:
    """Return a non-executable, ordered migration contract for legacy installs."""

    resolved_surface = str(
        (report.get("surface") or {}).get("resolved") or "claude-code-cli"
    )
    verified_snapshot_argv = [
        *_python_launcher_argv(report),
        "scripts/install.py",
        "--surface",
        resolved_surface,
        "--json",
    ]
    report_argv = [
        *_python_launcher_argv(report),
        "scripts/acgm_runtime.py",
        "report",
        "--project",
        "all",
        "--limit",
        FULL_LEDGER_REPORT_LIMIT,
        "--json",
    ]
    uninstall_id = "uninstall_legacy_plugin_keep_data_user_scope"
    verification_id = "verify_legacy_plugin_absent_and_data_retained"
    remove_id = "remove_legacy_marketplace_user_scope"
    target_id = "select_and_install_one_rc4_target_shape"
    actions: list[dict[str, Any]] = [
        {
            "id": "review_legacy_evidence_limits",
            "kind": "evidence_review",
            "instruction": (
                "Treat the matching repo, ref, version, and scope only as a legacy "
                "configuration clue. They do not prove publisher authenticity or "
                "the installed bytes. Stop if the user cannot accept that limit."
            ),
            "evidence_limitations": [
                "publisher_authenticity_not_proven",
                "installed_content_not_verified",
            ],
            "mutates_state": False,
            "requires_explicit_install_intent": False,
            "automatic_execution_allowed": False,
        },
        {
            "id": "close_all_acgm_sessions",
            "kind": "human_confirmation",
            "instruction": (
                "Close every Claude Code and Desktop Code session that may have ACGM "
                "loaded, then confirm no session is using the legacy plugin cache."
            ),
            "mutates_state": False,
            "requires_explicit_install_intent": False,
            "automatic_execution_allowed": False,
        },
        {
            "id": "preserve_privacy_safe_acgm_report",
            "kind": "command",
            "instruction": (
                "After every ACGM session is closed, save the full sanitized JSON "
                "ledger privately and review it for accidental identifying text before "
                "sharing it. No SessionEnd may still be pending after this baseline."
            ),
            "command_argv": report_argv,
            "cwd_token": "LOCAL_CHECKOUT",
            "output_contract": "private_privacy_reviewed_full_ledger_record",
            "stdout_evidence": {
                "source_alias": "LEGACY_DATA_REPORT_BEFORE",
                "fingerprint_alias": "LEGACY_DATA_REPORT_BEFORE_SHA256",
                "algorithm": "sha256",
                "input": "exact_stdout_bytes",
                "coverage": "full_sanitized_event_ledger",
                "event_count_expression": "len($.events)",
                "privacy_safe_review_required": True,
            },
            "mutates_state": False,
            "requires_explicit_install_intent": False,
            "automatic_execution_allowed": False,
        },
        {
            "id": "authorize_legacy_migration_mutations",
            "kind": "authorization",
            "instruction": (
                "Obtain a new, explicit user authorization for the exact user-scope "
                "uninstall, marketplace removal, and exactly one RC4 target install."
            ),
            "authorizes_action_ids": [uninstall_id, remove_id, target_id],
            "mutates_state": False,
            "requires_explicit_install_intent": True,
            "automatic_execution_allowed": False,
        },
        {
            "id": uninstall_id,
            "kind": "command",
            "instruction": (
                "Only after the separate authorization, uninstall the exact legacy "
                "user-scope plugin while retaining its plugin data."
            ),
            "command_argv": [
                "claude",
                "plugin",
                "uninstall",
                PLUGIN_ID,
                "--scope",
                "user",
                "--keep-data",
            ],
            "mutates_state": True,
            "requires_explicit_install_intent": True,
            "automatic_execution_allowed": False,
        },
        {
            "id": verification_id,
            "kind": "verification_gate",
            "instruction": (
                "Verify that the exact plugin ID is absent, rerun the same RC4 checkout "
                "report command, and require its exact-stdout SHA-256 fingerprint to "
                "equal the pre-uninstall fingerprint. Do not remove the marketplace "
                "unless both checks pass."
            ),
            "commands": [
                {
                    "id": "verify_plugin_absent",
                    "command_argv": ["claude", "plugin", "list", "--json"],
                },
                {
                    "id": "capture_post_uninstall_data_report",
                    "command_argv": report_argv,
                    "cwd_token": "LOCAL_CHECKOUT",
                    "capture_exact_stdout_as": "LEGACY_DATA_REPORT_AFTER",
                    "fingerprint_alias": "LEGACY_DATA_REPORT_AFTER_SHA256",
                    "fingerprint_algorithm": "sha256",
                    "coverage": "full_sanitized_event_ledger",
                    "event_count_expression": "len($.events)",
                },
            ],
            "required_postconditions": [
                f"plugin_absent:{PLUGIN_ID}",
                "LEGACY_DATA_REPORT_AFTER_SHA256_equals_LEGACY_DATA_REPORT_BEFORE_SHA256",
            ],
            "evidence_comparison": {
                "before_fingerprint_alias": "LEGACY_DATA_REPORT_BEFORE_SHA256",
                "after_fingerprint_alias": "LEGACY_DATA_REPORT_AFTER_SHA256",
                "algorithm": "sha256",
                "input": "exact_stdout_bytes",
                "coverage": "full_sanitized_event_ledger",
                "event_count_relation": "equal",
                "required_relation": "equal",
                "must_pass_before_step_id": remove_id,
            },
            "on_failure": "stop_before_marketplace_removal",
            "mutates_state": False,
            "requires_explicit_install_intent": False,
            "automatic_execution_allowed": False,
        },
        {
            "id": remove_id,
            "kind": "command",
            "instruction": (
                "Only after the verification gate passes, remove the exact legacy "
                "marketplace declaration from user scope."
            ),
            "command_argv": [
                "claude",
                "plugin",
                "marketplace",
                "remove",
                MARKETPLACE_NAME,
                "--scope",
                "user",
            ],
            "mutates_state": True,
            "requires_explicit_install_intent": True,
            "automatic_execution_allowed": False,
        },
        {
            "id": target_id,
            "kind": "target_install_choice",
            "instruction": (
                "Choose and install exactly one RC4 target shape. Never declare the "
                "same marketplace name from both sources in one scope."
            ),
            "selection_cardinality": "exactly_one",
            "target_options": [
                {
                    "installation_shape": "verified_snapshot_user",
                    "version": target_version,
                    "command_argv": verified_snapshot_argv,
                    "automatic_execution_allowed": False,
                },
                {
                    "installation_shape": "github_tag_desktop_ui",
                    "version": target_version,
                    "repository": PUBLIC_GITHUB_REPO,
                    "ref": f"v{target_version}",
                    "scope": "explicit_ui_choice_then_observe",
                    "automatic_execution_allowed": False,
                },
            ],
            "mutates_state": True,
            "requires_explicit_install_intent": True,
            "automatic_execution_allowed": False,
        },
        {
            "id": "reload_and_verify_same_surface",
            "kind": "runtime_verification",
            "instruction": (
                "In the exact target surface, reload and verify hooks, skills, the RC4 "
                "version, a controlled disposable hook probe, and doctor. Configuration "
                "alone is not ACTIVE_VERIFIED."
            ),
            "same_surface_checks": [
                {"kind": "slash_command", "value": "/reload-plugins"},
                {"kind": "slash_command", "value": "/hooks"},
                {"kind": "slash_command", "value": "/skills"},
                {"kind": "command", "command_argv": ["acgm", "version"]},
                {
                    "kind": "controlled_hook_probe",
                    "procedure": "tests/manual/CLAUDE_CODE_E2E.md",
                },
                {
                    "kind": "command",
                    "command_argv": ["acgm", "doctor", "--json"],
                },
            ],
            "mutates_state": False,
            "requires_explicit_install_intent": False,
            "automatic_execution_allowed": False,
        },
    ]
    return {
        "schema_version": 1,
        "automatic_execution_allowed": False,
        "requires_separate_authorization": True,
        "step_order": [action["id"] for action in actions],
        "verification_gate": {
            "after_step_id": uninstall_id,
            "gate_step_id": verification_id,
            "before_step_id": remove_id,
            "must_pass_before_next_mutation": True,
        },
        "steps": actions,
    }


def capture_verified_snapshot(
    root: Path,
) -> tuple[VerifiedSource | None, list[str]]:
    """Reconstruct and verify an installer-created immutable snapshot.

    This proves content self-consistency and the ACGM snapshot structure. Older
    snapshots do not contain a signature or full Git commit, so this does not
    claim publisher authenticity.
    """

    base = snapshot_base_directory()
    try:
        base_stat = base.lstat()
        root_stat = root.lstat()
    except OSError:
        return None, ["legacy_snapshot_unavailable"]
    if (
        not stat.S_ISDIR(base_stat.st_mode)
        or stat.S_ISLNK(base_stat.st_mode)
        or not stat.S_ISDIR(root_stat.st_mode)
        or stat.S_ISLNK(root_stat.st_mode)
    ):
        return None, ["legacy_snapshot_path_unsafe"]

    normalized_base = os.path.normcase(os.path.abspath(os.path.normpath(str(base))))
    normalized_root = os.path.normcase(os.path.abspath(os.path.normpath(str(root))))
    normalized_parent = os.path.normcase(
        os.path.abspath(os.path.normpath(str(root.parent)))
    )
    if normalized_parent != normalized_base or normalized_root == normalized_base:
        return None, ["legacy_snapshot_not_direct_child_of_snapshot_store"]

    try:
        version, revision_prefix, digest_prefix = root.name.rsplit("-", 2)
    except ValueError:
        return None, ["legacy_snapshot_name_invalid"]
    if (
        not SAFE_VERSION_PATTERN.fullmatch(version)
        or not SNAPSHOT_SUFFIX_PATTERN.fullmatch(revision_prefix)
        or not SNAPSHOT_SUFFIX_PATTERN.fullmatch(digest_prefix)
    ):
        return None, ["legacy_snapshot_name_invalid"]

    manifest_bytes, manifest_error = read_regular_file(root / PACKAGE_MANIFEST_NAME)
    if manifest_error or manifest_bytes is None:
        return None, ["legacy_snapshot_manifest_unreadable"]
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_digest[:12] != digest_prefix:
        return None, ["legacy_snapshot_manifest_identity_mismatch"]
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, ["legacy_snapshot_manifest_invalid_json"]
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version",
        "version",
        "files",
    }:
        return None, ["legacy_snapshot_manifest_unexpected_schema"]
    if manifest.get("schema_version") != 1 or manifest.get("version") != version:
        return None, ["legacy_snapshot_manifest_version_mismatch"]
    raw_files = manifest.get("files")
    if not isinstance(raw_files, dict) or not raw_files:
        return None, ["legacy_snapshot_manifest_files_invalid"]

    files: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    for relative, expected_digest in sorted(raw_files.items()):
        if (
            not isinstance(relative, str)
            or not _included_source_path(relative)
            or not isinstance(expected_digest, str)
            or not SHA256_PATTERN.fullmatch(expected_digest)
        ):
            return None, ["legacy_snapshot_manifest_entry_invalid"]
        content, read_error = read_regular_file(root / relative)
        if read_error or content is None:
            return None, ["legacy_snapshot_file_unreadable"]
        if hashlib.sha256(content).hexdigest() != expected_digest:
            return None, ["legacy_snapshot_content_hash_mismatch"]
        try:
            observed_mode = stat.S_IMODE((root / relative).stat().st_mode)
        except OSError:
            return None, ["legacy_snapshot_mode_unavailable"]
        files[relative] = content
        modes[relative] = 0o100755 if observed_mode & 0o111 else 0o100644

    source = VerifiedSource(
        revision=revision_prefix + ("0" * 28),
        version=version,
        manifest_bytes=manifest_bytes,
        manifest_digest=manifest_digest,
        files=files,
        modes=modes,
    )
    if source.snapshot_name != root.name:
        return None, ["legacy_snapshot_name_identity_mismatch"]
    verified, verification_error = verify_materialized_tree(root, source)
    if not verified:
        return None, [verification_error or "legacy_snapshot_tree_verification_failed"]

    if os.name != "nt":
        try:
            for current_root, directories, names in os.walk(
                root, topdown=True, followlinks=False
            ):
                current = Path(current_root)
                for candidate in [current, *(current / name for name in directories), *(current / name for name in names)]:
                    if stat.S_IMODE(candidate.lstat().st_mode) & 0o222:
                        return None, ["legacy_snapshot_not_read_only"]
        except OSError:
            return None, ["legacy_snapshot_mode_unavailable"]

    try:
        plugin = json.loads(files[".claude-plugin/plugin.json"].decode("utf-8"))
        marketplace = json.loads(
            files[".claude-plugin/marketplace.json"].decode("utf-8")
        )
        version_file = files["VERSION"].decode("utf-8").strip()
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return None, ["legacy_snapshot_acgm_identity_unreadable"]
    plugins = marketplace.get("plugins") if isinstance(marketplace, dict) else None
    if (
        not isinstance(plugin, dict)
        or plugin.get("name") != PLUGIN_NAME
        or plugin.get("version") != version
        or version_file != version
        or marketplace.get("name") != MARKETPLACE_NAME
        or not isinstance(plugins, list)
        or len(plugins) != 1
        or not isinstance(plugins[0], dict)
        or plugins[0].get("name") != PLUGIN_NAME
        or plugins[0].get("source") != "./"
    ):
        return None, ["legacy_snapshot_acgm_identity_mismatch"]
    return source, []


def _semver_parts(value: str) -> tuple[tuple[int, int, int], list[str] | None] | None:
    if not SAFE_VERSION_PATTERN.fullmatch(value):
        return None
    without_build = value.split("+", 1)[0]
    core_text, separator, prerelease_text = without_build.partition("-")
    try:
        core = tuple(int(part) for part in core_text.split("."))
    except ValueError:
        return None
    if len(core) != 3:
        return None
    prerelease = prerelease_text.split(".") if separator else None
    if prerelease is not None and any(not item for item in prerelease):
        return None
    return (core[0], core[1], core[2]), prerelease


def version_is_strictly_older(old: str, new: str) -> bool:
    old_parts = _semver_parts(old)
    new_parts = _semver_parts(new)
    if old_parts is None or new_parts is None:
        return False
    old_core, old_pre = old_parts
    new_core, new_pre = new_parts
    if old_core != new_core:
        return old_core < new_core
    if old_pre is None or new_pre is None:
        return old_pre is not None and new_pre is None
    for old_item, new_item in zip(old_pre, new_pre):
        if old_item == new_item:
            continue
        old_numeric = old_item.isdigit()
        new_numeric = new_item.isdigit()
        if old_numeric and new_numeric:
            return int(old_item) < int(new_item)
        if old_numeric != new_numeric:
            return old_numeric
        return old_item < new_item
    return len(old_pre) < len(new_pre)


def reverify_legacy_snapshot(
    expected: VerifiedSource, path: Path
) -> tuple[bool, str | None]:
    observed, errors = capture_verified_snapshot(path)
    if observed is None:
        return False, errors[0] if errors else "legacy_snapshot_reverification_failed"
    if (
        observed.version != expected.version
        or observed.manifest_digest != expected.manifest_digest
        or observed.expected_files != expected.expected_files
        or observed.modes != expected.modes
    ):
        return False, "legacy_snapshot_identity_changed"
    return True, None


def display_argv(
    argv: Sequence[str],
    *,
    claude_executable: str | None = None,
    materialized: Path | None = None,
) -> list[str]:
    """Return a shareable command plan without exposing private local paths."""

    private_root = os.path.normcase(str(REPO_ROOT.resolve(strict=False)))
    snapshot_value = (
        os.path.normcase(str(materialized.resolve(strict=False)))
        if materialized is not None
        else None
    )
    displayed: list[str] = []
    for value in argv:
        normalized = None
        try:
            if Path(value).is_absolute():
                normalized = os.path.normcase(str(Path(value).resolve(strict=False)))
        except (OSError, ValueError):
            pass
        if claude_executable is not None and value == claude_executable:
            displayed.append("claude")
        elif normalized == private_root:
            displayed.append("LOCAL_CHECKOUT")
        elif snapshot_value is not None and normalized == snapshot_value:
            displayed.append("VERIFIED_SNAPSHOT")
        else:
            displayed.append(value)
    return displayed


def command_record(
    name: str,
    argv: Sequence[str],
    result: CommandResult,
    *,
    claude_executable: str,
    materialized: Path,
) -> dict[str, Any]:
    return {
        "name": name,
        "argv": display_argv(
            argv,
            claude_executable=claude_executable,
            materialized=materialized,
        ),
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "error_code": result.error_code,
    }


def base_result(
    dry_run: bool,
    report: dict[str, Any],
    revision: str | None,
    clean: bool | None,
    *,
    upgrade_verified_snapshot: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "acgm_version": report.get("acgm_version"),
        "status": "UNKNOWN",
        "operation_ok": False,
        "ok": False,
        "ready_for_use": False,
        "requires_user_action": False,
        "changed": False,
        "mutation_attempted": False,
        "state_change_possible": False,
        "dry_run": dry_run,
        "scope": None,
        "suggested_scope": "user",
        "installation_shape": None,
        "legacy_detection": {
            "detected": False,
            "installation_shape": None,
            "repo": None,
            "ref": None,
            "version": None,
            "scope": None,
            "publisher_authenticity_proven": False,
            "installed_content_verified": False,
        },
        "manual_migration_plan": None,
        "source": {
            "kind": "verified_git_snapshot",
            "checkout_path_token": "LOCAL_CHECKOUT",
            "snapshot_path_token": "VERIFIED_SNAPSHOT",
            "git_commit": revision,
            "git_clean": clean,
            "package_integrity_ok": False,
        },
        "preflight": report,
        "surface": report.get("surface", {}),
        "verification": {
            "source": False,
            "configuration": False,
            "runtime_activation": False,
            "project_governance": False,
        },
        "executed": [],
        "planned_commands": [],
        "actions": list(report.get("actions") or []),
        "upgrade": {
            "requested": upgrade_verified_snapshot,
            "from_version": None,
            "to_version": report.get("acgm_version"),
            "from_snapshot_id": None,
            "preconditions_verified": False,
            "rollback_attempted": False,
            "rollback_verified": False,
            "data": {
                "source_state": "unknown",
                "backup_verified": False,
                "restored_verified": False,
                "backup_retained": False,
                "backup_location_token": None,
                "retained_backup_verified": False,
                "backup_cleanup_verified": False,
            },
        },
        "error_codes": [],
        "next_steps": [],
    }


def inspect_json(
    result: dict[str, Any],
    name: str,
    argv: Sequence[str],
    *,
    parser: Callable[[Any], tuple[list[dict[str, Any]] | None, str | None]],
    claude_executable: str,
    materialized: Path,
    claude_cwd: Path,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    completed = run_command(argv, timeout=INSPECT_TIMEOUT_SECONDS, cwd=claude_cwd)
    result["executed"].append(
        command_record(
            name,
            argv,
            completed,
            claude_executable=claude_executable,
            materialized=materialized,
        )
    )
    payload, error = parse_json_result(completed)
    if error:
        return None, f"{name}_{error}"
    records, schema_error = parser(payload)
    if schema_error:
        return None, f"{name}_{schema_error}"
    return records, None


def _source_blocked(
    result: dict[str, Any], status: str, errors: list[str], next_step: str
) -> tuple[int, dict[str, Any]]:
    result["status"] = status
    result["error_codes"] = errors
    result["next_steps"] = [next_step]
    return 2, result


def inspect_acgm_records(
    result: dict[str, Any],
    prefix: str,
    marketplace_list: Sequence[str],
    plugin_list: Sequence[str],
    *,
    claude_executable: str,
    materialized: Path,
    claude_cwd: Path,
) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None, list[str]]:
    marketplaces, marketplace_error = inspect_json(
        result,
        f"{prefix}_marketplace_list",
        marketplace_list,
        parser=parse_marketplace_payload,
        claude_executable=claude_executable,
        materialized=materialized,
        claude_cwd=claude_cwd,
    )
    plugins, plugin_error = inspect_json(
        result,
        f"{prefix}_plugin_list",
        plugin_list,
        parser=parse_plugin_payload,
        claude_executable=claude_executable,
        materialized=materialized,
        claude_cwd=claude_cwd,
    )
    errors = [
        error for error in (marketplace_error, plugin_error) if error is not None
    ]
    if errors:
        return None, None, errors
    assert marketplaces is not None and plugins is not None
    return matching_marketplaces(marketplaces), matching_plugins(plugins), []


def classify_upgrade_state(
    marketplaces: Sequence[dict[str, Any]],
    plugins: Sequence[dict[str, Any]],
    *,
    old_path: Path,
    old_source: VerifiedSource,
    new_path: Path,
    new_source: VerifiedSource,
) -> tuple[str, list[str]]:
    old_declaration, old_declaration_error = user_marketplace_declaration(old_path)
    new_declaration, new_declaration_error = user_marketplace_declaration(new_path)
    if old_declaration_error or new_declaration_error:
        return "unknown", [
            error
            for error in (old_declaration_error, new_declaration_error)
            if error is not None
        ]
    if len(marketplaces) > 1 or len(plugins) > 1:
        return "unknown", ["upgrade_state_not_unique"]
    if (
        not marketplaces
        and not plugins
        and old_declaration == "absent"
        and new_declaration == "absent"
    ):
        return "empty", []

    for label, path, source, declaration in (
        ("old", old_path, old_source, old_declaration),
        ("new", new_path, new_source, new_declaration),
    ):
        if (
            len(marketplaces) == 1
            and marketplace_source_matches(marketplaces[0], path)
            and declaration == "exact"
        ):
            if not plugins:
                return f"{label}_marketplace_only", []
            in_use, in_use_error = installed_plugin_in_use(plugins[0])
            if in_use_error or in_use:
                return "unknown", [
                    in_use_error or "installed_plugin_cache_in_use"
                ]
            verified, errors = verify_installed_plugin(plugins[0], source)
            if verified:
                return f"{label}_full", []
            return "unknown", errors
    return "unknown", ["upgrade_state_inconsistent_or_unrecognized"]


def observe_upgrade_state(
    result: dict[str, Any],
    prefix: str,
    marketplace_list: Sequence[str],
    plugin_list: Sequence[str],
    *,
    claude_executable: str,
    materialized: Path,
    old_path: Path,
    old_source: VerifiedSource,
    new_path: Path,
    new_source: VerifiedSource,
    claude_cwd: Path,
) -> tuple[str, list[str]]:
    marketplaces, plugins, inspection_errors = inspect_acgm_records(
        result,
        prefix,
        marketplace_list,
        plugin_list,
        claude_executable=claude_executable,
        materialized=materialized,
        claude_cwd=claude_cwd,
    )
    if inspection_errors or marketplaces is None or plugins is None:
        return "unknown", inspection_errors or ["upgrade_state_inspection_failed"]
    return classify_upgrade_state(
        marketplaces,
        plugins,
        old_path=old_path,
        old_source=old_source,
        new_path=new_path,
        new_source=new_source,
    )


def run_recorded_mutation(
    result: dict[str, Any],
    name: str,
    argv: Sequence[str],
    *,
    claude_executable: str,
    materialized: Path,
    claude_cwd: Path,
) -> CommandResult:
    result["mutation_attempted"] = True
    result["state_change_possible"] = True
    completed = run_command(argv, timeout=MUTATION_TIMEOUT_SECONDS, cwd=claude_cwd)
    result["executed"].append(
        command_record(
            name,
            argv,
            completed,
            claude_executable=claude_executable,
            materialized=materialized,
        )
    )
    return completed


def verify_upgrade_sources(
    new_source: VerifiedSource,
    new_path: Path,
    old_source: VerifiedSource,
    old_path: Path,
) -> tuple[bool, str | None]:
    new_ok, new_error = reverify_source_and_snapshot(new_source, new_path)
    if not new_ok:
        return False, new_error or "new_upgrade_source_reverification_failed"
    old_ok, old_error = reverify_legacy_snapshot(old_source, old_path)
    if not old_ok:
        return False, old_error or "legacy_snapshot_reverification_failed"
    return True, None


def record_retained_backup_state(
    result: dict[str, Any],
    backup: PluginDataBackup,
    *,
    cleanup_verified: bool,
) -> tuple[bool, str | None]:
    """Record whether a cleanup artifact is still a complete verified backup."""

    data = result["upgrade"]["data"]
    if cleanup_verified:
        data.update(
            {
                "backup_retained": False,
                "backup_location_token": None,
                "retained_backup_verified": False,
                "backup_cleanup_verified": True,
            }
        )
        return False, None

    artifact_retained = backup.backup_path is not None
    retained_verified = False
    verification_error: str | None = None
    if artifact_retained and backup.tree is not None and backup.backup_path is not None:
        retained_verified, verification_error = verify_private_data_tree(
            backup.backup_path, backup.tree
        )
    elif artifact_retained:
        verification_error = "plugin_data_backup_contract_invalid"
    data.update(
        {
            "backup_retained": artifact_retained,
            "backup_location_token": (
                "UPGRADE_DATA_BACKUP" if artifact_retained else None
            ),
            "retained_backup_verified": retained_verified,
            "backup_cleanup_verified": False,
        }
    )
    return retained_verified, verification_error


def retained_backup_manual_step(result: dict[str, Any]) -> str:
    data = result["upgrade"]["data"]
    if data.get("retained_backup_verified"):
        return (
            "Preserve UPGRADE_DATA_BACKUP: the retained artifact was reverified as "
            "an exact private ledger backup. Inspect live Claude state before manual repair."
        )
    if data.get("backup_location_token"):
        return (
            "UPGRADE_DATA_BACKUP identifies a retained cleanup artifact, but it is "
            "not a verified recoverable backup. Treat the live ledger as authoritative, "
            "stop automated changes, and repair the artifact manually."
        )
    return (
        "No verified retained backup artifact is available. Treat the live ledger as "
        "authoritative and perform only evidence-driven manual repair."
    )


def finalize_plugin_data_restore(
    result: dict[str, Any], backup: PluginDataBackup
) -> tuple[bool, str | None]:
    restored, restore_error = restore_plugin_data(backup)
    if not restored:
        return False, restore_error or "plugin_data_restore_verification_failed"
    result["upgrade"]["data"]["restored_verified"] = True
    cleanup_ok, cleanup_error = cleanup_plugin_data_backup(backup)
    _retained_verified, retained_error = record_retained_backup_state(
        result,
        backup,
        cleanup_verified=cleanup_ok,
    )
    if not cleanup_ok:
        return False, (
            cleanup_error
            or retained_error
            or "plugin_data_backup_cleanup_failed"
        )
    return True, None


def attempt_verified_rollback(
    result: dict[str, Any],
    *,
    claude_executable: str,
    marketplace_list: Sequence[str],
    plugin_list: Sequence[str],
    uninstall_argv: Sequence[str],
    remove_argv: Sequence[str],
    install_argv: Sequence[str],
    old_add_argv: Sequence[str],
    old_path: Path,
    old_source: VerifiedSource,
    new_path: Path,
    new_source: VerifiedSource,
    data_backup: PluginDataBackup,
    claude_cwd: Path,
) -> tuple[bool, list[str]]:
    result["upgrade"]["rollback_attempted"] = True
    data_safe, data_error = plugin_data_transition_safe(data_backup)
    if not data_safe:
        return False, [data_error or "plugin_data_transition_not_safe"]
    state, errors = observe_upgrade_state(
        result,
        "rollback_start",
        marketplace_list,
        plugin_list,
        claude_executable=claude_executable,
        materialized=new_path,
        old_path=old_path,
        old_source=old_source,
        new_path=new_path,
        new_source=new_source,
        claude_cwd=claude_cwd,
    )
    if state == "unknown":
        return False, errors or ["rollback_start_state_unknown"]
    if state == "old_full":
        restored, restore_error = finalize_plugin_data_restore(result, data_backup)
        if not restored:
            return False, [restore_error or "plugin_data_restore_failed"]
        result["upgrade"]["rollback_verified"] = True
        result["state_change_possible"] = False
        return True, []

    if state == "new_full":
        run_recorded_mutation(
            result,
            "rollback_uninstall_new_plugin_keep_data",
            uninstall_argv,
            claude_executable=claude_executable,
            materialized=new_path,
            claude_cwd=claude_cwd,
        )
        state, errors = observe_upgrade_state(
            result,
            "rollback_after_uninstall_new",
            marketplace_list,
            plugin_list,
            claude_executable=claude_executable,
            materialized=new_path,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            claude_cwd=claude_cwd,
        )
        data_safe, data_error = plugin_data_transition_safe(data_backup)
        if state != "new_marketplace_only" or not data_safe:
            return False, errors or [
                data_error or "rollback_new_plugin_keep_data_uninstall_unverified"
            ]

    if state == "new_marketplace_only":
        new_ok, new_error = verify_materialized_tree(new_path, new_source)
        if not new_ok:
            return False, [new_error or "rollback_new_snapshot_reverification_failed"]
        run_recorded_mutation(
            result,
            "rollback_remove_new_marketplace",
            remove_argv,
            claude_executable=claude_executable,
            materialized=new_path,
            claude_cwd=claude_cwd,
        )
        state, errors = observe_upgrade_state(
            result,
            "rollback_after_remove_new",
            marketplace_list,
            plugin_list,
            claude_executable=claude_executable,
            materialized=new_path,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            claude_cwd=claude_cwd,
        )
        if state == "old_full":
            restored, restore_error = finalize_plugin_data_restore(result, data_backup)
            if not restored:
                return False, [restore_error or "plugin_data_restore_failed"]
            result["upgrade"]["rollback_verified"] = True
            result["state_change_possible"] = False
            return True, []
        if state != "empty":
            return False, errors or ["rollback_new_marketplace_removal_unverified"]

    if state == "empty":
        old_ok, old_error = reverify_legacy_snapshot(old_source, old_path)
        if not old_ok:
            return False, [old_error or "rollback_legacy_snapshot_reverification_failed"]
        run_recorded_mutation(
            result,
            "rollback_add_old_marketplace",
            old_add_argv,
            claude_executable=claude_executable,
            materialized=old_path,
            claude_cwd=claude_cwd,
        )
        state, errors = observe_upgrade_state(
            result,
            "rollback_after_add_old",
            marketplace_list,
            plugin_list,
            claude_executable=claude_executable,
            materialized=old_path,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            claude_cwd=claude_cwd,
        )
        if state == "old_full":
            restored, restore_error = finalize_plugin_data_restore(result, data_backup)
            if not restored:
                return False, [restore_error or "plugin_data_restore_failed"]
            result["upgrade"]["rollback_verified"] = True
            result["state_change_possible"] = False
            return True, []
        if state != "old_marketplace_only":
            return False, errors or ["rollback_old_marketplace_add_unverified"]

    if state == "old_marketplace_only":
        old_ok, old_error = reverify_legacy_snapshot(old_source, old_path)
        if not old_ok:
            return False, [old_error or "rollback_legacy_snapshot_reverification_failed"]
        run_recorded_mutation(
            result,
            "rollback_install_old_plugin",
            install_argv,
            claude_executable=claude_executable,
            materialized=old_path,
            claude_cwd=claude_cwd,
        )
        state, errors = observe_upgrade_state(
            result,
            "rollback_after_install_old",
            marketplace_list,
            plugin_list,
            claude_executable=claude_executable,
            materialized=old_path,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            claude_cwd=claude_cwd,
        )
        if state == "old_full":
            restored, restore_error = finalize_plugin_data_restore(result, data_backup)
            if not restored:
                return False, [restore_error or "plugin_data_restore_failed"]
            result["upgrade"]["rollback_verified"] = True
            result["state_change_possible"] = False
            return True, []
        return False, errors or ["rollback_old_plugin_install_unverified"]

    return False, ["rollback_state_not_repairable"]


def fail_verified_upgrade(
    result: dict[str, Any],
    error_codes: list[str],
    *,
    claude_executable: str,
    marketplace_list: Sequence[str],
    plugin_list: Sequence[str],
    uninstall_argv: Sequence[str],
    remove_argv: Sequence[str],
    install_argv: Sequence[str],
    old_add_argv: Sequence[str],
    old_path: Path,
    old_source: VerifiedSource,
    new_path: Path,
    new_source: VerifiedSource,
    data_backup: PluginDataBackup,
    claude_cwd: Path,
) -> tuple[int, dict[str, Any]]:
    rolled_back, rollback_errors = attempt_verified_rollback(
        result,
        claude_executable=claude_executable,
        marketplace_list=marketplace_list,
        plugin_list=plugin_list,
        uninstall_argv=uninstall_argv,
        remove_argv=remove_argv,
        install_argv=install_argv,
        old_add_argv=old_add_argv,
        old_path=old_path,
        old_source=old_source,
        new_path=new_path,
        new_source=new_source,
        data_backup=data_backup,
        claude_cwd=claude_cwd,
    )
    result["operation_ok"] = False
    result["ok"] = False
    result["verification"]["configuration"] = False
    result["error_codes"] = [*error_codes, *rollback_errors]
    if rolled_back:
        result["status"] = "VERIFIED_UPGRADE_FAILED_ROLLED_BACK"
        result["next_steps"] = [
            "The RC4 upgrade did not complete, but the exact prior verified ACGM configuration was restored. Inspect the recorded error before retrying."
        ]
        return 1, result
    if data_backup.backup_path is not None:
        record_retained_backup_state(
            result,
            data_backup,
            cleanup_verified=False,
        )
    result["status"] = "VERIFIED_UPGRADE_PARTIAL_STATE_REQUIRES_MANUAL_REPAIR"
    result["requires_user_action"] = True
    result["next_steps"] = [
        "Stop automated changes. The installer could not prove a safe rollback state; inspect both Claude JSON lists and user marketplace settings.",
        retained_backup_manual_step(result),
    ]
    return 1, result


def execute_verified_upgrade(
    result: dict[str, Any],
    *,
    claude_executable: str,
    marketplace_list: Sequence[str],
    plugin_list: Sequence[str],
    uninstall_argv: Sequence[str],
    remove_argv: Sequence[str],
    add_argv: Sequence[str],
    install_argv: Sequence[str],
    old_add_argv: Sequence[str],
    old_path: Path,
    old_source: VerifiedSource,
    old_install_record: dict[str, Any],
    new_path: Path,
    new_source: VerifiedSource,
    claude_cwd: Path,
) -> tuple[int, dict[str, Any]]:
    sources_ok, source_error = verify_upgrade_sources(
        new_source, new_path, old_source, old_path
    )
    if not sources_ok:
        result["status"] = "VERIFIED_UPGRADE_SOURCE_RECHECK_FAILED"
        result["error_codes"] = [source_error or "upgrade_source_reverification_failed"]
        result["next_steps"] = ["No Claude mutation was attempted; restore the verified sources and retry."]
        return 2, result

    data_backup, data_backup_error = prepare_plugin_data_backup()
    if data_backup is None or data_backup_error:
        result["status"] = "VERIFIED_UPGRADE_DATA_BACKUP_BLOCKED"
        result["error_codes"] = [
            data_backup_error or "plugin_data_backup_verification_failed"
        ]
        result["next_steps"] = [
            "No Claude mutation was attempted. Make the ACGM plugin data directory private, regular, and symlink-free, then retry."
        ]
        return 2, result
    result["upgrade"]["data"].update(
        {
            "source_state": "present" if data_backup.existed else "absent",
            "backup_verified": True,
            "backup_retained": bool(data_backup.backup_path),
            "backup_location_token": (
                "UPGRADE_DATA_BACKUP" if data_backup.backup_path else None
            ),
            "retained_backup_verified": bool(data_backup.backup_path),
        }
    )

    old_in_use, old_in_use_error = installed_plugin_in_use(old_install_record)
    if old_in_use_error or old_in_use:
        cleanup_ok, cleanup_error = cleanup_plugin_data_backup(data_backup)
        retained_verified, retained_error = record_retained_backup_state(
            result,
            data_backup,
            cleanup_verified=cleanup_ok,
        )
        result["status"] = "VERIFIED_UPGRADE_PLUGIN_IN_USE"
        result["error_codes"] = [
            old_in_use_error or "installed_plugin_cache_in_use"
        ]
        if cleanup_error:
            result["error_codes"].append(cleanup_error)
        if not cleanup_ok and not retained_verified:
            result["error_codes"].append(
                "retained_plugin_data_backup_not_verified"
            )
            if retained_error:
                result["error_codes"].append(retained_error)
        if cleanup_ok:
            result["next_steps"] = [
                "Close every Claude session using ACGM and retry; the temporary verified backup was removed and no Claude mutation was attempted."
            ]
        else:
            result["next_steps"] = [
                "No Claude mutation was attempted. Close every ACGM session before any retry.",
                retained_backup_manual_step(result),
            ]
        return 2, result

    run_recorded_mutation(
        result,
        "upgrade_uninstall_old_plugin_keep_data",
        uninstall_argv,
        claude_executable=claude_executable,
        materialized=old_path,
        claude_cwd=claude_cwd,
    )
    result["changed"] = True
    state, errors = observe_upgrade_state(
        result,
        "upgrade_after_uninstall_old",
        marketplace_list,
        plugin_list,
        claude_executable=claude_executable,
        materialized=old_path,
        old_path=old_path,
        old_source=old_source,
        new_path=new_path,
        new_source=new_source,
        claude_cwd=claude_cwd,
    )
    if state != "old_marketplace_only":
        return fail_verified_upgrade(
            result,
            errors or ["old_plugin_keep_data_uninstall_unverified"],
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            data_backup=data_backup,
            claude_cwd=claude_cwd,
        )
    data_safe, data_error = plugin_data_unchanged(data_backup)
    if not data_safe:
        return fail_verified_upgrade(
            result,
            [data_error or "plugin_data_changed_after_keep_data_uninstall"],
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            data_backup=data_backup,
            claude_cwd=claude_cwd,
        )

    old_in_use, old_in_use_error = installed_plugin_in_use(old_install_record)
    if old_in_use_error or old_in_use:
        return fail_verified_upgrade(
            result,
            [old_in_use_error or "installed_plugin_cache_in_use"],
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            data_backup=data_backup,
            claude_cwd=claude_cwd,
        )
    run_recorded_mutation(
        result,
        "upgrade_remove_old_marketplace",
        remove_argv,
        claude_executable=claude_executable,
        materialized=old_path,
        claude_cwd=claude_cwd,
    )
    result["changed"] = True
    state, errors = observe_upgrade_state(
        result,
        "upgrade_after_remove_old",
        marketplace_list,
        plugin_list,
        claude_executable=claude_executable,
        materialized=old_path,
        old_path=old_path,
        old_source=old_source,
        new_path=new_path,
        new_source=new_source,
        claude_cwd=claude_cwd,
    )
    if state != "empty":
        return fail_verified_upgrade(
            result,
            errors or ["old_marketplace_removal_unverified"],
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            data_backup=data_backup,
            claude_cwd=claude_cwd,
        )

    data_safe, data_error = plugin_data_unchanged(data_backup)
    if not data_safe:
        return fail_verified_upgrade(
            result,
            [data_error or "plugin_data_transition_not_safe"],
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            data_backup=data_backup,
            claude_cwd=claude_cwd,
        )
    sources_ok, source_error = verify_upgrade_sources(
        new_source, new_path, old_source, old_path
    )
    if not sources_ok:
        return fail_verified_upgrade(
            result,
            [source_error or "upgrade_source_reverification_failed"],
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            data_backup=data_backup,
            claude_cwd=claude_cwd,
        )
    old_in_use, old_in_use_error = installed_plugin_in_use(old_install_record)
    if old_in_use_error or old_in_use:
        return fail_verified_upgrade(
            result,
            [old_in_use_error or "installed_plugin_cache_in_use"],
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            data_backup=data_backup,
            claude_cwd=claude_cwd,
        )
    run_recorded_mutation(
        result,
        "upgrade_add_new_marketplace",
        add_argv,
        claude_executable=claude_executable,
        materialized=new_path,
        claude_cwd=claude_cwd,
    )
    state, errors = observe_upgrade_state(
        result,
        "upgrade_after_add_new",
        marketplace_list,
        plugin_list,
        claude_executable=claude_executable,
        materialized=new_path,
        old_path=old_path,
        old_source=old_source,
        new_path=new_path,
        new_source=new_source,
        claude_cwd=claude_cwd,
    )
    if state == "new_full":
        pass
    elif state != "new_marketplace_only":
        return fail_verified_upgrade(
            result,
            errors or ["new_marketplace_add_unverified"],
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            data_backup=data_backup,
            claude_cwd=claude_cwd,
        )
    else:
        data_safe, data_error = plugin_data_unchanged(data_backup)
        if not data_safe:
            return fail_verified_upgrade(
                result,
                [data_error or "plugin_data_transition_not_safe"],
                claude_executable=claude_executable,
                marketplace_list=marketplace_list,
                plugin_list=plugin_list,
                uninstall_argv=uninstall_argv,
                remove_argv=remove_argv,
                install_argv=install_argv,
                old_add_argv=old_add_argv,
                old_path=old_path,
                old_source=old_source,
                new_path=new_path,
                new_source=new_source,
                data_backup=data_backup,
                claude_cwd=claude_cwd,
            )
        sources_ok, source_error = verify_upgrade_sources(
            new_source, new_path, old_source, old_path
        )
        if not sources_ok:
            return fail_verified_upgrade(
                result,
                [source_error or "upgrade_source_reverification_failed"],
                claude_executable=claude_executable,
                marketplace_list=marketplace_list,
                plugin_list=plugin_list,
                uninstall_argv=uninstall_argv,
                remove_argv=remove_argv,
                install_argv=install_argv,
                old_add_argv=old_add_argv,
                old_path=old_path,
                old_source=old_source,
                new_path=new_path,
                new_source=new_source,
                data_backup=data_backup,
                claude_cwd=claude_cwd,
            )
        old_in_use, old_in_use_error = installed_plugin_in_use(old_install_record)
        if old_in_use_error or old_in_use:
            return fail_verified_upgrade(
                result,
                [old_in_use_error or "installed_plugin_cache_in_use"],
                claude_executable=claude_executable,
                marketplace_list=marketplace_list,
                plugin_list=plugin_list,
                uninstall_argv=uninstall_argv,
                remove_argv=remove_argv,
                install_argv=install_argv,
                old_add_argv=old_add_argv,
                old_path=old_path,
                old_source=old_source,
                new_path=new_path,
                new_source=new_source,
                data_backup=data_backup,
                claude_cwd=claude_cwd,
            )
        run_recorded_mutation(
            result,
            "upgrade_install_new_plugin",
            install_argv,
            claude_executable=claude_executable,
            materialized=new_path,
            claude_cwd=claude_cwd,
        )
        state, errors = observe_upgrade_state(
            result,
            "upgrade_after_install_new",
            marketplace_list,
            plugin_list,
            claude_executable=claude_executable,
            materialized=new_path,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            claude_cwd=claude_cwd,
        )
        if state != "new_full":
            return fail_verified_upgrade(
                result,
                errors or ["new_plugin_install_unverified"],
                claude_executable=claude_executable,
                marketplace_list=marketplace_list,
                plugin_list=plugin_list,
                uninstall_argv=uninstall_argv,
                remove_argv=remove_argv,
                install_argv=install_argv,
                old_add_argv=old_add_argv,
                old_path=old_path,
                old_source=old_source,
                new_path=new_path,
                new_source=new_source,
                data_backup=data_backup,
                claude_cwd=claude_cwd,
            )

    data_safe, data_error = plugin_data_unchanged(data_backup)
    if not data_safe:
        return fail_verified_upgrade(
            result,
            [data_error or "plugin_data_transition_not_safe"],
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            data_backup=data_backup,
            claude_cwd=claude_cwd,
        )
    restored, restore_error = finalize_plugin_data_restore(result, data_backup)
    if not restored:
        return fail_verified_upgrade(
            result,
            [restore_error or "plugin_data_restore_failed"],
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            new_path=new_path,
            new_source=new_source,
            data_backup=data_backup,
            claude_cwd=claude_cwd,
        )

    result["status"] = "CONFIGURATION_VERIFIED_UPGRADED"
    result["operation_ok"] = True
    result["ok"] = True
    result["requires_user_action"] = True
    result["state_change_possible"] = False
    result["verification"]["configuration"] = True
    result["observed_installed_version"] = new_source.version
    result["actions"] = [
        action
        for action in result["actions"]
        if action.get("id") == "activate_and_verify_runtime"
    ]
    result["next_steps"] = [
        "Restart Claude Code or run /reload-plugins.",
        "Open a fresh target session and verify /hooks, /skills, acgm version, and acgm doctor --json before reporting ACTIVE_VERIFIED.",
    ]
    return 0, result


def _install_with_neutral_cwd(
    *,
    dry_run: bool = False,
    surface: str = "auto",
    upgrade_verified_snapshot: bool = False,
    claude_cwd: Path,
) -> tuple[int, dict[str, Any]]:
    report = preflight.build_report(surface)
    revision = checkout_revision()
    clean = checkout_clean()
    result = base_result(
        dry_run,
        report,
        revision,
        clean,
        upgrade_verified_snapshot=upgrade_verified_snapshot,
    )

    preflight_status = report.get("status")
    if preflight_status not in preflight.READY_STATUSES:
        result["status"] = str(preflight_status or "PREFLIGHT_BLOCKED")
        result["error_codes"] = list(report.get("error_codes") or ["preflight_blocked"])
        result["next_steps"] = [
            str(action.get("instruction") or action.get("command"))
            for action in report.get("actions") or []
            if action.get("instruction") or action.get("command")
        ] or ["Resolve the preflight blockers, then rerun this installer."]
        return 2, result
    if revision is None:
        return _source_blocked(
            result,
            "CHECKOUT_REVISION_BLOCKED",
            ["checkout_git_commit_unavailable"],
            "Use a Git clone at a recorded commit; no Claude state was changed.",
        )
    if clean is not True:
        return _source_blocked(
            result,
            "CHECKOUT_DIRTY_BLOCKED" if clean is False else "CHECKOUT_CLEANLINESS_BLOCKED",
            [
                "checkout_has_uncommitted_or_untracked_files"
                if clean is False
                else "checkout_cleanliness_unavailable"
            ],
            "Use a clean reviewed Git checkout; this installer never installs uncommitted files.",
        )

    expected_version = report.get("acgm_version")
    if not isinstance(expected_version, str) or not expected_version:
        return _source_blocked(
            result,
            "SOURCE_INTEGRITY_BLOCKED",
            ["preflight_version_missing"],
            "Use a checkout whose version contract can be verified.",
        )
    source, source_errors = capture_verified_source(
        expected_version, revision, clean
    )
    if source is None:
        return _source_blocked(
            result,
            "SOURCE_INTEGRITY_BLOCKED",
            source_errors or ["package_manifest_verification_failed"],
            "Use an unchanged clean checkout whose tracked inventory and PACKAGE_MANIFEST.json agree.",
        )
    result["source"]["package_integrity_ok"] = True
    result["source"]["snapshot_id"] = source.snapshot_name
    result["verification"]["source"] = True

    if preflight_status == "MANUAL_INSTALL_PLAN_AVAILABLE":
        result["installation_shape"] = "github_tag_desktop_ui"
        result["status"] = "SOURCE_VERIFIED_MANUAL_INSTALL_REQUIRED"
        result["operation_ok"] = True
        result["requires_user_action"] = True
        result["actions"] = [
            action
            for action in result["actions"]
            if action.get("id") != "verify_source_for_manual_install"
        ]
        result["next_steps"] = [
            str(action.get("instruction") or action.get("command"))
            for action in result["actions"]
            if action.get("instruction") or action.get("command")
        ]
        return 0, result

    claude_path, claude_error = preflight.resolve_claude_executable()
    if claude_error or claude_path is None:
        return _source_blocked(
            result,
            "CLAUDE_LAUNCHER_BLOCKED",
            [claude_error or "claude_launcher_unavailable"],
            "Install the native Claude Code executable and rerun preflight.",
        )
    claude_executable = str(claude_path)
    result["scope"] = "user"
    result["installation_shape"] = "verified_snapshot_user"
    materialized = snapshot_path(source)
    add_argv = [
        claude_executable,
        "plugin",
        "marketplace",
        "add",
        str(materialized),
        "--scope",
        "user",
    ]
    install_argv = [
        claude_executable,
        "plugin",
        "install",
        PLUGIN_ID,
        "--scope",
        "user",
    ]
    result["planned_commands"] = [
        display_argv(
            add_argv,
            claude_executable=claude_executable,
            materialized=materialized,
        ),
        display_argv(
            install_argv,
            claude_executable=claude_executable,
            materialized=materialized,
        ),
    ]
    if dry_run and not upgrade_verified_snapshot:
        result["status"] = "SOURCE_VERIFIED_AUTOMATED_INSTALL_READY"
        result["operation_ok"] = True
        result["requires_user_action"] = True
        result["next_steps"] = [
            "Rerun without --dry-run. Claude state will be inspected before a persistent verified snapshot or plugin declaration is created."
        ]
        return 0, result

    marketplace_list = [
        claude_executable,
        "plugin",
        "marketplace",
        "list",
        "--json",
    ]
    plugin_list = [claude_executable, "plugin", "list", "--json"]
    marketplaces, marketplace_error = inspect_json(
        result,
        "marketplace_list",
        marketplace_list,
        parser=parse_marketplace_payload,
        claude_executable=claude_executable,
        materialized=materialized,
        claude_cwd=claude_cwd,
    )
    plugins, plugin_error = inspect_json(
        result,
        "plugin_list",
        plugin_list,
        parser=parse_plugin_payload,
        claude_executable=claude_executable,
        materialized=materialized,
        claude_cwd=claude_cwd,
    )
    if marketplace_error or plugin_error:
        result["status"] = "STATE_INSPECTION_BLOCKED"
        result["error_codes"] = [
            code for code in (marketplace_error, plugin_error) if code is not None
        ]
        result["next_steps"] = [
            "Resolve Claude CLI/auth/lock errors and inspect both JSON list commands; no Claude mutation was attempted."
        ]
        return 2, result

    assert marketplaces is not None and plugins is not None
    existing_marketplaces = matching_marketplaces(marketplaces)
    existing_plugins = matching_plugins(plugins)
    if len(existing_marketplaces) > 1:
        result["status"] = "MARKETPLACE_CONFLICT"
        result["error_codes"] = [
            "multiple_marketplace_records_for_acgm_identity"
        ]
        result["next_steps"] = [
            "Inspect the duplicate marketplace records manually; this installer never chooses among them."
        ]
        return 2, result
    if len(existing_plugins) > 1:
        result["status"] = "INSTALLED_PLUGIN_CONFLICT"
        result["error_codes"] = ["multiple_installed_plugin_records"]
        result["next_steps"] = [
            "Resolve duplicate plugin scopes manually; this installer never uninstalls or changes scope."
        ]
        return 2, result

    legacy_detection = detect_legacy_public_github_install(
        existing_marketplaces, existing_plugins
    )
    if legacy_detection is not None:
        migration_plan = legacy_public_migration_plan(
            target_version=source.version,
            report=report,
        )
        result["status"] = "LEGACY_PUBLIC_GITHUB_INSTALL_REQUIRES_EXPLICIT_MIGRATION"
        result["operation_ok"] = False
        result["ok"] = False
        result["ready_for_use"] = False
        result["requires_user_action"] = True
        result["mutation_attempted"] = False
        result["state_change_possible"] = False
        result["scope"] = "user"
        result["installation_shape"] = "legacy_public_github_user"
        result["legacy_detection"] = legacy_detection
        result["manual_migration_plan"] = migration_plan
        result["planned_commands"] = []
        result["actions"] = migration_plan["steps"]
        result["error_codes"] = ["legacy_public_github_install_not_auto_migratable"]
        result["next_steps"] = [
            "The repo/ref fields identify a legacy configuration shape only; they do not prove publisher authenticity or installed bytes. Review and authorize a separate migration plan."
        ]
        return 2, result

    user_declaration, user_declaration_error = user_marketplace_declaration(materialized)
    if user_declaration_error:
        result["status"] = "USER_SCOPE_INSPECTION_BLOCKED"
        result["error_codes"] = [user_declaration_error]
        result["next_steps"] = [
            "The documented user-scope marketplace declaration could not be read safely; no Claude mutation was attempted."
        ]
        return 2, result
    marketplace_is_different = bool(existing_marketplaces) and not marketplace_source_matches(
        existing_marketplaces[0], materialized
    )
    has_marketplace_conflict = marketplace_is_different or user_declaration == "conflict"
    if has_marketplace_conflict:
        if not upgrade_verified_snapshot:
            result["status"] = "MARKETPLACE_CONFLICT"
            result["error_codes"] = [
                "marketplace_name_exists_with_different_or_unverifiable_source"
            ]
            result["next_steps"] = [
                "The ACGM marketplace name points elsewhere. Rerun only with --upgrade-verified-snapshot if this is a prior installer snapshot; unknown sources are never replaced."
            ]
            return 2, result

        upgrade_errors: list[str] = []
        old_path = (
            marketplace_source_path(existing_marketplaces[0])
            if len(existing_marketplaces) == 1
            else None
        )
        if old_path is None:
            upgrade_errors.append("legacy_marketplace_source_path_unavailable")
        if len(existing_plugins) != 1:
            upgrade_errors.append("legacy_installed_plugin_not_unique")
        old_source: VerifiedSource | None = None
        if old_path is not None:
            old_source, snapshot_errors = capture_verified_snapshot(old_path)
            upgrade_errors.extend(snapshot_errors)
        if old_path is not None:
            old_declaration, old_declaration_error = user_marketplace_declaration(old_path)
            if old_declaration_error:
                upgrade_errors.append(old_declaration_error)
            elif old_declaration != "exact":
                upgrade_errors.append("legacy_user_marketplace_declaration_not_exact")
        if old_source is not None and existing_plugins:
            old_plugin_ok, old_plugin_errors = verify_installed_plugin(
                existing_plugins[0], old_source
            )
            if not old_plugin_ok:
                upgrade_errors.extend(old_plugin_errors)
            old_plugin_in_use, old_plugin_in_use_error = installed_plugin_in_use(
                existing_plugins[0]
            )
            if old_plugin_in_use_error:
                upgrade_errors.append(old_plugin_in_use_error)
            elif old_plugin_in_use:
                result["status"] = "VERIFIED_UPGRADE_PLUGIN_IN_USE"
                result["error_codes"] = ["installed_plugin_cache_in_use"]
                result["next_steps"] = [
                    "Close every Claude Code and Desktop Code session using ACGM, confirm the cache .in_use marker is gone, then rerun; no mutation was attempted."
                ]
                return 2, result
        if old_source is not None and not version_is_strictly_older(
            old_source.version, source.version
        ):
            upgrade_errors.append("legacy_version_not_strictly_older")
        if old_path is not None and marketplace_source_matches(
            existing_marketplaces[0], materialized
        ):
            upgrade_errors.append("legacy_marketplace_does_not_differ_from_target")
        if upgrade_errors or old_path is None or old_source is None:
            result["status"] = "VERIFIED_UPGRADE_PRECONDITIONS_BLOCKED"
            result["error_codes"] = list(dict.fromkeys(upgrade_errors)) or [
                "verified_upgrade_preconditions_not_met"
            ]
            result["next_steps"] = [
                "No Claude mutation was attempted. Only a unique user-scope ACGM install backed by an intact older immutable snapshot and matching cache can be upgraded automatically."
            ]
            return 2, result

        remove_help_argv = [
            claude_executable,
            "plugin",
            "marketplace",
            "remove",
            "--help",
        ]
        remove_help = run_command(
            remove_help_argv,
            timeout=INSPECT_TIMEOUT_SECONDS,
            cwd=claude_cwd,
        )
        result["executed"].append(
            command_record(
                "upgrade_scoped_remove_capability",
                remove_help_argv,
                remove_help,
                claude_executable=claude_executable,
                materialized=materialized,
            )
        )
        remove_help_text = f"{remove_help.stdout}\n{remove_help.stderr}"
        if remove_help.returncode != 0 or "--scope" not in remove_help_text:
            result["status"] = "VERIFIED_UPGRADE_SCOPED_REMOVE_UNAVAILABLE"
            result["error_codes"] = ["marketplace_remove_user_scope_capability_missing"]
            result["next_steps"] = [
                "Upgrade Claude Code to a version whose marketplace remove command explicitly supports --scope; no unscoped removal was attempted."
            ]
            return 2, result

        uninstall_help_argv = [
            claude_executable,
            "plugin",
            "uninstall",
            "--help",
        ]
        uninstall_help = run_command(
            uninstall_help_argv,
            timeout=INSPECT_TIMEOUT_SECONDS,
            cwd=claude_cwd,
        )
        result["executed"].append(
            command_record(
                "upgrade_keep_data_uninstall_capability",
                uninstall_help_argv,
                uninstall_help,
                claude_executable=claude_executable,
                materialized=materialized,
            )
        )
        uninstall_help_text = f"{uninstall_help.stdout}\n{uninstall_help.stderr}"
        if (
            uninstall_help.returncode != 0
            or "--scope" not in uninstall_help_text
            or "--keep-data" not in uninstall_help_text
        ):
            result["status"] = "VERIFIED_UPGRADE_KEEP_DATA_UNINSTALL_UNAVAILABLE"
            result["error_codes"] = [
                "plugin_uninstall_user_scope_keep_data_capability_missing"
            ]
            result["next_steps"] = [
                "Upgrade Claude Code to a version whose plugin uninstall command explicitly supports both --scope and --keep-data; no mutation was attempted."
            ]
            return 2, result

        result["upgrade"].update(
            {
                "from_version": old_source.version,
                "to_version": source.version,
                "from_snapshot_id": old_path.name,
                "preconditions_verified": True,
            }
        )
        remove_argv = [
            claude_executable,
            "plugin",
            "marketplace",
            "remove",
            MARKETPLACE_NAME,
            "--scope",
            "user",
        ]
        uninstall_argv = [
            claude_executable,
            "plugin",
            "uninstall",
            PLUGIN_ID,
            "--scope",
            "user",
            "--keep-data",
        ]
        old_add_argv = [
            claude_executable,
            "plugin",
            "marketplace",
            "add",
            str(old_path),
            "--scope",
            "user",
        ]
        result["planned_commands"] = [
            display_argv(
                uninstall_argv,
                claude_executable=claude_executable,
                materialized=old_path,
            ),
            display_argv(
                remove_argv,
                claude_executable=claude_executable,
                materialized=old_path,
            ),
            display_argv(
                add_argv,
                claude_executable=claude_executable,
                materialized=materialized,
            ),
            display_argv(
                install_argv,
                claude_executable=claude_executable,
                materialized=materialized,
            ),
        ]
        if dry_run:
            result["status"] = "VERIFIED_UPGRADE_READY"
            result["operation_ok"] = True
            result["requires_user_action"] = True
            result["next_steps"] = [
                "Rerun without --dry-run and keep --upgrade-verified-snapshot to authorize the verified strictly-forward replacement."
            ]
            return 0, result

        materialized_snapshot, snapshot_created, snapshot_error = create_or_verify_snapshot(
            source
        )
        if materialized_snapshot is None or snapshot_error:
            result["status"] = "VERIFIED_SNAPSHOT_BLOCKED"
            result["error_codes"] = [snapshot_error or "verified_snapshot_unavailable"]
            result["next_steps"] = [
                "The old verified install remains unchanged; the new persistent snapshot could not be prepared."
            ]
            return 2, result
        materialized = materialized_snapshot
        result["changed"] = snapshot_created
        return execute_verified_upgrade(
            result,
            claude_executable=claude_executable,
            marketplace_list=marketplace_list,
            plugin_list=plugin_list,
            uninstall_argv=uninstall_argv,
            remove_argv=remove_argv,
            add_argv=add_argv,
            install_argv=install_argv,
            old_add_argv=old_add_argv,
            old_path=old_path,
            old_source=old_source,
            old_install_record=existing_plugins[0],
            new_path=materialized,
            new_source=source,
            claude_cwd=claude_cwd,
        )

    if dry_run:
        result["status"] = "SOURCE_VERIFIED_AUTOMATED_INSTALL_READY"
        result["operation_ok"] = True
        result["requires_user_action"] = True
        result["next_steps"] = [
            "Rerun without --dry-run. Claude state was inspected, but no snapshot or declaration was created."
        ]
        return 0, result

    if existing_marketplaces and user_declaration == "exact":
        result["planned_commands"] = [
            display_argv(
                install_argv,
                claude_executable=claude_executable,
                materialized=materialized,
            )
        ]

    materialized_snapshot, snapshot_created, snapshot_error = create_or_verify_snapshot(
        source
    )
    if materialized_snapshot is None or snapshot_error:
        result["status"] = "VERIFIED_SNAPSHOT_BLOCKED"
        result["error_codes"] = [snapshot_error or "verified_snapshot_unavailable"]
        result["next_steps"] = [
            "Inspect the persistent ACGM snapshot directory; no Claude mutation was attempted."
        ]
        return 2, result
    materialized = materialized_snapshot
    result["changed"] = snapshot_created

    if existing_plugins:
        if not existing_marketplaces or user_declaration != "exact":
            result["status"] = "ALREADY_INSTALLED_REQUIRES_MANUAL_REPAIR"
            result["error_codes"] = [
                "installed_plugin_user_marketplace_not_declared_or_mismatched"
            ]
            result["next_steps"] = [
                "The plugin ID exists without this exact user-scope verified marketplace declaration; repair it manually before retrying."
            ]
            return 2, result
        verified, errors = verify_installed_plugin(existing_plugins[0], source)
        if not verified:
            result["status"] = "ALREADY_INSTALLED_REQUIRES_RUNTIME_VERIFICATION"
            result["error_codes"] = errors
            result["next_steps"] = [
                "The installed ID was not proven to be this exact user-scope snapshot. Inspect or uninstall it manually; no Claude mutation was attempted."
            ]
            return 2, result
        result["status"] = "CONFIGURATION_VERIFIED_EXISTING"
        result["operation_ok"] = True
        result["ok"] = True
        result["requires_user_action"] = True
        result["verification"]["configuration"] = True
        result["observed_installed_version"] = source.version
        result["actions"] = [
            action
            for action in result["actions"]
            if action.get("id") == "activate_and_verify_runtime"
        ]
        result["next_steps"] = [
            "Restart Claude Code or run /reload-plugins.",
            "Open a fresh disposable target session and run /hooks, /skills, acgm version, and acgm doctor --json.",
            "Treat doctor's SessionStart record as historical corroboration only; establish ACTIVE_VERIFIED with the same-surface manual E2E checklist.",
            "Initialize project governance only after reviewing its project-specific choices.",
        ]
        return 0, result

    if not existing_marketplaces or user_declaration != "exact":
        source_ok, source_error = reverify_source_and_snapshot(source, materialized)
        if not source_ok:
            result["status"] = "PRE_MUTATION_SOURCE_VERIFICATION_FAILED"
            result["error_codes"] = [source_error or "source_reverification_failed"]
            result["next_steps"] = ["No Claude mutation was attempted; restore the clean checkout and snapshot."]
            return 2, result

        result["mutation_attempted"] = True
        result["state_change_possible"] = True
        added = run_command(
            add_argv,
            timeout=MUTATION_TIMEOUT_SECONDS,
            cwd=claude_cwd,
        )
        result["executed"].append(
            command_record(
                "marketplace_add",
                add_argv,
                added,
                claude_executable=claude_executable,
                materialized=materialized,
            )
        )
        if added.returncode != 0:
            result["status"] = "MARKETPLACE_ADD_FAILED"
            result["error_codes"] = [added.error_code or "marketplace_add_command_failed"]
            result["next_steps"] = [
                "No plugin install was attempted. Inspect Claude marketplace state before retrying."
            ]
            return 1, result
        result["changed"] = True

        verified_marketplaces, verify_marketplace_error = inspect_json(
            result,
            "marketplace_verify",
            marketplace_list,
            parser=parse_marketplace_payload,
            claude_executable=claude_executable,
            materialized=materialized,
            claude_cwd=claude_cwd,
        )
        matching_after_add = (
            matching_marketplaces(verified_marketplaces or [])
            if not verify_marketplace_error
            else []
        )
        verified_user_declaration, verified_user_error = user_marketplace_declaration(
            materialized
        )
        if (
            verify_marketplace_error
            or verified_user_error
            or len(matching_after_add) != 1
            or not marketplace_source_matches(matching_after_add[0], materialized)
            or verified_user_declaration != "exact"
        ):
            result["status"] = "MARKETPLACE_VERIFICATION_FAILED"
            result["error_codes"] = [
                verify_marketplace_error
                or verified_user_error
                or "marketplace_not_verified_after_add_at_user_scope"
            ]
            result["next_steps"] = [
                "Marketplace add may have partially succeeded. The plugin was not installed; inspect marketplace JSON and user-scope settings manually."
            ]
            return 1, result
        result["state_change_possible"] = False

    source_ok, source_error = reverify_source_and_snapshot(source, materialized)
    if not source_ok:
        result["status"] = "PRE_INSTALL_SOURCE_VERIFICATION_FAILED"
        result["error_codes"] = [source_error or "source_reverification_failed"]
        result["next_steps"] = [
            "The marketplace may now exist, but plugin install was stopped because verified source identity changed."
        ]
        return 1, result

    result["mutation_attempted"] = True
    result["state_change_possible"] = True
    installed_result = run_command(
        install_argv,
        timeout=MUTATION_TIMEOUT_SECONDS,
        cwd=claude_cwd,
    )
    result["executed"].append(
        command_record(
            "plugin_install",
            install_argv,
            installed_result,
            claude_executable=claude_executable,
            materialized=materialized,
        )
    )
    if installed_result.returncode != 0:
        result["status"] = "PLUGIN_INSTALL_FAILED"
        result["error_codes"] = [
            installed_result.error_code or "plugin_install_command_failed"
        ]
        result["next_steps"] = [
            "The verified marketplace may exist, but installation was not verified. Inspect plugin state before retrying."
        ]
        return 1, result
    result["changed"] = True

    verified_plugins, verify_plugin_error = inspect_json(
        result,
        "plugin_verify",
        plugin_list,
        parser=parse_plugin_payload,
        claude_executable=claude_executable,
        materialized=materialized,
        claude_cwd=claude_cwd,
    )
    matching_after_install = (
        matching_plugins(verified_plugins or []) if not verify_plugin_error else []
    )
    if verify_plugin_error or len(matching_after_install) != 1:
        result["status"] = "PLUGIN_VERIFICATION_FAILED"
        result["error_codes"] = [
            verify_plugin_error or "plugin_not_uniquely_listed_after_install"
        ]
        result["next_steps"] = [
            "Install may have partially succeeded; inspect plugin JSON state manually before retrying."
        ]
        return 1, result

    verified, verification_errors = verify_installed_plugin(
        matching_after_install[0], source
    )
    if not verified:
        result["status"] = "PLUGIN_CONTENT_VERIFICATION_FAILED"
        result["error_codes"] = verification_errors
        result["next_steps"] = [
            "Claude listed the plugin, but its user scope, enabled state, version, or cached bytes did not match this verified source. Do not rely on its hooks."
        ]
        return 1, result

    result["status"] = "CONFIGURATION_VERIFIED_NEW"
    result["operation_ok"] = True
    result["ok"] = True
    result["requires_user_action"] = True
    result["verification"]["configuration"] = True
    result["state_change_possible"] = False
    result["observed_installed_version"] = source.version
    result["actions"] = [
        action
        for action in result["actions"]
        if action.get("id") == "activate_and_verify_runtime"
    ]
    result["next_steps"] = [
        "Restart Claude Code or run /reload-plugins.",
        "Open a fresh disposable target session and run /hooks, /skills, acgm version, and acgm doctor --json.",
        "Treat doctor's SessionStart record as historical corroboration only; establish ACTIVE_VERIFIED with the same-surface manual E2E checklist.",
        "Review and initialize project governance manually; this installer did not create or edit project files.",
    ]
    return 0, result


def _path_entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except OSError:
        return False
    return True


def neutral_claude_cwd_is_safe(path: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
        home = Path.home().resolve(strict=True)
        repo = REPO_ROOT.resolve(strict=True)
        if resolved.is_relative_to(repo):
            return False
    except (OSError, ValueError):
        return False
    for candidate in (resolved, *resolved.parents):
        if _path_entry_exists(candidate / ".git"):
            return False
        if candidate != home and any(
            _path_entry_exists(candidate / ".claude" / name)
            for name in ("settings.json", "settings.local.json")
        ):
            return False
    return True


def finalize_install_result(
    outcome: tuple[int, dict[str, Any]],
) -> tuple[int, dict[str, Any]]:
    """Normalize only the top-level user-action contract at the public boundary."""

    exit_code, result = outcome
    if result.get("actions") or result.get("next_steps"):
        result["requires_user_action"] = True
    return exit_code, result


def install(
    *,
    dry_run: bool = False,
    surface: str = "auto",
    upgrade_verified_snapshot: bool = False,
) -> tuple[int, dict[str, Any]]:
    def neutral_blocked() -> tuple[int, dict[str, Any]]:
        report = preflight.build_report(surface)
        blocked = base_result(
            dry_run,
            report,
            checkout_revision(),
            checkout_clean(),
            upgrade_verified_snapshot=upgrade_verified_snapshot,
        )
        blocked["status"] = "NEUTRAL_CLAUDE_CWD_BLOCKED"
        blocked["error_codes"] = ["neutral_claude_cwd_unavailable_or_unsafe"]
        blocked["next_steps"] = [
            "Use a system with a private temporary directory outside every Claude project; no Claude command was run."
        ]
        return 2, blocked

    try:
        neutral_context = tempfile.TemporaryDirectory(
            prefix="acgm-installer-neutral-"
        )
    except OSError:
        return finalize_install_result(neutral_blocked())
    with neutral_context as raw_cwd:
        try:
            claude_cwd = Path(raw_cwd).resolve()
            if os.name != "nt":
                os.chmod(claude_cwd, 0o700)
            if not neutral_claude_cwd_is_safe(claude_cwd):
                raise OSError("neutral Claude cwd is not isolated")
        except OSError:
            return finalize_install_result(neutral_blocked())
        return finalize_install_result(
            _install_with_neutral_cwd(
                dry_run=dry_run,
                surface=surface,
                upgrade_verified_snapshot=upgrade_verified_snapshot,
                claude_cwd=claude_cwd,
            )
        )


def human_report(result: dict[str, Any]) -> str:
    lines = [
        f"ACGM installer: {result['status']}",
        f"Preflight: {result['preflight'].get('status')}",
        f"Source verified: {'yes' if result['verification']['source'] else 'no'}",
        f"Configuration verified: {'yes' if result['verification']['configuration'] else 'no'}",
        f"Runtime activated: {'yes' if result['verification']['runtime_activation'] else 'no'}",
        f"Changed: {'yes' if result['changed'] else 'no'}",
        f"Claude mutation attempted: {'yes' if result['mutation_attempted'] else 'no'}",
    ]
    if result["state_change_possible"]:
        lines.append(
            "Warning: a Claude mutation timed out, failed, or remains only partially verified."
        )
    if result["error_codes"]:
        lines.append("Errors: " + ", ".join(result["error_codes"]))
    if result["next_steps"]:
        lines.append("Next:")
        lines.extend(f"- {step}" for step in result["next_steps"])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install ACGM from a verified snapshot of this Git checkout"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="verify source and show commands without creating a snapshot or changing Claude state",
    )
    parser.add_argument("--json", action="store_true", help="emit stable machine-readable JSON")
    parser.add_argument(
        "--surface",
        choices=preflight.SURFACE_CHOICES,
        default="auto",
        help="target Claude surface; auto uses observable capabilities only",
    )
    parser.add_argument(
        "--upgrade-verified-snapshot",
        action="store_true",
        help=(
            "explicitly authorize a strictly-forward replacement only when the "
            "existing ACGM user install, immutable snapshot, and cache are fully verified"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    exit_code, result = install(
        dry_run=args.dry_run,
        surface=args.surface,
        upgrade_verified_snapshot=args.upgrade_verified_snapshot,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    else:
        print(human_report(result))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
