#!/usr/bin/env python3
"""
PPT Master - Icon Reference Check Tool

Checks whether SVG icon placeholders point to real files under templates/icons/.

Usage:
    conda run --no-capture-output -n ppt-master python scripts/icon_reference_checker.py <svg_file>
    conda run --no-capture-output -n ppt-master python scripts/icon_reference_checker.py <project_path>
    conda run --no-capture-output -n ppt-master python scripts/icon_reference_checker.py <directory> --summary-only
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path

try:
    from runtime_utils import configure_utf8_stdio
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runtime_utils import configure_utf8_stdio  # type: ignore


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ICONS_DIR = SKILL_DIR / "templates" / "icons"
KNOWN_LIBRARIES = ("chunk", "tabler-filled", "tabler-outline")


@dataclass
class IconIssue:
    file: str
    icon: str
    issue: str
    suggestion: str | None = None


class IconReferenceChecker:
    """Validate SVG data-icon placeholders against the local icon library."""

    def __init__(self) -> None:
        self.results: list[dict] = []
        self.summary = {
            "total": 0,
            "passed": 0,
            "warnings": 0,
            "errors": 0,
        }
        self.icon_index = self._build_icon_index()

    def _build_icon_index(self) -> dict[str, set[str]]:
        """Load available icon stems by library."""
        index: dict[str, set[str]] = {}
        for library in KNOWN_LIBRARIES:
            lib_dir = ICONS_DIR / library
            if not lib_dir.exists():
                index[library] = set()
                continue
            index[library] = {path.stem for path in lib_dir.glob("*.svg")}
        return index

    def check_file(self, svg_file: str) -> dict:
        """Check a single SVG file."""
        svg_path = Path(svg_file)
        result = {
            "file": svg_path.name,
            "path": str(svg_path),
            "exists": svg_path.exists(),
            "errors": [],
            "warnings": [],
            "icons": [],
            "passed": True,
        }

        if not svg_path.exists():
            result["errors"].append("File does not exist")
            result["passed"] = False
            self._finalize_result(result)
            return result

        try:
            root = ET.parse(svg_path).getroot()
        except ET.ParseError as exc:
            result["errors"].append(f"XML parse error: {exc}")
            result["passed"] = False
            self._finalize_result(result)
            return result

        seen_icons: set[str] = set()
        libraries_used: set[str] = set()

        for element in root.iter():
            if self._local_name(element.tag) != "use":
                continue

            data_icon = (element.attrib.get("data-icon") or "").strip()
            if not data_icon:
                continue

            seen_icons.add(data_icon)
            result["icons"].append(data_icon)

            issue = self._validate_icon_reference(svg_path.name, data_icon)
            if issue is None:
                library = data_icon.split("/", 1)[0]
                libraries_used.add(library)
                continue

            if issue.issue == "warning":
                result["warnings"].append(self._format_issue(issue))
            else:
                result["errors"].append(self._format_issue(issue))

        if len(libraries_used) > 1:
            result["errors"].append(
                "Mixed icon libraries detected in one SVG: "
                + ", ".join(sorted(libraries_used))
                + ". One presentation must use exactly one icon library."
            )

        result["passed"] = len(result["errors"]) == 0
        self._finalize_result(result)
        return result

    def _validate_icon_reference(self, file_name: str, data_icon: str) -> IconIssue | None:
        """Validate one data-icon value."""
        if "/" not in data_icon:
            return IconIssue(
                file=file_name,
                icon=data_icon,
                issue="error",
                suggestion="Expected format library/name, e.g. chunk/signal",
            )

        library, icon_name = data_icon.split("/", 1)
        if library not in KNOWN_LIBRARIES:
            return IconIssue(
                file=file_name,
                icon=data_icon,
                issue="error",
                suggestion=f"Unknown library '{library}'. Use one of: {', '.join(KNOWN_LIBRARIES)}",
            )

        available_icons = self.icon_index.get(library, set())
        if icon_name in available_icons:
            return None

        suggestion = self._suggest_icon(library, icon_name)
        return IconIssue(
            file=file_name,
            icon=data_icon,
            issue="error",
            suggestion=suggestion,
        )

    def _suggest_icon(self, library: str, icon_name: str) -> str | None:
        """Suggest a nearby icon name from the same library."""
        available_icons = sorted(self.icon_index.get(library, set()))
        if not available_icons:
            return None

        close = get_close_matches(icon_name, available_icons, n=3, cutoff=0.45)
        if close:
            return "Closest verified matches: " + ", ".join(f"{library}/{name}" for name in close)

        parts = [part for part in icon_name.replace("_", "-").split("-") if part]
        semantic_hits = []
        for candidate in available_icons:
            candidate_lower = candidate.lower()
            if any(part.lower() in candidate_lower for part in parts):
                semantic_hits.append(candidate)
            if len(semantic_hits) >= 3:
                break

        if semantic_hits:
            return "Semantic matches in same library: " + ", ".join(
                f"{library}/{name}" for name in semantic_hits
            )

        return None

    def _format_issue(self, issue: IconIssue) -> str:
        """Render a user-facing issue string."""
        base = f"{issue.icon} -> missing local icon reference"
        if issue.suggestion:
            return f"{base}. {issue.suggestion}"
        return base

    def _local_name(self, tag: str) -> str:
        """Return XML local name without namespace."""
        return tag.split("}", 1)[-1] if "}" in tag else tag

    def _finalize_result(self, result: dict) -> None:
        """Update aggregate counters."""
        self.summary["total"] += 1
        if result["passed"]:
            if result["warnings"]:
                self.summary["warnings"] += 1
            else:
                self.summary["passed"] += 1
        else:
            self.summary["errors"] += 1
        self.results.append(result)

    def check_directory(self, target: str, print_results: bool = True) -> list[dict]:
        """Check one SVG, an svg_output directory, or a project directory."""
        path = Path(target)
        if not path.exists():
            print(f"[ERROR] Path does not exist: {target}")
            return []

        if path.is_file():
            svg_files = [path]
        else:
            svg_dir = path / "svg_output" if (path / "svg_output").exists() else path
            svg_files = sorted(svg_dir.glob("*.svg"))

        if not svg_files:
            print("[WARN] No SVG files found")
            return []

        if print_results:
            print(f"\n[SCAN] Checking {len(svg_files)} SVG file(s) for icon references...\n")

        for svg_file in svg_files:
            result = self.check_file(str(svg_file))
            if print_results:
                self._print_result(result)

        return self.results

    def _print_result(self, result: dict) -> None:
        """Print one result block."""
        if result["passed"]:
            status = "Passed (with warnings)" if result["warnings"] else "Passed"
            prefix = "[WARN]" if result["warnings"] else "[OK]"
        else:
            status = "Failed"
            prefix = "[ERROR]"

        print(f"{prefix} {result['file']} - {status}")

        if result["icons"]:
            print(f"   icons: {', '.join(result['icons'])}")

        for error in result["errors"]:
            print(f"   [ERROR] {error}")

        for warning in result["warnings"]:
            print(f"   [WARN] {warning}")

        print()

    def summary_dict(self) -> dict:
        """Return machine-readable results."""
        return {
            "summary": dict(self.summary),
            "results": self.results,
        }

    def print_summary(self, compact: bool = False) -> None:
        """Print aggregate summary."""
        if compact:
            print(
                "Icon summary: "
                f"total={self.summary['total']} "
                f"passed={self.summary['passed']} "
                f"warnings={self.summary['warnings']} "
                f"errors={self.summary['errors']}"
            )
            return

        print("=" * 80)
        print("[SUMMARY] Icon Reference Check Summary")
        print("=" * 80)
        print(f"\nTotal files: {self.summary['total']}")
        print(f"  [OK] Fully passed: {self.summary['passed']}")
        print(f"  [WARN] With warnings: {self.summary['warnings']}")
        print(f"  [ERROR] With errors: {self.summary['errors']}")

    def apply_rewrite_map(self, target: str, rewrite_map: dict[str, str]) -> int:
        """Rewrite data-icon references in one SVG, a project, or a directory."""
        path = Path(target)
        if not path.exists():
            print(f"[ERROR] Path does not exist: {target}")
            return 1

        if path.is_file():
            svg_files = [path]
        else:
            svg_dir = path / "svg_output" if (path / "svg_output").exists() else path
            svg_files = sorted(svg_dir.glob("*.svg"))

        if not svg_files:
            print("[WARN] No SVG files found")
            return 1

        normalized_map: dict[str, str] = {}
        for old_icon, new_icon in rewrite_map.items():
            old_ref = str(old_icon).strip()
            new_ref = str(new_icon).strip()
            if not old_ref or not new_ref:
                raise ValueError("Rewrite map values must be non-empty icon references")
            issue = self._validate_icon_reference("<rewrite-map>", new_ref)
            if issue is not None:
                raise ValueError(f"Replacement target is invalid: {new_ref}")
            normalized_map[old_ref] = new_ref

        updated_files = 0
        total_rewrites = 0
        for svg_file in svg_files:
            changed = self._rewrite_svg_file(svg_file, normalized_map)
            if changed > 0:
                updated_files += 1
                total_rewrites += changed
                print(f"[OK] {svg_file.name}: rewrote {changed} icon reference(s)")

        if total_rewrites == 0:
            print("[INFO] No matching icon references found for rewrite map")
            return 1

        print(f"[DONE] Updated {updated_files} file(s), rewrote {total_rewrites} icon reference(s)")
        return 0

    def _rewrite_svg_file(self, svg_file: Path, rewrite_map: dict[str, str]) -> int:
        """Rewrite one SVG file in place and return number of replacements."""
        try:
            tree = ET.parse(svg_file)
        except ET.ParseError as exc:
            raise ValueError(f"XML parse error in {svg_file.name}: {exc}") from exc

        root = tree.getroot()
        changes = 0
        for element in root.iter():
            if self._local_name(element.tag) != "use":
                continue
            data_icon = (element.attrib.get("data-icon") or "").strip()
            if not data_icon or data_icon not in rewrite_map:
                continue
            element.set("data-icon", rewrite_map[data_icon])
            changes += 1

        if changes > 0:
            tree.write(svg_file, encoding="utf-8", xml_declaration=True)
        return changes


def main() -> None:
    """Run the CLI entry point."""
    configure_utf8_stdio()

    parser = argparse.ArgumentParser(
        description="PPT Master - Icon Reference Check Tool",
    )
    parser.add_argument("target", help="SVG file, project directory, or svg_output directory")
    parser.add_argument("--summary-only", action="store_true", help="Only print the final summary")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text")
    parser.add_argument(
        "--rewrite-map-json",
        type=Path,
        default=None,
        help="Apply a JSON object of old_icon:new_icon replacements before exiting",
    )
    args = parser.parse_args()

    checker = IconReferenceChecker()
    if args.rewrite_map_json is not None:
        try:
            rewrite_map = json.loads(args.rewrite_map_json.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[ERROR] Failed to read rewrite map JSON: {exc}")
            sys.exit(1)
        if not isinstance(rewrite_map, dict):
            print("[ERROR] --rewrite-map-json must contain a JSON object of old_icon:new_icon pairs")
            sys.exit(1)
        sys.exit(checker.apply_rewrite_map(args.target, rewrite_map))

    checker.check_directory(args.target, print_results=not args.summary_only and not args.json)

    if args.json:
        print(json.dumps(checker.summary_dict(), ensure_ascii=True, indent=2))
    else:
        checker.print_summary(compact=args.summary_only)

    sys.exit(1 if checker.summary["errors"] > 0 else 0)


if __name__ == "__main__":
    main()
