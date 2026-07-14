#!/usr/bin/env python3
"""ACGM V3 local runtime.

The hook layer intentionally stores only enumerated, sanitized metadata. It never
stores prompts, transcript text, commands, file paths, model names, remote URLs,
or credentials. Raw hook input is processed in memory and discarded.
"""

from __future__ import annotations

import argparse
import collections
from contextlib import contextmanager
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Iterable

try:  # Unix advisory locks.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised by Windows CI.
    _fcntl = None

try:  # Windows byte-range locks.
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - exercised by POSIX CI.
    _msvcrt = None


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ID = "agent-coding-governance-methodology@agent-coding-governance-methodology"
PLUGIN_DATA_KEY = re.sub(r"[^A-Za-z0-9_-]", "-", PLUGIN_ID)
EVENT_SCHEMA_VERSION = 1
GATE_MARKERS = (
    "ACGM-EVIDENCE:",
    "ACGM-CURRENT-STATE:",
    "ACGM-VERIFY-AFTER:",
    "ACGM-ROLLBACK:",
)


def restrict_descriptor(descriptor: int, mode: int = 0o600) -> None:
    """Apply best-effort descriptor permissions without requiring Unix APIs.

    ``os.fchmod`` was not available on Windows before Python 3.13. The plugin's
    Windows Git Bash candidate supports Python 3.10+, so permissions must never
    be the reason the runtime crashes. Windows access remains governed by the
    user's profile ACL; POSIX keeps the explicit restrictive mode.
    """

    fchmod = getattr(os, "fchmod", None)
    if os.name == "nt":
        if not callable(fchmod):
            return
        try:
            fchmod(descriptor, mode)
        except OSError:
            # Windows 3.10-3.12 lack fd chmod, and later Windows versions map
            # modes to limited ACL/read-only semantics. Preflight reports that
            # this RC does not yet attest an equivalent Windows DACL guarantee.
            return
    else:
        if not callable(fchmod):
            raise OSError("fchmod unavailable on POSIX runtime")
        fchmod(descriptor, mode)


@contextmanager
def exclusive_file_lock(path: Path) -> Iterable[None]:
    """Serialize state updates with stdlib-only POSIX or Windows locks."""

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    restrict_descriptor(descriptor)
    locked = False
    try:
        if _fcntl is not None:
            _fcntl.flock(descriptor, _fcntl.LOCK_EX)
        elif _msvcrt is not None:  # pragma: no branch - platform exclusive.
            # msvcrt.locking locks from the current offset and needs a real byte.
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            _msvcrt.locking(descriptor, _msvcrt.LK_LOCK, 1)
        else:  # No supported lock primitive means state cannot be trusted.
            raise OSError("no supported file-lock implementation")
        locked = True
        yield
    finally:
        if locked:
            try:
                if _fcntl is not None:
                    _fcntl.flock(descriptor, _fcntl.LOCK_UN)
                elif _msvcrt is not None:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    _msvcrt.locking(descriptor, _msvcrt.LK_UNLCK, 1)
            finally:
                os.close(descriptor)
        else:
            os.close(descriptor)


