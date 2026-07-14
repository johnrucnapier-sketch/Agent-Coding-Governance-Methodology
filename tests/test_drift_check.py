from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "drift-check.sh"


class DriftCheckTests(unittest.TestCase):
    def test_explicit_project_root_and_json_output_file_agree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acgm drift 中文 ") as temporary:
            base = Path(temporary)
            project = base / "project with spaces"
            project.mkdir()
            subprocess.run(
                ["git", "init", "-q", str(project)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            output = base / "report.json"

            result = subprocess.run(
                [
                    "sh",
                    str(SCRIPT),
                    "--project",
                    str(project),
                    "--json",
                    "--output",
                    str(output),
                ],
                cwd=base,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout_payload = json.loads(result.stdout)
            file_payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(stdout_payload, file_payload)
            self.assertEqual(Path(stdout_payload["project_root"]).resolve(), project.resolve())
            self.assertEqual(stdout_payload["summary"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
