"""Project metadata tests."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProjectMetadataTest(unittest.TestCase):
    def test_pyproject_declares_expected_metadata(self) -> None:
        metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = metadata["project"]

        self.assertEqual(project["name"], "ytcap")
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["dependencies"], ["yt-dlp>=2026.06.09"])
        self.assertEqual(project["dynamic"], ["version"])

    def test_console_script_points_to_cli_main(self) -> None:
        metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(metadata["project"]["scripts"]["ytcap"], "ytcap.cli:main")


if __name__ == "__main__":
    unittest.main()