def read_version() -> str:
    try:
        return (PLUGIN_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


ACGM_VERSION = read_version()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def json_print(value: Any) -> None:
    # Hook stdout is a JSON wire protocol, not terminal prose.  ASCII escapes
    # keep it decodable even when Windows Python inherits a legacy code page
    # while preserving the exact Unicode value after JSON decoding.
    print(json.dumps(value, ensure_ascii=True, separators=(",", ":")))


def read_hook_input() -> dict[str, Any]:
    try:
        # Claude/Git Bash send hook JSON as UTF-8.  Reading ``sys.stdin``
        # directly on Windows can apply the active ANSI code page instead.
        buffer = getattr(sys.stdin, "buffer", None)
        raw = buffer.read().decode("utf-8") if buffer is not None else sys.stdin.read()
        value = json.loads(raw) if raw.strip() else {}
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def run_git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError:
        return ""


def resolve_project_root(data: dict[str, Any] | None = None, explicit: str | None = None) -> Path:
    candidates: list[str] = []
    if explicit:
        explicit_path = Path(explicit).expanduser()
        if not explicit_path.exists():
            raise FileNotFoundError(f"project path does not exist: {explicit}")
        if not explicit_path.is_dir():
            raise NotADirectoryError(f"project path is not a directory: {explicit}")
        candidates.append(str(explicit_path))
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        candidates.append(env_root)
    if data:
        for key in ("cwd", "project_dir", "projectDir"):
            value = data.get(key)
            if isinstance(value, str) and value:
                candidates.append(value)
    candidates.append(os.getcwd())

    for candidate in candidates:
        path = Path(candidate).expanduser()
        if not path.exists():
            continue
        path = path.resolve()
        base = path if path.is_dir() else path.parent
        git_root = run_git(base, "rev-parse", "--show-toplevel")
        if git_root:
            return Path(git_root).resolve()
        return base
    return Path.cwd().resolve()


def get_data_dir() -> Path:
    configured = os.environ.get("ACGM_DATA_DIR") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if configured:
        return Path(configured).expanduser()
    config_root = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser()
    return config_root / "plugins" / "data" / PLUGIN_DATA_KEY


def effective_claude_env(name: str) -> str | None:
    """Return one Claude environment setting without exposing other config.

    Claude normally exports ``settings.json`` ``env`` entries to child
    processes. Reading the same single value here also makes an interactive
    ``acgm doctor`` useful before Claude Code has started.
    """

    if name in os.environ:
        return os.environ[name]
    config_root = Path(
        os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
    ).expanduser()
    try:
        settings = json.loads((config_root / "settings.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    configured = settings.get("env") if isinstance(settings, dict) else None
    value = configured.get(name) if isinstance(configured, dict) else None
    return value if isinstance(value, str) else None


def _git_bash_executable(path_value: str, *, explicitly_configured: bool) -> bool:
    """Validate a Git for Windows shell path, excluding the WSL launcher."""

    if not path_value.strip():
        return False
    candidate = Path(os.path.expandvars(path_value.strip().strip('"'))).expanduser()
    if not candidate.is_file():
        return False
    normalized = str(candidate).replace("\\", "/").casefold()
    basename = candidate.name.casefold()
    if basename not in {"bash", "bash.exe", "sh", "sh.exe"}:
        return False
    if "/windows/system32/" in normalized:
        return False
    if explicitly_configured:
        return basename in {"bash", "bash.exe"}
    return "/git/" in normalized or bool(
        re.match(r"^(?:mingw|msys)", os.environ.get("MSYSTEM", ""), re.I)
    )


def windows_git_bash_status() -> tuple[bool, str]:
    """Return availability and a non-sensitive reason code for Git Bash."""

    configured = effective_claude_env("CLAUDE_CODE_GIT_BASH_PATH")
    if configured is not None:
        if _git_bash_executable(configured, explicitly_configured=True):
            return True, "configured_path"
        return False, "configured_path_invalid"

    common_roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LocalAppData"),
    ]
    common_paths: list[Path] = []
    for index, root_value in enumerate(common_roots):
        if not root_value:
            continue
        root = Path(root_value)
        if index < 2:
            common_paths.append(root / "Git" / "bin" / "bash.exe")
        else:
            common_paths.append(root / "Programs" / "Git" / "bin" / "bash.exe")
    for candidate in common_paths:
        if _git_bash_executable(str(candidate), explicitly_configured=False):
            return True, "standard_install"

    for command in ("bash", "sh"):
        resolved = shutil.which(command)
        if resolved and _git_bash_executable(resolved, explicitly_configured=False):
            return True, "path_lookup"
    return False, "not_found"


class Store:
    """Persistent state containing identifiers and enums only, never raw evidence."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_data_dir()
        self._salt: bytes | None = None

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    def salt(self) -> bytes:
        if self._salt is not None:
            return self._salt
        self.ensure()
        salt_path = self.root / "local-id-salt"
        try:
            self._salt = salt_path.read_bytes()
            salt_path.chmod(0o600)
        except OSError:
            candidate = secrets.token_bytes(32)
            fd, temp_name = tempfile.mkstemp(prefix=".local-id-salt.", dir=self.root)
            try:
                try:
                    os.write(fd, candidate)
                finally:
                    os.close(fd)
                os.chmod(temp_name, 0o600)
                try:
                    # Linking a fully-written file makes first-use creation
                    # atomic without ever exposing an empty salt file.
                    os.link(temp_name, salt_path)
                    self._salt = candidate
                except FileExistsError:
                    # Another hook process won the race. All processes must
                    # use its persisted salt or their opaque IDs diverge.
                    self._salt = salt_path.read_bytes()
            finally:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
        return self._salt

    def opaque_id(self, prefix: str, raw: str) -> str:
        digest = hmac.new(self.salt(), raw.encode("utf-8", "replace"), hashlib.sha256).hexdigest()
        return f"{prefix}_{digest[:16]}"

    def project_id(self, root: Path) -> str:
        return self.opaque_id("prj", str(root.resolve()))

    def session_id(self, raw: str | None) -> str:
        return self.opaque_id("ses", raw or "unknown-session")

    def tool_id(self, raw: str | None) -> str:
        return self.opaque_id("tool", raw or f"missing-{uuid.uuid4()}")

    def append_event(
        self,
        *,
        project_id: str,
        session_id: str,
        event_type: str,
        initiator: str,
        phase: str,
        rule_id: str,
        action: str,
        status: str,
        outcome: str,
        confidence: str,
        detail_code: str,
        related_event_id: str | None = None,
    ) -> str:
        self.ensure()
        event_id = f"evt_{uuid.uuid4().hex}"
        event = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "event_id": event_id,
            "timestamp": utc_now(),
            "acgm_version": ACGM_VERSION,
            "project_id": project_id,
            "session_id": session_id,
            "event_type": event_type,
            "initiator": initiator,
            "phase": phase,
            "rule_id": rule_id,
            "action": action,
            "status": status,
            "outcome": outcome,
            "confidence": confidence,
            "detail_code": detail_code,
        }
        if related_event_id:
            event["related_event_id"] = related_event_id
        # Every non-ID value is an enum controlled above. This guard prevents a
        # future caller from accidentally putting path-like material in the ledger.
        for key, value in event.items():
            if key in {"timestamp", "event_id", "project_id", "session_id", "related_event_id"}:
                continue
            if isinstance(value, str) and ("/" in value or "\\" in value or "://" in value):
                raise ValueError(f"unsafe ledger value for {key}")
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        with exclusive_file_lock(self.root / "locks" / "events.lock"):
            fd = os.open(self.root / "events.jsonl", os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                restrict_descriptor(fd)
                remaining = memoryview(line.encode("utf-8"))
                while remaining:
                    written = os.write(fd, remaining)
                    if written <= 0:
                        raise OSError("short event ledger write")
                    remaining = remaining[written:]
            finally:
                os.close(fd)
        return event_id

    def events(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        try:
            with exclusive_file_lock(self.root / "locks" / "events.lock"):
                with (self.root / "events.jsonl").open(encoding="utf-8") as handle:
                    lines = handle.read().splitlines()
        except OSError:
            return result
        for line in lines:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("schema_version") == EVENT_SCHEMA_VERSION:
                result.append(value)
        return result

    def project_state_path(self, project_id: str) -> Path:
        return self.root / "projects" / f"{project_id}.json"

    def previous_project_state(self, project_id: str) -> str | None:
        try:
            value = json.loads(self.project_state_path(project_id).read_text(encoding="utf-8"))
            state = value.get("state")
            return state if isinstance(state, str) else None
        except (OSError, json.JSONDecodeError):
            return None

    def save_project_state(self, project_id: str, state: str) -> None:
        self.ensure()
        path = self.project_state_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_json_write(
            path,
            {
                "schema_version": 1,
                "project_id": project_id,
                "state": state,
                "last_seen_version": ACGM_VERSION,
                "updated_at": utc_now(),
            },
        )

    def health_once(self, session_id: str) -> bool:
        self.ensure()
        directory = self.root / "health"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / session_id
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        else:
            os.close(fd)
            return True

    def obligations_path(self, session_id: str) -> Path:
        return self.root / "obligations" / f"{session_id}.json"

    @contextmanager
    def obligations_lock(self, session_id: str) -> Iterable[None]:
        """Serialize per-session obligation updates across parallel hooks."""
        self.ensure()
        with exclusive_file_lock(self.root / "locks" / f"{session_id}.lock"):
            yield

    def load_obligations(self, session_id: str) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.obligations_path(session_id).read_text(encoding="utf-8"))
            items = value.get("obligations", [])
            if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                raise ValueError("invalid obligation store")
            return items
        except FileNotFoundError:
            return []
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise OSError("obligation store is unreadable or corrupt") from error

    def save_obligations(self, session_id: str, obligations: list[dict[str, Any]]) -> None:
        self.ensure()
        path = self.obligations_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_json_write(
            path,
            {"schema_version": 1, "session_id": session_id, "obligations": obligations},
        )


def atomic_json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def safe_log(store: Store, **kwargs: Any) -> str | None:
    try:
        return store.append_event(**kwargs)
    except (OSError, ValueError):
        return None


def package_integrity() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required = [
        "VERSION",
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        "hooks/hooks.json",
        "scripts/acgm-hook.sh",
        "scripts/acgm_runtime.py",
        "scripts/preflight.py",
        "bin/acgm",
        "skills/session-grounding/SKILL.md",
        "skills/truth-first/SKILL.md",
        "skills/governance-bootstrap/SKILL.md",
    ]
    for relative in required:
        if not (PLUGIN_ROOT / relative).is_file():
            errors.append(f"missing:{relative}")
    if os.name != "nt":
        for relative in ("scripts/acgm-hook.sh", "scripts/acgm_runtime.py", "bin/acgm"):
            path = PLUGIN_ROOT / relative
            if path.exists() and not os.access(path, os.X_OK):
                errors.append(f"not_executable:{relative}")
    try:
        manifest = json.loads((PLUGIN_ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        if manifest.get("version") != ACGM_VERSION:
            errors.append("version_mismatch")
    except (OSError, json.JSONDecodeError):
        errors.append("manifest_invalid")
    try:
        hooks = json.loads((PLUGIN_ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
        for event in ("SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop", "SessionEnd"):
            if event not in hooks:
                errors.append(f"hook_missing:{event}")
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        errors.append("hooks_invalid")

    package_manifest = PLUGIN_ROOT / "PACKAGE_MANIFEST.json"
    if package_manifest.exists():
        try:
            manifest_value = json.loads(package_manifest.read_text(encoding="utf-8"))
            if manifest_value.get("version") != ACGM_VERSION:
                errors.append("package_manifest_version_mismatch")
            entries = manifest_value.get("files", {})
            if not isinstance(entries, dict):
                raise ValueError
            for relative, expected in entries.items():
                if not isinstance(relative, str) or not isinstance(expected, str):
                    raise ValueError
                path = (PLUGIN_ROOT / relative).resolve()
                try:
                    path.relative_to(PLUGIN_ROOT.resolve())
                except ValueError:
                    errors.append(f"package_path_unsafe:{relative}")
                    continue
                if not path.is_file():
                    errors.append(f"package_file_missing:{relative}")
                    continue
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual != expected:
                    errors.append(f"package_hash_mismatch:{relative}")
        except (OSError, ValueError, json.JSONDecodeError):
            errors.append("package_manifest_invalid")
    else:
        warnings.append("package_manifest_missing")
    if sys.version_info < (3, 10):
        errors.append("python_too_old")
    if os.name == "nt":
        git_bash_available, _ = windows_git_bash_status()
        if not git_bash_available:
            errors.append("windows_git_bash_missing")
        if effective_claude_env("CLAUDE_CODE_USE_POWERSHELL_TOOL") != "0":
            errors.append("windows_powershell_tool_must_be_disabled")
        warnings.extend(
            [
                "windows_acl_equivalence_unvalidated",
                "windows_git_bash_candidate_only",
                "powershell_native_unsupported",
            ]
        )
    return errors, warnings


def store_integrity(store: Store, *, scan_obligations: bool = True) -> tuple[list[str], list[str]]:
    """Verify that persistent state is appendable and structurally readable."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        store.ensure()
        salt_path = store.root / "local-id-salt"
        if salt_path.exists() and len(salt_path.read_bytes()) != 32:
            errors.append("local_id_salt_invalid")

        events_path = store.root / "events.jsonl"
        descriptor = os.open(events_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            restrict_descriptor(descriptor)
        finally:
            os.close(descriptor)
        if events_path.stat().st_size:
            with exclusive_file_lock(store.root / "locks" / "events.lock"):
                with events_path.open("rb") as handle:
                    size = handle.seek(0, os.SEEK_END)
                    offset = max(0, size - 1024 * 1024)
                    handle.seek(offset)
                    lines = handle.read(1024 * 1024).splitlines()
                    if offset and lines:
                        lines = lines[1:]
                    for line in lines:
                        value = json.loads(line.decode("utf-8", "strict"))
                        if not isinstance(value, dict) or value.get("schema_version") != EVENT_SCHEMA_VERSION:
                            raise ValueError("invalid event ledger record")

        if scan_obligations:
            obligations_dir = store.root / "obligations"
            if obligations_dir.is_dir():
                for index, path in enumerate(obligations_dir.glob("ses_*.json")):
                    if index >= 1000:
                        warnings.append("obligation_scan_capped")
                        break
                    value = json.loads(path.read_text(encoding="utf-8"))
                    items = value.get("obligations") if isinstance(value, dict) else None
                    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                        raise ValueError("invalid obligation record")
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        errors.append("local_state_corrupt_or_unwritable")
    return errors, warnings


PLACEHOLDER_RE = re.compile(
    r"<(?:\.\.\.|项目名|原则\s*\d*|红线\s*\d*|业务判断|列你项目|YYYY-MM-DD|…)[^>]*>"
)


def project_components(root: Path) -> dict[str, bool]:
    constitution_candidates = (root / "CONSTITUTION.md", root / "docs/CONSTITUTION.md")
    constitution = next((p for p in constitution_candidates if p.is_file()), None)
    root_rule_files = [path for path in (root / "CLAUDE.md", root / "AGENTS.md") if path.is_file()]
    root_rules = False
    for path in root_rule_files:
        try:
            if path.read_text(encoding="utf-8").strip():
                root_rules = True
                break
        except OSError:
            continue
    placeholders = False
    if constitution:
        try:
            constitution_text = constitution.read_text(encoding="utf-8")
            placeholders = not constitution_text.strip() or bool(PLACEHOLDER_RE.search(constitution_text))
        except OSError:
            placeholders = True
    decision_dirs = (root / "decisions", root / "docs/decisions", root / ".governance/decisions")
    decisions = any(directory.is_dir() and any(directory.rglob("*.md")) for directory in decision_dirs)
    scope = False
    for path in (root / ".governance/scope.yml", root / ".governance/scope.yaml"):
        if not path.is_file():
            continue
        try:
            scope_text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"(?m)^\s*in\s*:", scope_text, re.I) and re.search(
            r"(?m)^\s*out\s*:", scope_text, re.I
        ):
            scope = True
            break
    snapshot_dirs = (root / ".governance/snapshots", root / "docs/snapshots", root / "snapshots")
    snapshots = any(
        directory.is_dir() and any(path.is_file() for path in directory.rglob("*"))
        for directory in snapshot_dirs
    )
    return {
        "constitution": constitution is not None,
        "root_rules": root_rules,
        "placeholders": placeholders,
        "decisions": decisions,
        "scope": scope,
        "snapshots": snapshots,
    }


def assess_project(root: Path, store: Store, update: bool = True) -> tuple[str, dict[str, bool], list[str], list[str]]:
    errors, warnings = package_integrity()
    components = project_components(root)
    project_id = store.project_id(root)
    if errors:
        state = "BROKEN"
    elif not components["constitution"] and not components["root_rules"]:
        state = "INSTALLED_NOT_BOOTSTRAPPED"
    elif not components["constitution"] or not components["root_rules"] or components["placeholders"]:
        state = "PARTIALLY_GOVERNED"
    elif components["decisions"] and components["scope"] and components["snapshots"]:
        state = "GOVERNED"
    else:
        state = "PARTIALLY_GOVERNED"
    previous = store.previous_project_state(project_id)
    if previous in {"GOVERNED", "DRIFTED"} and state in {
        "INSTALLED_NOT_BOOTSTRAPPED",
        "PARTIALLY_GOVERNED",
    }:
        state = "DRIFTED"
    if update:
        try:
            store.save_project_state(project_id, state)
        except OSError:
            errors.append("ledger_unwritable")
            state = "BROKEN"
    return state, components, errors, warnings


def hook_session_start(data: dict[str, Any], store: Store) -> None:
    root = resolve_project_root(data)
    project_id = store.project_id(root)
    session_id = store.session_id(str(data.get("session_id") or ""))
    state, _, errors, _ = assess_project(root, store, update=True)
    storage_errors, _ = store_integrity(store, scan_obligations=False)
    errors.extend(storage_errors)
    if storage_errors:
        state = "BROKEN"
    if store.health_once(session_id):
        event_id = safe_log(
            store,
            project_id=project_id,
            session_id=session_id,
            event_type="health",
            initiator="acgm_hook",
            phase="session_start",
            rule_id="runtime.health",
            action="checked",
            status="broken" if errors else ("healthy" if state == "GOVERNED" else "attention"),
            outcome="visible",
            confidence="high",
            detail_code=state.lower(),
        )
        if event_id is None:
            errors.append("event_ledger_unwritable")
            state = "BROKEN"

    source = str(data.get("source") or "startup")
    prefix = f"ACGM {ACGM_VERSION} · project root: {root} · project state: {state}."
    if state == "BROKEN":
        body = "Governance mechanics are not healthy. Run `acgm doctor` before relying on ACGM. / 治理机制不健康；依赖 ACGM 前先运行 `acgm doctor`。"
    elif state == "INSTALLED_NOT_BOOTSTRAPPED":
        body = "The plugin is installed, but this project has not started governance. Invoke `/agent-coding-governance-methodology:governance-bootstrap`; it is human-driven and must not overwrite existing files. / 插件已安装，但项目尚未启动治理；请调用 namespaced governance-bootstrap，保持人驱动且不覆盖现有文件。"
    elif state in {"PARTIALLY_GOVERNED", "DRIFTED"}:
        body = "Governance is partial or has drifted. Run `acgm doctor`, then invoke `/agent-coding-governance-methodology:session-grounding` before edits. / 治理不完整或已漂移；先运行 doctor，再调用 namespaced session-grounding。"
    else:
        body = "Before acting, invoke `/agent-coding-governance-methodology:session-grounding`. Before technical claims or high-risk actions, apply `/agent-coding-governance-methodology:truth-first`. / 动手前走 namespaced session-grounding；写技术结论或做高风险操作前执行 truth-first。"
    if source in {"resume", "compact"}:
        body += " This session resumed or compacted: every inherited technical reference is history, not current truth; re-read its source now before reuse. / 本 session 为续接或 compact 后状态：摘要继承的技术指称只是历史，不是当前真值，复用前必须当下重读源头。"
    elif source == "clear":
        body += " Context was cleared; rebuild grounding from current repository truth. / 上下文已清空，请从当前仓库真值重建 grounding。"
    json_print(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": f"{prefix} {body}",
            }
        }
    )


DESTRUCTIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("service_state", re.compile(r"\b(?:systemctl|service|launchctl)\b[^\n]*(?:\bstart\b|\bstop\b|\brestart\b|\breload\b|\benable\b|\bdisable\b|\bmask\b|\bunload\b|\bbootout\b)", re.I)),
    ("file_delete", re.compile(r"(?:^|[;&|]\s*|\s)(?:sudo\s+)?(?:[^\s;&|]*/)?(?:rm|unlink)\s+(?!--(?:help|version)\b)\S", re.I)),
    ("git_history", re.compile(r"\bgit\s+(?:push\b[^\n]*(?:--force|-f\b)|reset\s+--hard\b|clean\s+-[^\s]*f|branch\s+-D\b|restore\b|checkout\s+(?:--\s|\.\s*$))", re.I)),
    ("database_state", re.compile(r"\b(?:drop\s+(?:table|database|schema)|truncate\s+(?:table\s+)?|delete\s+from\s+)\b", re.I)),
    ("process_or_power", re.compile(r"\b(?:mkfs(?:\.[a-z0-9]+)?|kill\s+(?:-9|-KILL)|shutdown|reboot)\b|\bdd\s+[^\n]*\bof=", re.I)),
    ("container_state", re.compile(r"\b(?:docker\s+(?:rm|rmi|prune|stop|restart)|kubectl\s+(?:delete|scale)|helm\s+uninstall)\b", re.I)),
)


VERIFY_PATTERNS: dict[str, re.Pattern[str]] = {
    "service_state": re.compile(r"^\s*(?:sudo\s+)?(?:systemctl\s+(?:status|is-active|show|list-units)|service\s+\S+\s+status|launchctl\s+(?:print|list))\b", re.I),
    "file_delete": re.compile(r"^\s*(?:(?:test\s+(?:!\s+)?-[efd])|ls\b|find\b|stat\b)", re.I),
    "git_history": re.compile(r"^\s*git\s+(?:-C\s+\S+\s+)?(?:status|log|reflog|show|diff|branch)\b", re.I),
    "database_state": re.compile(r"^\s*(?:(?:psql|mysql|sqlite3)\b[^\n]*(?:select|show|pragma|describe|count)|(?:select|show\s+(?:tables|schemas|databases)|pragma|describe)\b)", re.I),
    "process_or_power": re.compile(r"^\s*(?:ps|pgrep|uptime|nvidia-smi|kill\s+-0)\b", re.I),
    "container_state": re.compile(r"^\s*(?:docker\s+(?:ps|inspect)|kubectl\s+(?:get|describe|rollout\s+status)|helm\s+status)\b", re.I),
}

SHELL_COMPOUND = re.compile(r"[\n;&|`]|\$\(")

CONSTITUTION_REFERENCE = re.compile(r"\bCONSTITUTION\.md\b", re.I)
CONSTITUTION_READ_ONLY = re.compile(
    r"^\s*(?:(?:cat|head|tail|less|more|stat|wc|ls|rg|grep|shasum|sha256sum)\b|"
    r"sed\s+-n\b|git\s+(?:diff|show|status|log|blame)\b)",
    re.I,
)


def destructive_category(command: str) -> str | None:
    for category, pattern in DESTRUCTIVE_PATTERNS:
        if pattern.search(command):
            return category
    return None


def constitution_bash_mutation(command: str) -> bool:
    """Conservatively identify shell access that may change the human-owned file.

    Read-only commands remain available. Ambiguous compound shell or interpreter
    calls fail closed because a Bash hook cannot prove that they are read-only.
    """
    if not CONSTITUTION_REFERENCE.search(command):
        return False
    if re.search(r"[;&|><`]|\$\(", command):
        return True
    return not bool(CONSTITUTION_READ_ONLY.match(command))


def is_verification_command(command: str, category: str | None = None) -> bool:
    if SHELL_COMPOUND.search(command):
        return False
    if category:
        pattern = VERIFY_PATTERNS.get(category)
        return bool(pattern and pattern.match(command))
    return any(pattern.match(command) for pattern in VERIFY_PATTERNS.values())


def is_single_shell_command(command: str) -> bool:
    return not bool(SHELL_COMPOUND.search(command))


def normalize_command(command: str) -> str:
    value = command.strip()
    if len(value) >= 2 and value[0] == value[-1] == "`":
        value = value[1:-1].strip()
    try:
        return " ".join(shlex.split(value))
    except ValueError:
        return re.sub(r"\s+", " ", value)


def gate_field(text: str, marker: str) -> str:
    match = re.search(
        rf"(?mi)^\s*(?:[-*]\s*)?{re.escape(marker)}\s*(\S.*)$",
        text,
    )
    return match.group(1).strip() if match else ""


def identifier_variants(value: str) -> set[str]:
    cleaned = value.strip(" \t\r\n'\"`.,:;()[]{}")
    if not cleaned:
        return set()
    variants = {cleaned.casefold()}
    basename = Path(cleaned).name
    if basename:
        variants.add(basename.casefold())
    return {item for item in variants if item not in {".", ".."}}


