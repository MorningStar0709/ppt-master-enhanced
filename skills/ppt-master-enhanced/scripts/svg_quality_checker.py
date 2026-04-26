#!/usr/bin/env python3
"""
PPT Master - SVG Quality Check Tool

Checks whether SVG files comply with project technical specifications.

Usage:
    conda run --no-capture-output -n ppt-master python scripts/svg_quality_checker.py <svg_file>
    conda run --no-capture-output -n ppt-master python scripts/svg_quality_checker.py <directory>
    conda run --no-capture-output -n ppt-master python scripts/svg_quality_checker.py --all examples --summary-only
"""

import argparse
import json
import sys
import re
import os
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
import xml.etree.ElementTree as ET

try:
    from runtime_utils import configure_utf8_stdio
    from icon_reference_checker import IconReferenceChecker
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runtime_utils import configure_utf8_stdio  # type: ignore
    from icon_reference_checker import IconReferenceChecker  # type: ignore

try:
    from project_utils import CANVAS_FORMATS
    from error_helper import ErrorHelper
except ImportError:
    print("Warning: Unable to import dependency modules")
    CANVAS_FORMATS = {}
    ErrorHelper = None


class SVGQualityChecker:
    """SVG quality checker"""

    def __init__(
        self,
        icon_checker: IconReferenceChecker | None = None,
        warn_on_icon_placeholders: bool = True,
    ):
        self.results = []
        self.summary = {
            'total': 0,
            'passed': 0,
            'warnings': 0,
            'errors': 0
        }
        self.issue_types = defaultdict(int)
        self.icon_checker = icon_checker
        self.warn_on_icon_placeholders = warn_on_icon_placeholders

    def check_file(self, svg_file: str, expected_format: str = None) -> Dict:
        """
        Check a single SVG file

        Args:
            svg_file: SVG file path
            expected_format: Expected canvas format (e.g., 'ppt169')

        Returns:
            Check result dictionary
        """
        svg_path = Path(svg_file)

        if not svg_path.exists():
            return {
                'file': str(svg_file),
                'exists': False,
                'errors': ['File does not exist'],
                'warnings': [],
                'passed': False
            }

        result = {
            'file': svg_path.name,
            'path': str(svg_path),
            'exists': True,
            'errors': [],
            'warnings': [],
            'info': {},
            'passed': True
        }

        try:
            with open(svg_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 0. XML parse must succeed before other checks mean anything.
            root = self._check_xml_parse(content, result)
            if root is None:
                result['passed'] = False
                self._finalize_result(result)
                return result

            # 1. Check viewBox
            self._check_viewbox(content, result, expected_format)

            # 2. Check forbidden elements
            self._check_forbidden_elements(content, root, result)

            # 3. Check fonts
            self._check_fonts(content, result)

            # 4. Check width/height consistency with viewBox
            self._check_dimensions(content, result)

            # 5. Check text wrapping methods
            self._check_text_elements(content, result)

            # 6. Check image references (file existence and resolution)
            self._check_image_references(content, svg_path, result)

            # Determine pass/fail
            result['passed'] = len(result['errors']) == 0

        except Exception as e:
            result['errors'].append(f"Failed to read file: {e}")
            result['passed'] = False

        self._finalize_result(result)
        return result

    def _finalize_result(self, result: Dict) -> None:
        """Update summary counters and cache the result."""
        self.summary['total'] += 1
        if result['passed']:
            if result['warnings']:
                self.summary['warnings'] += 1
            else:
                self.summary['passed'] += 1
        else:
            self.summary['errors'] += 1

        # Categorize issue types
        for error in result['errors']:
            self.issue_types[self._categorize_issue(error)] += 1

        self.results.append(result)

    def _check_xml_parse(self, content: str, result: Dict):
        """Ensure SVG is valid XML and return parsed root."""
        try:
            return ET.fromstring(content)
        except ET.ParseError as exc:
            result['errors'].append(f"XML parse error: {exc}")
            return None

    def _check_viewbox(self, content: str, result: Dict, expected_format: str = None):
        """Check viewBox attribute"""
        viewbox_match = re.search(r'viewBox="([^"]+)"', content)

        if not viewbox_match:
            result['errors'].append("Missing viewBox attribute")
            return

        viewbox = viewbox_match.group(1)
        result['info']['viewbox'] = viewbox

        # Check format
        if not re.match(r'0 0 \d+ \d+', viewbox):
            result['warnings'].append(f"Unusual viewBox format: {viewbox}")

        # Check if it matches expected format
        if expected_format and expected_format in CANVAS_FORMATS:
            expected_viewbox = CANVAS_FORMATS[expected_format]['viewbox']
            if viewbox != expected_viewbox:
                result['errors'].append(
                    f"viewBox mismatch: expected '{expected_viewbox}', got '{viewbox}'"
                )

    def _check_forbidden_elements(self, content: str, root, result: Dict):
        """Check forbidden elements (blocklist)"""
        content_lower = content.lower()

        # ============================================================
        # Forbidden elements blocklist - PPT incompatible
        # ============================================================

        # Clipping / masking
        # clipPath is ONLY allowed on <image> elements (converter maps to DrawingML
        # picture geometry).  On shapes it is pointless (just draw the target shape)
        # and breaks the SVG PPTX rendering.
        if '<clippath' in content_lower:
            # clip-path on non-image elements → error
            clip_on_non_image = re.search(
                r'<(?!image\b)\w+[^>]*\bclip-path\s*=', content, re.IGNORECASE)
            if clip_on_non_image:
                result['errors'].append(
                    "clip-path is only allowed on <image> elements — "
                    "for shapes, draw the target shape directly instead of clipping")
            # Check that every clip-path reference has a matching <clipPath> def
            clip_refs = re.findall(r'clip-path\s*=\s*["\']url\(#([^)]+)\)', content)
            for ref_id in clip_refs:
                if f'id="{ref_id}"' not in content and f"id='{ref_id}'" not in content:
                    result['errors'].append(
                        f"clip-path references #{ref_id} but no matching "
                        f"<clipPath id=\"{ref_id}\"> definition found")
        if '<mask' in content_lower:
            result['errors'].append("Detected forbidden <mask> element (PPT does not support SVG masks)")

        # Style system
        if '<style' in content_lower:
            result['errors'].append("Detected forbidden <style> element (use inline attributes instead)")
        if re.search(r'\bclass\s*=', content):
            result['errors'].append("Detected forbidden class attribute (use inline styles instead)")
        # id attribute: only report error when <style> also exists (id is harmful only with CSS selectors)
        # id inside <defs> for linearGradient/filter etc. is required, Inkscape also auto-adds id to elements,
        # standalone id attributes have no impact on PPT export
        if '<style' in content_lower and re.search(r'\bid\s*=', content):
            result['errors'].append(
                "Detected id attribute used with <style> (CSS selectors forbidden, use inline styles instead)"
            )
        if re.search(r'<\?xml-stylesheet\b', content_lower):
            result['errors'].append("Detected forbidden xml-stylesheet (external CSS references forbidden)")
        if re.search(r'<link[^>]*rel\s*=\s*["\']stylesheet["\']', content_lower):
            result['errors'].append("Detected forbidden <link rel=\"stylesheet\"> (external CSS references forbidden)")
        if re.search(r'@import\s+', content_lower):
            result['errors'].append("Detected forbidden @import (external CSS references forbidden)")

        # Structure / nesting
        if '<foreignobject' in content_lower:
            result['errors'].append(
                "Detected forbidden <foreignObject> element (use <tspan> for manual line breaks)")
        has_symbol = '<symbol' in content_lower
        has_use = re.search(r'<use\b', content_lower) is not None
        if has_symbol and has_use:
            result['errors'].append(
                "Detected forbidden <symbol> + <use> complex usage "
                "(use basic shapes, <use data-icon=\"library/name\"/> for icons, "
                "or local <use href=\"#id\"> references that stay within the same SVG)"
            )
        self._check_use_elements(root, result)
        # marker-start / marker-end are conditionally allowed (see shared-standards.md §1.1).
        # The converter maps qualifying <marker> defs to native DrawingML <a:headEnd>/<a:tailEnd>.
        # We only warn when a marker is used without an obvious <defs> definition in the same file.
        if re.search(r'\bmarker-(?:start|end)\s*=\s*["\']url\(#([^)]+)\)', content_lower):
            if '<marker' not in content_lower:
                result['errors'].append(
                    "Detected marker-start/marker-end referencing a marker id, "
                    "but no <marker> element found in the file")

        # Text / fonts
        if '<textpath' in content_lower:
            result['errors'].append("Detected forbidden <textPath> element (path text is incompatible with PPT)")
        if '@font-face' in content_lower:
            result['errors'].append("Detected forbidden @font-face (use system font stack)")

        # Animation / interaction
        if re.search(r'<animate', content_lower):
            result['errors'].append("Detected forbidden SMIL animation element <animate*> (SVG animations are not exported)")
        if re.search(r'<set\b', content_lower):
            result['errors'].append("Detected forbidden SMIL animation element <set> (SVG animations are not exported)")
        if '<script' in content_lower:
            result['errors'].append("Detected forbidden <script> element (scripts and event handlers forbidden)")
        if re.search(r'\bon\w+\s*=', content):  # onclick, onload etc.
            result['errors'].append("Detected forbidden event attributes (e.g., onclick, onload)")

        # Other discouraged elements
        if '<iframe' in content_lower:
            result['errors'].append("Detected <iframe> element (should not appear in SVG)")
        if re.search(r'rgba\s*\(', content_lower):
            result['errors'].append("Detected forbidden rgba() color (use fill-opacity/stroke-opacity instead)")
        if re.search(r'<g[^>]*\sopacity\s*=', content_lower):
            result['errors'].append("Detected forbidden <g opacity> (set opacity on each child element individually)")
        if re.search(r'<image[^>]*\sopacity\s*=', content_lower):
            result['errors'].append("Detected forbidden <image opacity> (use overlay mask approach)")

    def _check_use_elements(self, root, result: Dict):
        """Check <use> elements more strictly than plain regex scanning."""
        defined_ids = set()
        for element in root.iter():
            element_id = element.attrib.get('id')
            if element_id:
                defined_ids.add(element_id)

        for use_el in root.iter():
            if self._local_name(use_el.tag) != 'use':
                continue

            data_icon = use_el.attrib.get('data-icon', '').strip()
            href = (
                use_el.attrib.get('href')
                or use_el.attrib.get('{http://www.w3.org/1999/xlink}href')
                or ''
            ).strip()

            if data_icon:
                if self.icon_checker is None and self.warn_on_icon_placeholders:
                    # Placeholders are allowed in svg_output, but raw preview may not show them.
                    result['warnings'].append(
                        f"<use data-icon=\"{data_icon}\"> is an icon placeholder; raw SVG preview will not show the final embedded icon until finalize_svg.py runs"
                    )
                elif self.icon_checker is not None:
                    icon_issue = self.icon_checker._validate_icon_reference(result['file'], data_icon)
                    if icon_issue is not None:
                        result['errors'].append(self.icon_checker._format_issue(icon_issue))
                continue

            if not href:
                result['errors'].append(
                    "Detected <use> element without data-icon or href/xlink:href target"
                )
                continue

            if not href.startswith('#'):
                result['errors'].append(
                    f"Detected unsupported <use> href target '{href}'. "
                    "For icons, use <use data-icon=\"library/name\"/> so finalize_svg.py can embed it; "
                    "for non-icon reuse, only same-file <use href=\"#id\"> references are allowed."
                )
                continue

            if href.startswith('#') and href[1:] not in defined_ids:
                result['errors'].append(
                    f"Detected <use> referencing missing id {href}"
                )

    def _local_name(self, tag: str) -> str:
        """Return the local XML name without namespace."""
        return tag.split('}', 1)[-1] if '}' in tag else tag

    def _check_fonts(self, content: str, result: Dict):
        """Check font usage"""
        # Find font-family declarations
        font_matches = re.findall(
            r'font-family[:\s]*["\']([^"\']+)["\']', content, re.IGNORECASE)

        if font_matches:
            result['info']['fonts'] = list(set(font_matches))

            # Check if system UI font stack is used
            recommended_fonts = [
                'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI']

            for font_family in font_matches:
                has_recommended = any(
                    rec in font_family for rec in recommended_fonts)

                if not has_recommended:
                    result['warnings'].append(
                        f"Recommend using system UI font stack, current: {font_family}"
                    )
                    break  # Only warn once

    def _check_dimensions(self, content: str, result: Dict):
        """Check width/height consistency with viewBox"""
        width_match = re.search(r'width="(\d+)"', content)
        height_match = re.search(r'height="(\d+)"', content)

        if width_match and height_match:
            width = width_match.group(1)
            height = height_match.group(1)
            result['info']['dimensions'] = f"{width}x{height}"

            # Check consistency with viewBox
            if 'viewbox' in result['info']:
                viewbox_parts = result['info']['viewbox'].split()
                if len(viewbox_parts) == 4:
                    vb_width, vb_height = viewbox_parts[2], viewbox_parts[3]
                    if width != vb_width or height != vb_height:
                        result['warnings'].append(
                            f"width/height ({width}x{height}) does not match viewBox "
                            f"({vb_width}x{vb_height})"
                        )

    def _check_text_elements(self, content: str, result: Dict):
        """Check text elements and wrapping methods"""
        # Count text and tspan elements
        text_count = content.count('<text')
        tspan_count = content.count('<tspan')

        result['info']['text_elements'] = text_count
        result['info']['tspan_elements'] = tspan_count

        # Check for overly long single-line text (may need wrapping)
        text_matches = re.findall(r'<text[^>]*>([^<]{100,})</text>', content)
        if text_matches:
            result['warnings'].append(
                f"Detected {len(text_matches)} potentially overly long single-line text(s) (consider using tspan for wrapping)"
            )

    def _check_image_references(self, content: str, svg_path: Path, result: Dict):
        """Check image file existence and resolution vs display size."""
        # Find all <image ...> elements (capture the full tag)
        img_tag_pattern = re.compile(r'<image\b([^>]*)/?>', re.IGNORECASE)

        svg_dir = svg_path.parent
        checked = set()

        for tag_match in img_tag_pattern.finditer(content):
            attrs = tag_match.group(1)

            # Extract href (prefer href over xlink:href)
            href_match = (
                re.search(r'\bhref="(?!data:)([^"]+)"', attrs) or
                re.search(r'\bxlink:href="(?!data:)([^"]+)"', attrs)
            )
            if not href_match:
                continue

            href = href_match.group(1)
            if href in checked:
                continue
            checked.add(href)

            if self._is_absolute_local_image_href(href):
                result['errors'].append(
                    f"Image href must be relative to the SVG/project, not an absolute filesystem path: {href}"
                )
                continue

            # Resolve path relative to SVG file directory
            img_path = (svg_dir / href).resolve()

            if not img_path.exists():
                result['errors'].append(
                    f"Image file not found: {href} (resolved to {img_path})")
                continue

            # Check resolution vs display size
            w_match = re.search(r'\bwidth="([^"]+)"', attrs)
            h_match = re.search(r'\bheight="([^"]+)"', attrs)
            display_w_str = w_match.group(1) if w_match else None
            display_h_str = h_match.group(1) if h_match else None
            if not display_w_str or not display_h_str:
                continue

            try:
                display_w = float(display_w_str)
                display_h = float(display_h_str)
            except (ValueError, TypeError):
                continue

            try:
                from PIL import Image as PILImage
                with PILImage.open(img_path) as img:
                    actual_w, actual_h = img.size

                if actual_w < display_w or actual_h < display_h:
                    result['warnings'].append(
                        f"Image {href} is {actual_w}x{actual_h} but displayed at "
                        f"{int(display_w)}x{int(display_h)} — may appear blurry")
                elif actual_w > display_w * 4 and actual_h > display_h * 4:
                    result['warnings'].append(
                        f"Image {href} is {actual_w}x{actual_h} but displayed at "
                        f"{int(display_w)}x{int(display_h)} — consider downsizing "
                        f"to reduce file size")
            except ImportError:
                pass  # PIL not available, skip resolution check
            except Exception:
                pass  # Image unreadable, skip resolution check

    def _is_absolute_local_image_href(self, href: str) -> bool:
        """Return True when href points to a local filesystem absolute path."""
        lowered = href.lower()
        return (
            lowered.startswith('file:///')
            or re.match(r'^[a-zA-Z]:[\\/]', href) is not None
            or href.startswith('\\\\')
            or os.path.isabs(href)
        )

    def _categorize_issue(self, error_msg: str) -> str:
        """Categorize issue type"""
        if 'viewBox' in error_msg:
            return 'viewBox issues'
        elif 'XML parse error' in error_msg:
            return 'XML parse'
        elif 'foreignObject' in error_msg:
            return 'foreignObject'
        elif '<use>' in error_msg or 'data-icon' in error_msg:
            return 'use/icon reference'
        elif 'font' in error_msg.lower():
            return 'Font issues'
        else:
            return 'Other'

    def check_directory(
        self,
        directory: str,
        expected_format: str = None,
        print_results: bool = True,
        max_warnings: int = 2,
    ) -> List[Dict]:
        """
        Check all SVG files in a directory

        Args:
            directory: Directory path
            expected_format: Expected canvas format

        Returns:
            List of check results
        """
        dir_path = Path(directory)

        if not dir_path.exists():
            print(f"[ERROR] Directory does not exist: {directory}")
            return []

        # Find all SVG files
        if dir_path.is_file():
            svg_files = [dir_path]
        else:
            svg_output = dir_path / \
                'svg_output' if (
                    dir_path / 'svg_output').exists() else dir_path
            svg_files = sorted(svg_output.glob('*.svg'))

        if not svg_files:
            print(f"[WARN] No SVG files found")
            return []

        if print_results:
            print(f"\n[SCAN] Checking {len(svg_files)} SVG file(s)...\n")

        for svg_file in svg_files:
            result = self.check_file(str(svg_file), expected_format)
            if print_results:
                self._print_result(result, max_warnings=max_warnings)

        return self.results

    def _print_result(self, result: Dict, max_warnings: int = 2):
        """Print check result for a single file"""
        if result['passed']:
            if result['warnings']:
                icon = "[WARN]"
                status = "Passed (with warnings)"
            else:
                icon = "[OK]"
                status = "Passed"
        else:
            icon = "[ERROR]"
            status = "Failed"

        print(f"{icon} {result['file']} - {status}")

        # Display basic info
        if result['info']:
            info_items = []
            if 'viewbox' in result['info']:
                info_items.append(f"viewBox: {result['info']['viewbox']}")
            if info_items:
                print(f"   {' | '.join(info_items)}")

        # Display errors
        if result['errors']:
            for error in result['errors']:
                print(f"   [ERROR] {error}")

        # Display warnings
        if result['warnings']:
            for warning in result['warnings'][:max_warnings]:
                print(f"   [WARN] {warning}")
            if len(result['warnings']) > max_warnings:
                print(f"   ... and {len(result['warnings']) - max_warnings} more warning(s)")

        print()

    def print_summary(self, compact: bool = False):
        """Print check summary"""
        if compact:
            print(
                "Quality summary: "
                f"total={self.summary['total']} "
                f"passed={self.summary['passed']} "
                f"warnings={self.summary['warnings']} "
                f"errors={self.summary['errors']}"
            )
            if self.issue_types:
                top_issues = sorted(self.issue_types.items(), key=lambda x: x[1], reverse=True)[:5]
                print("Top issues:")
                for issue_type, count in top_issues:
                    print(f"  - {issue_type}: {count}")
            return

        print("=" * 80)
        print("[SUMMARY] Check Summary")
        print("=" * 80)

        print(f"\nTotal files: {self.summary['total']}")
        print(
            f"  [OK] Fully passed: {self.summary['passed']} ({self._percentage(self.summary['passed'])}%)")
        print(
            f"  [WARN] With warnings: {self.summary['warnings']} ({self._percentage(self.summary['warnings'])}%)")
        print(
            f"  [ERROR] With errors: {self.summary['errors']} ({self._percentage(self.summary['errors'])}%)")

        if self.issue_types:
            print(f"\nIssue categories:")
            for issue_type, count in sorted(self.issue_types.items(), key=lambda x: x[1], reverse=True):
                print(f"  {issue_type}: {count}")

        # Fix suggestions
        if self.summary['errors'] > 0 or self.summary['warnings'] > 0:
            print(f"\n[TIP] Common fixes:")
            print(f"  1. XML parse issues: escape literal '<' as '&lt;' inside text nodes")
            print(f"  2. viewBox issues: Ensure consistency with canvas format (see references/canvas-formats.md)")
            print(f"  3. foreignObject: Use <text> + <tspan> for manual line breaks")
            print(f"  4. Font issues: Use system UI font stack")

    def summary_dict(self) -> Dict:
        """Return a machine-readable summary."""
        return {
            "summary": dict(self.summary),
            "issue_types": dict(self.issue_types),
            "results": self.results,
        }

    def _percentage(self, count: int) -> int:
        """Calculate percentage"""
        if self.summary['total'] == 0:
            return 0
        return int(count / self.summary['total'] * 100)

    def export_report(self, output_file: str = 'svg_quality_report.txt'):
        """Export check report"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("PPT Master SVG Quality Check Report\n")
            f.write("=" * 80 + "\n\n")

            for result in self.results:
                status = "[OK] Passed" if result['passed'] else "[ERROR] Failed"
                f.write(f"{status} - {result['file']}\n")
                f.write(f"Path: {result.get('path', 'N/A')}\n")

                if result['info']:
                    f.write(f"Info: {result['info']}\n")

                if result['errors']:
                    f.write(f"\nErrors:\n")
                    for error in result['errors']:
                        f.write(f"  - {error}\n")

                if result['warnings']:
                    f.write(f"\nWarnings:\n")
                    for warning in result['warnings']:
                        f.write(f"  - {warning}\n")

                f.write("\n" + "-" * 80 + "\n\n")

            # Write summary
            f.write("\n" + "=" * 80 + "\n")
            f.write("Check Summary\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Total files: {self.summary['total']}\n")
            f.write(f"Fully passed: {self.summary['passed']}\n")
            f.write(f"With warnings: {self.summary['warnings']}\n")
            f.write(f"With errors: {self.summary['errors']}\n")

        print(f"\n[REPORT] Check report exported: {output_file}")


def main() -> None:
    """Run the CLI entry point."""
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="PPT Master - SVG Quality Check Tool",
    )
    parser.add_argument("target", nargs="?", help="SVG file, project directory, or --all")
    parser.add_argument("all_base_dir", nargs="?", default="examples", help=argparse.SUPPRESS)
    parser.add_argument("--all", action="store_true", help="Check all projects under the given base directory")
    parser.add_argument("--format", dest="expected_format", default=None, help="Expected canvas format")
    parser.add_argument("--export", action="store_true", help="Export a detailed text report")
    parser.add_argument("--output", default="svg_quality_report.txt", help="Report output path")
    parser.add_argument("--summary-only", action="store_true", help="Only print the final summary")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text")
    parser.add_argument(
        "--check-icons",
        action="store_true",
        help="Also validate data-icon references against local icon libraries",
    )
    parser.add_argument("--max-warnings", type=int, default=2, help="Max warnings to print per file")
    args = parser.parse_args()

    if not args.all and not args.target:
        parser.print_help()
        sys.exit(0)

    icon_checker = None
    icon_summary = None
    if args.check_icons:
        icon_checker = IconReferenceChecker()

    checker = SVGQualityChecker(icon_checker=icon_checker)

    if args.all:
        from project_utils import find_all_projects

        base_dir = args.target or args.all_base_dir
        projects = find_all_projects(base_dir)
        for project in projects:
            if not args.summary_only and not args.json:
                print(f"\n{'=' * 80}")
                print(f"Checking project: {project.name}")
                print('=' * 80)
            checker.check_directory(
                str(project),
                args.expected_format,
                print_results=not args.summary_only and not args.json,
                max_warnings=args.max_warnings,
            )
    else:
        checker.check_directory(
            args.target,
            args.expected_format,
            print_results=not args.summary_only and not args.json,
            max_warnings=args.max_warnings,
        )

    if args.check_icons and icon_checker is not None:
        icon_target = args.target if not args.all else (args.target or args.all_base_dir)
        icon_checker.check_directory(icon_target, print_results=False)
        icon_summary = icon_checker.summary_dict()

    if args.json:
        payload = {
            "quality_check": checker.summary_dict(),
        }
        if icon_summary is not None:
            payload["icon_check"] = icon_summary
            payload["passed"] = (
                checker.summary["errors"] == 0
                and icon_checker.summary["errors"] == 0
            )
        else:
            payload["passed"] = checker.summary["errors"] == 0
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        checker.print_summary(compact=args.summary_only)
        if icon_summary is not None:
            icon_summary_counts = icon_summary["summary"]
            if args.summary_only:
                print(
                    "Icon summary: "
                    f"total={icon_summary_counts['total']} "
                    f"passed={icon_summary_counts['passed']} "
                    f"warnings={icon_summary_counts['warnings']} "
                    f"errors={icon_summary_counts['errors']}"
                )
            else:
                print()
                print("=" * 80)
                print("[SUMMARY] Icon Reference Check Summary")
                print("=" * 80)
                print(f"\nTotal files: {icon_summary_counts['total']}")
                print(f"  [OK] Fully passed: {icon_summary_counts['passed']}")
                print(f"  [WARN] With warnings: {icon_summary_counts['warnings']}")
                print(f"  [ERROR] With errors: {icon_summary_counts['errors']}")

    if args.export:
        checker.export_report(args.output)

    icon_errors = icon_checker.summary["errors"] if icon_checker is not None else 0

    sys.exit(1 if checker.summary['errors'] > 0 or icon_errors > 0 else 0)


if __name__ == '__main__':
    main()
