#!/usr/bin/env python3
"""Fail-fast release contract checks for the ACGM plugin repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any


PLUGIN_NAME = "agent-coding-governance-methodology"
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
REQUIRED_HOOKS = {
    "SessionStart",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "Stop",
    "SessionEnd",
}
EXPECTED_MODES = {
    "SessionStart": {"session-start"},
    "PreToolUse": {"pretool-bash", "pretool-write"},
    "PostToolUse": {"posttool"},
    "PostToolUseFailure": {"posttool-failure"},
    "Stop": {"stop"},
    "SessionEnd": {"session-end"},
}
HOOK_SHELL_COMMAND = re.compile(
    r'^sh "\$CLAUDE_PLUGIN_ROOT/scripts/acgm-hook\.sh" '
    r'(session-start|pretool-bash|pretool-write|posttool|posttool-failure|stop|session-end) '
    r'"\$CLAUDE_PLUGIN_DATA"$'
)
EXECUTABLES = {
    "bin/acgm",
    "scripts/acgm-hook.sh",
    "scripts/acgm_runtime.py",
    "scripts/build-release.sh",
    "scripts/drift-check.sh",
    "scripts/generate-package-manifest.py",
    "scripts/governance-init.sh",
    "scripts/grounding-inject.sh",
    "scripts/post-tool-truth-first.sh",
    "scripts/preflight.py",
    "scripts/pretool-destructive-bash.sh",
    "scripts/release_check.py",
}
FORBIDDEN_RELEASE_PATHS = {
    "BUILD_BRIEF.md",
    "PUBLISHING.md",
}


class Results:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passed: list[str] = []

    def error(self, code: str) -> None:
        self.errors.append(code)

    def warn(self, code: str) -> None:
        self.warnings.append(code)

    def pass_(self, code: str) -> None:
        self.passed.append(code)

    def payload(self) -> dict[str, Any]:
        return {
            "ok": not self.errors,
            "errors": sorted(set(self.errors)),
            "warnings": sorted(set(self.warnings)),
            "passed": sorted(set(self.passed)),
        }


def read_json(path: Path, results: Results, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        results.error(code)
        return {}
    if not isinstance(value, dict):
        results.error(code)
        return {}
    return value


def check_versions(root: Path, results: Results) -> str:
    try:
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        results.error("version_file_missing")
        return ""
    if not SEMVER.fullmatch(version):
        results.error("version_not_semver")
    manifest = read_json(root / ".claude-plugin" / "plugin.json", results, "plugin_manifest_invalid")
    if manifest.get("name") != PLUGIN_NAME:
        results.error("plugin_name_mismatch")
    if manifest.get("version") != version:
        results.error("plugin_version_mismatch")
    marketplace = read_json(
        root / ".claude-plugin" / "marketplace.json", results, "marketplace_manifest_invalid"
    )
    entries = marketplace.get("plugins", [])
    entry = entries[0] if isinstance(entries, list) and entries and isinstance(entries[0], dict) else {}
    if marketplace.get("name") != PLUGIN_NAME or entry.get("name") != PLUGIN_NAME:
        results.error("marketplace_name_mismatch")
    if entry.get("source") != "./":
        results.error("marketplace_source_must_be_repo_root")
    if not results.errors:
        results.pass_("version_and_manifests")
    return version


def hook_modes(groups: Any) -> set[str]:
    modes: set[str] = set()
    if not isinstance(groups, list):
        return modes
    for group in groups:
        if not isinstance(group, dict):
            continue
        handlers = group.get("hooks", [])
        if not isinstance(handlers, list):
            continue
        for handler in handlers:
            if not isinstance(handler, dict):
                continue
            command = str(handler.get("command") or "")
            if "acgm-hook.sh" not in command:
                continue
            match = HOOK_SHELL_COMMAND.fullmatch(command)
            if match:
                modes.add(match.group(1))
    return modes


def check_hooks(root: Path, results: Results) -> None:
    value = read_json(root / "hooks" / "hooks.json", results, "hooks_invalid")
    hooks = value.get("hooks", {})
    if not isinstance(hooks, dict):
        results.error("hooks_invalid")
        return
    missing = REQUIRED_HOOKS - set(hooks)
    for event in sorted(missing):
        results.error(f"hook_missing:{event}")
    session_groups = hooks.get("SessionStart", [])
    matchers = {
        token
        for group in session_groups
        if isinstance(group, dict)
        for token in str(group.get("matcher") or "").split("|")
        if token
    }
    for source in ("startup", "resume", "clear", "compact"):
        if source not in matchers:
            results.error(f"session_start_matcher_missing:{source}")
    for event, expected in EXPECTED_MODES.items():
        actual = hook_modes(hooks.get(event))
        for mode in sorted(expected - actual):
            results.error(f"hook_mode_missing:{event}:{mode}")
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            for handler in group.get("hooks", []) if isinstance(group, dict) else []:
                if not isinstance(handler, dict) or "acgm-hook.sh" not in str(handler.get("command") or ""):
                    continue
                command = str(handler.get("command") or "")
                if "args" in handler:
                    results.error(f"hook_exec_form_forbidden:{event}")
                if "shell" in handler:
                    results.error(f"hook_shell_override_forbidden:{event}")
                if "${CLAUDE_PLUGIN_" in command:
                    results.error(f"hook_placeholder_interpolation_forbidden:{event}")
                if not HOOK_SHELL_COMMAND.fullmatch(command):
                    results.error(f"hook_shell_command_invalid:{event}")
    if not any(code.startswith(("hook_", "hooks_", "session_start_")) for code in results.errors):
        results.pass_("hook_inventory")


def check_executable_modes(root: Path, results: Results) -> None:
    for relative in sorted(EXECUTABLES):
        path = root / relative
        if not path.is_file():
            results.error(f"executable_missing:{relative}")
            continue
        if os.name != "nt" and not stat.S_IMODE(path.stat().st_mode) & 0o111:
            results.error(f"not_executable:{relative}")
    if not any(code.startswith(("executable_missing:", "not_executable:")) for code in results.errors):
        results.pass_("executable_modes")


def check_line_endings_contract(root: Path, results: Results) -> None:
    path = root / ".gitattributes"
    try:
        lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines()}
    except OSError:
        results.error("gitattributes_missing")
        return
    if "* text=auto eol=lf" not in lines:
        results.error("gitattributes_lf_contract_missing")
        return
    results.pass_("line_endings_contract")


def git_output(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout if completed.returncode == 0 else None


def check_release_paths(root: Path, results: Results) -> None:
    tracked_output = git_output(root, "ls-files")
    if tracked_output is None:
        results.warn("git_file_inventory_unavailable")
        return
    tracked = {line.strip() for line in tracked_output.splitlines() if line.strip()}
    ignored_output = git_output(root, "ls-files", "-ci", "--exclude-standard") or ""
    for relative in ignored_output.splitlines():
        if relative.strip():
            results.error(f"tracked_ignored_content:{relative.strip()}")
    for relative in sorted(tracked):
        path = Path(relative)
        if relative in FORBIDDEN_RELEASE_PATHS:
            results.error(f"local_only_content_tracked:{relative}")
        if path.parts[:2] == ("docs", "superpowers") or path.parts[:1] == (".claude",):
            results.error(f"local_only_content_tracked:{relative}")
        if path.name == ".DS_Store" or path.suffix == ".pyc" or "__pycache__" in path.parts:
            results.error(f"generated_content_tracked:{relative}")
    if not any(
        code.startswith(("tracked_ignored_content:", "local_only_content_tracked:", "generated_content_tracked:"))
        for code in results.errors
    ):
        results.pass_("release_path_hygiene")


def contains(path: Path, pattern: str) -> bool:
    try:
        return bool(re.search(pattern, path.read_text(encoding="utf-8"), re.I | re.S))
    except OSError:
        return False


def check_bilingual_contract(root: Path, results: Results) -> None:
    readme = root / "README.md"
    contracts = {
        "readme_event_ledger_en": (readme, r"Event Ledger"),
        "readme_event_ledger_zh": (readme, r"事件(?:日志|台账|账本)"),
        "readme_local_only_en": (readme, r"local-only|stored locally|local Event Ledger"),
        "readme_local_only_zh": (readme, r"仅存本机|只存本机|本机.{0,12}保存|本地.{0,12}保存"),
        "readme_no_upload_en": (readme, r"does not automatically upload|never uploads|no automatic upload"),
        "readme_no_upload_zh": (readme, r"不自动上传|不会自动上传|绝不自动上传"),
        "methodology_normative_en": (root / "METHODOLOGY.en.md", r"Normative"),
        "methodology_normative_zh": (root / "METHODOLOGY.md", r"规范层"),
    }
    for code, (path, pattern) in contracts.items():
        if not contains(path, pattern):
            results.error(f"bilingual_contract_missing:{code}")
    if not any(code.startswith("bilingual_contract_missing:") for code in results.errors):
        results.pass_("bilingual_contract")


def check_package_manifest(root: Path, version: str, results: Results, required: bool) -> None:
    path = root / "PACKAGE_MANIFEST.json"
    if not path.is_file():
        if required:
            results.error("package_manifest_missing")
        else:
            results.warn("package_manifest_missing")
        return
    manifest = read_json(path, results, "package_manifest_invalid")
    if manifest.get("version") != version:
        results.error("package_manifest_version_mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict):
        results.error("package_manifest_invalid")
        return
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            results.error("package_manifest_invalid")
            continue
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            results.error(f"package_manifest_unsafe_path:{relative}")
            continue
        if not candidate.is_file():
            results.error(f"package_file_missing:{relative}")
            continue
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != expected:
            results.error(f"package_hash_mismatch:{relative}")
    if not any(code.startswith("package_") for code in results.errors):
        results.pass_("package_manifest")


def run_checks(
    root: Path,
    *,
    require_package_manifest: bool = False,
    skip_bilingual: bool = False,
) -> Results:
    results = Results()
    version = check_versions(root, results)
    check_hooks(root, results)
    check_executable_modes(root, results)
    check_line_endings_contract(root, results)
    check_release_paths(root, results)
    if not skip_bilingual:
        check_bilingual_contract(root, results)
    check_package_manifest(root, version, results, require_package_manifest)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the ACGM release contract")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-package-manifest", action="store_true")
    parser.add_argument("--skip-bilingual", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    results = run_checks(
        root,
        require_package_manifest=args.require_package_manifest,
        skip_bilingual=args.skip_bilingual,
    )
    payload = results.payload()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        for code in payload["passed"]:
            print(f"PASS {code}")
        for code in payload["warnings"]:
            print(f"WARN {code}")
        for code in payload["errors"]:
            print(f"FAIL {code}")
        print("release contract: PASS" if payload["ok"] else "release contract: FAIL")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
