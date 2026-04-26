#!/usr/bin/env python3
"""Regression tests for project_manager CLI error/report behavior."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

class ProjectManagerCliTests(unittest.TestCase):
    def test_unknown_deprecated_command_writes_generic_error_report_with_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "project_manager.py"),
                    "copy-template",
                ],
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "PPT_MASTER_REPO_ROOT": str(Path(tmp).resolve()),
                    "PPT_MASTER_COMMAND_REPORTS_DIR": str(report_dir.resolve()),
                },
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Use 'apply-template <project_path> <template_name>' instead.", result.stdout)

            error_report = report_dir / "project_manager_error_last.json"
            self.assertTrue(error_report.exists())

            payload = json.loads(error_report.read_text(encoding="utf-8"))
            self.assertEqual(payload["command"], "copy-template")
            self.assertEqual(payload["invalid_command"], "copy-template")
            self.assertIn("apply-template", payload["error"])
            self.assertTrue(payload["report_file"].endswith("project_manager_error_last.json"))

            legacy_report = report_dir / "project_manager_copy-template_last.json"
            self.assertFalse(legacy_report.exists())


if __name__ == "__main__":
    unittest.main()
