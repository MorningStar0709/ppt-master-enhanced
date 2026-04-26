#!/usr/bin/env python3
"""Helpers for structured agent-driven revision rounds before whole-deck verify."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path


REVISION_ROUND_FILENAME = "revision_round.json"
REVISION_STATUSES = ("inactive", "active", "closed")
REVISION_PAGE_STATUSES = ("todo", "in_progress", "ready_for_review", "approved")
ISSUE_PRIORITIES = ("P0", "P1", "P2", "none")
ALLOWED_CHANGE_TYPES = ("layout", "copy", "visual", "structure", "assets")


@dataclass
class RevisionGateStatus:
    """Summarized revision-round gate state."""

    exists: bool
    file_path: str
    round_id: str
    title: str
    status: str
    allow_full_verify: bool
    page_counts: dict[str, int]
    pending_pages: list[str]
    blockers: list[str]

    @property
    def verify_allowed(self) -> bool:
        return not self.blockers


def get_revision_round_path(project_dir: Path | str) -> Path:
    """Return the standard revision-round JSON path under review/."""
    project_path = Path(project_dir)
    return project_path / "review" / REVISION_ROUND_FILENAME


def load_revision_round(project_dir: Path | str) -> dict:
    """Load and normalize revision_round.json when it exists."""
    round_path = get_revision_round_path(project_dir)
    if not round_path.exists():
        return _default_revision_round(Path(project_dir), exists=False)

    try:
        payload = json.loads(round_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = _default_revision_round(Path(project_dir), exists=True)
    return _normalize_revision_round(payload, Path(project_dir), exists=True)


def write_revision_round(project_dir: Path | str, state: dict) -> Path:
    """Write revision_round.json in normalized form."""
    round_path = get_revision_round_path(project_dir)
    round_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_revision_round(state, Path(project_dir), exists=True)
    round_path.write_text(
        json.dumps(normalized, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return round_path


def create_revision_round(
    project_dir: Path | str,
    entries: list[dict],
    *,
    created_by: str = "",
    title: str = "",
    notes: str = "",
) -> Path:
    """Create a fresh active revision round from a structured page-entry list."""
    project_path = Path(project_dir)
    round_id = f"revision-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    state = _default_revision_round(project_path, exists=True)
    state.update(
        {
            "round_id": round_id,
            "title": title.strip(),
            "status": "active",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "created_by": created_by.strip(),
            "notes": notes.strip(),
            "allow_full_verify": False,
            "pages": [_normalize_revision_page(entry) for entry in entries],
        }
    )
    return write_revision_round(project_dir, state)


def build_revision_task_template(
    project_dir: Path | str,
    *,
    page_files: list[str] | None = None,
) -> list[dict]:
    """Build a machine-friendly revision task skeleton for selected SVG pages."""
    project_path = Path(project_dir)
    svg_dir = project_path / "svg_output"
    if not svg_dir.exists():
        raise ValueError(f"svg_output directory does not exist: {svg_dir}")

    existing_pages = sorted(path.name for path in svg_dir.glob("*.svg"))
    if not existing_pages:
        raise ValueError(f"No SVG files found in: {svg_dir}")

    if page_files:
        normalized_pages = [_normalize_svg_name(page) for page in page_files]
        missing = [page for page in normalized_pages if page not in existing_pages]
        if missing:
            raise ValueError(
                "Requested pages are not present in svg_output/: " + ", ".join(missing)
            )
        target_pages = normalized_pages
    else:
        target_pages = existing_pages

    template: list[dict] = []
    for page in target_pages:
        template.append(
            {
                "file": page,
                "status": "todo",
                "note": "",
                "allowed_changes": [],
                "issues": [
                    {
                        "id": "issue-1",
                        "symptom": "",
                        "target": "",
                        "priority": "P2",
                        "note": "",
                        "allowed_changes": [],
                    }
                ],
            }
        )
    return template


def update_revision_page(
    project_dir: Path | str,
    *,
    page_file: str,
    status: str,
    note: str | None = None,
) -> Path:
    """Update one page status within the active revision round."""
    state = load_revision_round(project_dir)
    if state["status"] != "active":
        raise ValueError("No active revision round to update")

    page_name = _normalize_svg_name(page_file)
    target_page = None
    for page in state["pages"]:
        if page["file"] == page_name:
            target_page = page
            break
    if target_page is None:
        raise ValueError(f"Page is not part of the current revision round: {page_name}")

    target_page["status"] = _normalize_page_status(status)
    if note is not None:
        target_page["note"] = str(note).strip()
    target_page["updated_at"] = _now_iso()

    # Keep the bookkeeping marker conservative: any page update clears the "ready" stamp.
    state["allow_full_verify"] = False
    state["updated_at"] = _now_iso()
    return write_revision_round(project_dir, state)


def prepare_revision_verify(
    project_dir: Path | str,
    *,
    prepared_by: str = "",
    note: str = "",
) -> Path:
    """Record that the current agent-side revision batch is ready for whole-deck verify."""
    state = load_revision_round(project_dir)
    if state["status"] != "active":
        raise ValueError("No active revision round to prepare for verify")

    pending_pages = [
        page["file"]
        for page in state["pages"]
        if page["status"] in {"todo", "in_progress"}
    ]
    if pending_pages:
        raise ValueError(
            "Cannot prepare whole-deck verify while pages are still unresolved: "
            + ", ".join(pending_pages)
        )

    state["allow_full_verify"] = True
    state["updated_at"] = _now_iso()
    state["prepared_for_verify_at"] = _now_iso()
    state["prepared_for_verify_by"] = prepared_by.strip()
    if note.strip():
        state["prepared_for_verify_note"] = note.strip()
    return write_revision_round(project_dir, state)


def close_revision_round(project_dir: Path | str, *, force: bool = False) -> Path:
    """Close the current revision round after its queued fixes are resolved."""
    state = load_revision_round(project_dir)
    if state["status"] != "active":
        raise ValueError("No active revision round to close")

    if not force:
        pending_pages = [
            page["file"]
            for page in state["pages"]
            if page["status"] in {"todo", "in_progress"}
        ]
        if pending_pages:
            raise ValueError(
                "Cannot close revision round while pages are still unresolved: "
                + ", ".join(pending_pages)
            )

    state["status"] = "closed"
    state["allow_full_verify"] = False
    state["closed_at"] = _now_iso()
    state["updated_at"] = _now_iso()
    return write_revision_round(project_dir, state)


def get_revision_gate_status(project_dir: Path | str) -> RevisionGateStatus:
    """Summarize whether a whole-deck verify should be allowed right now."""
    state = load_revision_round(project_dir)
    round_path = get_revision_round_path(project_dir)
    page_counts = {status: 0 for status in REVISION_PAGE_STATUSES}
    for page in state["pages"]:
        page_counts[page["status"]] += 1

    pending_pages = [
        page["file"]
        for page in state["pages"]
        if page["status"] in {"todo", "in_progress"}
    ]

    blockers: list[str] = []
    if state["status"] == "active":
        if not state["pages"]:
            blockers.append(
                "Active revision round has no page tasks. Close it or recreate it before whole-deck verify."
            )
        if pending_pages:
            blockers.append(
                "Active revision round still has unresolved pages: "
                + ", ".join(pending_pages)
            )

    return RevisionGateStatus(
        exists=round_path.exists(),
        file_path=str(round_path),
        round_id=str(state.get("round_id", "")),
        title=str(state.get("title", "")),
        status=str(state.get("status", "inactive")),
        allow_full_verify=bool(state.get("allow_full_verify", False)),
        page_counts=page_counts,
        pending_pages=pending_pages,
        blockers=blockers,
    )


def format_revision_gate_status(status: RevisionGateStatus, compact: bool = False) -> str:
    """Render a CLI summary for the current agent-side revision round."""
    if compact:
        lines = [
            f"Revision gate: {'PASS' if status.verify_allowed else 'BLOCKED'}",
            f"Round status: {status.status}",
            f"Round id: {status.round_id or '-'}",
            (
                "Pages: "
                f"todo={status.page_counts['todo']} "
                f"in_progress={status.page_counts['in_progress']} "
                f"ready_for_review={status.page_counts['ready_for_review']} "
                f"approved={status.page_counts['approved']}"
            ),
            f"Revision batch marked ready: {'yes' if status.allow_full_verify else 'no'}",
        ]
        if status.blockers:
            lines.append("Top blockers:")
            lines.extend(f"  - {blocker}" for blocker in status.blockers[:5])
        return "\n".join(lines)

    lines = [
        f"Revision round file: {status.file_path}",
        f"Exists: {'yes' if status.exists else 'no'}",
        f"Round id: {status.round_id or '-'}",
        f"Title: {status.title or '-'}",
        f"Status: {status.status}",
        f"Revision batch marked ready: {'yes' if status.allow_full_verify else 'no'}",
        "",
        "Page counts:",
        f"  todo: {status.page_counts['todo']}",
        f"  in_progress: {status.page_counts['in_progress']}",
        f"  ready_for_review: {status.page_counts['ready_for_review']}",
        f"  approved: {status.page_counts['approved']}",
        "",
        f"Whole-deck verify allowed: {'yes' if status.verify_allowed else 'no'}",
    ]
    if status.pending_pages:
        lines.extend([
            "Pending pages:",
            *[f"  - {page}" for page in status.pending_pages],
        ])
    if status.blockers:
        lines.extend([
            "Blockers:",
            *[f"  - {blocker}" for blocker in status.blockers],
        ])
    return "\n".join(lines)


def revision_gate_status_to_dict(status: RevisionGateStatus) -> dict:
    """Serialize revision gate status for JSON output."""
    data = asdict(status)
    data["verify_allowed"] = status.verify_allowed
    return data


def _default_revision_round(project_dir: Path, *, exists: bool) -> dict:
    """Return the default revision-round payload."""
    return {
        "version": 1,
        "project": project_dir.name,
        "round_id": "",
        "title": "",
        "status": "inactive" if not exists else "closed",
        "created_at": "",
        "updated_at": "",
        "created_by": "",
        "notes": "",
        "allow_full_verify": False,
        "prepared_for_verify_at": "",
        "prepared_for_verify_by": "",
        "prepared_for_verify_note": "",
        "closed_at": "",
        "pages": [],
    }


def _normalize_revision_round(payload: dict, project_dir: Path, *, exists: bool) -> dict:
    """Normalize revision-round data into a stable machine shape."""
    state = _default_revision_round(project_dir, exists=exists)
    if isinstance(payload, dict):
        state.update({k: payload.get(k, state[k]) for k in state.keys() if k != "pages"})
        state["pages"] = [_normalize_revision_page(page) for page in payload.get("pages", []) if isinstance(page, dict)]

    state["version"] = 1
    state["project"] = project_dir.name
    state["round_id"] = str(state.get("round_id", "")).strip()
    state["title"] = str(state.get("title", "")).strip()
    normalized_status = str(state.get("status", "inactive")).strip().lower()
    state["status"] = normalized_status if normalized_status in REVISION_STATUSES else ("inactive" if not exists else "active")
    state["created_at"] = str(state.get("created_at", "")).strip()
    state["updated_at"] = str(state.get("updated_at", "")).strip()
    state["created_by"] = str(state.get("created_by", "")).strip()
    state["notes"] = str(state.get("notes", "")).strip()
    state["allow_full_verify"] = bool(state.get("allow_full_verify", False))
    state["prepared_for_verify_at"] = str(state.get("prepared_for_verify_at", "")).strip()
    state["prepared_for_verify_by"] = str(state.get("prepared_for_verify_by", "")).strip()
    state["prepared_for_verify_note"] = str(state.get("prepared_for_verify_note", "")).strip()
    state["closed_at"] = str(state.get("closed_at", "")).strip()
    return state


def _normalize_revision_page(entry: dict) -> dict:
    """Normalize one page entry for revision-round storage."""
    file_name = _normalize_svg_name(entry.get("file") or entry.get("page") or "")
    if not file_name:
        raise ValueError(f"Invalid revision page entry: {entry}")

    issues = []
    raw_issues = entry.get("issues")
    if isinstance(raw_issues, list):
        for index, raw_issue in enumerate(raw_issues, start=1):
            if not isinstance(raw_issue, dict):
                continue
            issues.append(_normalize_revision_issue(raw_issue, index))
    elif any(key in entry for key in ("symptom", "priority", "target")):
        issues.append(_normalize_revision_issue(entry, 1))

    allowed_changes = _normalize_allowed_changes(entry.get("allowed_changes", []))

    return {
        "file": file_name,
        "status": _normalize_page_status(entry.get("status", "todo")),
        "note": str(entry.get("note", "")).strip(),
        "allowed_changes": allowed_changes,
        "issues": issues,
        "updated_at": str(entry.get("updated_at", "")).strip(),
    }


def _normalize_revision_issue(entry: dict, index: int) -> dict:
    """Normalize one issue item inside a revision page."""
    priority = str(entry.get("priority", "P2")).strip().upper()
    if priority not in ISSUE_PRIORITIES:
        priority = "P2"

    return {
        "id": str(entry.get("id", f"issue-{index}")).strip() or f"issue-{index}",
        "symptom": str(entry.get("symptom", "")).strip(),
        "target": str(entry.get("target", "")).strip(),
        "priority": priority,
        "note": str(entry.get("note", "")).strip(),
        "allowed_changes": _normalize_allowed_changes(entry.get("allowed_changes", [])),
    }


def _normalize_allowed_changes(value: object) -> list[str]:
    """Normalize change-type labels into a stable sorted list."""
    if isinstance(value, str):
        candidates = [part.strip().lower() for part in value.split(",")]
    elif isinstance(value, list):
        candidates = [str(part).strip().lower() for part in value]
    else:
        candidates = []

    normalized = sorted(
        {
            item
            for item in candidates
            if item in ALLOWED_CHANGE_TYPES
        }
    )
    return normalized


def _normalize_page_status(value: object) -> str:
    """Normalize a page status into the supported revision vocabulary."""
    text = str(value or "todo").strip().lower()
    if text in REVISION_PAGE_STATUSES:
        return text
    alias_map = {
        "doing": "in_progress",
        "review": "ready_for_review",
        "done": "approved",
        "pass": "approved",
    }
    return alias_map.get(text, "todo")


def _normalize_svg_name(value: object) -> str:
    """Normalize a page reference to an SVG filename."""
    text = str(value or "").strip().strip("`")
    if not text:
        return ""
    normalized = text.replace("\\", "/").split("/")[-1]
    if not normalized.lower().endswith(".svg"):
        normalized = f"{normalized}.svg"
    return normalized


def _now_iso() -> str:
    """Return a seconds-level ISO timestamp."""
    return datetime.now().isoformat(timespec="seconds")
