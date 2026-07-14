#!/usr/bin/env python3
"""Generate the deterministic hash manifest consumed by ``acgm doctor``.

The generator deliberately excludes its output file, Git metadata, build output,
bytecode, and known local-only material. It can operate on either a working tree
or an extracted ``git archive`` without third-party dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Iterable


DEFAULT_NAME = "PACKAGE_MANIFEST.json"
EXCLUDED_NAMES = {
    ".DS_Store",
    "BUILD_BRIEF.md",
    "PUBLISHING.md",
    DEFAULT_NAME,
}
EXCLUDED_PARTS = {".git", ".claude", "__pycache__", "dist"}


def is_included(path: Path, root: Path, output: Path | None = None) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    if output is not None:
        try:
            if path.resolve() == output.resolve():
                return False
        except OSError:
            pass
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if relative.name in EXCLUDED_NAMES or relative.suffix == ".pyc":
        return False
    return path.is_file()


def git_files(root: Path) -> list[Path] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    names = [name for name in result.stdout.decode("utf-8", "surrogateescape").split("\0") if name]
    return [root / name for name in names]


def filesystem_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file()]


def discover_files(root: Path, source: str, output: Path | None = None) -> list[Path]:
    root = root.resolve()
    output = output.resolve() if output is not None else None
    candidates: Iterable[Path]
    if source == "git":
        candidates = git_files(root) or []
    elif source == "filesystem":
        candidates = filesystem_files(root)
    else:
        candidates = git_files(root) or filesystem_files(root)
    return sorted(
        {path.resolve() for path in candidates if is_included(path, root, output)},
        key=lambda item: item.relative_to(root).as_posix(),
    )


def build_manifest(root: Path, source: str = "auto", output: Path | None = None) -> dict[str, object]:
    root = root.resolve()
    output = output.resolve() if output is not None else None
    version_path = root / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else "unknown"
    files = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in discover_files(root, source, output)
    }
    return {"schema_version": 1, "version": version, "files": files}


def serialize(manifest: dict[str, object]) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate ACGM PACKAGE_MANIFEST.json")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source", choices=("auto", "git", "filesystem"), default="auto")
    parser.add_argument("--stdout", action="store_true", help="print instead of writing a file")
    parser.add_argument("--check", action="store_true", help="fail if the existing output differs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    output = (args.output or (root / DEFAULT_NAME)).expanduser()
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    content = serialize(build_manifest(root, args.source, output))
    if args.stdout:
        sys.stdout.write(content)
        return 0
    if args.check:
        try:
            current = output.read_text(encoding="utf-8")
        except OSError:
            print(f"missing package manifest: {output}", file=sys.stderr)
            return 1
        if current != content:
            print(f"stale package manifest: {output}", file=sys.stderr)
            return 1
        print(f"package manifest is current: {output}")
        return 0
    atomic_write(output, content)
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
