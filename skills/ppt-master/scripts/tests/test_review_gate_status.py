#!/usr/bin/env python3
"""Regression tests for Step 7 technical-gate vs export-approval semantics."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from review_utils import format_gate_status, get_review_gate_status, render_review_artifacts, write_review_state


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


class ReviewGateStatusTests(unittest.TestCase):
    def test_pending_approval_keeps_export_blocked_but_verify_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="pending")

            status = get_review_gate_status(project_dir)

            self.assertFalse(status.export_allowed)
            self.assertTrue(status.verify_ready)
            self.assertTrue(status.approval_blocked)
            self.assertEqual(status.non_approval_blockers, [])
            compact = format_gate_status(status, compact=True)
            self.assertIn("Review gate: TECHNICAL PASS / APPROVAL PENDING", compact)
            self.assertIn("Blocking tasks: P0=0 P1=0", compact)
            self.assertIn("Non-blocking notes: P2=0 (ignored by export gate)", compact)

    def test_user_confirmation_summary_distinguishes_blocking_vs_non_blocking_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="pending")
            state = {
                "version": 1,
                "project": project_dir.name,
                "review_scope": "whole-deck SVG review before export",
                "review_date": "2026-04-21",
                "reviewer": "tester",
                "notes_status": "generated",
                "preview_judgement": "pass",
                "approval": {
                    "status": "pending",
                    "approved_by": "",
                    "approved_at": "",
                    "user_decision": "",
                    "notes": "",
                },
                "pages": [
                    {
                        "file": "01_cover.svg",
                        "reviewed": True,
                        "priority": "P2",
                        "note": "non-blocking note",
                    }
                ],
            }
            write_review_state(project_dir, state)
            render_review_artifacts(project_dir, state, overwrite=True)

            confirmation = (project_dir / "review" / "user_confirmation.md").read_text(encoding="utf-8")
            self.assertIn("- Blocking export issues (`P0`/`P1`): `no`", confirmation)
            self.assertIn("- Non-blocking `P2` notes present: `yes`", confirmation)
            self.assertIn("- Open `P2` count: `1`", confirmation)

    def test_approved_project_is_verify_ready_and_export_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            _seed_project(project_dir, approval_status="approved")

            status = get_review_gate_status(project_dir)

            self.assertTrue(status.export_allowed)
            self.assertTrue(status.verify_ready)
            self.assertFalse(status.approval_blocked)


if __name__ == "__main__":
    unittest.main()
