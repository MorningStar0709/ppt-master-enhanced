#!/usr/bin/env python3
"""Generate a fixed-canvas HTML preview page for a chosen project SVG source."""

from __future__ import annotations

import argparse
from html import escape
import os
from pathlib import Path

try:
    from runtime_utils import configure_utf8_stdio, safe_print
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runtime_utils import configure_utf8_stdio, safe_print  # type: ignore


def _find_svg_files(project_path: Path, source_dir: str) -> tuple[Path, list[Path]]:
    """Resolve the source directory and SVG files."""
    svg_dir = project_path / source_dir
    if not svg_dir.exists():
        raise FileNotFoundError(f"SVG source directory does not exist: {svg_dir}")

    svg_files = sorted(svg_dir.glob("*.svg"))
    if not svg_files:
        raise FileNotFoundError(f"No SVG files found in: {svg_dir}")

    return svg_dir, svg_files


def inspect_preview_source(project_path: Path, source_dir: str = "svg_output") -> dict:
    """Return the resolved preview source metadata without writing files."""
    svg_dir, svg_files = _find_svg_files(project_path, source_dir)
    return {
        "project_path": str(project_path),
        "source_dir": str(svg_dir),
        "source_name": svg_dir.name,
        "slide_count": len(svg_files),
        "svg_files": [str(path) for path in svg_files],
    }


def _relative_href(from_file: Path, target_file: Path) -> str:
    """Return a browser-friendly relative href."""
    return os.path.relpath(target_file, from_file.parent).replace("\\", "/")


def _build_html(project_path: Path, source_dir: Path, svg_files: list[Path], title: str) -> str:
    """Build the preview HTML document."""
    output_file = project_path / "review" / "preview_deck.html"
    items: list[str] = []
    for index, svg_file in enumerate(svg_files, start=1):
        href = _relative_href(output_file, svg_file)
        items.append(
            f"""
    <section class="slide-card">
      <div class="slide-meta">
        <span class="slide-index">{index:02d}</span>
        <span class="slide-name">{escape(svg_file.name)}</span>
      </div>
      <div class="slide-frame">
        <img src="{escape(href)}" alt="{escape(svg_file.name)}" loading="lazy" />
      </div>
    </section>""".rstrip()
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #0b1020;
      --panel: #11182d;
      --panel-border: #2a3656;
      --text: #f2f5ff;
      --muted: #a8b2d1;
      --accent: #7fb3ff;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      padding: 24px;
      font-family: "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
    }}
    p {{
      margin: 0 0 20px;
      color: var(--muted);
    }}
    .deck {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(520px, 1fr));
      gap: 20px;
    }}
    .slide-card {{
      padding: 16px;
      border: 1px solid var(--panel-border);
      border-radius: 16px;
      background: var(--panel);
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.24);
    }}
    .slide-meta {{
      display: flex;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
      color: var(--muted);
      font-size: 14px;
    }}
    .slide-index {{
      min-width: 40px;
      padding: 4px 8px;
      border-radius: 999px;
      color: var(--accent);
      background: rgba(127, 179, 255, 0.12);
      text-align: center;
      font-weight: 700;
    }}
    .slide-frame {{
      position: relative;
      width: 100%;
      aspect-ratio: 16 / 9;
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      overflow: hidden;
      background:
        linear-gradient(45deg, rgba(255,255,255,0.03) 25%, transparent 25%, transparent 75%, rgba(255,255,255,0.03) 75%),
        linear-gradient(45deg, rgba(255,255,255,0.03) 25%, transparent 25%, transparent 75%, rgba(255,255,255,0.03) 75%);
      background-size: 20px 20px;
      background-position: 0 0, 10px 10px;
    }}
    .slide-frame img {{
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: white;
    }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p>Project: {escape(project_path.name)} | Source: {escape(source_dir.name)} | Slides: {len(svg_files)}</p>
  <main class="deck">
{''.join(items)}
  </main>
</body>
</html>
"""


def generate_preview_page(
    project_path: Path,
    source_dir: str = "svg_output",
    output_path: Path | None = None,
    title: str = "SVG Deck Preview",
) -> dict:
    """Generate preview HTML and return metadata for verification tooling."""
    resolved_source_dir, svg_files = _find_svg_files(project_path, source_dir)
    final_output = output_path or (project_path / "review" / "preview_deck.html")
    final_output.parent.mkdir(parents=True, exist_ok=True)
    html = _build_html(project_path, resolved_source_dir, svg_files, title)
    final_output.write_text(html, encoding="utf-8")
    return {
        "output": str(final_output),
        "source_dir": str(resolved_source_dir),
        "source_name": resolved_source_dir.name,
        "slide_count": len(svg_files),
        "title": title,
    }


def main() -> None:
    """CLI entry point."""
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="PPT Master - Generate HTML preview for a chosen SVG source under the project",
    )
    parser.add_argument("project_path", type=Path, help="Project directory path")
    parser.add_argument(
        "-s",
        "--source",
        default="svg_output",
        help="Source directory name under the project, e.g. svg_output, svg_final, or review/preview_finalized (default: svg_output)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output HTML path (default: <project>/review/preview_deck.html)",
    )
    parser.add_argument(
        "--title",
        default="SVG Deck Preview",
        help="Preview page title",
    )
    args = parser.parse_args()

    project_path = args.project_path
    if not project_path.exists():
        raise SystemExit(f"Error: Project path does not exist: {project_path}")

    preview = generate_preview_page(
        project_path=project_path,
        source_dir=args.source,
        output_path=args.output,
        title=args.title,
    )
    safe_print(f"[OK] Preview page written: {preview['output']}")


if __name__ == "__main__":
    main()
