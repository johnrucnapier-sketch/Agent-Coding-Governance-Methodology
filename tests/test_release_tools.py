from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, module_name: str):
    path = REPO_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load_script("generate-package-manifest.py", "generate_package_manifest")
release_check = load_script("release_check.py", "release_check")


class PackageManifestTests(unittest.TestCase):
    def test_filesystem_manifest_is_deterministic_and_excludes_local_material(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acgm manifest 中文 ") as temporary:
            root = Path(temporary)
            (root / "VERSION").write_text("9.8.7-rc.1\n", encoding="utf-8")
            (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
            (root / "目录 with space").mkdir()
            unicode_file = root / "目录 with space" / "内容.txt"
            unicode_file.write_text("content\n", encoding="utf-8")
            (root / "BUILD_BRIEF.md").write_text("local\n", encoding="utf-8")
            (root / "dist").mkdir()
            (root / "dist" / "old.tar.gz").write_bytes(b"old")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "module.pyc").write_bytes(b"bytecode")
            output = root / "PACKAGE_MANIFEST.json"
            output.write_text("stale\n", encoding="utf-8")

            first = generator.build_manifest(root, "filesystem", output)
            second = generator.build_manifest(root, "filesystem", output)
            self.assertEqual(first, second)
            self.assertEqual(first["version"], "9.8.7-rc.1")
            files = first["files"]
            self.assertEqual(
                set(files),
                {"VERSION", "alpha.txt", "目录 with space/内容.txt"},
            )
            self.assertEqual(files["alpha.txt"], hashlib.sha256(b"alpha\n").hexdigest())
            self.assertEqual(files["目录 with space/内容.txt"], hashlib.sha256(b"content\n").hexdigest())

    def test_cli_writes_and_checks_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acgm manifest cli ") as temporary:
            root = Path(temporary)
            (root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (root / "payload.txt").write_text("payload\n", encoding="utf-8")
            output = root / "PACKAGE_MANIFEST.json"
            command = [
                "python3",
                str(REPO_ROOT / "scripts" / "generate-package-manifest.py"),
                "--root",
                str(root),
                "--source",
                "filesystem",
                "--output",
                str(output),
            ]
            subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True)
            subprocess.run([*command, "--check"], check=True, stdout=subprocess.PIPE, text=True)
            value = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(value["version"], "1.2.3")
            self.assertIn("payload.txt", value["files"])


class ReleaseContractTests(unittest.TestCase):
    def test_current_version_hook_inventory_and_modes(self) -> None:
        results = release_check.run_checks(
            REPO_ROOT,
            require_package_manifest=False,
            skip_bilingual=True,
        )
        self.assertEqual(results.errors, [])
        self.assertIn("version_and_manifests", results.passed)
        self.assertIn("hook_inventory", results.passed)
        self.assertIn("executable_modes", results.passed)
        self.assertIn("release_path_hygiene", results.passed)

    def test_bilingual_contract_checker_reports_codes_not_document_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acgm docs contract ") as temporary:
            root = Path(temporary)
            (root / "README.md").write_text(
                "Event Ledger is local-only and does not automatically upload.\n"
                "事件日志仅存本机，不自动上传。\n",
                encoding="utf-8",
            )
            (root / "METHODOLOGY.en.md").write_text("Normative layer\n", encoding="utf-8")
            (root / "METHODOLOGY.md").write_text("规范层\n", encoding="utf-8")
            results = release_check.Results()
            release_check.check_bilingual_contract(root, results)
            self.assertEqual(results.errors, [])
            self.assertIn("bilingual_contract", results.passed)

    def test_ci_targets_linux_and_macos(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("ubuntu-latest", workflow)
        self.assertIn("macos-latest", workflow)
        self.assertIn("unittest discover", workflow)
        self.assertIn("release_check.py", workflow)


if __name__ == "__main__":
    unittest.main()