def command_target_identifiers(command: str, category: str) -> list[set[str]]:
    """Extract target identifiers for in-memory evidence binding only."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    lowered = [Path(token).name.casefold() for token in tokens]
    raw_targets: list[str] = []

    if category == "file_delete":
        index = next((i for i, token in enumerate(lowered) if token in {"rm", "unlink"}), -1)
        if index >= 0:
            raw_targets = [token for token in tokens[index + 1 :] if not token.startswith("-")]
    elif category == "service_state":
        actions = {"start", "stop", "restart", "reload", "enable", "disable", "mask", "unload", "bootout"}
        index = next((i for i, token in enumerate(lowered) if token in actions), -1)
        if index >= 0:
            raw_targets = [token for token in tokens[index + 1 :] if not token.startswith("-")]
    elif category == "git_history":
        operations = {"push", "reset", "clean", "branch", "restore", "checkout"}
        index = next((i for i, token in enumerate(lowered) if token in operations), -1)
        if index >= 0:
            candidates = [token for token in tokens[index + 1 :] if not token.startswith("-") and token != "--"]
            if candidates:
                raw_targets = [candidates[-1]]
    elif category == "database_state":
        raw_targets = re.findall(
            r"\b(?:table|database|schema|from)\s+(?:if\s+exists\s+)?([A-Za-z0-9_.-]+)",
            command,
            re.I,
        )
    elif category == "process_or_power":
        output_targets = re.findall(r"\bof=([^\s]+)", command)
        numeric_targets = [token for token in tokens if re.fullmatch(r"[0-9]+", token)]
        device_targets = [token for token in tokens if token.startswith("/dev/")]
        raw_targets = output_targets + numeric_targets + device_targets
    elif category == "container_state":
        operations = {"rm", "rmi", "prune", "stop", "restart", "delete", "scale", "uninstall"}
        index = next((i for i, token in enumerate(lowered) if token in operations), -1)
        if index >= 0:
            candidates = [token for token in tokens[index + 1 :] if not token.startswith("-")]
            if candidates:
                raw_targets = [candidates[-1]]

    return [variants for target in raw_targets if (variants := identifier_variants(target))]


def identifiers_are_bound(targets: list[set[str]], *sources: str) -> bool:
    if not targets:
        return True
    haystack = "\n".join(sources).casefold()
    return all(any(variant in haystack for variant in variants) for variants in targets)


def transcript_objects(
    path: str,
    limit: int = 500,
    max_bytes: int = 2 * 1024 * 1024,
) -> list[dict[str, Any]]:
    """Read only a bounded JSONL tail so long sessions cannot time out the hook."""
    if not path:
        return []
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        return []
    items: collections.deque[dict[str, Any]] = collections.deque(maxlen=limit)
    try:
        with file_path.open("rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            offset = max(0, size - max_bytes)
            handle.seek(offset)
            raw_lines = handle.read(max_bytes).splitlines()
            if offset and raw_lines:
                # The first record may be a partial JSON object.
                raw_lines = raw_lines[1:]
            for raw_line in raw_lines[-limit:]:
                try:
                    value = json.loads(raw_line.decode("utf-8", "replace"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(value, dict):
                    items.append(value)
    except OSError:
        return []
    return list(items)


def assistant_text(items: Iterable[dict[str, Any]]) -> str:
    for value in reversed(list(items)):
        if value.get("type") != "assistant":
            continue
        message = value.get("message", {})
        content = message.get("content", []) if isinstance(message, dict) else []
        if isinstance(content, str) and content.strip():
            return content[-8000:]
        if isinstance(content, list):
            blocks = [
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            text_value = "\n".join(blocks).strip()
            if text_value:
                return text_value[-8000:]
    return ""


def result_text(block: dict[str, Any], value: dict[str, Any]) -> str:
    chunks: list[str] = []
    content = block.get("content")
    if isinstance(content, str):
        chunks.append(content)
    elif isinstance(content, list):
        for child in content:
            if isinstance(child, dict) and isinstance(child.get("text"), str):
                chunks.append(child["text"])
            elif isinstance(child, str):
                chunks.append(child)
    metadata = value.get("toolUseResult")
    if isinstance(metadata, dict):
        for key in ("stdout", "stderr", "output"):
            child = metadata.get(key)
            if isinstance(child, str):
                chunks.append(child)
    return "\n".join(chunks)[-16000:]


def transcript_bash_checks(items: Iterable[dict[str, Any]]) -> list[tuple[str, bool, str]]:
    """Pair Bash tool calls with their recorded results.

    A command without a successful tool_result is not current-source evidence.
    Result text is used only in memory to bind identifiers and is never persisted.
    """
    pending: dict[str, str] = {}
    checks: list[tuple[str, bool, str]] = []
    for value in items:
        message = value.get("message", {})
        content = message.get("content", []) if isinstance(message, dict) else []
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                tool_input = block.get("input", {})
                command = tool_input.get("command") if isinstance(tool_input, dict) else None
                tool_id = block.get("id")
                if isinstance(command, str) and isinstance(tool_id, str):
                    pending[tool_id] = command
                continue
            if block.get("type") != "tool_result":
                continue
            tool_id = block.get("tool_use_id")
            if not isinstance(tool_id, str) or tool_id not in pending:
                continue
            command = pending.pop(tool_id)
            metadata = value.get("toolUseResult")
            failed = bool(block.get("is_error"))
            if isinstance(metadata, dict):
                failed = failed or bool(metadata.get("is_error")) or bool(metadata.get("interrupted"))
                exit_code = metadata.get("exitCode", metadata.get("exit_code"))
                if isinstance(exit_code, int):
                    failed = failed or exit_code != 0
            checks.append((command, not failed, result_text(block, value)))
    return checks


def hook_context(data: dict[str, Any], store: Store) -> tuple[Path, str, str]:
    root = resolve_project_root(data)
    project_id = store.project_id(root)
    session_id = store.session_id(str(data.get("session_id") or ""))
    return root, project_id, session_id


def hook_pretool_bash(data: dict[str, Any], store: Store) -> None:
    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str) or not command:
        json_print({})
        return
    constitution_mutation = constitution_bash_mutation(command)
    category = destructive_category(command)
    if not constitution_mutation and not category:
        json_print({})
        return
    _, project_id, session_id = hook_context(data, store)
    if constitution_mutation:
        safe_log(
            store,
            project_id=project_id,
            session_id=session_id,
            event_type="drift_intervention",
            initiator="acgm_hook",
            phase="pre_action",
            rule_id="authority.constitution_human_only",
            action="blocked",
            status="unresolved",
            outcome="prevented_before_write",
            confidence="high",
            detail_code="constitution_bash_write",
        )
        json_print(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "ACGM blocked Bash access that may mutate CONSTITUTION.md. The constitution is human-owned; use a clearly read-only command to inspect it, then propose the change for the human to apply. / ACGM 已阻止可能修改 CONSTITUTION.md 的 Bash 操作。宪法归人所有；可用明确只读命令检查，再把修改建议交给人执行。",
                }
            }
        )
        return

    if not is_single_shell_command(command):
        safe_log(
            store,
            project_id=project_id,
            session_id=session_id,
            event_type="drift_intervention",
            initiator="acgm_hook",
            phase="pre_action",
            rule_id="truth_first.high_risk_gate",
            action="blocked",
            status="unresolved",
            outcome="prevented_pending_evidence",
            confidence="high",
            detail_code="compound_high_risk_command",
        )
        json_print(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "ACGM requires a recognized high-risk state change to be one standalone Bash command. Split source inspection, the state change, and post-action verification into separate tool calls so ordering and partial failure remain auditable. / ACGM 要求已识别的高风险状态变更必须是单独一条 Bash 命令。请把取证、状态变更和后验核验拆成独立工具调用，保证顺序与部分失败可审计。",
                }
            }
        )
        return

    items = transcript_objects(str(data.get("transcript_path") or data.get("transcriptPath") or ""))
    last_text = assistant_text(items)
    fields = {marker: gate_field(last_text, marker) for marker in GATE_MARKERS}
    placeholder = re.compile(r"^(?:<.*>|\.\.\.|todo|tbd|unknown|none|n/?a)$", re.I)
    missing = [marker for marker, value in fields.items() if not value or placeholder.fullmatch(value)]
    verification_command = fields["ACGM-VERIFY-AFTER:"]
    verification_valid = bool(
        verification_command
        and is_single_shell_command(verification_command)
        and is_verification_command(verification_command, category)
    )
    targets = command_target_identifiers(command, str(category))
    fields_bind_targets = identifiers_are_bound(
        targets,
        fields["ACGM-EVIDENCE:"],
        fields["ACGM-CURRENT-STATE:"],
    )
    checks = transcript_bash_checks(items)[-30:]
    has_source_check = any(
        succeeded
        and is_verification_command(source_command, category)
        and identifiers_are_bound(targets, source_command, output)
        for source_command, succeeded, output in checks
    )
    if missing:
        detail = "gate_missing_fields"
    elif not verification_valid:
        detail = "gate_invalid_verification"
    elif not fields_bind_targets:
        detail = "gate_unbound_fields"
    else:
        detail = "gate_missing_source_check"
    if not items:
        detail = "gate_transcript_unavailable"

    if missing or not verification_valid or not fields_bind_targets or not has_source_check or not items:
        safe_log(
            store,
            project_id=project_id,
            session_id=session_id,
            event_type="drift_intervention",
            initiator="acgm_hook",
            phase="pre_action",
            rule_id="truth_first.high_risk_gate",
            action="blocked",
            status="unresolved",
            outcome="prevented_pending_evidence",
            confidence="high" if missing or not items else "medium",
            detail_code=detail,
        )
        if missing:
            missing_text = ", ".join(missing)
        elif not verification_valid:
            missing_text = "a standalone, category-matching ACGM-VERIFY-AFTER command"
        elif not fields_bind_targets:
            missing_text = "the current target identifier in ACGM-EVIDENCE and ACGM-CURRENT-STATE"
        else:
            missing_text = "a successful, target-matching current-session source check"
        reason = (
            "ACGM denied this high-risk operation before the human permission stage. "
            f"Missing: {missing_text}. In your next response provide exactly: "
            "ACGM-EVIDENCE: current-session source and observed identifier; "
            "ACGM-CURRENT-STATE: current state read now; "
            "ACGM-VERIFY-AFTER: concrete post-action verification; "
            "ACGM-ROLLBACK: recovery plan. Run the read-only source check first, then retry. "
            "/ ACGM 已在人工权限阶段之前拒绝该高风险操作。请先做本 session 当下只读取证，并在下一条回复中明确填写四个 ACGM 字段后重试。"
        )
        json_print(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
        return

    raw_tool_id = data.get("tool_use_id")
    if not isinstance(raw_tool_id, str) or not raw_tool_id:
        json_print(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "ACGM cannot correlate this high-risk operation because Claude Code supplied no tool_use_id. It failed closed; run `acgm doctor` before retrying. / Claude Code 未提供 tool_use_id，ACGM 无法关联本次高风险操作，已失败关闭；请先运行 `acgm doctor`。",
                }
            }
        )
        return
    tool_key = store.tool_id(raw_tool_id)
    verification_id = store.opaque_id("vfy", normalize_command(verification_command))
    with store.obligations_lock(session_id):
        obligations = store.load_obligations(session_id)
        if not any(item.get("tool_id") == tool_key for item in obligations):
            event_id = safe_log(
                store,
                project_id=project_id,
                session_id=session_id,
                event_type="verification_obligation",
                initiator="acgm_hook",
                phase="pre_action",
                rule_id="truth_first.post_action_verification",
                action="opened",
                status="pending_human_approval",
                outcome="evidence_present",
                confidence="medium",
                detail_code=str(category),
            )
            if event_id is None:
                json_print(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": "ACGM could not persist the high-risk verification obligation, so it failed closed before human approval. Run `acgm doctor` and repair the local ledger before retrying. / ACGM 无法持久化高风险验证义务，已在人工批准前失败关闭；请运行 `acgm doctor` 修复本地账本后重试。",
                        }
                    }
                )
                return
            obligations.append(
                {
                    "obligation_id": f"obl_{uuid.uuid4().hex}",
                    "event_id": event_id,
                    "project_id": project_id,
                    "category": category,
                    "tool_id": tool_key,
                    "verification_id": verification_id,
                    "status": "awaiting_execution",
                    "stop_prompts": 0,
                    "created_at": utc_now(),
                }
            )
            store.save_obligations(session_id, obligations)

    json_print(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "ACGM evidence gate is complete. This remains a high-risk operation and now requires explicit human approval; post-action verification will remain open until checked. / ACGM 证据门已满足；该高风险操作仍需人明确批准，执行后验证义务会保持开启直到核验完成。",
            }
        }
    )


def write_target_and_text(data: dict[str, Any]) -> tuple[str, str]:
    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return "", ""
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    chunks: list[str] = []
    for key in ("content", "new_string"):
        value = tool_input.get(key)
        if isinstance(value, str):
            chunks.append(value)
    edits = tool_input.get("edits", [])
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
                chunks.append(edit["new_string"])
    return str(path), "\n".join(chunks)


def is_constitution(path: str, root: Path) -> bool:
    if not path:
        return False
    try:
        candidate = Path(path).expanduser()
        resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return resolved.name == "CONSTITUTION.md"


def is_governance_path(path: str, root: Path) -> bool:
    if not path:
        return False
    try:
        candidate = Path(path).expanduser()
        resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
        relative = resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    if relative.name in {"CONSTITUTION.md", "AGENTS.md", "CLAUDE.md"}:
        return True
    return bool(relative.parts and relative.parts[0] in {"decisions", ".governance"})


def risky_governance_text(text: str) -> bool:
    if not text:
        return False
    stripped = re.sub(r"`[^`]*`|\"[^\"]*\"|'[^']*'|“[^”]*”", " ", text)
    uncertainty = re.search(r"我记得|应该是|大概|可能是|似乎|据说|I recall|should be|probably|supposedly|seems", stripped, re.I)
    technical = re.search(r"使用|依赖|调用|导入|配置为|uses|imports|depends on|calls|configured", stripped, re.I)
    source = re.search(r"(?:^|[\s`])[^\s`]+\.[A-Za-z0-9]+:[0-9]+(?:-[0-9]+)?", text)
    return bool(uncertainty or (technical and not source))


def hook_pretool_write(data: dict[str, Any], store: Store) -> None:
    root, project_id, session_id = hook_context(data, store)
    path, _ = write_target_and_text(data)
    if not is_constitution(path, root):
        json_print({})
        return
    safe_log(
        store,
        project_id=project_id,
        session_id=session_id,
        event_type="drift_intervention",
        initiator="acgm_hook",
        phase="pre_action",
        rule_id="authority.constitution_human_only",
        action="blocked",
        status="unresolved",
        outcome="prevented_before_write",
        confidence="high",
        detail_code="constitution_write",
    )
    json_print(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "ACGM blocked an Agent write to CONSTITUTION.md. The constitution is human-owned; propose the amendment and let the human edit or explicitly manage it outside the Agent write path. / ACGM 已阻止 Agent 写入 CONSTITUTION.md。宪法归人所有；请先提出修订建议，由人亲自处理。",
            }
        }
    )


def update_obligation_after_bash(data: dict[str, Any], store: Store, failed: bool = False) -> str | None:
    _, project_id, session_id = hook_context(data, store)
    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    command = command if isinstance(command, str) else ""
    category = destructive_category(command)
    raw_tool_id = data.get("tool_use_id")
    tool_key = store.tool_id(raw_tool_id) if isinstance(raw_tool_id, str) and raw_tool_id else None
    if category and tool_key is None:
        raise OSError("missing tool_use_id for high-risk post-action event")
    verification_id = store.opaque_id("vfy", normalize_command(command)) if command else None
    changed = False
    context: str | None = None

    with store.obligations_lock(session_id):
        obligations = store.load_obligations(session_id)
        execution_matches = [
            item
            for item in obligations
            if tool_key
            and item.get("tool_id") == tool_key
            and item.get("status") == "awaiting_execution"
        ]
        if category and not execution_matches and any(
            item.get("status") == "awaiting_execution" and item.get("project_id") == project_id
            for item in obligations
        ):
            raise OSError("high-risk post-action event did not match its obligation")
        for item in execution_matches:
            if item.get("project_id") != project_id:
                raise OSError("obligation project mismatch")
            # A non-zero result can still follow partial side effects. Success
            # and failure therefore both require a separate declared check.
            item["status"] = "awaiting_verification"
            changed = True
            outcome = "execution_failed_state_unknown" if failed else "verification_pending"
            action = "observed_failure" if failed else "executed"
            store.append_event(
                project_id=project_id,
                session_id=session_id,
                event_type="verification_obligation",
                initiator="agent",
                phase="post_action",
                rule_id="truth_first.post_action_verification",
                action=action,
                status="pending_verification",
                outcome=outcome,
                confidence="high",
                detail_code=str(item.get("category") or category or "unknown"),
                related_event_id=item.get("event_id"),
            )
        if execution_matches:
            if failed:
                context = "ACGM cannot infer unchanged state from a failed or interrupted high-risk command; partial effects are possible. The declared post-action verification remains mandatory. / 高风险命令失败或中断不等于状态未变，可能已有部分副作用；已声明的后验核验仍必须执行。"
            else:
                context = "ACGM post-action verification is still open. Run the exact standalone `ACGM-VERIFY-AFTER` command before finishing. / ACGM 后验验证义务仍开启；结束前请单独执行已声明的准确核验命令。"
        elif verification_id:
            matching = [
                item
                for item in obligations
                if item.get("status") == "awaiting_verification"
                and item.get("project_id") == project_id
                and item.get("verification_id") == verification_id
            ]
            for item in matching:
                item_category = str(item.get("category") or "")
                if not is_verification_command(command, item_category):
                    continue
                if failed:
                    store.append_event(
                        project_id=project_id,
                        session_id=session_id,
                        event_type="verification_obligation",
                        initiator="agent",
                        phase="post_action",
                        rule_id="truth_first.post_action_verification",
                        action="checked",
                        status="pending_verification",
                        outcome="verification_failed",
                        confidence="high",
                        detail_code=item_category,
                        related_event_id=item.get("event_id"),
                    )
                    context = "The exact declared verification command failed, so ACGM kept the obligation open. Inspect the result and establish the intended state; do not treat the failed check as proof of no change. / 已声明的准确核验命令失败，ACGM 保持义务开启。请检查结果并确认预期状态，不得把失败核验当成状态未变的证明。"
                    continue
                item["status"] = "verified"
                changed = True
                store.append_event(
                    project_id=project_id,
                    session_id=session_id,
                    event_type="verification_obligation",
                    initiator="agent",
                    phase="post_action",
                    rule_id="truth_first.post_action_verification",
                    action="verified",
                    status="verified",
                    outcome="declared_check_succeeded",
                    confidence="medium",
                    detail_code=item_category,
                    related_event_id=item.get("event_id"),
                )
                context = "ACGM observed the exact declared post-action check succeed and resolved the matching obligation. The medium-confidence ledger record remains reviewable for false positives. / ACGM 观察到准确声明的后验核验成功，已关闭匹配义务；该中置信度记录仍可由人复审并标记误报。"

            if not matching:
                same_category_pending = any(
                    item.get("status") == "awaiting_verification"
                    and item.get("project_id") == project_id
                    and is_verification_command(command, str(item.get("category") or ""))
                    for item in obligations
                )
                if same_category_pending:
                    context = "This check does not exactly match the declared `ACGM-VERIFY-AFTER` command, so no obligation was closed. Run the declared standalone check. / 本次检查与已声明的 `ACGM-VERIFY-AFTER` 命令不完全匹配，因此没有关闭任何义务；请执行原先声明的独立核验。"

        if changed:
            store.save_obligations(session_id, obligations)
    return context


def hook_posttool(data: dict[str, Any], store: Store) -> None:
    tool_name = str(data.get("tool_name") or "")
    context: str | None = None
    if tool_name == "Bash":
        context = update_obligation_after_bash(data, store, failed=False)
    elif tool_name in {"Edit", "Write", "MultiEdit"}:
        root, project_id, session_id = hook_context(data, store)
        path, text = write_target_and_text(data)
        if is_governance_path(path, root) and risky_governance_text(text):
            safe_log(
                store,
                project_id=project_id,
                session_id=session_id,
                event_type="drift_intervention",
                initiator="acgm_hook",
                phase="post_action",
                rule_id="truth_first.sourced_governance_claims",
                action="advised",
                status="unresolved",
                outcome="review_requested",
                confidence="medium",
                detail_code="unsourced_governance_claim",
            )
            context = "ACGM detected an unsourced technical claim or asserted uncertainty in a governance-file write. ACGM did not modify the file. Re-read the current source and correct or cite the claim before treating it as truth. / ACGM 在治理文件写入中发现无来源技术结论或断言式不确定措辞；ACGM 未修改文件。请重读当前真值源并修正或补证据。"
    if context:
        json_print(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": context,
                }
            }
        )
    else:
        json_print({})


def hook_posttool_failure(data: dict[str, Any], store: Store) -> None:
    context = update_obligation_after_bash(data, store, failed=True)
    if context:
        json_print(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUseFailure",
                    "additionalContext": context,
                }
            }
        )
    else:
        json_print({})


def hook_stop(data: dict[str, Any], store: Store) -> None:
    _, current_project_id, session_id = hook_context(data, store)
    active = bool(data.get("stop_hook_active"))
    with store.obligations_lock(session_id):
        obligations = store.load_obligations(session_id)
        pending = [item for item in obligations if item.get("status") == "awaiting_verification"]
        if not pending:
            json_print({})
            return
        blockable = [item for item in pending if int(item.get("stop_prompts") or 0) < 2]
        if blockable:
            for item in blockable:
                item["stop_prompts"] = int(item.get("stop_prompts") or 0) + 1
                store.append_event(
                    project_id=str(item.get("project_id") or current_project_id),
                    session_id=session_id,
                    event_type="verification_obligation",
                    initiator="acgm_hook",
                    phase="stop",
                    rule_id="truth_first.post_action_verification",
                    action="continued",
                    status="pending_verification",
                    outcome="stop_blocked_for_verification",
                    confidence="high",
                    detail_code=str(item.get("category") or "unknown"),
                    related_event_id=item.get("event_id"),
                )
            store.save_obligations(session_id, obligations)
            json_print(
                {
                    "decision": "block",
                    "reason": f"ACGM cannot close this turn quietly: {len(pending)} high-risk post-action verification obligation(s) remain open. Run each exact declared `ACGM-VERIFY-AFTER` command in its originating project and inspect the result. / ACGM 不能让本轮安静结束：仍有 {len(pending)} 个高风险后验验证义务。请在各自原项目中执行准确声明的核验命令并检查结果。",
                }
            )
            return
        for item in pending:
            item["status"] = "unresolved"
            store.append_event(
                project_id=str(item.get("project_id") or current_project_id),
                session_id=session_id,
                event_type="verification_obligation",
                initiator="acgm_hook",
                phase="stop",
                rule_id="truth_first.post_action_verification",
                action="released",
                status="unresolved",
                outcome="loop_cap_reached",
                confidence="high",
                detail_code="stop_loop_cap" if active else "verification_unresolved",
                related_event_id=item.get("event_id"),
            )
        store.save_obligations(session_id, obligations)
    json_print({})


def hook_session_end(data: dict[str, Any], store: Store) -> None:
    _, current_project_id, session_id = hook_context(data, store)
    with store.obligations_lock(session_id):
        obligations = store.load_obligations(session_id)
        changed = False
        for item in obligations:
            item_project_id = str(item.get("project_id") or current_project_id)
            if item.get("status") == "awaiting_execution":
                # No PostTool event means ACGM cannot distinguish human denial
                # from a mechanism failure after execution. Preserve uncertainty.
                item["status"] = "unresolved"
                changed = True
                store.append_event(
                    project_id=item_project_id,
                    session_id=session_id,
                    event_type="verification_obligation",
                    initiator="acgm_hook",
                    phase="session_end",
                    rule_id="truth_first.post_action_verification",
                    action="observed",
                    status="unresolved",
                    outcome="execution_not_observed",
                    confidence="high",
                    detail_code=str(item.get("category") or "unknown"),
                    related_event_id=item.get("event_id"),
                )
            elif item.get("status") == "awaiting_verification":
                item["status"] = "unresolved"
                changed = True
                store.append_event(
                    project_id=item_project_id,
                    session_id=session_id,
                    event_type="verification_obligation",
                    initiator="acgm_hook",
                    phase="session_end",
                    rule_id="truth_first.post_action_verification",
                    action="observed",
                    status="unresolved",
                    outcome="session_ended_unverified",
                    confidence="high",
                    detail_code=str(item.get("category") or "unknown"),
                    related_event_id=item.get("event_id"),
                )
        if changed:
            store.save_obligations(session_id, obligations)
    json_print({})


def installed_plugin_records() -> tuple[list[dict[str, Any]], str | None]:
    """Return every registered ACGM install record without choosing a winner.

    Multiple scope records are an ambiguous installation state.  Doctor must not
    silently select the last one and then use a retained ledger event as activation
    evidence.
    """

    config_root = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser()
    path = config_root / "plugins" / "installed_plugins.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], None
    except (OSError, json.JSONDecodeError):
        return [], "installed_plugin_registry_unreadable"
    if not isinstance(value, dict):
        return [], "installed_plugin_registry_invalid"
    plugins = value.get("plugins")
    if not isinstance(plugins, dict):
        return [], "installed_plugin_registry_invalid"
    records = plugins.get(PLUGIN_ID, [])
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        return [], "installed_plugin_records_invalid"
    return [dict(record) for record in records], None


def installed_plugin_record() -> dict[str, Any] | None:
    """Return the sole install record, or ``None`` for absent/ambiguous state."""

    records, error = installed_plugin_records()
    return records[0] if error is None and len(records) == 1 else None


def running_from_source_checkout() -> bool:
    """Return whether this runtime is executing from a Git working tree."""

    return (PLUGIN_ROOT / ".git").exists()


def registered_install_matches_running_source(record: dict[str, Any] | None) -> bool:
    """Compare the registered install root without exposing it in diagnostics."""

    if not record:
        return False
    raw_path = record.get("installPath")
    if not isinstance(raw_path, str) or not raw_path:
        return False
    try:
        return Path(raw_path).expanduser().resolve(strict=True) == PLUGIN_ROOT.resolve(
            strict=True
        )
    except OSError:
        return False


def plugin_enabled_declaration(project_root: Path) -> tuple[bool, str | None]:
    """Resolve the explicit ACGM enable declaration for this project.

    Installed-plugin records do not contain the current enable flag.  Read the
    documented user, project, and project-local settings layers in increasing
    precedence and fail closed on malformed values.  This proves only a settings
    declaration, not that a live Claude surface loaded the plugin.
    """

    config_root = Path(
        os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
    ).expanduser()
    settings_paths = (
        config_root / "settings.json",
        project_root / ".claude" / "settings.json",
        project_root / ".claude" / "settings.local.json",
    )
    enabled: bool | None = None
    for path in settings_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, json.JSONDecodeError):
            return False, "plugin_enable_settings_unreadable"
        if not isinstance(payload, dict):
            return False, "plugin_enable_settings_invalid"
        declarations = payload.get("enabledPlugins")
        if declarations is None:
            continue
        if not isinstance(declarations, dict):
            return False, "plugin_enable_settings_invalid"
        if PLUGIN_ID not in declarations:
            continue
        value = declarations[PLUGIN_ID]
        if not isinstance(value, bool):
            return False, "plugin_enable_declaration_invalid"
        enabled = value
    if enabled is not True:
        return False, "plugin_not_explicitly_enabled_for_project"
    return True, None


def installation_registration_status(
    records: list[dict[str, Any]],
    *,
    registry_error: str | None,
    project_root: Path,
) -> dict[str, Any]:
    """Build fail-closed registration prerequisites for historical evidence."""

    record = records[0] if len(records) == 1 else None
    errors: list[str] = []
    if registry_error:
        errors.append(registry_error)
    if len(records) > 1:
        errors.append("multiple_installed_plugin_records")
    if record is not None:
        if record.get("scope") not in {"user", "project", "local"}:
            errors.append("installed_plugin_scope_invalid")
        if record.get("version") != ACGM_VERSION:
            errors.append("installed_version_differs_from_running_source")
        if record.get("errors") not in (None, False, "", [], {}):
            errors.append("installed_plugin_reports_errors")
        if not registered_install_matches_running_source(record):
            errors.append("installed_plugin_path_differs_from_running_source")
    enabled, enabled_error = plugin_enabled_declaration(project_root)
    if enabled_error:
        errors.append(enabled_error)
    return {
        "registered": bool(records),
        "record_count": len(records),
        "installed_version": record.get("version") if record else None,
        "installed_commit": record.get("gitCommitSha") if record else None,
        "running_version": ACGM_VERSION,
        "source_mode": running_from_source_checkout(),
        "running_source_matches_registered_install": bool(
            record and registered_install_matches_running_source(record)
        ),
        "explicitly_enabled_for_project": enabled,
        "registration_consistent": bool(record) and not errors,
        "error_codes": sorted(set(errors)),
    }


def session_start_activation_evidence(
    store: Store,
    *,
    project_id: str,
    installation: dict[str, Any],
    storage_errors: list[str],
) -> dict[str, Any]:
    """Report narrowly scoped evidence that SessionStart ran for this version.

    A health ledger record proves only that the current ACGM version's
    ``SessionStart`` hook wrote that record. It does not prove that any other
    hook event, Claude surface, or project-governance state is working.
    """

    evidence = {
        "status": "CURRENT_VERSION_SESSION_START_NOT_OBSERVED",
        "evidence_scope": "historical_session_start_health_event_only",
        "current_version_session_start_observed": False,
        "current_project_session_start_observed": False,
        "historical_observation_only": True,
        "sufficient_for_active_verified": False,
        "latest_observed_at": None,
        "current_project_observed_at": None,
    }
    if storage_errors:
        evidence["status"] = "EVIDENCE_UNAVAILABLE"
        return evidence
    if installation.get("source_mode"):
        evidence["status"] = "SOURCE_CHECKOUT_NOT_RUNTIME_PROOF"
        return evidence
    if not installation.get("registration_consistent"):
        evidence["status"] = "CURRENT_INSTALLATION_NOT_CONFIRMED"
        return evidence

    installed_version = installation.get("installed_version")
    matching_events: list[dict[str, Any]] = []
    for event in store.events():
        if (
            event.get("acgm_version") == installed_version
            and event.get("event_type") == "health"
            and event.get("initiator") == "acgm_hook"
            and event.get("phase") == "session_start"
            and event.get("rule_id") == "runtime.health"
            and event.get("action") == "checked"
            and event.get("outcome") == "visible"
            and isinstance(event.get("timestamp"), str)
            and bool(event.get("timestamp"))
        ):
            matching_events.append(event)

    if not matching_events:
        return evidence

    evidence["status"] = "HISTORICAL_CURRENT_VERSION_SESSION_START_OBSERVED"
    evidence["current_version_session_start_observed"] = True
    evidence["latest_observed_at"] = matching_events[-1]["timestamp"]
    project_events = [
        event for event in matching_events if event.get("project_id") == project_id
    ]
    if project_events:
        evidence["current_project_session_start_observed"] = True
        evidence["current_project_observed_at"] = project_events[-1]["timestamp"]
    return evidence


def continuity_status() -> dict[str, Any]:
    config_root = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser()
    settings_path = config_root / "settings.json"
    cleanup_days = 30
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        value = settings.get("cleanupPeriodDays")
        if isinstance(value, int) and value >= 0:
            cleanup_days = value
    except (OSError, json.JSONDecodeError):
        pass
    reasons: list[str] = []
    if os.environ.get("CLAUDE_CODE_SKIP_PROMPT_HISTORY"):
        reasons.append("prompt_history_disabled")
    if cleanup_days <= 30:
        reasons.append("short_retention")
    projects = config_root / "projects"
    recent = 0
    cutoff = dt.datetime.now().timestamp() - 30 * 86400
    if projects.is_dir():
        try:
            for index, path in enumerate(projects.rglob("*.jsonl")):
                if index >= 5000:
                    break
                try:
                    if path.stat().st_mtime >= cutoff:
                        recent += 1
                except OSError:
                    continue
        except OSError:
            pass
    if recent == 0:
        reasons.append("no_recent_local_transcript")
    return {
        "status": "RECOVERY_AT_RISK" if reasons else "READY",
        "cleanup_period_days": cleanup_days,
        "recent_transcript_files": recent,
        "reason_codes": reasons,
    }


def doctor_report(project: str | None, update: bool = True) -> dict[str, Any]:
    store = Store()
    root = resolve_project_root(explicit=project)
    project_id = store.project_id(root)
    state, components, errors, warnings = assess_project(root, store, update=update)
    storage_errors, storage_warnings = store_integrity(store)
    errors.extend(storage_errors)
    warnings.extend(storage_warnings)
    records, registry_error = installed_plugin_records()
    install = installation_registration_status(
        records,
        registry_error=registry_error,
        project_root=root,
    )
    warnings.extend(install["error_codes"])
    ledger_writable = not storage_errors
    activation = session_start_activation_evidence(
        store,
        project_id=project_id,
        installation=install,
        storage_errors=storage_errors,
    )
    return {
        "acgm_version": ACGM_VERSION,
        "project_id": project_id,
        "project_state": "BROKEN" if errors else state,
        "installation": install,
        "runtime": {
            "healthy": not errors,
            "error_codes": sorted(set(errors)),
            "warning_codes": sorted(set(warnings)),
            "ledger_writable": ledger_writable,
            "python": sys.version.split()[0],
        },
        "activation": activation,
        "components": components,
        "continuity": continuity_status(),
    }


def command_doctor(args: argparse.Namespace) -> int:
    try:
        report = doctor_report(args.project, update=not args.no_update)
    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"ACGM doctor: {error}", file=sys.stderr)
        return 2
    if args.json:
        json_print(report)
    else:
        print(f"ACGM Doctor {report['acgm_version']}")
        print(f"Project: {report['project_id']}  State: {report['project_state']}")
        install = report["installation"]
        print(
            "Plugin: "
            + (f"registered {install['installed_version']}" if install["registered"] else "not registered in installed_plugins.json")
            + f"; running {install['running_version']}"
        )
        activation = report["activation"]
        print(
            "Activation: "
            f"{activation['status']} "
            "(historical SessionStart health event only; never sufficient by itself for ACTIVE_VERIFIED)"
        )
        runtime = report["runtime"]
        print(f"Runtime: {'HEALTHY' if runtime['healthy'] else 'BROKEN'}  Ledger: {'writable' if runtime['ledger_writable'] else 'unwritable'}")
        print("Project components:")
        for key, value in report["components"].items():
            print(f"  {'✓' if value else '·'} {key}")
        continuity = report["continuity"]
        print(f"Continuity: {continuity['status']}  retention={continuity['cleanup_period_days']}d  recent_transcripts={continuity['recent_transcript_files']}")
        for code in runtime["error_codes"]:
            print(f"ERROR: {code}")
        for code in runtime["warning_codes"] + continuity["reason_codes"]:
            print(f"WARN: {code}")
        if continuity["status"] == "RECOVERY_AT_RISK":
            print("ACGM does not change Claude settings or copy transcripts. Review retention and local backup choices yourself. / ACGM 不会修改 Claude 设置或复制 transcript；请自行审查保留期与本地备份。")
    broken = bool(report["runtime"]["error_codes"])
    attention = report["project_state"] != "GOVERNED" or report["continuity"]["status"] != "READY"
    return 2 if broken else (1 if args.strict and attention else 0)


AGENTS_SCAFFOLD = """# Agent governance / agent 治理约束

