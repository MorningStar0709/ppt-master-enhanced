#!/usr/bin/env python3
"""Regression tests for the agent-first next-action interface."""

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

from review_utils import render_review_artifacts, write_review_state
from project_manager import ProjectManager


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


class ReviewManagerNextActionTests(unittest.TestCase):
    def _run_verify(self, project_dir: Path) -> None:
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "review_manager.py"),
                "verify",
                str(project_dir),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_next_action(self, project_dir: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "review_manager.py"),
                "next-action",
                str(project_dir),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return json.loads(result.stdout)

    def _run_approve(self, project_dir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "review_manager.py"),
                "approve",
                str(project_dir),
                "--by",
                "tester",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_next_action_requests_user_approval_after_technical_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="pending")
            self._run_verify(project_dir)

            payload = self._run_next_action(project_dir)
            self.assertEqual(payload["next_action"], "request_user_approval")
            self.assertTrue(payload["technical_passed"])
            self.assertTrue(payload["approval_pending"])
            self.assertFalse(payload["export_allowed"])
            self.assertTrue(
                any("Do not run total_md_split.py" in reason for reason in payload["reasons"])
            )
            self.assertEqual(
                payload["suggested_command"],
                f'conda run --no-capture-output -n ppt-master python scripts/review_manager.py approve "{project_dir}" --by "<approver_name>"',
            )

    def test_next_action_forces_reverify_when_review_state_is_newer_than_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="pending")
            self._run_verify(project_dir)

            report_path = project_dir / "review" / "verify_report.json"
            review_state_path = project_dir / "review" / "review_state.json"
            new_timestamp = report_path.stat().st_mtime + 5
            os.utime(review_state_path, (new_timestamp, new_timestamp))

            payload = self._run_next_action(project_dir)
            self.assertEqual(payload["next_action"], "run_verify")
            self.assertTrue(any("review/review_state.json" in reason for reason in payload["reasons"]))
            self.assertEqual(
                payload["suggested_command"],
                f'conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify "{project_dir}" --json',
            )

    def test_next_action_forces_reverify_when_svg_is_newer_than_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="pending")
            self._run_verify(project_dir)

            report_path = project_dir / "review" / "verify_report.json"
            svg_path = project_dir / "svg_output" / "01_cover.svg"
            new_timestamp = report_path.stat().st_mtime + 5
            os.utime(svg_path, (new_timestamp, new_timestamp))

            payload = self._run_next_action(project_dir)
            self.assertEqual(payload["next_action"], "run_verify")
            self.assertTrue(any("svg_output/01_cover.svg" in reason for reason in payload["reasons"]))

    def test_next_action_prioritizes_template_repair_when_manifest_exists_but_template_assets_are_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(base_dir=tmp)
            project_dir = Path(manager.init_project("demo_template_guard", "ppt169", base_dir=tmp))
            _seed_project(project_dir, approval_status="pending")
            manager.apply_template(str(project_dir), "google_style")
            (project_dir / "templates" / "design_spec.md").unlink()

            payload = self._run_next_action(project_dir)
            self.assertEqual(payload["next_action"], "apply_template")
            self.assertTrue(any("template assets" in reason for reason in payload["reasons"]))
            self.assertIn('scripts/project_manager.py apply-template', payload["suggested_command"])
            self.assertIn('google_style --force', payload["suggested_command"])

    def test_approve_refreshes_verify_report_and_allows_immediate_run_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="pending")
            self._run_verify(project_dir)

            report_path = project_dir / "review" / "verify_report.json"
            old_mtime = report_path.stat().st_mtime_ns
            result = self._run_approve(project_dir)

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertGreaterEqual(report_path.stat().st_mtime_ns, old_mtime)
            payload = self._run_next_action(project_dir)
            self.assertEqual(payload["next_action"], "run_export")
            self.assertTrue(payload["export_allowed"])


if __name__ == "__main__":
    unittest.main()
