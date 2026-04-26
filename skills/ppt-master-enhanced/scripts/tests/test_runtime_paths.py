#!/usr/bin/env python3
"""Regression tests for portable runtime path resolution."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asset_lookup import default_report_path as asset_lookup_report_path
from project_manager import default_report_path as project_manager_report_path
from runtime_utils import format_display_path, get_command_reports_dir, resolve_repo_root, resolve_skill_dir


class RuntimePathTests(unittest.TestCase):
    def test_command_reports_dir_is_skill_local_runtime_directory(self) -> None:
        skill_dir = resolve_skill_dir(__file__)
        reports_dir = get_command_reports_dir(__file__)

        self.assertEqual(reports_dir, skill_dir / ".runtime" / "command_reports")
        self.assertEqual(
            project_manager_report_path("validate"),
            reports_dir / "project_manager_validate_last.json",
        )
        self.assertEqual(
            asset_lookup_report_path(),
            reports_dir / "asset_lookup_last.json",
        )

    def test_display_path_prefers_repo_relative_path_for_skill_runtime_files(self) -> None:
        report_path = get_command_reports_dir(__file__) / "project_manager_init_last.json"
        self.assertEqual(
            format_display_path(report_path, __file__),
            "skills/ppt-master-enhanced/.runtime/command_reports/project_manager_init_last.json",
        )

    def test_repo_root_resolution_finds_workspace_without_fixed_parent_depth(self) -> None:
        repo_root = resolve_repo_root(__file__)
        self.assertTrue((repo_root / "skills" / "ppt-master-enhanced" / "SKILL.md").exists())

    def test_command_reports_dir_honors_environment_override(self) -> None:
        override = Path.cwd() / "temp_runtime_reports_override"
        old_value = os.environ.get("PPT_MASTER_COMMAND_REPORTS_DIR")
        try:
            os.environ["PPT_MASTER_COMMAND_REPORTS_DIR"] = str(override)
            self.assertEqual(get_command_reports_dir(__file__), override.resolve())
        finally:
            if old_value is None:
                os.environ.pop("PPT_MASTER_COMMAND_REPORTS_DIR", None)
            else:
                os.environ["PPT_MASTER_COMMAND_REPORTS_DIR"] = old_value


if __name__ == "__main__":
    unittest.main()

