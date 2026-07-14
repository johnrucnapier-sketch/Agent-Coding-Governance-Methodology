#!/usr/bin/env python3
"""Conservative one-command installer for a verified ACGM checkout.

The installer uses the documented Claude plugin CLI for Claude configuration
changes. It never edits Claude settings directly, initializes a project,
removes or replaces a marketplace, or treats a command exit code as proof that
the requested plugin bytes were installed.
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
PACKAGE_MANIFEST_NAME = "PACKAGE_MANIFEST.json"
EXCLUDED_SOURCE_NAMES = {
    ".DS_Store",
    "BUILD_BRIEF.md",
    "PUBLISHING.md",
    PACKAGE_MANIFEST_NAME,
}
EXCLUDED_SOURCE_PARTS = {".git", ".claude", "__pycache__", "dist"}
CACHE_MANAGEMENT_PARTS = {".in_use"}


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


def marketplace_source_matches(record: dict[str, Any], source: Path) -> bool:
    expected = _normalized_path(str(source.absolute()))
    if expected is None:
        return False
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
        return False
    normalized = _normalized_path(raw_path)
    return normalized == expected


def user_settings_path() -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(configured).expanduser() if configured else Path.home() / ".claude"
    return base / "settings.json"


def user_marketplace_declaration(
    source: Path,
) -> tuple[str | None, str | None]:
    """Check only the user-scope marketplace declaration documented by Claude."""

    path = user_settings_path()
    try:
        content, read_error = read_regular_file(path)
    except OSError:
        return None, "user_settings_unavailable"
    if read_error == "file_unavailable":
        return "absent", None
    if read_error or content is None:
        return None, "user_settings_unreadable"
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "user_settings_invalid_json"
    if not isinstance(payload, dict):
        return None, "user_settings_unexpected_schema"
    marketplaces = payload.get("extraKnownMarketplaces")
    if marketplaces is None:
        return "absent", None
    if not isinstance(marketplaces, dict):
        return None, "user_marketplaces_unexpected_schema"
    declaration = marketplaces.get(MARKETPLACE_NAME)
    if declaration is None:
        return "absent", None
    if not isinstance(declaration, dict):
        return None, "user_marketplace_declaration_invalid"
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
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "acgm_version": report.get("acgm_version"),
        "status": "UNKNOWN",
        "ok": False,
        "changed": False,
        "mutation_attempted": False,
        "state_change_possible": False,
        "dry_run": dry_run,
        "scope": "user",
        "source": {
            "kind": "verified_git_snapshot",
            "checkout_path_token": "LOCAL_CHECKOUT",
            "snapshot_path_token": "VERIFIED_SNAPSHOT",
            "git_commit": revision,
            "git_clean": clean,
            "package_integrity_ok": False,
        },
        "preflight": report,
        "executed": [],
        "planned_commands": [],
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
) -> tuple[list[dict[str, Any]] | None, str | None]:
    completed = run_command(argv, timeout=INSPECT_TIMEOUT_SECONDS)
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


def install(*, dry_run: bool = False) -> tuple[int, dict[str, Any]]:
    report = preflight.build_report()
    revision = checkout_revision()
    clean = checkout_clean()
    result = base_result(dry_run, report, revision, clean)

    if report.get("status") != "READY_FOR_RC_TEST":
        return _source_blocked(
            result,
            "PREFLIGHT_BLOCKED",
            list(report.get("error_codes") or ["preflight_blocked"]),
            "Resolve the preflight blockers, then rerun this installer.",
        )
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

    claude_path, claude_error = preflight.resolve_claude_executable()
    if claude_error or claude_path is None:
        return _source_blocked(
            result,
            "CLAUDE_LAUNCHER_BLOCKED",
            [claude_error or "claude_launcher_unavailable"],
            "Install the native Claude Code executable and rerun preflight.",
        )
    claude_executable = str(claude_path)
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
    if dry_run:
        result["status"] = "DRY_RUN_READY"
        result["ok"] = True
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
    )
    plugins, plugin_error = inspect_json(
        result,
        "plugin_list",
        plugin_list,
        parser=parse_plugin_payload,
        claude_executable=claude_executable,
        materialized=materialized,
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
    if len(existing_marketplaces) > 1 or (
        existing_marketplaces
        and not marketplace_source_matches(existing_marketplaces[0], materialized)
    ):
        result["status"] = "MARKETPLACE_CONFLICT"
        result["error_codes"] = [
            "marketplace_name_exists_with_different_duplicate_or_unverifiable_source"
        ]
        result["next_steps"] = [
            "Inspect the existing marketplace and choose its source manually; this installer never removes, updates, or replaces a conflict."
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
    if user_declaration == "conflict":
        result["status"] = "MARKETPLACE_CONFLICT"
        result["error_codes"] = [
            "user_scope_marketplace_name_exists_with_different_source"
        ]
        result["next_steps"] = [
            "The user-scope marketplace name already points elsewhere; this installer will not replace it."
        ]
        return 2, result
    if existing_marketplaces and user_declaration == "exact":
        result["planned_commands"] = [
            display_argv(
                install_argv,
                claude_executable=claude_executable,
                materialized=materialized,
            )
        ]

    existing_plugins = matching_plugins(plugins)
    if len(existing_plugins) > 1:
        result["status"] = "INSTALLED_PLUGIN_CONFLICT"
        result["error_codes"] = ["multiple_installed_plugin_records"]
        result["next_steps"] = [
            "Resolve duplicate plugin scopes manually; this installer never uninstalls or changes scope."
        ]
        return 2, result

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
        result["status"] = "ALREADY_INSTALLED_VERIFIED"
        result["ok"] = True
        result["observed_installed_version"] = source.version
        result["next_steps"] = [
            "Restart Claude Code or run /reload-plugins.",
            "Open a disposable target project and run /hooks, /skills, acgm version, and acgm doctor.",
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
        added = run_command(add_argv, timeout=MUTATION_TIMEOUT_SECONDS)
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
    installed_result = run_command(install_argv, timeout=MUTATION_TIMEOUT_SECONDS)
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

    result["status"] = "INSTALLED"
    result["ok"] = True
    result["state_change_possible"] = False
    result["observed_installed_version"] = source.version
    result["next_steps"] = [
        "Restart Claude Code or run /reload-plugins.",
        "Open a disposable target project and run /hooks, /skills, acgm version, and acgm doctor.",
        "Review and initialize project governance manually; this installer did not create or edit project files.",
    ]
    return 0, result


def human_report(result: dict[str, Any]) -> str:
    lines = [
        f"ACGM installer: {result['status']}",
        f"Preflight: {result['preflight'].get('status')}",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    exit_code, result = install(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    else:
        print(human_report(result))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
