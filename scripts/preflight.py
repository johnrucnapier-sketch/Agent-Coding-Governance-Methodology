#!/usr/bin/env python3
"""Read-only ACGM V3 installation preflight.

The preflight reports capability signals only. It does not edit Claude settings,
install the plugin, infer the backing model/account, or initialize a project.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from typing import Any, Sequence

import acgm_runtime as runtime


MINIMUM_PYTHON = (3, 10)
VERSION_PATTERN = re.compile(r"(?<![0-9])([0-9]+(?:\.[0-9]+){1,3})(?![0-9])")


def numeric_version(text: str) -> tuple[int, ...] | None:
    match = VERSION_PATTERN.search(text)
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def version_text(value: tuple[int, ...] | None) -> str | None:
    return ".".join(str(part) for part in value) if value else None


def command_version(argv: Sequence[str]) -> tuple[bool, tuple[int, ...] | None]:
    if not shutil.which(argv[0]):
        return False, None
    try:
        completed = subprocess.run(
            list(argv),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, None
    return completed.returncode == 0, numeric_version(completed.stdout or "")


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


def build_report() -> dict[str, Any]:
    system = platform.system()
    errors: list[str] = []
    warnings: list[str] = []

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

    claude_ok, claude_version = command_version(["claude", "--version"])
    if not claude_ok:
        errors.append("claude_code_missing_or_unusable")
    elif claude_version is None:
        warnings.append("claude_code_version_unreadable")

    git_bash_required = system == "Windows"
    git_bash_ok = True
    git_bash_source = "not_required"
    powershell_setting_required = system == "Windows"
    powershell_tool_disabled = True

    if is_wsl():
        profile = "wsl_unvalidated"
        errors.append("wsl_profile_not_supported_by_this_rc")
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

    unique_errors = sorted(set(errors))
    return {
        "schema_version": 1,
        "acgm_version": runtime.ACGM_VERSION,
        "status": "READY_FOR_RC_TEST" if not unique_errors else "BLOCKED",
        "read_only": True,
        "platform": {
            "system": system,
            "profile": profile,
        },
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
    }


def human_report(report: dict[str, Any]) -> str:
    lines = [
        f"ACGM {report['acgm_version']} preflight: {report['status']}",
        f"Platform / 平台: {report['platform']['profile']}",
    ]
    for name, check in report["checks"].items():
        state = "OK" if check["ok"] else "BLOCKED"
        lines.append(f"- {name}: {state}")
    if report["error_codes"]:
        lines.append("Errors / 阻塞: " + ", ".join(report["error_codes"]))
    if report["warning_codes"]:
        lines.append("Warnings / 提醒: " + ", ".join(report["warning_codes"]))
    lines.append(
        "Read-only result: no settings, plugin, project, account, or model was changed or inferred. / "
        "只读结果：未修改设置、插件或项目，也未推断账号与模型。"
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only ACGM V3 installation preflight")
    parser.add_argument("--json", action="store_true", help="emit stable machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    else:
        print(human_report(report))
    return 0 if report["status"] == "READY_FOR_RC_TEST" else 1


if __name__ == "__main__":
    raise SystemExit(main())
