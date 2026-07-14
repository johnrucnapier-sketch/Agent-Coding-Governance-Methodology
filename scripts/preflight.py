#!/usr/bin/env python3
"""Read-only, surface-aware ACGM V3 installation preflight.

The preflight reports observable host capabilities only. It does not edit Claude
settings, install the plugin, infer the backing model/account, or initialize a
project. A ready installation route is not proof that the runtime hooks loaded.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence

import acgm_runtime as runtime


MINIMUM_PYTHON = (3, 10)
MINIMUM_CLAUDE_PLUGIN_TRUST = (2, 1, 195)
VERSION_PATTERN = re.compile(r"(?<![0-9])([0-9]+(?:\.[0-9]+){1,3})(?![0-9])")
SURFACE_CHOICES = (
    "auto",
    "claude-code-cli",
    "desktop-code-local",
    "desktop-code-ssh",
    "desktop-code-cloud",
    "desktop-code-remote",
    "desktop-code-wsl",
    "desktop-chat",
    "cowork",
)
SURFACE_ALIASES = {"desktop-code-remote": "desktop-code-cloud"}
READY_STATUSES = {
    "READY_FOR_AUTOMATED_INSTALL",
    "MANUAL_INSTALL_PLAN_AVAILABLE",
}


def neutral_cwd_is_safe(path: Path) -> bool:
    """Reject a temporary control cwd nested below any project configuration."""

    try:
        candidate = path.resolve(strict=True)
        home = Path.home().resolve(strict=True)
    except OSError:
        return False
    for ancestor in (candidate, *candidate.parents):
        if (ancestor / ".git").exists():
            return False
        if ancestor != home and any(
            (ancestor / ".claude" / name).exists()
            for name in ("settings.json", "settings.local.json")
        ):
            return False
    return True


def numeric_version(text: str) -> tuple[int, ...] | None:
    match = VERSION_PATTERN.search(text)
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def version_text(value: tuple[int, ...] | None) -> str | None:
    return ".".join(str(part) for part in value) if value else None


def command_version(argv: Sequence[str]) -> tuple[bool, tuple[int, ...] | None]:
    if not shutil.which(argv[0]):
        return False, None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        executable_name = Path(argv[0]).name.casefold()
        cwd = None
        if executable_name in {"claude", "claude.exe"}:
            temporary = tempfile.TemporaryDirectory(prefix="acgm-claude-probe-")
            os.chmod(temporary.name, 0o700)
            if not neutral_cwd_is_safe(Path(temporary.name)):
                return False, None
            cwd = temporary.name
        completed = subprocess.run(
            list(argv),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
            cwd=cwd,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, None
    finally:
        if temporary is not None:
            temporary.cleanup()
    return completed.returncode == 0, numeric_version(completed.stdout or "")


def command_succeeds(argv: Sequence[str]) -> bool:
    """Return whether a fixed, read-only capability probe succeeds."""

    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        temporary = tempfile.TemporaryDirectory(prefix="acgm-claude-probe-")
        os.chmod(temporary.name, 0o700)
        if not neutral_cwd_is_safe(Path(temporary.name)):
            return False
        completed = subprocess.run(
            list(argv),
            check=False,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            cwd=temporary.name,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        if temporary is not None:
            temporary.cleanup()
    return completed.returncode == 0


def resolve_claude_executable() -> tuple[Path | None, str | None]:
    """Resolve a directly executable Claude binary without batch indirection."""

    raw = shutil.which("claude")
    if not raw:
        return None, "claude_code_missing_or_unusable"
    try:
        candidate = Path(raw).expanduser().resolve(strict=True)
    except OSError:
        return None, "claude_code_missing_or_unusable"
    if not candidate.is_file():
        return None, "claude_code_missing_or_unusable"
    if platform.system() != "Windows":
        return candidate, None

    if candidate.suffix.casefold() in {".cmd", ".bat"}:
        return None, "windows_claude_batch_launcher_unsupported"
    try:
        with candidate.open("rb") as handle:
            magic = handle.read(2)
    except OSError:
        return None, "windows_claude_launcher_unreadable"
    if magic != b"MZ":
        return None, "windows_claude_launcher_not_native"
    return candidate, None


def python_launcher() -> tuple[bool, str | None, tuple[int, ...] | None]:
    probe = "import sys; print('.'.join(map(str, sys.version_info[:3])))"
    for kind, argv in (
        ("python3", ["python3", "-c", probe]),
        ("python", ["python", "-c", probe]),
        ("py-3", ["py", "-3", "-c", probe]),
    ):
        available, version = command_version(argv)
        if available and version and version >= MINIMUM_PYTHON:
            return True, kind, version
    return False, None, None


def is_wsl() -> bool:
    return bool(os.environ.get("WSL_DISTRO_NAME")) or "microsoft" in platform.release().casefold()


def observable_signals() -> dict[str, bool]:
    """Return booleans only; never expose endpoint, account, or provider values."""

    return {
        "inside_claude_code_subprocess": os.environ.get("CLAUDECODE") == "1",
        "cloud_session": os.environ.get("CLAUDE_CODE_REMOTE", "").casefold() == "true",
        "cloud_session_id_present": bool(os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID")),
        "provider_managed_by_host": bool(os.environ.get("CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST")),
    }


def resolve_surface(
    requested: str,
    *,
    signals: dict[str, bool],
    wsl: bool,
    claude_ok: bool,
    claude_launcher_error: str | None,
) -> tuple[str, str]:
    normalized = SURFACE_ALIASES.get(requested, requested)
    # Official Cloud and OS-level WSL signals describe the environment in which
    # this preflight is actually executing.  A caller-provided label must never
    # override those stronger facts and unlock a mutating installation route.
    if signals["cloud_session"]:
        confidence = (
            "official_cloud_signal"
            if normalized in {"auto", "desktop-code-cloud"}
            else "official_cloud_signal_conflicts_with_user_selection"
        )
        return "desktop-code-cloud", confidence
    if wsl:
        confidence = (
            "wsl_runtime_signal"
            if normalized in {"auto", "desktop-code-wsl"}
            else "wsl_runtime_signal_conflicts_with_user_selection"
        )
        return "desktop-code-wsl", confidence
    if normalized != "auto":
        return normalized, "user_selected"
    if signals["inside_claude_code_subprocess"] and claude_ok:
        return "claude-code-cli-or-desktop", "surface_ambiguous_inside_claude_code"
    if claude_ok or (
        claude_launcher_error is not None
        and claude_launcher_error != "claude_code_missing_or_unusable"
    ):
        return "claude-code-cli", "local_cli_capability"
    if signals["inside_claude_code_subprocess"]:
        return "desktop-code-local-or-ssh", "claude_code_subprocess_capability"
    return "unknown", "insufficient_observable_signals"


def action_plan(
    *,
    status: str,
    resolved_surface: str,
    launcher_kind: str | None,
    error_codes: Sequence[str] = (),
) -> list[dict[str, Any]]:
    python = "py -3" if launcher_kind == "py-3" else (launcher_kind or "python3")
    if status == "READY_FOR_AUTOMATED_INSTALL":
        return [
            {
                "id": "verify_source_and_plan",
                "kind": "command",
                "command": f"{python} scripts/install.py --surface {resolved_surface} --dry-run --json",
                "mutates_state": False,
                "requires_explicit_install_intent": False,
            },
            {
                "id": "install_verified_configuration",
                "kind": "command",
                "command": f"{python} scripts/install.py --surface {resolved_surface} --json",
                "mutates_state": True,
                "requires_explicit_install_intent": True,
            },
            {
                "id": "activate_and_verify_runtime",
                "kind": "runtime_verification",
                "instruction": "Reload plugins, start a fresh disposable session, inspect /hooks and /skills, then run acgm version and acgm doctor --json.",
                "mutates_state": False,
                "requires_explicit_install_intent": False,
            },
        ]
    if status == "MANUAL_INSTALL_PLAN_AVAILABLE":
        actions: list[dict[str, Any]] = [
            {
                "id": "verify_plugin_trust_contract_version",
                "kind": "decision",
                "instruction": "Verify that the exact target Claude Code surface is version 2.1.195 or newer so repository-declared plugins require explicit install and trust consent.",
                "mutates_state": False,
                "requires_explicit_install_intent": False,
            }
        ]
        if resolved_surface in {"desktop-code-local", "desktop-code-ssh"}:
            actions.append(
                {
                    "id": "verify_source_for_manual_install",
                    "kind": "command",
                    "command": f"{python} scripts/install.py --surface {resolved_surface} --dry-run --json",
                    "mutates_state": False,
                    "requires_explicit_install_intent": False,
                }
            )
        else:
            actions.append(
                {
                    "id": "confirm_exact_code_surface",
                    "kind": "decision",
                    "instruction": "Confirm whether this is Desktop Code Local or Desktop Code SSH, then rerun with that explicit --surface before installation.",
                    "mutates_state": False,
                    "requires_explicit_install_intent": False,
                }
            )
        actions.extend([
            {
                "id": "accept_repository_plugin_prompt",
                "kind": "ui",
                "instruction": "In the same Claude Desktop Code Local/SSH surface, trust this checkout and accept its marketplace/plugin prompts, or use the Plugins UI to add the repository marketplace and install ACGM. The project bridge is not a user-wide install; choose user scope only when the user explicitly requested ACGM across projects.",
                "mutates_state": True,
                "requires_explicit_install_intent": True,
            },
            {
                "id": "activate_and_verify_runtime",
                "kind": "runtime_verification",
                "instruction": "Reload plugins in that same Code surface, start a fresh disposable session, inspect /hooks and /skills, then run acgm version and acgm doctor --json.",
                "mutates_state": False,
                "requires_explicit_install_intent": False,
            },
        ])
        return actions
    if status == "TARGET_SURFACE_REQUIRED":
        return [
            {
                "id": "select_target_surface",
                "kind": "command",
                "instruction": "Rerun preflight with an explicit --surface. Do not infer the surface from an account label or model name.",
                "allowed_surfaces": [value for value in SURFACE_CHOICES if value not in {"auto", "desktop-code-remote"}],
                "mutates_state": False,
                "requires_explicit_install_intent": False,
            }
        ]
    if status == "ADVISORY_ONLY":
        return [
            {
                "id": "use_skill_only_mode_or_change_surface",
                "kind": "decision",
                "instruction": "Desktop Chat can use plugin skills, but it does not run ACGM enforcement hooks. Use Claude Code Local/SSH for full governance.",
                "mutates_state": False,
                "requires_explicit_install_intent": False,
            }
        ]
    if status == "EXPERIMENTAL_SURFACE_UNVERIFIED":
        return [
            {
                "id": "cowork_e2e_required",
                "kind": "runtime_verification",
                "instruction": "Cowork hook support exists, but ACGM command-hook compatibility is unverified. Do not claim full governance without a dedicated disposable E2E pass.",
                "mutates_state": False,
                "requires_explicit_install_intent": False,
            }
        ]
    if status == "SURFACE_SIGNAL_CONFLICT":
        return [
            {
                "id": "use_observed_runtime_surface",
                "kind": "decision",
                "instruction": "Do not override the observed Cloud/WSL runtime. Open the checkout in Claude Code CLI or Desktop Code Local/SSH, then rerun preflight there.",
                "mutates_state": False,
                "requires_explicit_install_intent": False,
            }
        ]
    if status == "UNSUPPORTED_SURFACE":
        return [
            {
                "id": "change_to_supported_code_surface",
                "kind": "decision",
                "instruction": "This surface cannot load full ACGM plugins. Reopen the checkout in Claude Code CLI or Desktop Code Local/SSH and rerun preflight.",
                "mutates_state": False,
                "requires_explicit_install_intent": False,
            }
        ]
    if status == "BLOCKED":
        if "claude_code_plugin_trust_contract_too_old_or_unverified" in error_codes:
            return [
                {
                    "id": "update_claude_code_for_plugin_trust_contract",
                    "kind": "decision",
                    "instruction": "With explicit user approval, update the exact target Claude Code installation to version 2.1.195 or newer, then rerun this read-only preflight.",
                    "mutates_state": True,
                    "requires_explicit_install_intent": True,
                }
            ]
        return [
            {
                "id": "resolve_preflight_errors",
                "kind": "decision",
                "instruction": "Resolve the listed preflight error codes without bypassing source, trust, shell, or platform checks, then rerun preflight.",
                "mutates_state": False,
                "requires_explicit_install_intent": False,
            }
        ]
    return []


def build_report(requested_surface: str = "auto") -> dict[str, Any]:
    system = platform.system()
    errors: list[str] = []
    warnings: list[str] = []
    if requested_surface not in SURFACE_CHOICES:
        raise ValueError(f"unsupported surface value: {requested_surface}")

    current_python = tuple(sys.version_info[:3])
    current_python_ok = current_python >= MINIMUM_PYTHON
    if not current_python_ok:
        errors.append("python_runtime_too_old")

    launcher_ok, launcher_kind, launcher_version = python_launcher()
    if not launcher_ok:
        errors.append("python_launcher_3_10_missing")

    git_ok, git_version = command_version(["git", "--version"])
    if not git_ok:
        errors.append("git_missing_or_unusable")

    claude_executable, claude_launcher_error = resolve_claude_executable()
    claude_ok = False
    plugin_cli_ok = False
    claude_version = None
    if claude_executable is not None and claude_launcher_error is None:
        claude_ok, claude_version = command_version(
            [str(claude_executable), "--version"]
        )
        if claude_ok:
            plugin_cli_ok = command_succeeds(
                [str(claude_executable), "plugin", "list", "--help"]
            ) and command_succeeds(
                [str(claude_executable), "plugin", "marketplace", "list", "--help"]
            )
        if claude_ok and claude_version is None:
            warnings.append("claude_code_version_unreadable")

    git_bash_required = system == "Windows"
    git_bash_ok = True
    git_bash_source = "not_required"
    powershell_setting_required = system == "Windows"
    powershell_tool_disabled = True

    wsl = is_wsl()
    if wsl:
        profile = "wsl_unvalidated"
    elif system == "Windows":
        profile = "windows_git_bash_candidate"
        git_bash_ok, git_bash_source = runtime.windows_git_bash_status()
        powershell_tool_disabled = (
            runtime.effective_claude_env("CLAUDE_CODE_USE_POWERSHELL_TOOL") == "0"
        )
        if not git_bash_ok:
            errors.append("windows_git_bash_missing_or_invalid")
        if not powershell_tool_disabled:
            errors.append("windows_powershell_tool_must_be_disabled")
        warnings.extend(
            [
                "windows_git_bash_candidate_only",
                "windows_acl_equivalence_unvalidated",
                "powershell_native_unsupported",
            ]
        )
    elif system in {"Darwin", "Linux"}:
        profile = "posix_supported"
    else:
        profile = "unsupported_platform"
        errors.append("platform_not_supported")

    signals = observable_signals()
    if signals["provider_managed_by_host"]:
        warnings.append("provider_route_managed_by_host_identity_not_inferred")
    resolved_surface, surface_confidence = resolve_surface(
        requested_surface,
        signals=signals,
        wsl=wsl,
        claude_ok=claude_ok,
        claude_launcher_error=claude_launcher_error,
    )
    surface_signal_conflict = surface_confidence.endswith(
        "conflicts_with_user_selection"
    )
    if surface_signal_conflict:
        errors.append("requested_surface_conflicts_with_observed_runtime")

    support_level = "unknown"
    install_route = "none"
    hooks_expected: bool | None = None
    if resolved_surface == "claude-code-cli":
        support_level = "full_governance_candidate"
        hooks_expected = True
        install_route = "claude_plugin_cli"
        if not claude_ok:
            errors.append(claude_launcher_error or "claude_code_missing_or_unusable")
        if not plugin_cli_ok:
            errors.append("claude_plugin_cli_missing_or_unusable")
    elif resolved_surface in {"desktop-code-local", "desktop-code-ssh"}:
        support_level = "full_governance_candidate"
        hooks_expected = True
        # A CLI configuration write is not same-surface Desktop acceptance.
        # Keep explicit Desktop targets on their own UI/trust route even when a
        # standalone CLI happens to be installed on the same machine.
        install_route = "desktop_plugin_manager"
        if not (claude_ok and plugin_cli_ok):
            warnings.append(
                claude_launcher_error or "claude_plugin_cli_unavailable_use_desktop_ui"
            )
    elif resolved_surface == "desktop-code-local-or-ssh":
        support_level = "full_governance_candidate"
        install_route = "desktop_plugin_manager"
        hooks_expected = True
        warnings.append("exact_code_surface_not_observable_verify_in_target_surface")
        warnings.append("claude_plugin_cli_unavailable_use_desktop_ui")
    elif resolved_surface == "claude-code-cli-or-desktop":
        support_level = "target_surface_required"
        install_route = "none"
        hooks_expected = None
        errors.append("target_surface_required_inside_claude_code")
    elif resolved_surface in {"desktop-code-cloud", "desktop-code-wsl"}:
        support_level = "unsupported"
        hooks_expected = False
        errors.append(f"full_acgm_plugins_unavailable_on_{resolved_surface}")
    elif resolved_surface == "desktop-chat":
        support_level = "advisory_only"
        install_route = "desktop_customize"
        hooks_expected = False
        errors.append("desktop_chat_does_not_run_acgm_enforcement_hooks")
    elif resolved_surface == "cowork":
        support_level = "full_governance_unverified"
        install_route = "desktop_customize"
        hooks_expected = True
        warnings.append("cowork_acgm_command_hooks_require_dedicated_e2e")
    else:
        errors.append("target_surface_required")

    if install_route == "claude_plugin_cli" and not plugin_cli_ok:
        errors.append("claude_plugin_cli_missing_or_unusable")

    trust_contract_required = support_level == "full_governance_candidate"
    trust_contract_ok = bool(
        claude_version and claude_version >= MINIMUM_CLAUDE_PLUGIN_TRUST
    )
    if trust_contract_required and install_route == "claude_plugin_cli":
        if not trust_contract_ok:
            errors.append("claude_code_plugin_trust_contract_too_old_or_unverified")
    elif trust_contract_required and not trust_contract_ok:
        warnings.append("target_surface_plugin_trust_contract_version_unverified")

    unique_errors = sorted(set(errors))
    if surface_signal_conflict:
        status = "SURFACE_SIGNAL_CONFLICT"
    elif resolved_surface in {"desktop-code-cloud", "desktop-code-wsl"}:
        status = "UNSUPPORTED_SURFACE"
    elif resolved_surface == "desktop-chat":
        status = "ADVISORY_ONLY"
    elif resolved_surface == "cowork":
        status = "EXPERIMENTAL_SURFACE_UNVERIFIED"
    elif resolved_surface in {"unknown", "claude-code-cli-or-desktop"}:
        status = "TARGET_SURFACE_REQUIRED"
    elif unique_errors:
        status = "BLOCKED"
    elif install_route == "claude_plugin_cli":
        status = "READY_FOR_AUTOMATED_INSTALL"
    elif install_route == "desktop_plugin_manager":
        status = "MANUAL_INSTALL_PLAN_AVAILABLE"
    else:
        status = "BLOCKED"

    actions = action_plan(
        status=status,
        resolved_surface=resolved_surface,
        launcher_kind=launcher_kind,
        error_codes=unique_errors,
    )
    return {
        "schema_version": 2,
        "acgm_version": runtime.ACGM_VERSION,
        "status": status,
        "read_only": True,
        "platform": {
            "system": system,
            "profile": profile,
        },
        "surface": {
            "requested": requested_surface,
            "resolved": resolved_surface,
            "confidence": surface_confidence,
            "support_level": support_level,
            "install_route": install_route,
            "hooks_expected": hooks_expected,
            "runtime_activation_verified": False,
        },
        "observable_signals": signals,
        "checks": {
            "python_runtime": {
                "ok": current_python_ok,
                "version": version_text(current_python),
                "minimum": version_text(MINIMUM_PYTHON),
            },
            "python_hook_launcher": {
                "ok": launcher_ok,
                "kind": launcher_kind,
                "version": version_text(launcher_version),
            },
            "git": {"ok": git_ok, "version": version_text(git_version)},
            "claude_code": {
                "ok": claude_ok,
                "version": version_text(claude_version),
                "launcher": (
                    "native_executable"
                    if claude_executable is not None and claude_launcher_error is None
                    else "blocked"
                ),
            },
            "claude_plugin_cli": {
                "required": install_route == "claude_plugin_cli",
                "ok": plugin_cli_ok,
            },
            "plugin_trust_contract": {
                "required": trust_contract_required,
                "ok": trust_contract_ok,
                "minimum_claude_code_version": version_text(
                    MINIMUM_CLAUDE_PLUGIN_TRUST
                ),
                "observed_claude_code_version": version_text(claude_version),
            },
            "git_bash": {
                "required": git_bash_required,
                "ok": git_bash_ok,
                "source": git_bash_source,
            },
            "powershell_tool_disabled": {
                "required": powershell_setting_required,
                "ok": powershell_tool_disabled,
            },
        },
        "error_codes": unique_errors,
        "warning_codes": sorted(set(warnings)),
        "identity_inference": "not_performed",
        "actions": actions,
    }


def human_report(report: dict[str, Any]) -> str:
    lines = [
        f"ACGM {report['acgm_version']} preflight: {report['status']}",
        f"Platform / 平台: {report['platform']['profile']}",
        f"Surface / 运行表面: {report['surface']['resolved']}",
        f"Install route / 安装路径: {report['surface']['install_route']}",
    ]
    for name, check in report["checks"].items():
        state = "OK" if check["ok"] else "BLOCKED"
        lines.append(f"- {name}: {state}")
    if report["error_codes"]:
        lines.append("Errors / 阻塞: " + ", ".join(report["error_codes"]))
    if report["warning_codes"]:
        lines.append("Warnings / 提醒: " + ", ".join(report["warning_codes"]))
    lines.append(
        "Read-only capability result: no settings, plugin, project, account, or model was changed or inferred; runtime activation is still unverified. / "
        "只读能力结果：未修改设置、插件或项目，也未推断账号与模型；运行时激活仍未验证。"
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only ACGM V3 installation preflight")
    parser.add_argument("--json", action="store_true", help="emit stable machine-readable JSON")
    parser.add_argument(
        "--surface",
        choices=SURFACE_CHOICES,
        default="auto",
        help="target Claude surface; auto uses observable capabilities only",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_report(args.surface)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    else:
        print(human_report(report))
    return 0 if report["status"] in READY_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