This project uses agent-coding-governance. The rules below are non-negotiable and
apply to every session. Read and follow them before doing anything.

本项目启用 agent-coding-governance。以下规则不可妥协,适用于每个 session。
动手前先读并遵守。

## Before acting / 动手前:grounding(5 steps / 五步)

1. Read `CONSTITUTION.md` + the root rules in full — not skim. /
   完整读 `CONSTITUTION.md` + 根规则,不跳读。
2. Identify which track / scope this session is in; load that layer's docs. /
   判断本次落在哪个轨道/范围,加读对应层文档。
3. Report these 5, then WAIT for human confirmation before acting: which track;
   `git log` + `git status`; structure seen by actually reading code (not memory);
   exact file list you will change; the steps you will take. /
   报告这 5 项后等人确认再动手:落在哪个轨道;`git log`+`git status`;实际读代码
   看到的结构(不凭印象);要改的文件清单;打算的执行步骤。
4. After changes, run the verification scripts. / 改完跑验证脚本。
5. Closing report + commit draft — wait for human approval before committing. /
   收尾报告 + commit 草稿,等人审批再 commit。

## Before any technical conclusion or irreversible action / 写结论或不可逆操作前:truth-first

- Every claim carries `file:line` from grep/reading code. No "I think / usually /
  I recall". If you cannot read a truth source, say so — never guess. /
  每条结论带 grep/读码得到的 `文件:行号`。禁"我觉得/通常/我记得"。读不到真值就直说,不许编。
