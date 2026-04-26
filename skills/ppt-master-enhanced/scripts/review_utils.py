#!/usr/bin/env python3
"""Shared helpers for SVG review artifacts and export gating."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import json
import re

try:
    from revision_utils import get_revision_gate_status
except ImportError:
    from pathlib import Path as _Path
    import sys as _sys

    _sys.path.insert(0, str(_Path(__file__).resolve().parent))
    from revision_utils import get_revision_gate_status  # type: ignore

TOOLS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TOOLS_DIR.parent
REVIEW_TEMPLATE_DIR = SKILL_DIR / "templates" / "review"
REVIEW_DIRNAME = "review"

REVIEW_LOG_FILENAME = "review_log.md"
FIX_TASKS_FILENAME = "fix_tasks.md"
USER_CONFIRMATION_FILENAME = "user_confirmation.md"
REVIEW_STATE_FILENAME = "review_state.json"

REVIEW_TEMPLATE_FILES = {
    REVIEW_LOG_FILENAME: "review_log_template.md",
    FIX_TASKS_FILENAME: "fix_task_template.md",
    USER_CONFIRMATION_FILENAME: "user_confirmation_template.md",
}

BLOCKING_PRIORITIES = ("P0", "P1")
PAGE_PRIORITIES = ("none", "P2", "P1", "P0")
APPROVAL_BLOCKER_PREFIX = "Review approval status is "


@dataclass
class ReviewArtifacts:
    """Resolved review artifact locations for a project."""

    project_dir: Path
    review_dir: Path
    review_log: Path
    fix_tasks: Path
    user_confirmation: Path
    review_state: Path


@dataclass
class ReviewGateStatus:
    """Summarized review gate state."""

    artifacts: ReviewArtifacts
    source: str
    approval_status: str
    approved_by: str
    approved_at: str
    open_tasks: dict[str, int]
    review_log_mentions: dict[str, int]
    missing_files: list[Path]
    expected_svg_files: list[str]
    reviewed_svg_files: list[str]
    missing_page_reviews: list[str]
    unreviewed_pages: list[str]
    duplicate_page_reviews: list[str]
    incomplete_page_reviews: dict[str, list[str]]
    review_inconsistencies: list[str]
    revision_status: str
    revision_round_id: str
    revision_allow_full_verify: bool
    revision_blockers: list[str]
    blockers: list[str]

    @property
    def export_allowed(self) -> bool:
        return not self.blockers

    @property
    def approval_blocked(self) -> bool:
        return any(blocker.startswith(APPROVAL_BLOCKER_PREFIX) for blocker in self.blockers)

    @property
    def non_approval_blockers(self) -> list[str]:
        return [
            blocker
            for blocker in self.blockers
            if not blocker.startswith(APPROVAL_BLOCKER_PREFIX)
        ]

    @property
    def verify_ready(self) -> bool:
        return not self.non_approval_blockers


def get_review_artifacts(project_dir: Path | str) -> ReviewArtifacts:
    """Return the standard review paths for a project."""
    project_path = Path(project_dir)
    review_dir = project_path / REVIEW_DIRNAME
    return ReviewArtifacts(
        project_dir=project_path,
        review_dir=review_dir,
        review_log=review_dir / REVIEW_LOG_FILENAME,
        fix_tasks=review_dir / FIX_TASKS_FILENAME,
        user_confirmation=review_dir / USER_CONFIRMATION_FILENAME,
        review_state=review_dir / REVIEW_STATE_FILENAME,
    )


def init_review_artifacts(project_dir: Path | str, overwrite: bool = False) -> ReviewArtifacts:
    """Create review directory, seed JSON state, and render Markdown reports."""
    artifacts = get_review_artifacts(project_dir)
    artifacts.review_dir.mkdir(parents=True, exist_ok=True)

    if overwrite or not artifacts.review_state.exists():
        if not overwrite:
            legacy_state = _build_state_from_markdown(artifacts)
            state = legacy_state if legacy_state["pages"] else _default_review_state(artifacts.project_dir)
        else:
            state = _default_review_state(artifacts.project_dir)
        write_review_state(artifacts.project_dir, state)

    state = load_review_state(artifacts.project_dir)
    render_review_artifacts(artifacts.project_dir, state, overwrite=overwrite)
    return artifacts


def load_review_state(project_dir: Path | str) -> dict:
    """Load review_state.json or return the default shape when missing."""
    artifacts = get_review_artifacts(project_dir)
    if not artifacts.review_state.exists():
        return _default_review_state(artifacts.project_dir)

    try:
        state = json.loads(artifacts.review_state.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        state = _default_review_state(artifacts.project_dir)

    return _normalize_state(state, artifacts.project_dir)


def write_review_state(project_dir: Path | str, state: dict) -> ReviewArtifacts:
    """Persist review_state.json in a normalized form."""
    artifacts = get_review_artifacts(project_dir)
    artifacts.review_dir.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_state(state, artifacts.project_dir)
    artifacts.review_state.write_text(
        json.dumps(normalized, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return artifacts


def sync_review_state(project_dir: Path | str) -> ReviewArtifacts:
    """Rebuild review_state.json from legacy Markdown artifacts."""
    artifacts = get_review_artifacts(project_dir)
    artifacts.review_dir.mkdir(parents=True, exist_ok=True)
    state = _build_state_from_markdown(artifacts)
    write_review_state(project_dir, state)
    render_review_artifacts(project_dir, state, overwrite=True)
    return artifacts


def render_review_artifacts(project_dir: Path | str, state: dict | None = None, overwrite: bool = True) -> ReviewArtifacts:
    """Render human-readable Markdown artifacts from review_state.json."""
    artifacts = get_review_artifacts(project_dir)
    artifacts.review_dir.mkdir(parents=True, exist_ok=True)
    state = _normalize_state(state or load_review_state(project_dir), artifacts.project_dir)

    files_to_render = {
        artifacts.review_log: _render_review_log(state),
        artifacts.fix_tasks: _render_fix_tasks(state),
        artifacts.user_confirmation: _render_user_confirmation(state),
    }
    for path, content in files_to_render.items():
        if path.exists() and not overwrite:
            continue
        path.write_text(content, encoding="utf-8")

    return artifacts


def get_review_gate_status(project_dir: Path | str) -> ReviewGateStatus:
    """Summarize whether a project is ready for post-processing / export."""
    artifacts = get_review_artifacts(project_dir)
    expected_svg_files = _list_expected_svg_files(artifacts.project_dir)

    if artifacts.review_state.exists():
        source = "review_state.json"
        state = load_review_state(artifacts.project_dir)
        open_tasks = _count_open_tasks_from_state(state)
        page_reviews, duplicate_page_reviews = _pages_from_state(state)
        reviewed_svg_files = sorted(
            page for page, details in page_reviews.items()
            if str(details.get("reviewed", "")).strip().lower() == "yes"
        )
        unreviewed_pages = sorted(
            page for page, details in page_reviews.items()
            if str(details.get("reviewed", "")).strip().lower() != "yes"
        )
        review_log_mentions = _count_page_review_priorities(page_reviews)
        incomplete_page_reviews = {
            page: details["missing_fields"]
            for page, details in page_reviews.items()
            if details["missing_fields"]
        }
        review_inconsistencies = _collect_page_review_inconsistencies(page_reviews)
        approval = state.get("approval", {})
        approval_status = str(approval.get("status", "missing")).strip().lower() or "missing"
        approved_by = str(approval.get("approved_by", "")).strip()
        approved_at = str(approval.get("approved_at", "")).strip()
        missing_files = [
            path for path in (
                artifacts.review_state,
                artifacts.review_log,
                artifacts.fix_tasks,
                artifacts.user_confirmation,
            )
            if not path.exists()
        ]
    else:
        source = "markdown-fallback"
        missing_files = [
            path for path in (
                artifacts.review_log,
                artifacts.fix_tasks,
                artifacts.user_confirmation,
            )
            if not path.exists()
        ]
        approval_status = "missing"
        approved_by = ""
        approved_at = ""
        open_tasks = {"P0": 0, "P1": 0, "P2": 0}
        review_log_mentions = {"P0": 0, "P1": 0, "P2": 0}
        reviewed_svg_files = []
        unreviewed_pages = []
        duplicate_page_reviews = []
        incomplete_page_reviews = {}
        review_inconsistencies = []

        if artifacts.fix_tasks.exists():
            open_tasks = _parse_open_fix_tasks(artifacts.fix_tasks.read_text(encoding="utf-8", errors="replace"))
        if artifacts.review_log.exists():
            review_log_content = artifacts.review_log.read_text(encoding="utf-8", errors="replace")
            page_reviews, duplicate_page_reviews = _parse_page_reviews(review_log_content)
            reviewed_svg_files = sorted(page_reviews.keys())
            review_log_mentions = _count_page_review_priorities(page_reviews)
            incomplete_page_reviews = {
                page: details["missing_fields"]
                for page, details in page_reviews.items()
                if details["missing_fields"]
            }
            review_inconsistencies.extend(_collect_page_review_inconsistencies(page_reviews))
            review_summary = _parse_review_summary(review_log_content)
            review_inconsistencies.extend(_compare_review_summary(page_reviews, review_summary))
        else:
            page_reviews = {}
        if artifacts.user_confirmation.exists():
            confirmation_content = artifacts.user_confirmation.read_text(encoding="utf-8", errors="replace")
            approval_status, approved_by, approved_at = _parse_confirmation_status(confirmation_content)
            confirmation_summary = _parse_confirmation_summary(confirmation_content)
            review_inconsistencies.extend(_compare_confirmation_summary(review_log_mentions, confirmation_summary))

    known_page_reviews = page_reviews.keys() if 'page_reviews' in locals() else []
    missing_page_reviews = [
        page for page in expected_svg_files
        if page not in known_page_reviews
    ]

    blockers: list[str] = []
    if missing_files:
        blockers.append(
            "Missing review artifacts: " + ", ".join(path.name for path in missing_files)
        )
    if expected_svg_files and missing_page_reviews:
        blockers.append(
            "Missing per-page review records for: " + ", ".join(missing_page_reviews)
        )
    if unreviewed_pages:
        blockers.append(
            "Unreviewed SVG pages: " + ", ".join(unreviewed_pages)
        )
    if duplicate_page_reviews:
        blockers.append(
            "Duplicate review records found for: " + ", ".join(duplicate_page_reviews)
        )
    for page, fields in incomplete_page_reviews.items():
        blockers.append(
            f"Incomplete review record for {page}: missing {', '.join(fields)}"
        )
    blockers.extend(review_inconsistencies)
    for priority in BLOCKING_PRIORITIES:
        if open_tasks.get(priority, 0) > 0:
            blockers.append(f"Open {priority} fix tasks: {open_tasks[priority]}")
    if approval_status != "approved":
        blockers.append(f"{APPROVAL_BLOCKER_PREFIX}'{approval_status}'")

    revision_status = get_revision_gate_status(artifacts.project_dir)
    blockers.extend(revision_status.blockers)

    return ReviewGateStatus(
        artifacts=artifacts,
        source=source,
        approval_status=approval_status,
        approved_by=approved_by,
        approved_at=approved_at,
        open_tasks=open_tasks,
        review_log_mentions=review_log_mentions,
        missing_files=missing_files,
        expected_svg_files=expected_svg_files,
        reviewed_svg_files=reviewed_svg_files,
        missing_page_reviews=missing_page_reviews,
        unreviewed_pages=unreviewed_pages,
        duplicate_page_reviews=duplicate_page_reviews,
        incomplete_page_reviews=incomplete_page_reviews,
        review_inconsistencies=review_inconsistencies,
        revision_status=revision_status.status,
        revision_round_id=revision_status.round_id,
        revision_allow_full_verify=revision_status.allow_full_verify,
        revision_blockers=revision_status.blockers,
        blockers=blockers,
    )


def mark_review_approved(
    project_dir: Path | str,
    approved_by: str,
    note: str | None = None,
) -> ReviewArtifacts:
    """Mark the review state as approved and re-render Markdown reports."""
    artifacts = init_review_artifacts(project_dir, overwrite=False)
    state = load_review_state(project_dir)
    approved_at = datetime.now().isoformat(timespec="seconds")

    state["approval"]["status"] = "approved"
    state["approval"]["approved_by"] = approved_by
    state["approval"]["approved_at"] = approved_at
    state["approval"]["user_decision"] = "approved"
    if note:
        state["approval"]["notes"] = note

    write_review_state(project_dir, state)
    render_review_artifacts(project_dir, state, overwrite=True)
    return artifacts


def update_page_review(
    project_dir: Path | str,
    page_file: str,
    priority: str,
    reviewed: bool = True,
    note: str | None = None,
    reviewer: str | None = None,
) -> ReviewArtifacts:
    """Update one page in the minimal review state and re-render reports."""
    artifacts = init_review_artifacts(project_dir, overwrite=False)
    state = load_review_state(project_dir)
    page_name = _normalize_review_page_name(page_file)
    if not page_name:
        raise ValueError(f"Invalid page file: {page_file}")

    matched = False
    for page in state["pages"]:
        if page["file"] != page_name:
            continue
        page["reviewed"] = reviewed
        page["priority"] = _normalize_priority_value(priority, reviewed=reviewed)
        if note is not None:
            page["note"] = note.strip()
        matched = True
        break

    if not matched:
        state["pages"].append({
            "file": page_name,
            "reviewed": reviewed,
            "priority": _normalize_priority_value(priority, reviewed=reviewed),
            "note": note.strip() if note else "",
        })

    if reviewer:
        state["reviewer"] = reviewer.strip()
    if reviewed and not state.get("review_date"):
        state["review_date"] = datetime.now().date().isoformat()

    write_review_state(project_dir, state)
    render_review_artifacts(project_dir, state, overwrite=True)
    return artifacts


def bulk_update_page_reviews(
    project_dir: Path | str,
    entries: list[dict],
    reviewer: str | None = None,
) -> ReviewArtifacts:
    """Update multiple page review records in one normalized write."""
    artifacts = init_review_artifacts(project_dir, overwrite=False)
    state = load_review_state(project_dir)

    page_index = {
        page["file"]: page
        for page in state["pages"]
        if page.get("file")
    }
    reviewed_any = False

    for entry in entries:
        page_name = _normalize_review_page_name(str(entry.get("file", "")))
        if not page_name:
            raise ValueError(f"Invalid page file: {entry.get('file')}")

        reviewed_value = entry.get("reviewed", True)
        if isinstance(reviewed_value, str):
            reviewed = reviewed_value.strip().lower() == "yes"
        else:
            reviewed = bool(reviewed_value)

        priority = str(entry.get("priority", "none"))
        note_value = entry.get("note")

        page = page_index.get(page_name)
        if page is None:
            page = {
                "file": page_name,
                "reviewed": reviewed,
                "priority": _normalize_priority_value(priority, reviewed=reviewed),
                "note": note_value.strip() if isinstance(note_value, str) else "",
            }
            state["pages"].append(page)
            page_index[page_name] = page
        else:
            page["reviewed"] = reviewed
            page["priority"] = _normalize_priority_value(priority, reviewed=reviewed)
            if note_value is not None:
                page["note"] = note_value.strip() if isinstance(note_value, str) else str(note_value)

        entry_reviewer = entry.get("reviewer")
        if isinstance(entry_reviewer, str) and entry_reviewer.strip():
            state["reviewer"] = entry_reviewer.strip()

        if reviewed:
            reviewed_any = True

    if reviewer:
        state["reviewer"] = reviewer.strip()
    if reviewed_any and not state.get("review_date"):
        state["review_date"] = datetime.now().date().isoformat()

    write_review_state(project_dir, state)
    render_review_artifacts(project_dir, state, overwrite=True)
    return artifacts


def format_gate_status(status: ReviewGateStatus, compact: bool = False) -> str:
    """Render a readable CLI summary of the current review state."""
    if compact:
        if status.export_allowed:
            headline = "Review gate: PASS"
        elif status.verify_ready and status.approval_blocked:
            headline = "Review gate: TECHNICAL PASS / APPROVAL PENDING"
        else:
            headline = "Review gate: BLOCKED"
        lines = [
            headline,
            f"Source: {status.source}",
            f"Approval: {status.approval_status}",
            f"Verify ready: {'yes' if status.verify_ready else 'no'}",
            f"Revision: {status.revision_status} ({'unlocked' if status.revision_allow_full_verify else 'locked'})",
            f"Pages: {len(status.reviewed_svg_files)}/{len(status.expected_svg_files)} reviewed",
            f"Blocking tasks: P0={status.open_tasks['P0']} P1={status.open_tasks['P1']}",
            f"Non-blocking notes: P2={status.open_tasks['P2']} (ignored by export gate)",
        ]
        if status.verify_ready and status.approval_blocked:
            lines.append("Next: record user approval before Step 8 export.")
        if status.blockers:
            lines.append("Top blockers:")
            lines.extend(f"  - {blocker}" for blocker in status.blockers[:5])
            if len(status.blockers) > 5:
                lines.append(f"  - ... and {len(status.blockers) - 5} more")
        return "\n".join(lines)

    lines = [
        f"Project: {status.artifacts.project_dir}",
        f"Review dir: {status.artifacts.review_dir}",
        f"Review source: {status.source}",
        f"Approval status: {status.approval_status}",
        f"Approved by: {status.approved_by or '-'}",
        f"Approved at: {status.approved_at or '-'}",
        f"Verify ready: {'yes' if status.verify_ready else 'no'}",
        f"Revision round status: {status.revision_status}",
        f"Revision round id: {status.revision_round_id or '-'}",
        f"Whole-deck verify unlocked: {'yes' if status.revision_allow_full_verify else 'no'}",
        "",
        "Open fix tasks:",
        f"  P0: {status.open_tasks['P0']}",
        f"  P1: {status.open_tasks['P1']}",
        f"  P2: {status.open_tasks['P2']}",
        "",
        "Page priorities:",
        f"  P0: {status.review_log_mentions['P0']}",
        f"  P1: {status.review_log_mentions['P1']}",
        f"  P2: {status.review_log_mentions['P2']}",
        "",
        f"Expected SVG pages: {len(status.expected_svg_files)}",
        f"Reviewed SVG pages: {len(status.reviewed_svg_files)}",
    ]

    if status.missing_files:
        lines.extend([
            "",
            "Missing files:",
            *[f"  - {path.name}" for path in status.missing_files],
        ])

    if status.missing_page_reviews:
        lines.extend([
            "",
            "Missing page reviews:",
            *[f"  - {page}" for page in status.missing_page_reviews],
        ])

    if status.unreviewed_pages:
        lines.extend([
            "",
            "Unreviewed pages:",
            *[f"  - {page}" for page in status.unreviewed_pages],
        ])

    if status.duplicate_page_reviews:
        lines.extend([
            "",
            "Duplicate page reviews:",
            *[f"  - {page}" for page in status.duplicate_page_reviews],
        ])

    if status.incomplete_page_reviews:
        lines.extend(["", "Incomplete page reviews:"])
        for page, fields in status.incomplete_page_reviews.items():
            lines.append(f"  - {page}: missing {', '.join(fields)}")

    if status.revision_blockers:
        lines.extend([
            "",
            "Revision round blockers:",
            *[f"  - {blocker}" for blocker in status.revision_blockers],
        ])

    lines.extend([
        "",
        f"Export allowed: {'yes' if status.export_allowed else 'no'}",
    ])

    if status.blockers:
        lines.extend([
            "Blockers:",
            *[f"  - {blocker}" for blocker in status.blockers],
        ])

    return "\n".join(lines)


def gate_status_to_dict(status: ReviewGateStatus) -> dict:
    """Serialize gate status for JSON output."""
    data = asdict(status)
    data["export_allowed"] = status.export_allowed
    data["verify_ready"] = status.verify_ready
    data["approval_blocked"] = status.approval_blocked
    data["non_approval_blockers"] = status.non_approval_blockers
    data["artifacts"] = {
        "project_dir": str(status.artifacts.project_dir),
        "review_dir": str(status.artifacts.review_dir),
        "review_log": str(status.artifacts.review_log),
        "fix_tasks": str(status.artifacts.fix_tasks),
        "user_confirmation": str(status.artifacts.user_confirmation),
        "review_state": str(status.artifacts.review_state),
    }
    data["missing_files"] = [str(path) for path in status.missing_files]
    return data


def _default_review_state(project_dir: Path) -> dict:
    """Return the normalized empty review state."""
    return {
        "version": 1,
        "project": project_dir.name,
        "review_scope": "whole-deck SVG review before export",
        "review_date": "",
        "reviewer": "",
        "notes_status": "",
        "preview_judgement": "",
        "approval": {
            "status": "pending",
            "approved_by": "",
            "approved_at": "",
            "user_decision": "",
            "notes": "",
        },
        "pages": [],
    }


def _normalize_state(state: dict, project_dir: Path) -> dict:
    """Normalize potentially partial state dictionaries."""
    base = _default_review_state(project_dir)
    legacy = _extract_legacy_state(state)
    merged = {
        **base,
        **legacy,
        **(state or {}),
    }
    normalized = {
        key: merged.get(key, base[key])
        for key in base
    }
    normalized["project"] = project_dir.name

    approval = {
        **base["approval"],
        **dict(legacy.get("approval", {})),
        **dict(merged.get("approval", {})),
    }
    normalized["approval"] = approval

    pages = []
    page_source = merged.get("pages") or legacy.get("pages", [])
    for page in page_source:
        file_name = _normalize_review_page_name(str(page.get("file") or page.get("page_name") or ""))
        if not file_name:
            continue
        pages.append({
            "file": file_name,
            "reviewed": _coerce_reviewed(page),
            "priority": _normalize_priority_value(page.get("priority"), reviewed=_coerce_reviewed(page)),
            "note": _build_page_note(page),
        })
    normalized["pages"] = pages
    return _sync_state_pages_with_expected_files(normalized, project_dir)


def _extract_legacy_state(state: dict | None) -> dict:
    """Map older review_state.json layouts into the current minimal schema."""
    if not isinstance(state, dict):
        return {}

    legacy_pages_raw = state.get("review_state")
    summary = state.get("summary")
    if not isinstance(legacy_pages_raw, dict) and not isinstance(summary, dict):
        return {}

    legacy: dict[str, object] = {}
    summary_dict = summary if isinstance(summary, dict) else {}
    zero_issue_summary = all(
        str(summary_dict.get(key, "")).strip() in {"", "0", "0.0", "false", "False"}
        for key in ("p0_issues", "p1_issues", "p2_issues")
    )

    if isinstance(legacy_pages_raw, dict):
        legacy_pages: list[dict[str, object]] = []
        for page_name, details in sorted(legacy_pages_raw.items()):
            if not isinstance(details, dict):
                continue
            reviewed = _coerce_reviewed(details)
            priority_value = "none" if reviewed and zero_issue_summary else details.get("priority", "none")
            legacy_pages.append({
                "file": page_name,
                "reviewed": reviewed,
                "priority": priority_value,
                "note": _build_page_note(details),
            })
        legacy["pages"] = legacy_pages

    if isinstance(summary_dict, dict):
        approval_status = str(summary_dict.get("approval_status", "")).strip().lower()
        if approval_status:
            legacy["approval"] = {
                "status": approval_status,
            }

    return legacy


def _build_state_from_markdown(artifacts: ReviewArtifacts) -> dict:
    """Build JSON review state from legacy Markdown artifacts."""
    state = _default_review_state(artifacts.project_dir)

    if artifacts.review_log.exists():
        review_log_content = artifacts.review_log.read_text(encoding="utf-8", errors="replace")
        state["reviewer"] = _match_line_value(review_log_content, "Reviewer")
        state["review_date"] = _match_line_value(review_log_content, "Review date")
        page_reviews, _ = _parse_page_reviews(review_log_content)
        for page_name, details in sorted(page_reviews.items()):
            state["pages"].append({
                "file": page_name,
                "priority": str(details.get("priority", "")).strip(),
                "reviewed": True,
                "note": _build_legacy_note_from_details(details),
            })

    if artifacts.user_confirmation.exists():
        confirmation_content = artifacts.user_confirmation.read_text(encoding="utf-8", errors="replace")
        approval_status, approved_by, approved_at = _parse_confirmation_status(confirmation_content)
        state["approval"]["status"] = approval_status
        state["approval"]["approved_by"] = approved_by
        state["approval"]["approved_at"] = approved_at
        state["approval"]["user_decision"] = _match_line_value(confirmation_content, "User decision")
        state["approval"]["notes"] = _match_line_value(confirmation_content, "Notes")
        state["notes_status"] = _match_line_value(confirmation_content, "Notes status")
        state["preview_judgement"] = _match_line_value(confirmation_content, "Preview judgement")

    return _normalize_state(state, artifacts.project_dir)


def _render_review_log(state: dict) -> str:
    """Render review_log.md from JSON state."""
    pages_by_priority = _pages_by_priority(state["pages"])
    highest_priority = _highest_priority_from_pages(state["pages"])
    export_recommendation = _export_recommendation_from_state(state)
    reviewed_count = sum(1 for page in state["pages"] if page.get("reviewed"))

    lines = [
        "# SVG Review Log",
        "",
        "## Basic Information",
        "",
        f"- Project: {state['project']}",
        "- Review stage: `whole-deck review`",
        f"- Review date: {state.get('review_date', '')}",
        f"- Reviewer: {state.get('reviewer', '')}",
        f"- Scope: {state.get('review_scope', '')}",
        "",
        "## Deck Summary",
        "",
        f"- Reviewed pages: `{reviewed_count}/{len(state['pages'])}`",
        f"- Highest priority found: `{highest_priority or 'none'}`",
        f"- Pages with `P0`: {_format_page_list(pages_by_priority['P0'])}",
        f"- Pages with `P1`: {_format_page_list(pages_by_priority['P1'])}",
        f"- Pages with `P2`: {_format_page_list(pages_by_priority['P2'])}",
        f"- Export recommendation: `{export_recommendation}`",
        "",
        "---",
    ]

    for page in sorted(state["pages"], key=lambda item: item["file"]):
        lines.extend([
            "",
            f"## Page: `{page['file']}`",
            "",
            f"- File: `{page['file']}`",
            f"- Reviewed: `{'yes' if page.get('reviewed') else 'no'}`",
            f"- Priority: `{page['priority']}`",
            f"- Export block: `{'yes' if _page_blocks_export(page) else 'no'}`",
            f"- Note: {page['note']}" if page.get("note") else "- Note:",
        ])

    lines.extend([
        "",
        "## Whole-deck Review Conclusion",
        "",
        f"- Export recommendation: `{export_recommendation}`",
        "",
    ])
    return "\n".join(lines)


def _render_fix_tasks(state: dict) -> str:
    """Render fix_tasks.md from JSON state."""
    overview = _count_open_tasks_from_state(state)
    actionable_pages = _build_actionable_pages(state)
    lines = [
        "# SVG Fix Tasks",
        "",
        "## Round Summary",
        "",
        f"- Project: {state['project']}",
        "- Review source: `review_state.json`",
        "- Target version: `svg_output`",
        f"- Owner: {state.get('reviewer', '')}",
        f"- Date: {state.get('review_date', '')}",
        "",
        "## Priority Overview",
        "",
        f"- `P0` pages: {overview['P0']}",
        f"- `P1` pages: {overview['P1']}",
        f"- `P2` pages: {overview['P2']}",
        "",
        "## Execution Order",
        "",
        "1. Close all `P0` tasks",
        "2. Close unresolved `P1` tasks",
        "3. Re-check retained `P2` items before export",
        "",
        "---",
    ]

    for task in actionable_pages:
        lines.extend([
            "",
            f"## Task: `{task['file']}`",
            "",
            f"- File: `{task['file']}`",
            f"- Reviewed: `{'yes' if task['reviewed'] else 'no'}`",
            f"- Priority: `{task['priority']}`",
            f"- Export block: `{'yes' if task['export_block'] else 'no'}`",
            f"- Action: {task['action']}",
            f"- Note: {task['note']}" if task["note"] else "- Note:",
        ])

    lines.append("")
    return "\n".join(lines)


def _render_user_confirmation(state: dict) -> str:
    """Render user_confirmation.md from JSON state."""
    approval = state["approval"]
    open_tasks = _count_open_tasks_from_state(state)
    has_non_blocking_p2 = open_tasks["P2"] > 0
    blocking_export_issues = "yes" if open_tasks["P0"] or open_tasks["P1"] else "no"
    export_recommendation = _export_recommendation_from_state(state)
    approved = approval["status"] == "approved"
    lines = [
        "# SVG Export Approval",
        "",
        "## Basic Information",
        "",
        f"- Project: {state['project']}",
        f"- Review scope: {state.get('review_scope', '')}",
        f"- Review date: {state.get('review_date', '')}",
        f"- Reviewer: {state.get('reviewer', '')}",
        f"- Approval status: `{approval['status']}`",
        f"- Approved by: {approval['approved_by']}",
        f"- Approved at: {approval['approved_at']}",
        "",
        "## Review Summary",
        "",
        f"- Blocking export issues (`P0`/`P1`): `{blocking_export_issues}`",
        f"- Open `P0` count: `{open_tasks['P0']}`",
        f"- Open `P1` count: `{open_tasks['P1']}`",
        f"- Non-blocking `P2` notes present: `{'yes' if has_non_blocking_p2 else 'no'}`",
        f"- Open `P2` count: `{open_tasks['P2']}`",
        f"- Export recommendation: `{export_recommendation}`",
        "",
        "## Evidence",
        "",
        "- Review log: `review/review_log.md`",
        "- Fix tasks: `review/fix_tasks.md`",
        f"- Reviewed pages: {sum(1 for page in state['pages'] if page.get('reviewed'))}/{len(state['pages'])}",
        f"- Notes status: {state.get('notes_status', '')}",
        f"- Preview judgement: {state.get('preview_judgement', '')}",
        "",
        "## User Confirmation",
        "",
        f"- [{'x' if approved else ' '}] I confirm the reviewed SVG set is acceptable for post-processing",
        f"- [{'x' if approved else ' '}] I allow `total_md_split.py` to run",
        f"- [{'x' if approved else ' '}] I allow `finalize_svg.py` to run",
        f"- [{'x' if approved else ' '}] I allow `svg_to_pptx.py` to run",
        f"- [{'x' if approved else ' '}] I understand future issues should be tracked from this confirmed review version",
        "",
        "## Final Decision",
        "",
        f"- User decision: {approval.get('user_decision', '')}",
        f"- Notes: {approval.get('notes', '')}",
        "",
    ]
    return "\n".join(lines)


def _pages_from_state(state: dict) -> tuple[dict[str, dict[str, str | list[str]]], list[str]]:
    """Convert page list from JSON state into record mapping."""
    page_reviews: dict[str, dict[str, str | list[str]]] = {}
    duplicates: list[str] = []
    for page in state.get("pages", []):
        page_name = _normalize_review_page_name(page.get("file", ""))
        if not page_name:
            continue
        if page_name in page_reviews:
            duplicates.append(page_name)
        record = {
            "page_name": page_name,
            "file": page_name,
            "reviewed": "yes" if page.get("reviewed") else "no",
            "priority": page.get("priority", "none"),
            "note": page.get("note", ""),
            "missing_fields": [],
        }
        if page.get("reviewed") and _normalize_priority_value(page.get("priority"), reviewed=True) == "":
            record["missing_fields"] = ["Priority"]
        page_reviews[page_name] = record
    return page_reviews, sorted(set(duplicates))


def _count_open_tasks_from_state(state: dict) -> dict[str, int]:
    """Count actionable pages by priority from JSON state."""
    counts = {"P0": 0, "P1": 0, "P2": 0}
    for page in state.get("pages", []):
        if not page.get("reviewed"):
            continue
        priority = str(page.get("priority", "")).strip()
        if priority in counts and priority != "none":
            counts[priority] += 1
    return counts


def _sync_state_pages_with_expected_files(state: dict, project_dir: Path) -> dict:
    """Ensure state.pages is aligned with the current svg_output directory."""
    expected = _list_expected_svg_files(project_dir)
    existing = {
        _normalize_review_page_name(str(page.get("file", ""))): page
        for page in state.get("pages", [])
        if _normalize_review_page_name(str(page.get("file", "")))
    }
    synced_pages: list[dict] = []
    for file_name in expected:
        page = dict(existing.pop(file_name, {}))
        synced_pages.append({
            "file": file_name,
            "reviewed": bool(page.get("reviewed", False)),
            "priority": _normalize_priority_value(page.get("priority"), reviewed=bool(page.get("reviewed", False))),
            "note": str(page.get("note", "")).strip(),
        })
    for file_name in sorted(existing):
        page = existing[file_name]
        synced_pages.append({
            "file": file_name,
            "reviewed": bool(page.get("reviewed", False)),
            "priority": _normalize_priority_value(page.get("priority"), reviewed=bool(page.get("reviewed", False))),
            "note": str(page.get("note", "")).strip(),
        })
    state["pages"] = synced_pages
    return state


def _coerce_reviewed(page: dict) -> bool:
    """Return whether a page should be treated as reviewed."""
    if "reviewed" in page:
        value = page.get("reviewed")
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"yes", "true", "1", "reviewed", "done", "pass"}:
            return True
        if text in {"no", "false", "0", "pending"}:
            return False
    return _derive_reviewed_from_legacy_page(page)


def _derive_reviewed_from_legacy_page(page: dict) -> bool:
    """Infer reviewed state from older rich page-review fields."""
    legacy_fields = (
        "priority",
        "review_conclusion",
        "can_move_to_next_page",
        "needs_export_block",
        "note",
        "symptoms",
        "findings",
        "fix_direction",
        "priority_reason",
    )
    return any(str(page.get(field, "")).strip() for field in legacy_fields)


def _normalize_priority_value(value: object, reviewed: bool) -> str:
    """Normalize priority into the minimal gate vocabulary."""
    text = str(value or "").strip()
    if text in {"", "None", "null"}:
        return "none" if reviewed else ""
    upper = text.upper()
    if upper in {"P0", "P1", "P2"}:
        return upper
    if text.lower() in {"none", "ok", "pass", "clear"}:
        return "none"
    return "none" if reviewed else ""


def _build_page_note(page: dict) -> str:
    """Build a compact note from minimal or legacy page fields."""
    for key in ("note", "findings", "fix_direction", "symptoms", "priority_reason", "review_conclusion"):
        value = str(page.get(key, "")).strip()
        if value:
            return value
    return ""


def _build_legacy_note_from_details(details: dict[str, str | list[str]]) -> str:
    """Build a compact note from parsed legacy review markdown."""
    for key in ("findings", "fix_direction", "symptoms", "priority_reason", "result"):
        value = str(details.get(key, "")).strip()
        if value:
            return value
    return ""


def _page_blocks_export(page: dict) -> bool:
    """Return whether a page blocks export under the minimal gate rules."""
    if not page.get("reviewed"):
        return True
    return str(page.get("priority", "")).strip() in {"P0", "P1"}


def _build_actionable_pages(state: dict) -> list[dict]:
    """Build a compact list of pages that still need attention."""
    items: list[dict] = []
    for page in state.get("pages", []):
        if page.get("reviewed") and str(page.get("priority", "")).strip() == "none":
            continue
        items.append({
            "file": page["file"],
            "reviewed": bool(page.get("reviewed")),
            "priority": page.get("priority", ""),
            "export_block": _page_blocks_export(page),
            "action": "Complete review first" if not page.get("reviewed") else "Revise SVG and re-check",
            "note": page.get("note", ""),
        })
    return items


def _match_line_value(content: str, label: str) -> str:
    """Extract a single-line markdown bullet value."""
    match = re.search(rf"(?m)^- {re.escape(label)}:[ \t]*(.*)$", content)
    if not match:
        return ""
    return match.group(1).strip().strip("`")


def _parse_open_fix_tasks(content: str) -> dict[str, int]:
    """Count open tasks by priority from the fix task markdown."""
    counts = {"P0": 0, "P1": 0, "P2": 0}
    for task in _parse_fix_task_blocks(content):
        priority = task["priority"]
        status = task["status"]
        if priority in counts and status not in {"done", "pass", "closed", "approved"}:
            counts[priority] += 1
    return counts


def _parse_fix_task_blocks(content: str) -> list[dict]:
    """Parse fix task blocks from fix_tasks.md."""
    tasks: list[dict] = []
    blocks = re.findall(r"(?ms)^## Task:\s*`?([^`\n]+)`?\s*\n(.*?)(?=^## Task:|\Z)", content)
    for title, block in blocks:
        actions = []
        for action_match in re.findall(r"(?m)^- Action \d+:\s*(.*)$", block):
            action_value = action_match.strip()
            if action_value:
                actions.append(action_value)
        tasks.append({
            "title": title.strip(),
            "file": _normalize_review_page_name(_match_line_value(block, "File")),
            "page_type": _match_line_value(block, "Page type"),
            "priority": _match_line_value(block, "Priority"),
            "status": _match_line_value(block, "Status").lower(),
            "symptom": _match_line_value(block, "Symptom 1"),
            "root_cause_layer": _match_line_value(block, "Layer"),
            "reason": _match_line_value(block, "Reason"),
            "expected_result": _match_line_value(block, "Should achieve"),
            "fix_actions": actions,
            "generation_source": _match_line_value(block, "Generation source"),
            "related_helper": _match_line_value(block, "Related helper / component"),
            "actual_change": _match_line_value(block, "Actual change"),
            "review_result": _match_line_value(block, "Review result"),
            "carry_to_next_round": _match_line_value(block, "Carry to next round"),
        })
    return tasks


def _count_page_review_priorities(page_reviews: dict[str, dict[str, str | list[str]]]) -> dict[str, int]:
    """Count review priorities from parsed page blocks."""
    counts = {"P0": 0, "P1": 0, "P2": 0}
    for details in page_reviews.values():
        priority = str(details.get("priority", "")).strip()
        if priority in counts:
            counts[priority] += 1
    return counts


def _parse_confirmation_status(content: str) -> tuple[str, str, str]:
    """Extract approval metadata from the confirmation markdown."""
    status_match = re.search(r"(?m)^- Approval status:[ \t]*`?([^`\n]+)`?", content)
    by_match = re.search(r"(?m)^- Approved by:[ \t]*(.*)$", content)
    at_match = re.search(r"(?m)^- Approved at:[ \t]*(.*)$", content)

    approval_status = status_match.group(1).strip().lower() if status_match else "missing"
    approved_by = by_match.group(1).strip() if by_match else ""
    approved_at = at_match.group(1).strip() if at_match else ""
    return approval_status, approved_by, approved_at


def _parse_confirmation_summary(content: str) -> dict[str, str]:
    """Extract remaining-priority flags from the user confirmation file."""
    summary = {"P0": "", "P1": "", "P2": ""}
    for priority in summary:
        match = re.search(rf"(?m)^- Remaining `{priority}`:[ \t]*`?([^`\n]+)`?", content)
        if match:
            summary[priority] = match.group(1).strip().lower()
    return summary


def _list_expected_svg_files(project_dir: Path) -> list[str]:
    """Return the expected SVG filenames in svg_output/."""
    svg_dir = project_dir / "svg_output"
    if not svg_dir.exists():
        return []
    return sorted(path.name for path in svg_dir.glob("*.svg"))


def _parse_page_reviews(content: str) -> tuple[dict[str, dict[str, str | list[str]]], list[str]]:
    """Parse page review sections from review_log.md."""
    page_reviews: dict[str, dict[str, str | list[str]]] = {}
    duplicates: list[str] = []
    pattern = re.compile(
        r"(?ms)^## Page:\s*`?([^`\n]+)`?\s*\n(.*?)(?=^## Page:|^## Whole-deck Review Conclusion|\Z)"
    )

    for match in pattern.finditer(content):
        page_heading = match.group(1).strip()
        block = match.group(2)
        file_ref = _extract_review_value(block, "File")
        page_name = _normalize_review_page_name(file_ref or page_heading)
        if not page_name:
            page_name = _normalize_review_page_name(page_heading)
        if page_name in page_reviews:
            duplicates.append(page_name)
        page_reviews[page_name] = _build_page_review_record(page_name, block)

    return page_reviews, sorted(set(duplicates))


def _build_page_review_record(page_name: str, block: str) -> dict[str, str | list[str]]:
    """Build a normalized page review record from a markdown block."""
    reviewed_value = _extract_review_value(block, "Reviewed").lower()
    minimal_priority = _extract_review_value(block, "Priority")
    minimal_note = _extract_review_value(block, "Note")
    minimal_export_block = _extract_review_value(block, "Export block").lower()
    if reviewed_value:
        record = {
            "page_name": page_name,
            "file": _extract_review_value(block, "File") or page_name,
            "reviewed": reviewed_value,
            "priority": _normalize_priority_value(minimal_priority, reviewed=reviewed_value == "yes"),
            "note": minimal_note,
            "needs_export_block": minimal_export_block,
            "missing_fields": [],
        }
        if reviewed_value == "yes" and not record["priority"]:
            record["missing_fields"] = ["Priority"]
        return record

    record = {
        "page_name": page_name,
        "file": _extract_review_value(block, "File"),
        "page_type": _extract_review_value(block, "Page type"),
        "review_stage": _extract_review_value(block, "Review stage"),
        "symptoms": _extract_review_value(block, "Symptoms"),
        "root_cause_layer": _extract_review_value(block, "Root-cause Layer"),
        "findings": _extract_review_value(block, "Findings"),
        "fix_direction": _extract_review_value(block, "Fix Direction"),
        "priority": _extract_review_value(block, "Priority"),
        "priority_reason": _extract_inline_review_value(block, "Reason"),
        "result": _extract_review_value(block, "Review Conclusion"),
        "can_move_to_next_page": _extract_inline_review_value(block, "Can move to next page"),
        "needs_export_block": _extract_inline_review_value(block, "Needs export block"),
        "missing_fields": [],
    }

    required_fields = {
        "file": "File",
        "page_type": "Page type",
        "review_stage": "Review stage",
        "symptoms": "Symptoms",
        "root_cause_layer": "Root-cause Layer",
        "findings": "Findings",
        "fix_direction": "Fix Direction",
        "priority": "Priority",
        "result": "Review Conclusion",
        "can_move_to_next_page": "Can move to next page",
        "needs_export_block": "Needs export block",
    }
    record["missing_fields"] = [
        label for key, label in required_fields.items()
        if _is_missing_review_value(str(record.get(key, "")))
    ]
    return record


def _extract_review_value(block: str, label: str) -> str:
    """Extract a bullet field from a page review block."""
    match = re.search(rf"(?m)^- {re.escape(label)}:\s*(.*)$", block)
    if not match:
        return ""
    value = match.group(1).strip()
    if ";" in value and label in {"Review Conclusion", "Priority"}:
        value = value.split(";", 1)[0].strip()
    return value.strip("`")


def _extract_inline_review_value(block: str, label: str) -> str:
    """Extract inline values appended on the same line."""
    match = re.search(rf"{re.escape(label)}:\s*`?([^`;]+)`?", block)
    if not match:
        return ""
    return match.group(1).strip().strip("`")


def _normalize_review_page_name(value: str) -> str:
    """Normalize a file/path reference to a page filename."""
    text = value.strip().strip("`").strip()
    if not text:
        return ""
    text = text.replace("\\", "/").split("/")[-1]
    if not text.lower().endswith(".svg"):
        text = f"{text}.svg"
    return text


def _is_missing_review_value(value: str) -> bool:
    """Return whether a review field is still effectively blank/templated."""
    normalized = value.strip().strip("`").lower()
    if not normalized:
        return True
    placeholders = {
        "__",
        "p0 / p1 / p2",
        "pass / revise immediately / carry to whole-deck review",
        "yes / no",
        "allow / block",
        "pending",
    }
    return normalized in placeholders


def _collect_page_review_inconsistencies(
    page_reviews: dict[str, dict[str, str | list[str]]]
) -> list[str]:
    """Return blocking inconsistencies inside page review records."""
    inconsistencies: list[str] = []
    for page, details in page_reviews.items():
        priority = str(details.get("priority", "")).strip()
        result = str(details.get("result", "")).strip().lower()
        can_move = str(details.get("can_move_to_next_page", "")).strip().lower()
        needs_export_block = str(details.get("needs_export_block", "")).strip().lower()
        symptoms = str(details.get("symptoms", "")).strip().lower()

        file_name = _normalize_review_page_name(str(details.get("file", "")))
        if file_name and file_name != page:
            inconsistencies.append(
                f"Review record file mismatch for {page}: file field points to {file_name}"
            )
        if priority == "P0" and can_move == "yes":
            inconsistencies.append(
                f"Review record inconsistency for {page}: P0 cannot move to next page"
            )
        if priority == "P0" and needs_export_block == "no":
            inconsistencies.append(
                f"Review record inconsistency for {page}: P0 cannot mark export block as no"
            )
        if priority == "P1" and needs_export_block == "no":
            inconsistencies.append(
                f"Review record inconsistency for {page}: unresolved P1 cannot mark export block as no"
            )
        if priority in {"P0", "P1"} and "pass" in result:
            inconsistencies.append(
                f"Review record inconsistency for {page}: {priority} cannot conclude pass without downgrade/closure"
            )
        if priority in {"P1", "P2"} and (
            symptoms.startswith("none")
            or symptoms in {"none", "none material", "no issue", "no issues", "none blocking"}
        ):
            inconsistencies.append(
                f"Review record inconsistency for {page}: priority {priority} conflicts with symptoms '{details.get('symptoms', '')}'"
            )
    return inconsistencies


def _parse_review_summary(content: str) -> dict[str, str | set[str]]:
    """Extract the deck summary section from review_log.md."""
    summary: dict[str, str | set[str]] = {
        "highest_priority": "",
        "P0": set(),
        "P1": set(),
        "P2": set(),
    }
    section_match = re.search(
        r"(?ms)^## Deck Summary\s*\n(.*?)(?=^---|^## Page:|^## Whole-deck Review Conclusion|\Z)",
        content,
    )
    if not section_match:
        return summary
    section = section_match.group(1)

    highest = re.search(r"(?m)^- Highest priority found:\s*`?([^`\n]+)`?", section)
    if highest:
        summary["highest_priority"] = highest.group(1).strip()

    for priority in ("P0", "P1", "P2"):
        match = re.search(rf"(?m)^- Pages with `{priority}`:\s*(.*)$", section)
        if match:
            summary[priority] = _parse_summary_page_list(match.group(1))
    return summary


def _parse_summary_page_list(raw_value: str) -> set[str]:
    """Parse a summary bullet containing none or a list of page filenames."""
    cleaned = raw_value.strip().strip("`").strip()
    if not cleaned or cleaned.lower() in {"none", "no", "n/a"}:
        return set()
    page_names = re.findall(r"`([^`]+)`", raw_value)
    if not page_names:
        page_names = [part.strip() for part in cleaned.split(",")]
    return {
        _normalize_review_page_name(page)
        for page in page_names
        if page.strip()
    }


def _compare_review_summary(
    page_reviews: dict[str, dict[str, str | list[str]]],
    summary: dict[str, str | set[str]],
) -> list[str]:
    """Compare the deck summary section with actual page review blocks."""
    inconsistencies: list[str] = []
    actual_by_priority = {"P0": set(), "P1": set(), "P2": set()}
    for page, details in page_reviews.items():
        priority = str(details.get("priority", "")).strip()
        if priority in actual_by_priority:
            actual_by_priority[priority].add(page)

    actual_highest = ""
    if actual_by_priority["P0"]:
        actual_highest = "P0"
    elif actual_by_priority["P1"]:
        actual_highest = "P1"
    elif actual_by_priority["P2"]:
        actual_highest = "P2"

    summary_highest = str(summary.get("highest_priority", "")).strip().strip("`")
    if summary_highest and summary_highest != actual_highest:
        inconsistencies.append(
            f"Review summary mismatch: highest priority says {summary_highest}, actual page records imply {actual_highest or 'none'}"
        )

    for priority in ("P0", "P1", "P2"):
        summary_pages = summary.get(priority, set())
        if isinstance(summary_pages, set) and summary_pages != actual_by_priority[priority]:
            inconsistencies.append(
                f"Review summary mismatch for {priority}: summary has {sorted(summary_pages)}, page records have {sorted(actual_by_priority[priority])}"
            )
    return inconsistencies


def _compare_confirmation_summary(
    review_log_mentions: dict[str, int],
    confirmation_summary: dict[str, str],
) -> list[str]:
    """Compare the export approval summary with actual remaining priorities."""
    inconsistencies: list[str] = []
    for priority, count in review_log_mentions.items():
        expected = "yes" if count > 0 else "no"
        actual = confirmation_summary.get(priority, "")
        if actual and actual != expected:
            inconsistencies.append(
                f"User confirmation mismatch: Remaining {priority} says '{actual}' but review log shows {count}"
            )
    return inconsistencies


def _format_page_list(page_names: list[str]) -> str:
    """Render a page list for summary bullets."""
    if not page_names:
        return "`none`"
    return ", ".join(f"`{page}`" for page in page_names)


def _pages_by_priority(pages: list[dict]) -> dict[str, list[str]]:
    """Group page names by priority."""
    grouped = {"P0": [], "P1": [], "P2": []}
    for page in pages:
        priority = page.get("priority", "")
        file_name = page.get("file", "")
        if priority in grouped and file_name:
            grouped[priority].append(file_name)
    for priority in grouped:
        grouped[priority].sort()
    return grouped


def _highest_priority_from_pages(pages: list[dict]) -> str:
    """Return the highest priority remaining in the page list."""
    priorities = _pages_by_priority(pages)
    if priorities["P0"]:
        return "P0"
    if priorities["P1"]:
        return "P1"
    if priorities["P2"]:
        return "P2"
    return ""


def _export_recommendation_from_state(state: dict) -> str:
    """Derive export recommendation from the minimal gate state."""
    for page in state.get("pages", []):
        if _page_blocks_export(page):
            return "block"
    if state.get("approval", {}).get("status") != "approved":
        return "hold"
    return "allow"


def _format_priority_line(page: dict) -> str:
    """Render priority and reason on one line."""
    priority = page.get("priority", "")
    reason = page.get("priority_reason", "")
    if priority and reason:
        return f"- Priority: `{priority}`; Reason: `{reason}`"
    if priority:
        return f"- Priority: `{priority}`"
    return "- Priority:"
