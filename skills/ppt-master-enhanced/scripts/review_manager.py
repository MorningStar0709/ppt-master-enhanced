#!/usr/bin/env python3
"""PPT Master review artifact manager and export gate helper.

Usage:
    conda run --no-capture-output -n ppt-master python scripts/review_manager.py init <project_path>
    conda run --no-capture-output -n ppt-master python scripts/review_manager.py sync <project_path>
    conda run --no-capture-output -n ppt-master python scripts/review_manager.py render <project_path>
    conda run --no-capture-output -n ppt-master python scripts/review_manager.py set-page <project_path> --file 01_cover.svg --reviewed yes --priority P2 --note "Cover reviewed"
    conda run --no-capture-output -n ppt-master python scripts/review_manager.py status <project_path> --compact
    conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify <project_path> --compact
    conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify <project_path> --json
    conda run --no-capture-output -n ppt-master python scripts/review_manager.py approve <project_path> --by <name> [--note "text"]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from runtime_utils import configure_utf8_stdio, safe_print, write_json_report
    from finalize_svg import finalize_project
    from icon_reference_checker import IconReferenceChecker
    from preview_svg_deck import generate_preview_page
    from review_utils import (
        gate_status_to_dict,
        format_gate_status,
        get_review_gate_status,
        init_review_artifacts,
        load_review_state,
        mark_review_approved,
        render_review_artifacts,
        sync_review_state,
        bulk_update_page_reviews,
        update_page_review,
    )
    from revision_utils import (
        close_revision_round,
        format_revision_gate_status,
        get_revision_gate_status,
        revision_gate_status_to_dict,
    )
    from project_utils import get_project_info
    from svg_layout_checker import SVGLayoutChecker
    from svg_quality_checker import SVGQualityChecker
    from svg_text_container_checker import SVGTextContainerChecker
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runtime_utils import configure_utf8_stdio, safe_print, write_json_report  # type: ignore
    from finalize_svg import finalize_project  # type: ignore
    from icon_reference_checker import IconReferenceChecker  # type: ignore
    from preview_svg_deck import generate_preview_page  # type: ignore
    from review_utils import (  # type: ignore
        gate_status_to_dict,
        format_gate_status,
        get_review_gate_status,
        init_review_artifacts,
        load_review_state,
        mark_review_approved,
        render_review_artifacts,
        sync_review_state,
        bulk_update_page_reviews,
        update_page_review,
    )
    from revision_utils import (  # type: ignore
        close_revision_round,
        format_revision_gate_status,
        get_revision_gate_status,
        revision_gate_status_to_dict,
    )
    from project_utils import get_project_info  # type: ignore
    from svg_layout_checker import SVGLayoutChecker  # type: ignore
    from svg_quality_checker import SVGQualityChecker  # type: ignore
    from svg_text_container_checker import SVGTextContainerChecker  # type: ignore


REVIEW_PREVIEW_SOURCE_DIR = "review/preview_finalized"
VERIFY_REPORT_FILENAME = "verify_report.json"
STEP8_BLOCKED_COMMANDS = [
    "scripts/total_md_split.py",
    "scripts/finalize_svg.py",
    "scripts/svg_to_pptx.py",
]


def _iter_verify_inputs(project_path: Path) -> list[Path]:
    """Return the current inputs that determine whether verify_report is still fresh."""
    inputs: list[Path] = []

    svg_dir = project_path / "svg_output"
    if svg_dir.exists():
        inputs.extend(sorted(svg_dir.glob("*.svg")))

    review_state = project_path / "review" / "review_state.json"
    if review_state.exists():
        inputs.append(review_state)

    revision_round = project_path / "review" / "revision_round.json"
    if revision_round.exists():
        inputs.append(revision_round)

    return inputs


def _get_stale_verify_inputs(project_path: Path, verify_report_path: Path | None = None) -> list[str]:
    """Return the verify inputs that are newer than the last verify report."""
    report_path = verify_report_path or (project_path / "review" / VERIFY_REPORT_FILENAME)
    if not report_path.exists():
        return []

    try:
        report_mtime_ns = report_path.stat().st_mtime_ns
    except OSError:
        return []

    stale_inputs: list[str] = []
    for path in _iter_verify_inputs(project_path):
        try:
            if path.stat().st_mtime_ns > report_mtime_ns:
                stale_inputs.append(str(path.relative_to(project_path)).replace("\\", "/"))
        except OSError:
            continue
    return stale_inputs


def _print_status(project_path: Path, compact: bool, json_output: bool) -> int:
    """Print the current gate state in the requested format."""
    status = get_review_gate_status(project_path)
    if json_output:
        print(json.dumps(gate_status_to_dict(status), ensure_ascii=True, indent=2))
    else:
        print(format_gate_status(status, compact=compact))
    return 0 if status.export_allowed else 1


def _build_review_preview_source(project_path: Path) -> tuple[int, dict]:
    """Build the unified Step 7 review SVG source under review/."""
    options = {
        "embed_icons": True,
        "crop_images": True,
        "fix_aspect": True,
        "embed_images": True,
        "flatten_text": True,
        "fix_rounded": True,
    }
    try:
        success = finalize_project(
            project_dir=project_path,
            options=options,
            quiet=True,
            output_dir_name=REVIEW_PREVIEW_SOURCE_DIR,
        )
        if not success:
            return 1, {
                "ok": False,
                "error": "review preview build failed",
                "source_name": REVIEW_PREVIEW_SOURCE_DIR,
            }
        return 0, {
            "ok": True,
            "source_name": REVIEW_PREVIEW_SOURCE_DIR,
            "output_dir": str(project_path / REVIEW_PREVIEW_SOURCE_DIR),
        }
    except Exception as exc:
        return 1, {
            "ok": False,
            "error": str(exc),
            "source_name": REVIEW_PREVIEW_SOURCE_DIR,
        }


def _run_icon_verify(target_dir: Path) -> tuple[int, dict]:
    """Run icon reference verification for the reviewed raw SVG set."""
    checker = IconReferenceChecker()
    checker.check_directory(str(target_dir), print_results=False)
    summary = checker.summary_dict()
    exit_code = 0 if summary["summary"]["errors"] == 0 else 1
    return exit_code, summary


def _run_quality_verify(target_dir: Path) -> tuple[int, dict]:
    """Run technical SVG validation on the reviewed raw SVG set."""
    checker = SVGQualityChecker(warn_on_icon_placeholders=False)
    checker.check_directory(str(target_dir), print_results=False)
    summary = checker.summary_dict()
    exit_code = 0 if summary["summary"]["errors"] == 0 else 1
    return exit_code, summary


def _run_layout_verify(target_dir: Path) -> tuple[int, dict]:
    """Run SVG layout geometry validation on the reviewed raw SVG set."""
    checker = SVGLayoutChecker()
    checker.check_directory(str(target_dir), print_results=False)
    summary = checker.summary_dict()
    exit_code = 0 if summary["summary"]["errors"] == 0 else 1
    return exit_code, summary


def _run_text_container_verify(target_dir: Path) -> tuple[int, dict]:
    """Run text-vs-container overflow validation on the reviewed raw SVG set."""
    checker = SVGTextContainerChecker()
    checker.check_directory(str(target_dir), print_results=False)
    summary = checker.summary_dict()
    exit_code = 0 if summary["summary"]["errors"] == 0 else 1
    return exit_code, summary


def _run_preview_verify(project_path: Path, source_dir: str = REVIEW_PREVIEW_SOURCE_DIR) -> tuple[int, dict]:
    """Generate the browser preview page and return its metadata."""
    try:
        preview = generate_preview_page(project_path=project_path, source_dir=source_dir)
        return 0, {
            "ok": True,
            "output": preview["output"],
            "source_dir": preview["source_dir"],
            "source_name": preview["source_name"],
            "slide_count": preview["slide_count"],
            "title": preview["title"],
        }
    except Exception as exc:
        return 1, {
            "ok": False,
            "error": str(exc),
            "source_name": source_dir,
        }


def _parse_content_outline_slides(design_spec_path: Path) -> list[dict[str, str | int]]:
    """Parse Section IX slide declarations from design_spec.md."""
    if not design_spec_path.exists():
        return []

    content = design_spec_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"(?ms)^##\s+IX\.\s+Content Outline.*?\n(.*?)(?=^##\s+X\.|^##\s+[A-Z]|\Z)",
        content,
    )
    if not match:
        return []

    section = match.group(1)
    slides: list[dict[str, str | int]] = []
    for line in section.splitlines():
        heading = line.strip()
        slide_match = re.match(r"^####\s+Slide\s+(\d+)\s*-\s*(.+?)\s*$", heading, flags=re.IGNORECASE)
        if not slide_match:
            continue
        slides.append({
            "number": int(slide_match.group(1)),
            "label": slide_match.group(1),
            "title": slide_match.group(2).strip(),
        })
    return slides


def _collect_svg_page_numbers(target_dir: Path) -> tuple[list[str], list[str]]:
    """Collect declared page numbers from svg_output filenames."""
    numbered: list[str] = []
    unmatched: list[str] = []
    for svg_file in sorted(target_dir.glob("*.svg")):
        match = re.match(r"^(\d+)", svg_file.stem)
        if match:
            numbered.append(match.group(1))
        else:
            unmatched.append(svg_file.name)
    return numbered, unmatched


def _run_outline_accountability_verify(project_path: Path, target_dir: Path) -> tuple[int, dict]:
    """Ensure Content Outline slide declarations align with actual SVG page outputs."""
    design_spec_path = project_path / "design_spec.md"
    declared_slides = _parse_content_outline_slides(design_spec_path)
    if not declared_slides:
        return 0, {
            "ok": True,
            "skipped": True,
            "reason": "No slide declarations found under design_spec.md Section IX Content Outline",
            "summary": {"total": 0, "passed": 0, "warnings": 0, "errors": 0},
            "results": [],
        }

    svg_files = sorted(target_dir.glob("*.svg"))
    actual_labels, unmatched_files = _collect_svg_page_numbers(target_dir)
    expected_labels = [str(item["label"]) for item in declared_slides]

    expected_set = set(expected_labels)
    actual_set = set(actual_labels)
    missing_labels = sorted(expected_set - actual_set, key=lambda item: int(item))
    extra_labels = sorted(actual_set - expected_set, key=lambda item: int(item))

    errors: list[str] = []
    warnings: list[str] = []

    if len(svg_files) != len(declared_slides):
        errors.append(
            "design_spec.md Content Outline declares "
            f"{len(declared_slides)} slides but svg_output contains {len(svg_files)} SVG files"
        )
    if missing_labels:
        errors.append(
            "Content Outline slide numbers missing in svg_output filenames: "
            + ", ".join(f"Slide {label}" for label in missing_labels)
        )
    if extra_labels:
        errors.append(
            "svg_output contains slide numbers not declared in Content Outline: "
            + ", ".join(f"Slide {label}" for label in extra_labels)
        )
    if unmatched_files:
        warnings.append(
            "Some SVG filenames do not start with a slide number and were excluded from outline number matching: "
            + ", ".join(unmatched_files[:6])
        )

    results = [{
        "file": "design_spec.md",
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
        "info": {
            "declared_slide_count": len(declared_slides),
            "svg_count": len(svg_files),
            "declared_slide_numbers": expected_labels,
            "svg_numbered_files": actual_labels,
            "svg_unmatched_files": unmatched_files,
        },
    }]
    summary = {
        "total": 1,
        "passed": 0 if errors else 1,
        "warnings": 1 if warnings else 0,
        "errors": 1 if errors else 0,
    }
    return (0 if not errors else 1), {
        "ok": not errors,
        "summary": summary,
        "results": results,
    }


def _parse_generated_image_rows(design_spec_path: Path) -> list[dict[str, str]]:
    """Parse Section VIII image-resource table rows whose status is Generated."""
    if not design_spec_path.exists():
        return []

    content = design_spec_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"(?ms)^##\s+VIII\.\s+Image Resource List.*?\n(.*?)(?=^##\s+IX\.|^##\s+[A-Z]|\Z)",
        content,
    )
    if not match:
        return []

    section = match.group(1)
    table_lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 3:
        return []

    headers = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    header_map = {name.lower(): index for index, name in enumerate(headers)}
    filename_idx = header_map.get("filename")
    status_idx = header_map.get("status")
    if filename_idx is None or status_idx is None:
        return []

    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) <= max(filename_idx, status_idx):
            continue
        filename = cells[filename_idx].strip("` ")
        status = cells[status_idx].strip("` ").lower()
        if not filename:
            continue
        if "generated" not in status:
            continue
        rows.append({
            "filename": filename,
            "status": cells[status_idx].strip(),
        })
    return rows


def _collect_svg_image_refs(target_dir: Path) -> dict[str, list[str]]:
    """Collect referenced image basenames from raw SVG files."""
    refs: dict[str, list[str]] = {}
    for svg_file in sorted(target_dir.glob("*.svg")):
        content = svg_file.read_text(encoding="utf-8", errors="replace")
        for href in re.findall(r'(?:xlink:)?href="(?!data:)([^"]+)"', content):
            normalized = href.strip().replace("\\", "/")
            if normalized.startswith("#") or normalized.startswith("http://") or normalized.startswith("https://"):
                continue
            basename = Path(normalized).name
            if not basename:
                continue
            refs.setdefault(basename, []).append(svg_file.name)
    return refs


def _run_image_accountability_verify(project_path: Path, target_dir: Path) -> tuple[int, dict]:
    """Ensure generated images recorded in the design spec are present and consumed by SVGs."""
    design_spec_path = project_path / "design_spec.md"
    generated_rows = _parse_generated_image_rows(design_spec_path)
    if not generated_rows:
        return 0, {
            "ok": True,
            "skipped": True,
            "reason": "No Generated image rows found in design_spec.md",
            "summary": {"total": 0, "passed": 0, "warnings": 0, "errors": 0},
            "results": [],
        }

    image_refs = _collect_svg_image_refs(target_dir)
    images_dir = project_path / "images"
    results: list[dict] = []
    errors = 0
    passed = 0

    for row in generated_rows:
        filename = row["filename"]
        image_path = images_dir / filename
        row_errors: list[str] = []
        row_warnings: list[str] = []

        if not image_path.exists():
            row_errors.append(
                f"Generated image listed in design_spec.md is missing from images/: {filename}"
            )
        elif filename not in image_refs:
            row_errors.append(
                f"Generated image exists but is not referenced by any svg_output page: {filename}"
            )

        if row_errors:
            errors += 1
        else:
            passed += 1

        results.append({
            "file": filename,
            "errors": row_errors,
            "warnings": row_warnings,
            "passed": not row_errors,
            "info": {
                "referenced_by": image_refs.get(filename, []),
                "status": row["status"],
            },
        })

    summary = {
        "total": len(results),
        "passed": passed,
        "warnings": 0,
        "errors": errors,
    }
    return (0 if errors == 0 else 1), {
        "ok": errors == 0,
        "summary": summary,
        "results": results,
    }


def _extract_stage_errors(summary: dict | None, *, max_items: int = 6) -> list[str]:
    """Extract concise per-file errors from a stage summary."""
    if not summary:
        return []
    items: list[str] = []
    for result in summary.get("results", []):
        file_name = result.get("file", "<unknown>")
        compact_issues = result.get("compact_issues", [])
        file_has_compact_errors = False
        if compact_issues:
            for issue in compact_issues:
                if issue.get("severity") != "error":
                    continue
                file_has_compact_errors = True
                issue_type = issue.get("type", "issue")
                container = issue.get("container", "<container>")
                excerpt = issue.get("text_excerpt", "")
                suffix = f" text='{excerpt}'" if excerpt else ""
                items.append(f"{file_name}: {issue_type} container={container}{suffix}")
                if len(items) >= max_items:
                    return items
            if file_has_compact_errors:
                continue
        for error in result.get("errors", []):
            items.append(f"{file_name}: {error}")
            if len(items) >= max_items:
                return items
    if not items and summary.get("error"):
        items.append(str(summary["error"]))
    return items


def _extract_stage_warnings(summary: dict | None, *, max_items: int = 6) -> list[str]:
    """Extract concise per-file warnings from a stage summary."""
    if not summary:
        return []
    items: list[str] = []
    for result in summary.get("results", []):
        file_name = result.get("file", "<unknown>")
        compact_issues = result.get("compact_issues", [])
        file_has_compact_warnings = False
        if compact_issues:
            for issue in compact_issues:
                if issue.get("severity") != "warning":
                    continue
                file_has_compact_warnings = True
                issue_type = issue.get("type", "issue")
                container = issue.get("container", "<container>")
                excerpt = issue.get("text_excerpt", "")
                suffix = f" text='{excerpt}'" if excerpt else ""
                items.append(f"{file_name}: {issue_type} container={container}{suffix}")
                if len(items) >= max_items:
                    return items
            if file_has_compact_warnings:
                continue
        for warning in result.get("warnings", []):
            items.append(f"{file_name}: {warning}")
            if len(items) >= max_items:
                return items
    if not items and summary.get("warning"):
        items.append(str(summary["warning"]))
    return items


def _build_repair_focus(
    failing_stages: list[str],
    failure_details: dict[str, list[str]],
    warning_details: dict[str, list[str]],
    *,
    max_items: int = 8,
) -> list[str]:
    """Build a compact next-repair queue that de-emphasizes gate bookkeeping blockers."""
    items: list[str] = []
    preferred_failure_order = [
        "outline_accountability",
        "image_accountability",
        "text_container_check",
        "quality_check",
        "layout_check",
        "icon_check",
        "review_source",
        "preview_check",
    ]
    for stage in preferred_failure_order:
        if stage not in failing_stages:
            continue
        for detail in failure_details.get(stage, []):
            if detail not in items:
                items.append(detail)
            if len(items) >= max_items:
                return items

    preferred_warning_order = [
        "outline_accountability",
        "image_accountability",
        "text_container_check",
        "layout_check",
        "quality_check",
        "icon_check",
        "preview_check",
        "review_source",
    ]
    for stage in preferred_warning_order:
        for detail in warning_details.get(stage, []):
            if detail not in items:
                items.append(detail)
            if len(items) >= max_items:
                return items

    if not items:
        for detail in failure_details.get("review_gate", []):
            if detail not in items:
                items.append(detail)
            if len(items) >= max_items:
                return items
    return items


def _write_verify_report(project_path: Path, payload: dict) -> Path:
    """Persist a machine-readable verify report under review/."""
    report_path = project_path / "review" / VERIFY_REPORT_FILENAME
    write_json_report(report_path, payload)
    return report_path


def _build_verify_skip_payload(
    status,
    *,
    failing_stage: str,
    blockers: list[str],
    report_path: Path,
) -> dict:
    """Build a consistent skipped-stage verify payload."""
    return {
        "review_gate": gate_status_to_dict(status),
        "review_source": {"skipped": True},
        "outline_accountability": {"skipped": True},
        "quality_check": {"skipped": True},
        "layout_check": {"skipped": True},
        "text_container_check": {"skipped": True},
        "image_accountability": {"skipped": True},
        "icon_check": {"skipped": True},
        "preview_check": {"skipped": True},
        "technical_passed": False,
        "approval_pending": status.approval_blocked,
        "export_allowed": False,
        "failing_stages": [failing_stage],
        "first_failing_stage": failing_stage,
        "failure_details": {
            failing_stage: blockers,
        },
        "warning_details": {},
        "repair_focus": blockers[:8],
        "report_file": str(report_path).replace("\\", "/"),
    }


def _load_verify_report(project_path: Path) -> dict | None:
    """Load the latest verify report when it exists and is valid JSON."""
    report_path = project_path / "review" / VERIFY_REPORT_FILENAME
    if not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _auto_close_active_revision_round(project_path: Path) -> tuple[bool, str]:
    """Close the active revision round after a successful whole-deck verify."""
    revision_status = get_revision_gate_status(project_path)
    if revision_status.status != "active":
        return False, ""
    if not revision_status.allow_full_verify or revision_status.pending_pages:
        return False, ""
    round_path = close_revision_round(project_path, force=False)
    return True, str(round_path)


def _print_repair_focus(project_path: Path, *, json_output: bool, max_items: int) -> int:
    """Print the compact repair queue from the latest verify report."""
    payload = _load_verify_report(project_path)
    if not payload:
        message = {
            "error": "verify_report_missing",
            "hint": f'Run `conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify "{project_path}" --compact` first.',
        }
        if json_output:
            print(json.dumps(message, ensure_ascii=True, indent=2))
        else:
            print("[ERROR] verify_report.json is missing or unreadable.")
            print("Generate or refresh it first:")
            print(f'  conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify "{project_path}" --compact')
        return 1

    focus = list(payload.get("repair_focus", []))[:max_items]
    if json_output:
        print(json.dumps({
            "project_path": str(project_path).replace("\\", "/"),
            "repair_focus": focus,
            "failing_stages": payload.get("failing_stages", []),
            "first_failing_stage": payload.get("first_failing_stage"),
            "report_file": payload.get("report_file", str(project_path / "review" / VERIFY_REPORT_FILENAME).replace("\\", "/")),
        }, ensure_ascii=True, indent=2))
    else:
        if focus:
            print("Repair focus")
            for detail in focus:
                print(f"  - {detail}")
        else:
            print("Repair focus")
            print("  - none")
        report_file = payload.get("report_file")
        if report_file:
            print(f"Verify report: {report_file}")
    return 0


def _build_next_action_payload(project_path: Path) -> dict:
    """Build a compact agent-first next-step decision payload."""
    revision_status = get_revision_gate_status(project_path)
    review_status = get_review_gate_status(project_path)
    verify_report = _load_verify_report(project_path)
    stale_verify_inputs = _get_stale_verify_inputs(project_path)
    project_info = get_project_info(str(project_path))

    payload = {
        "project_path": str(project_path).replace("\\", "/"),
        "project_info": {
            "template_ready": bool(project_info.get("template_ready")),
            "template_name": project_info.get("template_name", ""),
            "template_svg_count": int(project_info.get("template_svg_count", 0) or 0),
            "has_template_spec": bool(project_info.get("has_template_spec")),
            "has_template_manifest": bool(project_info.get("has_template_manifest")),
        },
        "revision_round": revision_gate_status_to_dict(revision_status),
        "review_gate": gate_status_to_dict(review_status),
        "verify_report_available": verify_report is not None,
        "step7_status": "needs_review_gate",
        "technical_passed": None,
        "approval_pending": review_status.approval_blocked,
        "export_allowed": review_status.export_allowed,
        "step8_ready": review_status.export_allowed,
        "must_not_run": [],
        "next_action": "",
        "reasons": [],
        "repair_focus": [],
        "suggested_command": "",
    }

    if payload["project_info"]["has_template_manifest"] and not payload["project_info"]["template_ready"]:
        payload["step7_status"] = "setup_incomplete"
        payload["step8_ready"] = False
        payload["must_not_run"] = list(STEP8_BLOCKED_COMMANDS)
        template_name = payload["project_info"]["template_name"] or "<template_name>"
        payload["next_action"] = "apply_template"
        payload["reasons"] = [
            "Project template manifest exists but template assets under templates/ are incomplete.",
            "If Step 3 selected an existing template, restore it before continuing review or export decisions.",
        ]
        payload["suggested_command"] = (
            f'conda run --no-capture-output -n ppt-master python scripts/project_manager.py apply-template "{project_path}" {template_name} --force'
        )
        return payload

    if not revision_status.verify_allowed:
        payload["step7_status"] = "revision_round_active"
        payload["step8_ready"] = False
        payload["must_not_run"] = list(STEP8_BLOCKED_COMMANDS)
        payload["next_action"] = "revise_pages"
        payload["reasons"] = list(revision_status.blockers)
        payload["suggested_command"] = (
            f'conda run --no-capture-output -n ppt-master python scripts/revision_manager.py status "{project_path}" --json'
        )
        return payload

    if not review_status.verify_ready:
        payload["step7_status"] = "needs_review_gate"
        payload["step8_ready"] = False
        payload["must_not_run"] = list(STEP8_BLOCKED_COMMANDS)
        payload["next_action"] = "repair_review_gate"
        payload["reasons"] = list(review_status.non_approval_blockers)
        payload["suggested_command"] = (
            f'conda run --no-capture-output -n ppt-master python scripts/review_manager.py status "{project_path}" --json'
        )
        return payload

    if verify_report is None:
        payload["step7_status"] = "needs_verify"
        payload["step8_ready"] = False
        payload["must_not_run"] = list(STEP8_BLOCKED_COMMANDS)
        payload["next_action"] = "run_verify"
        payload["reasons"] = ["No verify report exists for the current technically-eligible state."]
        payload["suggested_command"] = (
            f'conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify "{project_path}" --json'
        )
        return payload

    if stale_verify_inputs:
        payload["step7_status"] = "needs_verify"
        payload["step8_ready"] = False
        payload["must_not_run"] = list(STEP8_BLOCKED_COMMANDS)
        payload["next_action"] = "run_verify"
        payload["reasons"] = [
            "Latest verify report is stale for the current review inputs: "
            + ", ".join(stale_verify_inputs)
        ]
        payload["suggested_command"] = (
            f'conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify "{project_path}" --json'
        )
        return payload

    technical_passed = bool(verify_report.get("technical_passed", False))
    approval_pending = bool(verify_report.get("approval_pending", review_status.approval_blocked))
    export_allowed = bool(verify_report.get("export_allowed", review_status.export_allowed))
    repair_focus = list(verify_report.get("repair_focus", []))

    payload["technical_passed"] = technical_passed
    payload["approval_pending"] = approval_pending
    payload["export_allowed"] = export_allowed
    payload["step8_ready"] = export_allowed
    payload["repair_focus"] = repair_focus

    if not technical_passed:
        payload["step7_status"] = "repair_required"
        payload["must_not_run"] = list(STEP8_BLOCKED_COMMANDS)
        payload["next_action"] = "repair_svg_issues"
        payload["reasons"] = repair_focus or ["Latest verify report still contains blocking technical issues."]
        payload["suggested_command"] = (
            f'conda run --no-capture-output -n ppt-master python scripts/review_manager.py repair-focus "{project_path}" --json'
        )
        return payload

    if approval_pending:
        payload["step7_status"] = "awaiting_user_approval"
        payload["step8_ready"] = False
        payload["must_not_run"] = list(STEP8_BLOCKED_COMMANDS)
        payload["next_action"] = "request_user_approval"
        payload["reasons"] = [
            "Technical gate passed. Final user approval is still pending before Step 8 export.",
            "Do not run total_md_split.py, finalize_svg.py, or svg_to_pptx.py until approval is recorded.",
        ]
        payload["suggested_command"] = (
            f'conda run --no-capture-output -n ppt-master python scripts/review_manager.py approve "{project_path}" --by "<approver_name>"'
        )
        return payload

    if export_allowed:
        payload["step7_status"] = "approved"
        payload["must_not_run"] = []
        payload["next_action"] = "run_export"
        payload["reasons"] = ["Technical gate passed and approval is already recorded."]
        payload["suggested_command"] = (
            f'conda run -n ppt-master python scripts/total_md_split.py "{project_path}"'
        )
        return payload

    payload["step7_status"] = "inspect_state"
    payload["step8_ready"] = False
    payload["must_not_run"] = list(STEP8_BLOCKED_COMMANDS)
    payload["next_action"] = "inspect_state"
    payload["reasons"] = ["No standard next action matched the current state. Inspect review and verify artifacts."]
    payload["suggested_command"] = (
        f'conda run --no-capture-output -n ppt-master python scripts/review_manager.py status "{project_path}" --json'
    )
    return payload


def _print_next_action(project_path: Path, *, json_output: bool) -> int:
    """Print the compact next-action payload for agent consumption."""
    payload = _build_next_action_payload(project_path)
    if json_output:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print(f"Next action: {payload['next_action']}")
        for reason in payload["reasons"]:
            print(f"  - {reason}")
        if payload["repair_focus"]:
            print("Repair focus:")
            for detail in payload["repair_focus"][:6]:
                print(f"  - {detail}")
        if payload["suggested_command"]:
            print(f"Suggested command: {payload['suggested_command']}")

    return 0 if payload["next_action"] in {"request_user_approval", "run_export"} else 1


def _refresh_verify_report_after_approval(project_path: Path) -> tuple[int, dict | None, str]:
    """Refresh review/verify_report.json after approval is recorded."""
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "verify",
            str(project_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = None
    error = ""
    stdout = result.stdout.strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            error = stdout
    if not error and result.stderr.strip():
        error = result.stderr.strip()
    return result.returncode, payload, error


def main() -> None:
    """Run the CLI entry point."""
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="PPT Master - Review artifact manager",
        epilog=(
            "Notes:\n"
            "  - set-page requires --file; the SVG filename is not a positional argument.\n"
            "  - verify returns exit code 1 whenever the review gate is still BLOCKED or any automatic check fails.\n"
            "    This is expected gate behavior, not a path-format error.\n"
            f"  - verify prepares the Step 7 preview source under {REVIEW_PREVIEW_SOURCE_DIR} for preview generation only;\n"
            "    technical/layout/icon checks still validate the reviewed raw SVG set under svg_output/."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize review artifacts")
    init_parser.add_argument("project_path", type=Path, help="Project directory path")
    init_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing review artifact files",
    )

    sync_parser = subparsers.add_parser(
        "sync",
        help="Build review_state.json from legacy Markdown artifacts and re-render reports",
    )
    sync_parser.add_argument("project_path", type=Path, help="Project directory path")

    render_parser = subparsers.add_parser(
        "render",
        help="Render Markdown review artifacts from review_state.json",
    )
    render_parser.add_argument("project_path", type=Path, help="Project directory path")

    set_page_parser = subparsers.add_parser(
        "set-page",
        help="Update one page in the minimal review state",
    )
    set_page_parser.add_argument("project_path", type=Path, help="Project directory path")
    set_page_parser.add_argument("--file", required=True, help="SVG filename, e.g. 01_cover.svg")
    set_page_parser.add_argument(
        "--priority",
        required=True,
        choices=["none", "P2", "P1", "P0"],
        help="Minimal review priority",
    )
    set_page_parser.add_argument(
        "--reviewed",
        choices=["yes", "no"],
        default="yes",
        help="Whether the page has been reviewed (default: yes)",
    )
    set_page_parser.add_argument("--note", default=None, help="Compact note for the page")
    set_page_parser.add_argument("--reviewer", default=None, help="Reviewer name")

    set_pages_parser = subparsers.add_parser(
        "set-pages",
        help="Update multiple pages in one review-state write",
    )
    set_pages_parser.add_argument("project_path", type=Path, help="Project directory path")
    set_pages_parser.add_argument(
        "--json-file",
        required=True,
        type=Path,
        help="JSON file containing a list of page update objects",
    )
    set_pages_parser.add_argument("--reviewer", default=None, help="Default reviewer name")

    status_parser = subparsers.add_parser("status", help="Show review gate status")
    status_parser.add_argument("project_path", type=Path, help="Project directory path")
    status_parser.add_argument("--compact", action="store_true", help="Show compact summary")
    status_parser.add_argument("--json", action="store_true", help="Output JSON")

    repair_focus_parser = subparsers.add_parser(
        "repair-focus",
        help="Show the compact next-repair queue from review/verify_report.json",
    )
    repair_focus_parser.add_argument("project_path", type=Path, help="Project directory path")
    repair_focus_parser.add_argument("--json", action="store_true", help="Output JSON")
    repair_focus_parser.add_argument(
        "--max-items",
        type=int,
        default=8,
        help="Maximum repair-focus items to print (default: 8)",
    )

    next_action_parser = subparsers.add_parser(
        "next-action",
        help="Return the smallest agent-first next-step decision payload",
    )
    next_action_parser.add_argument("project_path", type=Path, help="Project directory path")
    next_action_parser.add_argument("--json", action="store_true", help="Output JSON")

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify per-page review coverage and summary consistency",
    )
    verify_parser.add_argument("project_path", type=Path, help="Project directory path")
    verify_parser.add_argument("--compact", action="store_true", help="Show compact summary")
    verify_parser.add_argument("--json", action="store_true", help="Output JSON")
    verify_parser.add_argument(
        "--report-file",
        type=Path,
        default=None,
        help="Optional JSON report path (default: <project_path>/review/verify_report.json)",
    )
    verify_parser.add_argument(
        "--skip-icon-check",
        action="store_true",
        help="Skip automatic data-icon validation during verify",
    )
    verify_parser.add_argument(
        "--skip-quality-check",
        action="store_true",
        help="Skip technical SVG validation during verify",
    )
    verify_parser.add_argument(
        "--skip-layout-check",
        action="store_true",
        help="Skip layout geometry validation during verify",
    )
    verify_parser.add_argument(
        "--skip-text-container-check",
        action="store_true",
        help="Skip text-vs-container overflow validation during verify",
    )
    verify_parser.add_argument(
        "--skip-preview-check",
        action="store_true",
        help="Skip preview page generation during verify",
    )

    approve_parser = subparsers.add_parser("approve", help="Mark export review as approved")
    approve_parser.add_argument("project_path", type=Path, help="Project directory path")
    approve_parser.add_argument("--by", required=True, help="Approver name")
    approve_parser.add_argument("--note", default=None, help="Optional approval note")

    args = parser.parse_args()

    if not args.project_path.exists():
        print(f"[ERROR] Project directory does not exist: {args.project_path}")
        sys.exit(1)

    if args.command == "init":
        artifacts = init_review_artifacts(args.project_path, overwrite=args.overwrite)
        print("[OK] Review artifacts initialized")
        print(f"  - {artifacts.review_state}")
        print(f"  - {artifacts.review_log}")
        print(f"  - {artifacts.fix_tasks}")
        print(f"  - {artifacts.user_confirmation}")
        return

    if args.command == "sync":
        artifacts = sync_review_state(args.project_path)
        print(f"[OK] Review state synchronized: {artifacts.review_state}")
        print(f"[OK] Markdown artifacts re-rendered under: {artifacts.review_dir}")
        return

    if args.command == "render":
        state = load_review_state(args.project_path)
        artifacts = render_review_artifacts(args.project_path, state, overwrite=True)
        safe_print(f"[OK] Markdown artifacts rendered from: {artifacts.review_state}")
        return

    if args.command == "set-page":
        reviewed = args.reviewed == "yes"
        artifacts = update_page_review(
            args.project_path,
            page_file=args.file,
            priority=args.priority,
            reviewed=reviewed,
            note=args.note,
            reviewer=args.reviewer,
        )
        status = get_review_gate_status(args.project_path)
        safe_print(f"[OK] Page review updated: {artifacts.review_state}")
        safe_print(format_gate_status(status, compact=True))
        return

    if args.command == "set-pages":
        try:
            payload = json.loads(args.json_file.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[ERROR] Failed to read JSON file: {exc}")
            sys.exit(1)

        if not isinstance(payload, list):
            print("[ERROR] --json-file must contain a JSON list of page update objects")
            sys.exit(1)

        try:
            artifacts = bulk_update_page_reviews(
                args.project_path,
                entries=payload,
                reviewer=args.reviewer,
            )
        except Exception as exc:
            print(f"[ERROR] Failed to update review pages: {exc}")
            sys.exit(1)

        status = get_review_gate_status(args.project_path)
        safe_print(f"[OK] Review pages updated: {artifacts.review_state}")
        safe_print(format_gate_status(status, compact=True))
        return

    if args.command == "status":
        sys.exit(_print_status(args.project_path, compact=args.compact, json_output=args.json))

    if args.command == "repair-focus":
        sys.exit(_print_repair_focus(args.project_path, json_output=args.json, max_items=max(1, args.max_items)))

    if args.command == "next-action":
        sys.exit(_print_next_action(args.project_path, json_output=args.json))

    if args.command == "verify":
        revision_status = get_revision_gate_status(args.project_path)
        if not revision_status.verify_allowed:
            payload = {
                "revision_round": revision_gate_status_to_dict(revision_status),
                "review_gate": {"skipped": True},
                "review_source": {"skipped": True},
                "outline_accountability": {"skipped": True},
                "quality_check": {"skipped": True},
                "layout_check": {"skipped": True},
                "text_container_check": {"skipped": True},
                "image_accountability": {"skipped": True},
                "icon_check": {"skipped": True},
                "preview_check": {"skipped": True},
                "export_allowed": False,
                "failing_stages": ["revision_round"],
                "first_failing_stage": "revision_round",
                "failure_details": {
                    "revision_round": revision_status.blockers,
                },
            }
            report_path = args.report_file or (args.project_path / "review" / VERIFY_REPORT_FILENAME)
            payload["report_file"] = str(report_path).replace("\\", "/")
            write_json_report(report_path, payload)
            if args.json:
                print(json.dumps(payload, ensure_ascii=True, indent=2))
            else:
                print(format_revision_gate_status(revision_status, compact=args.compact))
                print(f"Verify report: {report_path}")
                print("\n[ERROR] Active revision round blocks whole-deck verify.")
                print("[INFO] Resolve any pages still in `todo` / `in_progress` first.")
                print("[INFO] After that, rerun whole-deck verify directly.")
                print("[INFO] `revision_manager.py prepare-verify` is optional bookkeeping only.")
            sys.exit(1)

        status = get_review_gate_status(args.project_path)
        if not status.verify_ready:
            report_path = args.report_file or (args.project_path / "review" / VERIFY_REPORT_FILENAME)
            payload = _build_verify_skip_payload(
                status,
                failing_stage="review_gate",
                blockers=status.non_approval_blockers,
                report_path=report_path,
            )
            write_json_report(report_path, payload)
            if args.json:
                print(json.dumps(payload, ensure_ascii=True, indent=2))
            else:
                print(format_gate_status(status, compact=args.compact))
                print(f"Verify report: {report_path}")
                print("\n[ERROR] Whole-deck verify stopped before heavy checks.")
                print("[INFO] Resolve non-approval review blockers first, then rerun verify.")
            sys.exit(1)

        if args.json:
            gate_exit_code = 0
        else:
            print(format_gate_status(status, compact=args.compact))
            gate_exit_code = 0
        raw_svg_dir = args.project_path / "svg_output"
        review_source_exit_code = 0
        review_source_summary = None
        review_source_dir = args.project_path / REVIEW_PREVIEW_SOURCE_DIR
        if not args.skip_preview_check:
            review_source_exit_code, review_source_summary = _build_review_preview_source(args.project_path)
        quality_exit_code = 0
        quality_summary = None
        if not args.skip_quality_check:
            quality_exit_code, quality_summary = _run_quality_verify(raw_svg_dir)

        outline_accountability_exit_code = 0
        outline_accountability_summary = None
        outline_accountability_exit_code, outline_accountability_summary = _run_outline_accountability_verify(
            args.project_path,
            raw_svg_dir,
        )

        layout_exit_code = 0
        layout_summary = None
        if not args.skip_layout_check:
            layout_exit_code, layout_summary = _run_layout_verify(raw_svg_dir)

        text_container_exit_code = 0
        text_container_summary = None
        if not args.skip_text_container_check:
            text_container_exit_code, text_container_summary = _run_text_container_verify(raw_svg_dir)

        image_accountability_exit_code = 0
        image_accountability_summary = None
        image_accountability_exit_code, image_accountability_summary = _run_image_accountability_verify(
            args.project_path,
            raw_svg_dir,
        )

        icon_exit_code = 0
        icon_summary = None
        if not args.skip_icon_check:
            icon_exit_code, icon_summary = _run_icon_verify(raw_svg_dir)

        preview_exit_code = 0
        preview_summary = None
        if review_source_exit_code == 0 and not args.skip_preview_check:
            preview_exit_code, preview_summary = _run_preview_verify(args.project_path)
        elif review_source_exit_code != 0:
            preview_exit_code = 1

        failing_stages: list[str] = []
        if gate_exit_code != 0:
            failing_stages.append("review_gate")
        if review_source_exit_code != 0:
            failing_stages.append("review_source")
        if outline_accountability_exit_code != 0:
            failing_stages.append("outline_accountability")
        if quality_exit_code != 0:
            failing_stages.append("quality_check")
        if layout_exit_code != 0:
            failing_stages.append("layout_check")
        if text_container_exit_code != 0:
            failing_stages.append("text_container_check")
        if image_accountability_exit_code != 0:
            failing_stages.append("image_accountability")
        if icon_exit_code != 0:
            failing_stages.append("icon_check")
        if preview_exit_code != 0:
            failing_stages.append("preview_check")

        first_failing_stage = failing_stages[0] if failing_stages else None
        failure_details = {
            "review_gate": status.blockers if gate_exit_code != 0 else [],
            "review_source": _extract_stage_errors(review_source_summary),
            "outline_accountability": _extract_stage_errors(outline_accountability_summary),
            "quality_check": _extract_stage_errors(quality_summary),
            "layout_check": _extract_stage_errors(layout_summary),
            "text_container_check": _extract_stage_errors(text_container_summary),
            "image_accountability": _extract_stage_errors(image_accountability_summary),
            "icon_check": _extract_stage_errors(icon_summary),
            "preview_check": _extract_stage_errors(preview_summary),
        }
        warning_details = {
            "review_source": _extract_stage_warnings(review_source_summary),
            "outline_accountability": _extract_stage_warnings(outline_accountability_summary),
            "quality_check": _extract_stage_warnings(quality_summary),
            "layout_check": _extract_stage_warnings(layout_summary),
            "text_container_check": _extract_stage_warnings(text_container_summary),
            "image_accountability": _extract_stage_warnings(image_accountability_summary),
            "icon_check": _extract_stage_warnings(icon_summary),
            "preview_check": _extract_stage_warnings(preview_summary),
        }
        repair_focus = _build_repair_focus(
            failing_stages,
            failure_details,
            warning_details,
        )
        technical_passed = (
            gate_exit_code == 0
            and review_source_exit_code == 0
            and outline_accountability_exit_code == 0
            and quality_exit_code == 0
            and layout_exit_code == 0
            and text_container_exit_code == 0
            and image_accountability_exit_code == 0
            and icon_exit_code == 0
            and preview_exit_code == 0
        )
        approval_pending = status.approval_blocked

        payload = {
            "review_gate": gate_status_to_dict(status),
            "review_source": review_source_summary if review_source_summary is not None else {"skipped": True},
            "outline_accountability": outline_accountability_summary
            if outline_accountability_summary is not None else {"skipped": True},
            "quality_check": quality_summary if quality_summary is not None else {"skipped": True},
            "layout_check": layout_summary if layout_summary is not None else {"skipped": True},
            "text_container_check": text_container_summary if text_container_summary is not None else {"skipped": True},
            "image_accountability": image_accountability_summary if image_accountability_summary is not None else {"skipped": True},
            "icon_check": icon_summary if icon_summary is not None else {"skipped": True},
            "preview_check": preview_summary if preview_summary is not None else {"skipped": True},
            "technical_passed": technical_passed,
            "approval_pending": approval_pending,
            "export_allowed": technical_passed and not approval_pending,
            "failing_stages": failing_stages,
            "first_failing_stage": first_failing_stage,
            "failure_details": failure_details,
            "warning_details": warning_details,
            "repair_focus": repair_focus,
        }
        report_path = args.report_file or (args.project_path / "review" / VERIFY_REPORT_FILENAME)
        payload["report_file"] = str(report_path).replace("\\", "/")
        write_json_report(report_path, payload)

        if args.json:
            print(json.dumps(payload, ensure_ascii=True, indent=2))
        else:
            if review_source_summary is not None:
                if review_source_summary.get("ok"):
                    print(
                        "\nReview source: "
                        f"ok=True source={review_source_summary['source_name']} "
                        f"output={review_source_summary['output_dir']}"
                    )
                else:
                    print(f"\nReview source: ok=False error={review_source_summary['error']}")

            if outline_accountability_summary is not None and not outline_accountability_summary.get("skipped"):
                summary = outline_accountability_summary["summary"]
                print(
                    "Outline accountability: "
                    f"total={summary['total']} "
                    f"passed={summary['passed']} "
                    f"warnings={summary['warnings']} "
                    f"errors={summary['errors']}"
                )

            if quality_summary is not None:
                summary = quality_summary["summary"]
                print(
                    "\nQuality check: "
                    f"total={summary['total']} "
                    f"passed={summary['passed']} "
                    f"warnings={summary['warnings']} "
                    f"errors={summary['errors']}"
                )

            if layout_summary is not None:
                summary = layout_summary["summary"]
                print(
                    "Layout check: "
                    f"total={summary['total']} "
                    f"passed={summary['passed']} "
                    f"warnings={summary['warnings']} "
                    f"errors={summary['errors']}"
                )

            if icon_summary is not None:
                summary = icon_summary["summary"]
                print(
                    "Icon check: "
                    f"total={summary['total']} "
                    f"passed={summary['passed']} "
                    f"warnings={summary['warnings']} "
                    f"errors={summary['errors']}"
                )

            if text_container_summary is not None:
                summary = text_container_summary["summary"]
                print(
                    "Text/container check: "
                    f"total={summary['total']} "
                    f"passed={summary['passed']} "
                    f"warnings={summary['warnings']} "
                    f"errors={summary['errors']}"
                )
                if summary["warnings"] > 0 and text_container_exit_code == 0:
                    for detail in warning_details["text_container_check"][:4]:
                        print(f"  [WARN] {detail}")

            if image_accountability_summary is not None and not image_accountability_summary.get("skipped"):
                summary = image_accountability_summary["summary"]
                print(
                    "Image accountability: "
                    f"total={summary['total']} "
                    f"passed={summary['passed']} "
                    f"warnings={summary['warnings']} "
                    f"errors={summary['errors']}"
                )

            if preview_summary is not None:
                if preview_summary.get("ok"):
                    print(
                        "Preview check: "
                        f"ok=True source={preview_summary['source_name']} "
                        f"slides={preview_summary['slide_count']} "
                        f"output={preview_summary['output']}"
                    )
                else:
                    print(f"Preview check: ok=False error={preview_summary['error']}")

            print(f"Verify report: {report_path}")

            if first_failing_stage:
                print(f"First failing stage: {first_failing_stage}")
                for detail in failure_details.get(first_failing_stage, [])[:6]:
                    print(f"  - {detail}")
            if repair_focus:
                print("Repair focus:")
                for detail in repair_focus[:6]:
                    print(f"  - {detail}")

            if technical_passed:
                closed_revision_round, closed_round_path = _auto_close_active_revision_round(args.project_path)
                print("\n[OK] Review evidence, preview-source build, technical checks, layout checks, text/container checks, icon references, and preview generation all passed.")
                if approval_pending:
                    print("[INFO] User approval is still pending. Step 8 export remains blocked until approval is recorded.")
                if closed_revision_round:
                    print(f"[OK] Active revision round auto-closed: {closed_round_path}")
            elif gate_exit_code != 0:
                print("\n[ERROR] Review evidence is incomplete or inconsistent.")
                print("[INFO] verify returns exit code 1 while the SVG Review Gate is still BLOCKED.")
                print("[INFO] Common causes: unreviewed pages, pending approval, or inconsistent review artifacts.")
            elif review_source_exit_code != 0:
                print("\n[ERROR] Unified review-source generation failed.")
            elif outline_accountability_exit_code != 0:
                print("\n[ERROR] Content Outline declarations do not match svg_output page outputs.")
            elif quality_exit_code != 0:
                print("\n[ERROR] Technical SVG validation contains blocking issues.")
            elif layout_exit_code != 0:
                print("\n[ERROR] Layout geometry validation contains blocking issues.")
            elif text_container_exit_code != 0:
                print("\n[ERROR] Text/container validation found blocking overflow issues.")
            elif image_accountability_exit_code != 0:
                print("\n[ERROR] Generated-image accountability check found missing or unused generated images.")
            else:
                if icon_exit_code != 0:
                    print("\n[ERROR] Icon references contain blocking issues.")
                else:
                    print("\n[ERROR] Preview generation failed.")

        sys.exit(
            1
            if not technical_passed
            else 0
        )

    if args.command == "approve":
        artifacts = mark_review_approved(args.project_path, approved_by=args.by, note=args.note)
        status = get_review_gate_status(args.project_path)
        refresh_code, refresh_payload, refresh_error = _refresh_verify_report_after_approval(args.project_path)
        print(f"[OK] Review approval updated: {artifacts.user_confirmation}")
        print(format_gate_status(status, compact=True))
        if refresh_code == 0:
            print(f"[OK] Verify report refreshed: {args.project_path / 'review' / VERIFY_REPORT_FILENAME}")
        else:
            print("[WARN] Approval was recorded, but verify report refresh failed.")
            if refresh_error:
                print(f"  - {refresh_error}")
            print("[INFO] Rerun verify before trusting next-action/export decisions.")
        export_allowed = bool(refresh_payload.get("export_allowed")) if refresh_payload else False
        sys.exit(0 if export_allowed else 1)


if __name__ == "__main__":
    main()
