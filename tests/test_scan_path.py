from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path


def _py_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if path.is_file()]


def _import_lines(root: Path) -> list[str]:
    found: list[str] = []
    for path in _py_files(root):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                found.append(stripped)
    return found


class ScanPathOwnershipTests(unittest.TestCase):
    def test_fala_package_lists_separate_block_organs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        paths = {item["id"]: item for item in package["correlation_paths"]}
        self.assertIn("github_scan", paths)
        commands = [item["adapter"]["command"] for item in paths["github_scan"]["effectors"]]
        self.assertEqual(
            commands,
            [
                ["python3", "-m", "github_survey"],
                ["python3", "-m", "github_pack"],
                ["python3", "-m", "influenzer.brief_admit"],
            ],
        )
        self.assertEqual(paths["operator_tick"]["effectors"][0]["adapter"]["command"], ["python3", "-m", "influenzer.tick_all"])
        blob = json.dumps(package)
        self.assertNotIn("native_function", blob)
        self.assertNotIn("ads", blob.lower())

    def test_blocks_are_not_an_influenzer_scan_bag(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / "influenzer" / "github_scan.py").exists())
        self.assertFalse((root / "influenzer" / "scan").exists())
        survey_imports = _import_lines(root / "github_survey")
        pack_imports = _import_lines(root / "github_pack")
        survey_py = "\n".join(path.read_text(encoding="utf-8") for path in _py_files(root / "github_survey"))
        pack_py = "\n".join(path.read_text(encoding="utf-8") for path in _py_files(root / "github_pack"))
        admit = (root / "influenzer" / "brief_admit.py").read_text(encoding="utf-8")
        tick = (root / "influenzer" / "tick_all.py").read_text(encoding="utf-8")
        init = (root / "influenzer" / "__init__.py").read_text(encoding="utf-8")
        self.assertFalse(any("influenzer" in line for line in survey_imports))
        self.assertNotIn("StateRepository", survey_py)
        self.assertNotIn("class Brief", survey_py)
        self.assertFalse(any("influenzer" in line for line in pack_imports))
        self.assertFalse(any(line == "import subprocess" or line.startswith("from subprocess") for line in pack_imports))
        self.assertNotIn("StateRepository", pack_py)
        self.assertNotIn("github_survey", admit)
        self.assertNotIn("run_gh", admit)
        self.assertNotIn("import subprocess", admit)
        self.assertNotIn("github_survey", tick)
        self.assertNotIn("github_pack", tick)
        self.assertNotIn("github_survey", init)
        self.assertNotIn("github_pack", init)
        self.assertIn("Does not call gh", admit)
        self.assertIn("Does not survey GitHub", tick)
