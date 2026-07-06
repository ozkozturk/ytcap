"""Package import tests."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class PackageImportTest(unittest.TestCase):
    def test_package_exports_version(self) -> None:
        ytcap = importlib.import_module("ytcap")

        self.assertEqual(ytcap.__version__, "0.1.0")

    def test_version_is_public_export(self) -> None:
        ytcap = importlib.import_module("ytcap")

        self.assertIn("__version__", ytcap.__all__)


if __name__ == "__main__":
    unittest.main()