- A summary is never code-truth: never inherit a code fact from a summary,
  handoff, or memory layer — read it from the code now. /
  摘要永不作为代码真值:不从摘要/交接/记忆层继承代码事实——当下从代码读。
- Before destructive ops: list what is affected + write a rollback + quote the
  human's authorization verbatim. /
  破坏性操作前:列影响面 + 写回滚 + 原文引用人的授权。
- Before a high-risk Bash retry, use the exact four fields required by the ACGM
  gate: `ACGM-EVIDENCE:`, `ACGM-CURRENT-STATE:`, `ACGM-VERIFY-AFTER:`, and
  `ACGM-ROLLBACK:`. The hook denies missing evidence before asking the human. /
  重试高风险 Bash 前,按 ACGM 门控准确填写四个字段;缺证据时 hook 会先拒绝,不会把
  不完整操作直接交给人批准。

## Scope / 范围

Default rule: only content needed for the software to be built / shipped / run
belongs here; business / strategy / non-software planning is OUT. This criterion
is a default — redefine it for your project if needed, but keep it explicit. /
默认判据:只有"为软件能开发/上线/运行"的内容属于这里;经营/战略/与软件无关的
规划 = OUT。此判据是默认值——需要可按项目重定义,但必须显式。

> Full methodology: see the agent-coding-governance-methodology repo
> (METHODOLOGY.md). Full setup is human-driven (governance-bootstrap / §12). /
> 完整方法论见 agent-coding-governance-methodology 仓库;完整搭建是人驱动的。
"""


CLAUDE_SCAFFOLD = """# Root rules — meta + pointers, never facts / 根规则 — 元规则+指针,绝不放事实

