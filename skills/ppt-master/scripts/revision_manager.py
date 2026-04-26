#!/usr/bin/env python3
"""Manage structured revision rounds between page fixes and whole-deck verify."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from revision_utils import (
        build_revision_task_template,
        close_revision_round,
        create_revision_round,
        format_revision_gate_status,
        get_revision_gate_status,
        load_revision_round,
        prepare_revision_verify,
        revision_gate_status_to_dict,
        update_revision_page,
    )
    from runtime_utils import configure_utf8_stdio, safe_print
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from revision_utils import (  # type: ignore
        build_revision_task_template,
        close_revision_round,
        create_revision_round,
        format_revision_gate_status,
        get_revision_gate_status,
        load_revision_round,
        prepare_revision_verify,
        revision_gate_status_to_dict,
        update_revision_page,
    )
    from runtime_utils import configure_utf8_stdio, safe_print  # type: ignore


def main() -> None:
    """Run the CLI entry point."""
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="PPT Master - Revision round manager",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser(
        "create-round",
        help="Create a structured revision round from a JSON list of page tasks",
    )
    create_parser.add_argument("project_path", type=Path, help="Project directory path")
    create_parser.add_argument("--json-file", required=True, type=Path, help="JSON list of revision page entries")
    create_parser.add_argument("--by", default="", help="Creator / reviewer name")
    create_parser.add_argument("--title", default="", help="Short round title")
    create_parser.add_argument("--notes", default="", help="Optional round-level note")

    scaffold_parser = subparsers.add_parser(
        "scaffold-tasks",
        help="Generate a machine-friendly revision task JSON skeleton for selected SVG pages",
    )
    scaffold_parser.add_argument("project_path", type=Path, help="Project directory path")
    scaffold_parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Optional SVG filenames to include; defaults to every page in svg_output/",
    )
    scaffold_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: <project_path>/review/revision_tasks.json)",
    )

    status_parser = subparsers.add_parser("status", help="Show agent-side revision round status")
    status_parser.add_argument("project_path", type=Path, help="Project directory path")
    status_parser.add_argument("--compact", action="store_true", help="Show compact summary")
    status_parser.add_argument("--json", action="store_true", help="Output JSON")

    set_page_parser = subparsers.add_parser("set-page", help="Update one page status in the active revision round")
    set_page_parser.add_argument("project_path", type=Path, help="Project directory path")
    set_page_parser.add_argument("--file", required=True, help="SVG filename, e.g. 03_architecture.svg")
    set_page_parser.add_argument(
        "--status",
        required=True,
        choices=["todo", "in_progress", "ready_for_review", "approved"],
        help="Revision page status (`ready_for_review` / `approved` are both treated as resolved for whole-deck verify)",
    )
    set_page_parser.add_argument("--note", default=None, help="Optional page note")

    prepare_parser = subparsers.add_parser(
        "prepare-verify",
        help="Mark the current revision batch as ready for whole-deck verify after unresolved pages are cleared",
    )
    prepare_parser.add_argument("project_path", type=Path, help="Project directory path")
    prepare_parser.add_argument("--by", default="", help="Actor preparing whole-deck verify")
    prepare_parser.add_argument("--note", default="", help="Optional preparation note")

    close_parser = subparsers.add_parser("close-round", help="Close the active revision round")
    close_parser.add_argument("project_path", type=Path, help="Project directory path")
    close_parser.add_argument("--force", action="store_true", help="Force-close even if pages are still pending")

    args = parser.parse_args()

    if not args.project_path.exists():
        safe_print(f"[ERROR] Project directory does not exist: {args.project_path}")
        sys.exit(1)

    if args.command == "create-round":
        try:
            entries = json.loads(args.json_file.read_text(encoding="utf-8"))
        except Exception as exc:
            safe_print(f"[ERROR] Failed to read revision JSON: {exc}")
            sys.exit(1)
        if not isinstance(entries, list):
            safe_print("[ERROR] --json-file must contain a JSON list of page entries")
            sys.exit(1)
        try:
            round_path = create_revision_round(
                args.project_path,
                entries,
                created_by=args.by,
                title=args.title,
                notes=args.notes,
            )
        except Exception as exc:
            safe_print(f"[ERROR] Failed to create revision round: {exc}")
            sys.exit(1)
        safe_print(f"[OK] Revision round created: {round_path}")
        status = get_revision_gate_status(args.project_path)
        safe_print(format_revision_gate_status(status, compact=True))
        sys.exit(0)

    if args.command == "scaffold-tasks":
        try:
            payload = build_revision_task_template(
                args.project_path,
                page_files=args.files,
            )
        except Exception as exc:
            safe_print(f"[ERROR] Failed to scaffold revision tasks: {exc}")
            sys.exit(1)

        output_path = args.output or (args.project_path / "review" / "revision_tasks.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        safe_print(f"[OK] Revision task skeleton written: {output_path}")
        safe_print(f"[INFO] Entries: {len(payload)}")
        sys.exit(0)

    if args.command == "status":
        status = get_revision_gate_status(args.project_path)
        if args.json:
            payload = revision_gate_status_to_dict(status)
            payload["round"] = load_revision_round(args.project_path)
            safe_print(json.dumps(payload, ensure_ascii=True, indent=2))
        else:
            safe_print(format_revision_gate_status(status, compact=args.compact))
        sys.exit(0 if status.verify_allowed else 1)

    if args.command == "set-page":
        try:
            round_path = update_revision_page(
                args.project_path,
                page_file=args.file,
                status=args.status,
                note=args.note,
            )
        except Exception as exc:
            safe_print(f"[ERROR] Failed to update revision page: {exc}")
            sys.exit(1)
        safe_print(f"[OK] Revision page updated: {round_path}")
        safe_print(format_revision_gate_status(get_revision_gate_status(args.project_path), compact=True))
        sys.exit(0)

    if args.command == "prepare-verify":
        try:
            round_path = prepare_revision_verify(
                args.project_path,
                prepared_by=args.by,
                note=args.note,
            )
        except Exception as exc:
            safe_print(f"[ERROR] Failed to unlock whole-deck verify: {exc}")
            sys.exit(1)
        safe_print(f"[OK] Whole-deck verify unlocked for current revision round: {round_path}")
        safe_print(format_revision_gate_status(get_revision_gate_status(args.project_path), compact=True))
        sys.exit(0)

    if args.command == "close-round":
        try:
            round_path = close_revision_round(args.project_path, force=args.force)
        except Exception as exc:
            safe_print(f"[ERROR] Failed to close revision round: {exc}")
            sys.exit(1)
        safe_print(f"[OK] Revision round closed: {round_path}")
        safe_print(format_revision_gate_status(get_revision_gate_status(args.project_path), compact=True))
        sys.exit(0)


if __name__ == "__main__":
    main()
