#!/usr/bin/env python3
"""Targeted lookup for chart templates and icon assets.

Usage:
    conda run -n ppt-master python scripts/asset_lookup.py charts roadmap
    conda run -n ppt-master python scripts/asset_lookup.py charts comparison --limit 5
    conda run -n ppt-master python scripts/asset_lookup.py icons home --library chunk
    conda run -n ppt-master python scripts/asset_lookup.py icons chart --library tabler-outline
    conda run -n ppt-master python scripts/asset_lookup.py icons chunk/signal --exact
"""

from __future__ import annotations

import argparse
import json
import sys
from difflib import get_close_matches
from pathlib import Path

try:
    from runtime_utils import (
        configure_utf8_stdio,
        format_display_path,
        get_command_reports_dir,
        resolve_repo_root,
        safe_print,
        write_json_report,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runtime_utils import (  # type: ignore
        configure_utf8_stdio,
        format_display_path,
        get_command_reports_dir,
        resolve_repo_root,
        safe_print,
        write_json_report,
    )


TOOLS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TOOLS_DIR.parent
REPO_ROOT = resolve_repo_root(__file__)
CHARTS_INDEX_PATH = SKILL_DIR / "templates" / "charts" / "charts_index.json"
ICONS_DIR = SKILL_DIR / "templates" / "icons"
REPORTS_DIR = get_command_reports_dir(__file__)


def default_report_path() -> Path:
    return REPORTS_DIR / "asset_lookup_last.json"


def _display_path(path: Path) -> str:
    return format_display_path(path, __file__)


def main() -> None:
    """Run CLI."""
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Targeted asset lookup for ppt-master")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--report-file", type=Path, default=None, help="Optional JSON report path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    charts_parser = subparsers.add_parser("charts", help="Search chart templates by keyword")
    charts_parser.add_argument("keyword", help="Keyword or intent, e.g. roadmap, comparison, KPI")
    charts_parser.add_argument("--limit", type=int, default=8, help="Maximum number of results")

    icons_parser = subparsers.add_parser("icons", help="Search icon files by keyword")
    icons_parser.add_argument("keyword", help="Icon keyword, e.g. home, chart, shield")
    icons_parser.add_argument(
        "--library",
        choices=["chunk", "tabler-filled", "tabler-outline", "all"],
        default="all",
        help="Limit search to one icon library",
    )
    icons_parser.add_argument("--limit", type=int, default=12, help="Maximum number of results")
    icons_parser.add_argument(
        "--exact",
        action="store_true",
        help="Validate one exact icon reference (library/name) instead of running semantic search",
    )

    args = parser.parse_args()

    if args.command == "charts":
        sys.exit(run_chart_lookup(args.keyword, args.limit, json_output=args.json, report_file=args.report_file))
    if args.command == "icons":
        sys.exit(run_icon_lookup(args.keyword, args.library, args.limit, exact=args.exact, json_output=args.json, report_file=args.report_file))


def run_chart_lookup(keyword: str, limit: int, *, json_output: bool = False, report_file: Path | None = None) -> int:
    """Search chart metadata by keyword."""
    data = json.loads(CHARTS_INDEX_PATH.read_text(encoding="utf-8"))
    needle = keyword.strip().lower()

    direct = []
    for quick_key, chart_names in data.get("quickLookup", {}).items():
        if needle in quick_key.lower():
            for chart_name in chart_names:
                direct.append((chart_name, "quickLookup", quick_key))

    scored: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for chart_name, via, source in direct:
        if chart_name in seen:
            continue
        seen.add(chart_name)
        scored.append((300, chart_name, f"{via}:{source}"))

    for chart_name, meta in data.get("charts", {}).items():
        haystacks = [
            meta.get("label", ""),
            meta.get("summary", ""),
            " ".join(meta.get("keywords", [])),
        ]
        score = score_texts(needle, haystacks)
        if score <= 0 or chart_name in seen:
            continue
        seen.add(chart_name)
        scored.append((score, chart_name, "metadata"))

    scored.sort(key=lambda item: (-item[0], item[1]))
    payload = {
        "ok": bool(scored),
        "command": "charts",
        "keyword": keyword,
        "results": [],
    }

    for score, chart_name, source in scored[:limit]:
        meta = data["charts"][chart_name]
        payload["results"].append({
            "chart_name": chart_name,
            "source": source,
            "score": score,
            "label": meta.get("label", "-"),
            "summary": meta.get("summary", "-"),
            "keywords": meta.get("keywords", []),
            "file": f"templates/charts/{chart_name}.svg",
        })

    target = report_file or default_report_path()
    write_json_report(target, payload)

    if not scored:
        safe_print(f"No chart templates matched: {keyword}")
        safe_print(f"Report file: {_display_path(target)}")
        if json_output:
            safe_print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 1

    if json_output:
        safe_print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    safe_print(f"Chart matches for: {keyword}")
    for score, chart_name, source in scored[:limit]:
        meta = data["charts"][chart_name]
        keywords = ", ".join(meta.get("keywords", []))
        safe_print(f"- {chart_name} [{source}, score={score}]")
        safe_print(f"  label: {meta.get('label', '-')}")
        safe_print(f"  summary: {meta.get('summary', '-')}")
        safe_print(f"  keywords: {keywords}")
        safe_print(f"  file: templates/charts/{chart_name}.svg")
    safe_print(f"Report file: {_display_path(target)}")
    return 0


def run_icon_lookup(keyword: str, library: str, limit: int, exact: bool = False, *, json_output: bool = False, report_file: Path | None = None) -> int:
    """Search icon files by filename substring or validate an exact icon reference."""
    if exact:
        return run_icon_exact_check(keyword, library, json_output=json_output, report_file=report_file)

    needle = keyword.strip().lower()
    libraries = ["chunk", "tabler-filled", "tabler-outline"] if library == "all" else [library]
    matches: list[str] = []

    for lib in libraries:
        lib_dir = ICONS_DIR / lib
        if not lib_dir.exists():
            continue
        for svg_file in sorted(lib_dir.glob("*.svg")):
            if needle in svg_file.stem.lower():
                matches.append(f"{lib}/{svg_file.stem}")

    payload = {
        "ok": bool(matches),
        "command": "icons",
        "keyword": keyword,
        "library": library,
        "exact": False,
        "results": matches[:limit],
    }
    target = report_file or default_report_path()
    write_json_report(target, payload)

    if not matches:
        safe_print(f"No icons matched: {keyword}")
        safe_print(f"Report file: {_display_path(target)}")
        if json_output:
            safe_print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 1

    if json_output:
        safe_print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    safe_print(f"Icon matches for: {keyword}")
    for match in matches[:limit]:
        safe_print(f"- {match}")
    safe_print(f"Report file: {_display_path(target)}")
    return 0


def run_icon_exact_check(keyword: str, library: str, *, json_output: bool = False, report_file: Path | None = None) -> int:
    """Validate one exact icon reference in library/name format."""
    raw = keyword.strip()
    target = report_file or default_report_path()
    if not raw:
        safe_print("Exact icon check requires a non-empty icon reference")
        write_json_report(target, {"ok": False, "command": "icons", "exact": True, "error": "empty icon reference"})
        return 1

    if "/" not in raw:
        safe_print("Exact icon check expects format library/name, e.g. chunk/signal")
        write_json_report(target, {"ok": False, "command": "icons", "exact": True, "error": "invalid icon reference format"})
        return 1

    requested_library, icon_name = raw.split("/", 1)
    requested_library = requested_library.strip()
    icon_name = icon_name.strip()

    if not requested_library or not icon_name:
        safe_print("Exact icon check expects format library/name, e.g. chunk/signal")
        write_json_report(target, {"ok": False, "command": "icons", "exact": True, "error": "invalid icon reference format"})
        return 1

    if library != "all" and requested_library != library:
        safe_print(
            f"Exact icon check mismatch: reference uses library '{requested_library}' "
            f"but --library={library}"
        )
        write_json_report(target, {"ok": False, "command": "icons", "exact": True, "error": "library mismatch"})
        return 1

    lib_dir = ICONS_DIR / requested_library
    if not lib_dir.exists():
        safe_print(
            f"Library not found: {requested_library}. "
            "Use one of: chunk, tabler-filled, tabler-outline"
        )
        write_json_report(target, {"ok": False, "command": "icons", "exact": True, "error": "library not found"})
        return 1

    exact_path = lib_dir / f"{icon_name}.svg"
    if exact_path.exists():
        payload = {
            "ok": True,
            "command": "icons",
            "exact": True,
            "keyword": keyword,
            "result": {
                "icon": f"{requested_library}/{icon_name}",
                "file": f"templates/icons/{requested_library}/{icon_name}.svg",
            },
        }
        write_json_report(target, payload)
        if json_output:
            safe_print(json.dumps(payload, ensure_ascii=True, indent=2))
            return 0
        safe_print(f"Exact icon match: {requested_library}/{icon_name}")
        safe_print(f"file: templates/icons/{requested_library}/{icon_name}.svg")
        safe_print(f"Report file: {_display_path(target)}")
        return 0

    available_icons = sorted(path.stem for path in lib_dir.glob("*.svg"))
    close_matches = [
        candidate
        for candidate in get_close_matches(icon_name, available_icons, n=5, cutoff=0.45)
        if len(candidate) >= 2
    ]
    semantic_hits = []
    parts = [part for part in icon_name.replace("_", "-").split("-") if part]
    for candidate in available_icons:
        candidate_lower = candidate.lower()
        if any(part.lower() in candidate_lower for part in parts):
            if candidate not in close_matches:
                semantic_hits.append(candidate)
        if len(semantic_hits) >= 5:
            break

    payload = {
        "ok": False,
        "command": "icons",
        "exact": True,
        "keyword": keyword,
        "closest_matches": [f"{requested_library}/{candidate}" for candidate in close_matches],
        "semantic_matches": [f"{requested_library}/{candidate}" for candidate in semantic_hits],
    }
    write_json_report(target, payload)
    if json_output:
        safe_print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 1

    safe_print(f"No exact icon match: {requested_library}/{icon_name}")
    if close_matches:
        safe_print("Closest verified names in same library:")
        for candidate in close_matches:
            safe_print(f"- {requested_library}/{candidate}")
    elif semantic_hits:
        safe_print("Semantic matches in same library:")
        for candidate in semantic_hits:
            safe_print(f"- {requested_library}/{candidate}")
    else:
        safe_print(
            "No close verified name found. "
            "Next step: run one semantic lookup pass with up to 3 keywords, then switch to fallback if still unresolved."
        )
    safe_print(f"Report file: {_display_path(target)}")
    return 1


def score_texts(needle: str, haystacks: list[str]) -> int:
    """Very small heuristic scorer for keyword lookup."""
    score = 0
    for text in haystacks:
        lower = text.lower()
        if needle == lower:
            score = max(score, 260)
        elif needle in lower:
            score = max(score, 180)

        tokens = [token.strip().lower() for token in text.replace("/", " ").replace(",", " ").split()]
        if needle in tokens:
            score = max(score, 220)

    return score


if __name__ == "__main__":
    main()
