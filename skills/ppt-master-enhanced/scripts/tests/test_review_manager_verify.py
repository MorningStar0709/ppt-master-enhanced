#!/usr/bin/env python3
"""Regression tests for review_manager verify command semantics."""

from __future__ import annotations

import json
import base64
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from review_utils import render_review_artifacts, write_review_state


def _seed_project(project_dir: Path, *, approval_status: str) -> None:
    svg_dir = project_dir / "svg_output"
    svg_dir.mkdir(parents=True, exist_ok=True)
    (svg_dir / "01_cover.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"></svg>\n',
        encoding="utf-8",
    )
    state = {
        "version": 1,
        "project": project_dir.name,
        "review_scope": "whole-deck SVG review before export",
        "review_date": "2026-04-21",
        "reviewer": "tester",
        "notes_status": "",
        "preview_judgement": "",
        "approval": {
            "status": approval_status,
            "approved_by": "tester" if approval_status == "approved" else "",
            "approved_at": "2026-04-21T12:00:00" if approval_status == "approved" else "",
            "user_decision": approval_status if approval_status == "approved" else "",
            "notes": "",
        },
        "pages": [
            {
                "file": "01_cover.svg",
                "reviewed": True,
                "priority": "none",
                "note": "ok",
            }
        ],
    }
    write_review_state(project_dir, state)
    render_review_artifacts(project_dir, state, overwrite=True)


class ReviewManagerVerifyTests(unittest.TestCase):
    def test_verify_returns_success_when_only_user_approval_is_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="pending")
            report_path = project_dir / "review" / "verify_test_report.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "review_manager.py"),
                    "verify",
                    str(project_dir),
                    "--json",
                    "--report-file",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["technical_passed"])
            self.assertTrue(payload["approval_pending"])
            self.assertFalse(payload["export_allowed"])

    def test_verify_fails_when_generated_image_exists_but_is_not_used_by_any_svg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="pending")
            (project_dir / "images").mkdir(parents=True, exist_ok=True)
            png_bytes = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWuoAAAAASUVORK5CYII="
            )
            (project_dir / "images" / "cover_bg.png").write_bytes(png_bytes)
            (project_dir / "design_spec.md").write_text(
                "\n".join(
                    [
                        "# Demo",
                        "",
                        "## VIII. Image Resource List",
                        "",
                        "| Filename | Dimensions | Ratio | Purpose | Type | Status | Generation Description |",
                        "| -------- | ---------- | ----- | ------- | ---- | ------ | ---------------------- |",
                        "| cover_bg.png | 1280x720 | 1.78 | Cover background | Background | Generated | abstract blue background |",
                        "",
                        "## IX. Content Outline",
                    ]
                ),
                encoding="utf-8",
            )
            report_path = project_dir / "review" / "verify_test_report.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "review_manager.py"),
                    "verify",
                    str(project_dir),
                    "--json",
                    "--report-file",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr or result.stdout)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["technical_passed"])
            self.assertIn("image_accountability", payload["failing_stages"])
            self.assertTrue(
                any("not referenced by any svg_output page" in item for item in payload["failure_details"]["image_accountability"])
            )

    def test_verify_fails_when_content_outline_slide_count_does_not_match_svg_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="pending")
            (project_dir / "design_spec.md").write_text(
                "\n".join(
                    [
                        "# Demo",
                        "",
                        "## IX. Content Outline",
                        "",
                        "### Part 1: Intro",
                        "",
                        "#### Slide 01 - Cover",
                        "",
                        "- **Layout**: Cover",
                        "",
                        "#### Slide 02 - Overview",
                        "",
                        "- **Layout**: Two-column",
                        "",
                        "## X. Speaker Notes Requirements",
                    ]
                ),
                encoding="utf-8",
            )
            report_path = project_dir / "review" / "verify_test_report.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "review_manager.py"),
                    "verify",
                    str(project_dir),
                    "--json",
                    "--report-file",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr or result.stdout)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["technical_passed"])
            self.assertIn("outline_accountability", payload["failing_stages"])
            self.assertTrue(
                any("declares 2 slides but svg_output contains 1 SVG files" in item for item in payload["failure_details"]["outline_accountability"])
            )

    def test_verify_passes_when_content_outline_matches_svg_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="pending")
            svg_dir = project_dir / "svg_output"
            (svg_dir / "02_overview.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"></svg>\n',
                encoding="utf-8",
            )
            state = json.loads((project_dir / "review" / "review_state.json").read_text(encoding="utf-8"))
            state["pages"].append(
                {
                    "file": "02_overview.svg",
                    "reviewed": True,
                    "priority": "none",
                    "note": "ok",
                }
            )
            write_review_state(project_dir, state)
            render_review_artifacts(project_dir, state, overwrite=True)
            (project_dir / "design_spec.md").write_text(
                "\n".join(
                    [
                        "# Demo",
                        "",
                        "## IX. Content Outline",
                        "",
                        "### Part 1: Intro",
                        "",
                        "#### Slide 01 - Cover",
                        "",
                        "- **Layout**: Cover",
                        "",
                        "#### Slide 02 - Overview",
                        "",
                        "- **Layout**: Two-column",
                        "",
                        "## X. Speaker Notes Requirements",
                    ]
                ),
                encoding="utf-8",
            )
            report_path = project_dir / "review" / "verify_test_report.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "review_manager.py"),
                    "verify",
                    str(project_dir),
                    "--json",
                    "--report-file",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["technical_passed"])
            self.assertNotIn("outline_accountability", payload["failing_stages"])
            self.assertEqual(payload["outline_accountability"]["summary"]["errors"], 0)


if __name__ == "__main__":
    unittest.main()
