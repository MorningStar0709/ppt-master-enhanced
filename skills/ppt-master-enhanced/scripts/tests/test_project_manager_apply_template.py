#!/usr/bin/env python3
"""Regression tests for applying library templates into projects."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(SCRIPT_DIR))

from project_manager import ProjectManager
from project_utils import get_project_info, validate_project_structure


class ProjectManagerApplyTemplateTests(unittest.TestCase):
    def test_apply_template_routes_svg_and_spec_to_templates_and_assets_to_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(base_dir=tmp)
            project_path = Path(manager.init_project("demo_apply_template", "ppt169", base_dir=tmp))

            result = manager.apply_template(str(project_path), "招商银行")

            self.assertTrue((project_path / "templates" / "01_cover.svg").exists())
            self.assertTrue((project_path / "templates" / "design_spec.md").exists())
            self.assertTrue((project_path / "images" / "cover_bg.png").exists())
            self.assertFalse((project_path / "templates" / "cover_bg.png").exists())
            self.assertTrue((project_path / "templates" / "template_manifest.json").exists())
            self.assertEqual(result["template_name"], "招商银行")
            self.assertGreater(len(result["templates"]), 0)
            self.assertGreater(len(result["images"]), 0)

            info = get_project_info(str(project_path))
            self.assertTrue(info["template_ready"])
            self.assertEqual(info["template_name"], "招商银行")

    def test_apply_template_requires_force_before_overwriting_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(base_dir=tmp)
            project_path = Path(manager.init_project("demo_force_template", "ppt169", base_dir=tmp))
            manager.apply_template(str(project_path), "google_style")

            with self.assertRaises(FileExistsError):
                manager.apply_template(str(project_path), "google_style")

            result = manager.apply_template(str(project_path), "google_style", force=True)
            self.assertGreater(len(result["templates"]), 0)

    def test_validate_warns_when_template_manifest_exists_but_assets_are_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(base_dir=tmp)
            project_path = Path(manager.init_project("demo_incomplete_template", "ppt169", base_dir=tmp))
            manager.apply_template(str(project_path), "google_style")

            (project_path / "templates" / "design_spec.md").unlink()

            is_valid, errors, warnings = validate_project_structure(str(project_path))
            self.assertTrue(is_valid)
            self.assertFalse(errors)
            self.assertTrue(any("apply-template" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
