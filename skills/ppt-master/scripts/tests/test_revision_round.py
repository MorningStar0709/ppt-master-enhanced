#!/usr/bin/env python3
"""Regression tests for structured revision-round gating."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from review_manager import _auto_close_active_revision_round
from revision_utils import (
    build_revision_task_template,
    create_revision_round,
    get_revision_gate_status,
    prepare_revision_verify,
    update_revision_page,
)
from review_utils import get_review_gate_status, render_review_artifacts, write_review_state


def _write_project_scaffold(project_dir: Path) -> None:
    svg_dir = project_dir / "svg_output"
    review_dir = project_dir / "review"
    svg_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
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
            "status": "approved",
            "approved_by": "tester",
            "approved_at": "2026-04-21T12:00:00",
            "user_decision": "approved",
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
    write_review_state(
        project_dir,
        state,
    )
    render_review_artifacts(project_dir, state, overwrite=True)


class RevisionRoundTests(unittest.TestCase):
    def test_scaffold_task_template_uses_selected_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _write_project_scaffold(project_dir)
            (project_dir / "svg_output" / "02_detail.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"></svg>\n',
                encoding="utf-8",
            )

            payload = build_revision_task_template(
                project_dir,
                page_files=["02_detail.svg"],
            )

            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["file"], "02_detail.svg")
            self.assertEqual(payload[0]["status"], "todo")
            self.assertEqual(payload[0]["issues"][0]["priority"], "P2")

    def test_active_revision_round_blocks_review_gate_until_pages_are_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _write_project_scaffold(project_dir)

            create_revision_round(
                project_dir,
                [
                    {
                        "file": "01_cover.svg",
                        "issues": [
                            {
                                "id": "issue-1",
                                "symptom": "title alignment drifts",
                                "priority": "P2",
                                "target": "re-center title group",
                                "allowed_changes": ["layout"],
                            }
                        ],
                    }
                ],
                created_by="tester",
                title="round 1",
            )

            revision_status = get_revision_gate_status(project_dir)
            self.assertFalse(revision_status.verify_allowed)
            self.assertTrue(any("unresolved pages" in blocker for blocker in revision_status.blockers))

            review_status = get_review_gate_status(project_dir)
            self.assertFalse(review_status.export_allowed)
            self.assertTrue(any("Active revision round" in blocker for blocker in review_status.blockers))

            update_revision_page(project_dir, page_file="01_cover.svg", status="approved", note="fixed")

            revision_status = get_revision_gate_status(project_dir)
            self.assertTrue(revision_status.verify_allowed, revision_status.blockers)

            review_status = get_review_gate_status(project_dir)
            self.assertTrue(review_status.export_allowed, review_status.blockers)

            revision_status = get_revision_gate_status(project_dir)
            self.assertTrue(revision_status.verify_allowed, revision_status.blockers)

            prepare_revision_verify(project_dir, prepared_by="tester")
            revision_status = get_revision_gate_status(project_dir)
            self.assertTrue(revision_status.verify_allowed, revision_status.blockers)

    def test_successful_verify_path_auto_closes_active_revision_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _write_project_scaffold(project_dir)

            create_revision_round(
                project_dir,
                [
                    {
                        "file": "01_cover.svg",
                        "issues": [
                            {
                                "id": "issue-1",
                                "symptom": "minor spacing issue",
                                "priority": "P2",
                                "target": "stabilize spacing",
                            }
                        ],
                    }
                ],
                created_by="tester",
                title="round 1",
            )
            update_revision_page(project_dir, page_file="01_cover.svg", status="approved")
            prepare_revision_verify(project_dir, prepared_by="tester")

            closed, round_path = _auto_close_active_revision_round(project_dir)

            self.assertTrue(closed)
            self.assertTrue(round_path.endswith("revision_round.json"))
            revision_status = get_revision_gate_status(project_dir)
            self.assertEqual(revision_status.status, "closed")
            self.assertTrue(revision_status.verify_allowed)


if __name__ == "__main__":
    unittest.main()