This project uses agent-coding-governance.

- If the Claude Code plugin is installed, its lifecycle hooks report the project
  state and inject grounding — follow them. Run `acgm doctor` when the state is
  partial, drifted, or broken. If the plugin is absent, read `AGENTS.md`.
- Governance constitution: `./CONSTITUTION.md` (humans only).
- This file holds only meta-rules, pointers, and behavior constraints — never
  facts that can be re-derived from code (Principle 2).

本项目启用 agent-coding-governance。

- 装了 Claude Code 插件:生命周期 hooks 会报告项目状态并注入 grounding,照做。
  状态为 partial/drifted/broken 时运行 `acgm doctor`;没装则读 `AGENTS.md`。
- 治理宪法:`./CONSTITUTION.md`(仅人可改)。
- 本文件只装元规则、指针、行为约束——绝不写能从代码反推的事实(第 2 原则)。
"""


def create_file_exclusive(path: Path, content: bytes) -> bool:
    """Create one scaffold file atomically; never follow or replace a path."""

    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags, 0o644)
    except FileExistsError:
        return False
    complete = False
    try:
        remaining = memoryview(content)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("short scaffold write")
            remaining = remaining[written:]
        os.fsync(descriptor)
        complete = True
    finally:
        try:
            os.close(descriptor)
        finally:
            if not complete:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
    return True


def scaffold_project(target: Path) -> tuple[int, int]:
    template = PLUGIN_ROOT / "templates" / "CONSTITUTION.skeleton.md"
    if not template.is_file():
        raise FileNotFoundError(f"constitution template missing: {template}")

    entries = (
        ("CONSTITUTION.md", template.read_bytes(), "CONSTITUTION.md  (fill every <...> — humans only / 仅人可改)"),
        ("AGENTS.md", AGENTS_SCAFFOLD.encode("utf-8"), "AGENTS.md  (generic agent-governance directive)"),
        ("CLAUDE.md", CLAUDE_SCAFFOLD.encode("utf-8"), "CLAUDE.md  (thin pointer)"),
    )
    created = 0
    skipped = 0
    print(f"agent-coding-governance · scaffold → {target}")
    print("----------------------------------------------------------------")
    for filename, content, created_label in entries:
        path = target / filename
        if create_file_exclusive(path, content):
            print(f"  • create / 新建: {created_label}")
            created += 1
        else:
            print(f"  • skip / 跳过 (已存在,未改动): {filename}")
            skipped += 1
    print("----------------------------------------------------------------")
    print(f"Done / 完成: created {created}, skipped {skipped}.")
    return created, skipped


def command_init(args: argparse.Namespace) -> int:
    """Create the non-overwriting scaffold without a shell dependency."""
    try:
        target = resolve_project_root(explicit=args.project)
    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"ACGM init: {error}", file=sys.stderr)
        return 2
    try:
        scaffold_project(target)
    except OSError as error:
        print(f"ACGM init: {error}", file=sys.stderr)
        return 2
    # Record the resulting adoption state, but never rewrite user-owned files.
    report = doctor_report(str(target), update=True)
    print(f"ACGM project state: {report['project_state']}")
    if report["project_state"] != "GOVERNED":
        print(
            "The safe scaffold is present; constitution, decisions, scope, and snapshots remain human-driven. "
            "/ 安全脚手架已就位；宪法、决策、范围与快照仍由人驱动完成。"
        )
    return 0


EVENT_LABELS = {
    "health": "Session health checked / Session 健康检查",
    "drift_intervention": "Governance intervention / 治理介入",
    "verification_obligation": "Post-action verification / 后验验证义务",
    "event_resolution": "Event resolution / 事件处理",
}


def effective_event_status(events: list[dict[str, Any]]) -> dict[str, str]:
    """Return the latest status for each root governance event.

    Follow-up records are immutable ledger entries with ``related_event_id``;
    they update the lifecycle of the original event instead of becoming a
    second unresolved incident in reports.
    """
    result: dict[str, str] = {}
    for event in events:
        event_id = event.get("event_id")
        related = event.get("related_event_id")
        root_id = related if isinstance(related, str) else event_id
        if isinstance(root_id, str):
            result[root_id] = str(event.get("status") or "unknown")
    return result


def root_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index original events while excluding lifecycle follow-up records."""
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        event_id = event.get("event_id")
        related = event.get("related_event_id")
        if isinstance(event_id, str) and not isinstance(related, str):
            result[event_id] = event
    return result


