#!/usr/bin/env python3
"""PPT Master notes helper.

Usage:
    conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/notes_manager.py upsert-total <project_path> --slide 11_ending --body-file ending.md
    conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/notes_manager.py upsert-total <project_path> --slide 11_ending --body "Closing remarks"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from runtime_utils import configure_utf8_stdio, safe_print
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runtime_utils import configure_utf8_stdio, safe_print  # type: ignore


def _read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        return args.body_file.read_text(encoding="utf-8").strip()
    return (args.body or "").strip()


def upsert_total_note(project_path: Path, slide: str, body: str) -> Path:
    """Create or replace one slide section in notes/total.md."""
    notes_dir = project_path / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    total_md_path = notes_dir / "total.md"

    heading = slide.strip()
    if not heading:
        raise ValueError("--slide is required")
    if not body.strip():
        raise ValueError("Note body is required")

    new_block = f"# {heading}\n\n{body.strip()}\n"
    if not total_md_path.exists():
        total_md_path.write_text(new_block, encoding="utf-8")
        return total_md_path

    content = total_md_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    blocks: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_lines
        if current_heading is not None:
            blocks.append((current_heading, current_lines[:]))
        current_heading = None
        current_lines = []

    for line in lines:
        if line.startswith("# "):
            flush()
            current_heading = line[2:].strip()
        else:
            current_lines.append(line)
    flush()

    replaced = False
    rendered_blocks: list[str] = []
    for block_heading, block_lines in blocks:
        if block_heading == heading:
            rendered_blocks.append(new_block.strip())
            replaced = True
        else:
            block_body = "\n".join(block_lines).strip()
            rendered_blocks.append(f"# {block_heading}\n\n{block_body}" if block_body else f"# {block_heading}")

    if not replaced:
        rendered_blocks.append(new_block.strip())

    total_md_path.write_text("\n\n".join(rendered_blocks).rstrip() + "\n", encoding="utf-8")
    return total_md_path


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="PPT Master notes helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upsert_parser = subparsers.add_parser(
        "upsert-total",
        help="Create or replace one slide section in notes/total.md",
    )
    upsert_parser.add_argument("project_path", type=Path, help="Project directory path")
    upsert_parser.add_argument("--slide", required=True, help="Slide stem / heading, e.g. 11_ending")
    upsert_parser.add_argument("--body", default=None, help="Inline note body")
    upsert_parser.add_argument("--body-file", type=Path, default=None, help="Path to a UTF-8 note body file")

    args = parser.parse_args()
    if args.command == "upsert-total":
        if not args.project_path.exists():
            print(f"[ERROR] Project directory does not exist: {args.project_path}")
            sys.exit(1)
        if not args.body and not args.body_file:
            print("[ERROR] Provide --body or --body-file")
            sys.exit(1)

        body = _read_body(args)
        try:
            output = upsert_total_note(args.project_path, args.slide, body)
        except Exception as exc:
            print(f"[ERROR] Failed to update total.md: {exc}")
            sys.exit(1)
        safe_print(f"[OK] Updated notes file: {output}")


if __name__ == "__main__":
    main()