def command_report(args: argparse.Namespace) -> int:
    store = Store()
    integrity_errors, _ = store_integrity(store)
    if integrity_errors:
        if args.json:
            json_print({"schema_version": 1, "error": "local_state_corrupt_or_unwritable"})
        else:
            print("ACGM report refused: the local Event Ledger or obligation state is corrupt/unwritable. Run `acgm doctor`. / 本地事件账本或义务状态损坏/不可写，报告已拒绝；请运行 `acgm doctor`。", file=sys.stderr)
        return 2
    events = store.events()
    project_id: str | None = None
    if args.project == "current":
        project_id = store.project_id(resolve_project_root())
        events = [event for event in events if event.get("project_id") == project_id]
    statuses = effective_event_status(events)
    roots = root_events(events)
    summary = {
        "sessions_checked": len(
            {e.get("session_id") for e in roots.values() if e.get("event_type") == "health"}
        ),
        "potential_drift_events": sum(
            e.get("event_type") == "drift_intervention" for e in roots.values()
        ),
        "operations_blocked_before_action": sum(
            e.get("action") == "blocked" and e.get("phase") == "pre_action"
            for e in roots.values()
        ),
        "verified_obligations": sum(
            e.get("event_type") == "verification_obligation"
            and statuses.get(event_id) == "verified"
            for event_id, e in roots.items()
        ),
        "human_overrides": sum(status == "human_override" for status in statuses.values()),
        "false_positives": sum(status == "false_positive" for status in statuses.values()),
        "unresolved": sum(
            status
            in {
                "unresolved",
                "pending_human_approval",
                "pending_verification",
            }
            for status in statuses.values()
        ),
        "mechanism_errors": sum(
            e.get("event_type") == "mechanism_error" for e in roots.values()
        ),
    }
    payload = {"schema_version": 1, "project_id": project_id, "summary": summary, "events": events[-args.limit :]}
    if args.json:
        json_print(payload)
        return 0
    print(f"ACGM Activity Report {ACGM_VERSION}")
    if project_id:
        print(f"Project: {project_id}")
    for key, value in summary.items():
        print(f"{key.replace('_', ' ').title()}: {value}")
    print("\nRecent sanitized events:")
    for event in events[-args.limit :]:
        label = EVENT_LABELS.get(str(event.get("event_type")), str(event.get("event_type")))
        print(
            f"- {event.get('timestamp')} | {event.get('project_id')} | {label} | "
            f"{event.get('action')} → {event.get('status')} ({event.get('detail_code')})"
        )
    if not events:
        print("- No events recorded. / 尚无事件。")
    return 0


def command_export_case(args: argparse.Namespace) -> int:
    store = Store()
    integrity_errors, _ = store_integrity(store)
    if integrity_errors:
        print("ACGM export refused: local state is corrupt or unwritable. Run `acgm doctor`. / 本地状态损坏或不可写，已拒绝导出；请运行 `acgm doctor`。", file=sys.stderr)
        return 2
    events = store.events()
    event = next((item for item in events if item.get("event_id") == args.event_id), None)
    if not event:
        print("Event not found / 未找到事件", file=sys.stderr)
        return 1
    content = f"""# ACGM sanitized case preview / ACGM 脱敏案例预览

> Generated locally. Nothing was uploaded. Review every line before sharing.
> 本文件仅在本机生成，未上传。分享前请逐行人工检查。

- Project / 项目: Project-A
- Month / 月份: {str(event.get('timestamp', ''))[:7]}
- Event / 事件: {EVENT_LABELS.get(str(event.get('event_type')), str(event.get('event_type')))}
- Rule / 规则: {event.get('rule_id')}
- Phase / 阶段: {event.get('phase')}
- Intervention / 介入: {event.get('action')}
- Outcome / 结果: {event.get('outcome')}
- Status / 状态: {event.get('status')}
- Confidence / 置信度: {event.get('confidence')}

Excluded by design / 从源头不记录：project paths, file names, commands, prompts,
transcript content, model/provider names, infrastructure identifiers, credentials,
and reconstructable technical fingerprints. / 项目路径、文件名、命令、prompt、
transcript 正文、模型或服务商、基础设施标识、凭据及可重建技术指纹。
"""
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"Preview written / 预览已生成: {output}")
    else:
        print(content)
    return 0


def command_resolve(args: argparse.Namespace) -> int:
    store = Store()
    integrity_errors, _ = store_integrity(store)
    if integrity_errors:
        print("ACGM resolve refused: local state is corrupt or unwritable. Run `acgm doctor`. / 本地状态损坏或不可写，已拒绝分类；请运行 `acgm doctor`。", file=sys.stderr)
        return 2
    events = store.events()
    event = next((item for item in events if item.get("event_id") == args.event_id), None)
    if not event:
        print("Event not found / 未找到事件", file=sys.stderr)
        return 1
    store.append_event(
        project_id=str(event.get("project_id")),
        session_id=str(event.get("session_id")),
        event_type="event_resolution",
        initiator="user",
        phase="audit",
        rule_id="event.lifecycle",
        action="classified",
        status=args.status,
        outcome=args.status,
        confidence="high",
        detail_code="manual_classification",
        related_event_id=args.event_id,
    )
    print(f"Event {args.event_id} → {args.status}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acgm", description="ACGM V3 local governance utilities")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="show ACGM version")
    init = sub.add_parser("init", help="create the non-overwriting minimum governance scaffold")
    init.add_argument("project", nargs="?", default=".")
    doctor = sub.add_parser("doctor", help="check plugin, project governance, and continuity readiness")
    doctor.add_argument("--project")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--strict", action="store_true")
    doctor.add_argument("--no-update", action="store_true", help="do not update the local project-state marker")

    report = sub.add_parser("report", help="show the local sanitized Event Ledger")
    report.add_argument("--project", choices=("all", "current"), default="all")
    report.add_argument("--limit", type=int, default=20)
    report.add_argument("--json", action="store_true")

    export = sub.add_parser("export-case", help="generate a manual-share sanitized case preview")
    export.add_argument("event_id")
    export.add_argument("--output", "-o")

    resolve = sub.add_parser("resolve", help="classify a ledger event after human review")
    resolve.add_argument("event_id")
    resolve.add_argument(
        "--status",
        required=True,
        choices=("resolved", "verified", "human_override", "false_positive", "unresolved"),
    )

    for name in (
        "hook-session-start",
        "hook-pretool-bash",
        "hook-pretool-write",
        "hook-posttool",
        "hook-posttool-failure",
        "hook-stop",
        "hook-session-end",
    ):
        sub.add_parser(name, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "version":
        print(ACGM_VERSION)
        return 0
    if args.command == "init":
        return command_init(args)
    if args.command == "doctor":
        return command_doctor(args)
    if args.command == "report":
        return command_report(args)
    if args.command == "export-case":
        return command_export_case(args)
    if args.command == "resolve":
        return command_resolve(args)

    data = read_hook_input()
    store = Store()
    try:
        if args.command == "hook-session-start":
            hook_session_start(data, store)
        elif args.command == "hook-pretool-bash":
            hook_pretool_bash(data, store)
        elif args.command == "hook-pretool-write":
            hook_pretool_write(data, store)
        elif args.command == "hook-posttool":
            hook_posttool(data, store)
        elif args.command == "hook-posttool-failure":
            hook_posttool_failure(data, store)
        elif args.command == "hook-stop":
            hook_stop(data, store)
        elif args.command == "hook-session-end":
            hook_session_end(data, store)
        else:
            parser.error(f"unknown command: {args.command}")
    except OSError:
        # A mechanism failure is visible to Claude where the event permits it. A
        # destructive command was already fail-closed before this point.
        if args.command == "hook-session-start":
            json_print(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": "ACGM is BROKEN: its local state directory is unavailable. Run `acgm doctor`; do not assume governance is active. / ACGM 本地状态目录不可用，当前为 BROKEN；请运行 doctor，不要假定治理已生效。",
                    }
                }
            )
        elif args.command == "hook-pretool-bash":
            json_print(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "ACGM cannot persist the high-risk operation state, so it failed closed. Run `acgm doctor` and repair the ledger before retrying. / ACGM 无法持久化高风险操作状态，已按失败关闭；请运行 doctor 修复后重试。",
                    }
                }
            )
        elif args.command == "hook-pretool-write" and "CONSTITUTION.md" in json.dumps(
            data.get("tool_input", {}), ensure_ascii=False
        ):
            json_print(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "ACGM is BROKEN and cannot persist Constitution ownership state, so this possible Constitution write failed closed. Run `acgm doctor` before retrying. / ACGM 已损坏，无法持久化宪法权属状态；本次可能的宪法写入已失败关闭，请先运行 `acgm doctor`。",
                    }
                }
            )
        elif args.command in {"hook-posttool", "hook-posttool-failure"}:
            event_name = "PostToolUse" if args.command == "hook-posttool" else "PostToolUseFailure"
            json_print(
                {
                    "hookSpecificOutput": {
                        "hookEventName": event_name,
                        "additionalContext": "ACGM mechanism error: post-action state could not be persisted or correlated. Do not assume the operation had no effect and do not finish quietly; run the declared verification manually and repair the ledger with `acgm doctor`. / ACGM 机制错误：动作后状态无法持久化或关联。不得假定操作没有副作用，也不得安静结束；请手动执行已声明核验并用 `acgm doctor` 修复账本。",
                    }
                }
            )
        elif args.command == "hook-stop":
            json_print(
                {
                    "decision": "block",
                    "reason": "ACGM cannot read or persist post-action obligations, so it cannot prove the turn is safe to close. Run the declared verification manually and repair the local state with `acgm doctor`. / ACGM 无法读取或持久化后验义务，不能证明本轮可安全结束。请手动执行核验并用 `acgm doctor` 修复本地状态。",
                }
            )
        else:
            json_print({})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
