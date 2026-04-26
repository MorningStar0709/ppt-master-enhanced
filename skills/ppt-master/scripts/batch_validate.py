#!/usr/bin/env python3
"""
PPT Master - Batch Project Validation Tool

Checks the structural integrity and compliance of multiple projects at once.

Usage:
    conda run -n ppt-master python scripts/batch_validate.py examples
    conda run -n ppt-master python scripts/batch_validate.py projects
    conda run -n ppt-master python scripts/batch_validate.py --all
    conda run -n ppt-master python scripts/batch_validate.py examples projects
"""

import sys
from collections import defaultdict
from pathlib import Path

try:
    from icon_reference_checker import IconReferenceChecker
    from preview_svg_deck import inspect_preview_source
    from project_utils import (
        find_all_projects,
        get_project_info,
        validate_project_structure,
        validate_svg_viewbox,
        CANVAS_FORMATS
    )
    from review_utils import get_review_gate_status
    from runtime_utils import configure_utf8_stdio, safe_print
    from svg_layout_checker import SVGLayoutChecker
    from svg_quality_checker import SVGQualityChecker
except ImportError:
    print("Error: Unable to import project_utils module")
    print("Please ensure project_utils.py is in the same directory")
    sys.exit(1)


class BatchValidator:
    """Batch validator"""

    def __init__(self):
        self.results: list[dict[str, object]] = []
        self.summary = {
            'total': 0,
            'valid': 0,
            'has_errors': 0,
            'has_warnings': 0,
            'missing_readme': 0,
            'missing_spec': 0,
            'svg_issues': 0,
            'quality_issues': 0,
            'layout_issues': 0,
            'icon_issues': 0,
            'review_blocked': 0,
            'preview_failures': 0,
        }

    def validate_directory(self, directory: str, recursive: bool = False) -> list[dict[str, object]]:
        """
        Validate all projects in a directory

        Args:
            directory: Directory path
            recursive: Whether to recursively search subdirectories

        Returns:
            List of validation results
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            print(f"[ERROR] Directory does not exist: {directory}")
            return []

        print(f"\n[SCAN] Scanning directory: {directory}")
        print("=" * 80)

        projects = find_all_projects(directory)

        if not projects:
            print(f"[WARN] No projects found")
            return []

        print(f"Found {len(projects)} project(s)\n")

        for project_path in projects:
            self.validate_project(str(project_path))

        return self.results

    def validate_project(self, project_path: str) -> dict[str, object]:
        """
        Validate a single project

        Args:
            project_path: Project path

        Returns:
            Validation result dictionary
        """
        self.summary['total'] += 1

        # Get project info
        info = get_project_info(project_path)

        # Validate project structure
        is_valid, errors, warnings = validate_project_structure(project_path)

        # Validate SVG viewBox
        svg_warnings = []
        quality_summary = {"summary": {"errors": 0, "warnings": 0}}
        layout_summary = {"summary": {"errors": 0, "warnings": 0}}
        icon_summary = {"summary": {"errors": 0, "warnings": 0}}
        preview_summary: dict[str, object] = {"ok": False, "error": "No SVG files found"}
        review_status = None
        if info['svg_files']:
            project_path_obj = Path(project_path)
            svg_files = [project_path_obj / 'svg_output' /
                         f for f in info['svg_files']]
            svg_warnings = validate_svg_viewbox(svg_files, info['format'])
            quality_checker = SVGQualityChecker(warn_on_icon_placeholders=False)
            quality_checker.check_directory(project_path, expected_format=info['format'], print_results=False)
            quality_summary = quality_checker.summary_dict()

            layout_checker = SVGLayoutChecker()
            layout_checker.check_directory(project_path, print_results=False)
            layout_summary = layout_checker.summary_dict()

            icon_checker = IconReferenceChecker()
            icon_checker.check_directory(project_path, print_results=False)
            icon_summary = icon_checker.summary_dict()

            try:
                preview_summary = {"ok": True, **inspect_preview_source(project_path_obj)}
            except Exception as exc:
                preview_summary = {"ok": False, "error": str(exc)}

            review_status = get_review_gate_status(project_path_obj)

        # Aggregate results
        combined_warnings = warnings + svg_warnings
        combined_errors = list(errors)
        if quality_summary["summary"]["errors"] > 0:
            combined_errors.append(
                f"SVG technical validation failed ({quality_summary['summary']['errors']} file(s) with errors)"
            )
        elif quality_summary["summary"]["warnings"] > 0:
            combined_warnings.append(
                f"SVG technical validation produced warnings ({quality_summary['summary']['warnings']} file(s))"
            )

        if layout_summary["summary"]["errors"] > 0:
            combined_errors.append(
                f"SVG layout validation failed ({layout_summary['summary']['errors']} file(s) with errors)"
            )
        elif layout_summary["summary"]["warnings"] > 0:
            combined_warnings.append(
                f"SVG layout validation produced warnings ({layout_summary['summary']['warnings']} file(s))"
            )

        if icon_summary["summary"]["errors"] > 0:
            combined_errors.append(
                f"Icon reference validation failed ({icon_summary['summary']['errors']} file(s) with errors)"
            )

        if review_status is not None and not review_status.export_allowed:
            combined_errors.append("Review gate is not export-ready")

        if info['svg_files'] and not preview_summary.get("ok", False):
            combined_errors.append(f"Preview inspection failed: {preview_summary.get('error', 'unknown error')}")

        result = {
            'path': project_path,
            'name': info['name'],
            'format': info['format_name'],
            'date': info['date_formatted'],
            'svg_count': info['svg_count'],
            'is_valid': is_valid and len(combined_errors) == 0,
            'errors': combined_errors,
            'warnings': combined_warnings,
            'has_readme': info['has_readme'],
            'has_spec': info['has_spec'],
            'quality_summary': quality_summary["summary"],
            'layout_summary': layout_summary["summary"],
            'icon_summary': icon_summary["summary"],
            'preview_summary': preview_summary,
            'review_export_allowed': review_status.export_allowed if review_status is not None else False,
        }

        self.results.append(result)

        # Update statistics
        if result['is_valid'] and not result['warnings']:
            self.summary['valid'] += 1
            status = "[OK]"
        elif result['errors']:
            self.summary['has_errors'] += 1
            status = "[ERROR]"
        else:
            self.summary['has_warnings'] += 1
            status = "[WARN]"

        if not info['has_readme']:
            self.summary['missing_readme'] += 1
        if not info['has_spec']:
            self.summary['missing_spec'] += 1
        if svg_warnings:
            self.summary['svg_issues'] += 1
        if quality_summary["summary"]["errors"] > 0 or quality_summary["summary"]["warnings"] > 0:
            self.summary['quality_issues'] += 1
        if layout_summary["summary"]["errors"] > 0 or layout_summary["summary"]["warnings"] > 0:
            self.summary['layout_issues'] += 1
        if icon_summary["summary"]["errors"] > 0:
            self.summary['icon_issues'] += 1
        if review_status is not None and not review_status.export_allowed:
            self.summary['review_blocked'] += 1
        if info['svg_files'] and not preview_summary.get("ok", False):
            self.summary['preview_failures'] += 1

        # Print result
        safe_print(f"{status} {info['name']}")
        safe_print(f"   Path: {project_path}")
        safe_print(
            f"   Format: {info['format_name']} | SVG: {info['svg_count']} file(s) | Date: {info['date_formatted']}")

        if result['errors']:
            safe_print(f"   [ERROR] Errors ({len(result['errors'])}):")
            for error in result['errors']:
                safe_print(f"      - {error}")

        if result['warnings']:
            all_warnings = result['warnings']
            safe_print(f"   [WARN] Warnings ({len(all_warnings)}):")
            for warning in all_warnings[:3]:  # Only show first 3 warnings
                safe_print(f"      - {warning}")
            if len(all_warnings) > 3:
                safe_print(f"      ... and {len(all_warnings) - 3} more warning(s)")

        if info['svg_files']:
            safe_print(
                "   [CHECKS] "
                f"quality(e={quality_summary['summary']['errors']},w={quality_summary['summary']['warnings']}) "
                f"layout(e={layout_summary['summary']['errors']},w={layout_summary['summary']['warnings']}) "
                f"icons(e={icon_summary['summary']['errors']},w={icon_summary['summary']['warnings']}) "
                f"review_ready={result['review_export_allowed']} "
                f"preview_ok={preview_summary.get('ok', False)}"
            )

        safe_print()

        return result

    def print_summary(self) -> None:
        """Print a summary of validation results."""
        safe_print("\n" + "=" * 80)
        safe_print("[Summary] Validation Summary")
        safe_print("=" * 80)

        safe_print(f"\nTotal projects: {self.summary['total']}")
        safe_print(
            f"  [OK] Fully valid: {self.summary['valid']} ({self._percentage(self.summary['valid'])}%)")
        safe_print(
            f"  [WARN] With warnings: {self.summary['has_warnings']} ({self._percentage(self.summary['has_warnings'])}%)")
        safe_print(
            f"  [ERROR] With errors: {self.summary['has_errors']} ({self._percentage(self.summary['has_errors'])}%)")

        safe_print(f"\nCommon issues:")
        safe_print(f"  Missing README.md: {self.summary['missing_readme']} project(s)")
        safe_print(f"  Missing design spec: {self.summary['missing_spec']} project(s)")
        safe_print(f"  SVG format issues: {self.summary['svg_issues']} project(s)")
        safe_print(f"  SVG technical issues: {self.summary['quality_issues']} project(s)")
        safe_print(f"  SVG layout issues: {self.summary['layout_issues']} project(s)")
        safe_print(f"  Icon reference issues: {self.summary['icon_issues']} project(s)")
        safe_print(f"  Review gate blocked: {self.summary['review_blocked']} project(s)")
        safe_print(f"  Preview inspection failures: {self.summary['preview_failures']} project(s)")

        # Group statistics by format
        format_stats = defaultdict(int)
        for result in self.results:
            format_stats[result['format']] += 1

        if format_stats:
            safe_print(f"\nCanvas format distribution:")
            for fmt, count in sorted(format_stats.items(), key=lambda x: x[1], reverse=True):
                safe_print(f"  {fmt}: {count} project(s)")

        # Provide fix suggestions
        if self.summary['has_errors'] > 0 or self.summary['has_warnings'] > 0:
            safe_print(f"\n[TIP] Fix suggestions:")

            if self.summary['missing_readme'] > 0:
                safe_print(f"  1. Create documentation for projects missing README")
                safe_print(
                    f"     Reference: examples/google_annual_report_ppt169_20251116/README.md")

            if self.summary['svg_issues'] > 0:
                safe_print(f"  2. Check and fix SVG viewBox settings")
                safe_print(f"     Ensure consistency with canvas format")

            if self.summary['missing_spec'] > 0:
                safe_print(f"  3. Add design specification files")
            if self.summary['review_blocked'] > 0:
                safe_print(f"  4. Reconcile review_state.json, approval state, and page coverage before export")
            if self.summary['quality_issues'] > 0 or self.summary['layout_issues'] > 0:
                safe_print(f"  5. Run svg_quality_checker.py / svg_layout_checker.py on failing projects and repair before export")

    def _percentage(self, count: int) -> int:
        """Calculate percentage"""
        if self.summary['total'] == 0:
            return 0
        return int(count / self.summary['total'] * 100)

    def export_report(self, output_file: str = 'validation_report.txt') -> None:
        """
        Export validation report to file

        Args:
            output_file: Output file path
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("PPT Master Project Validation Report\n")
            f.write("=" * 80 + "\n\n")

            for result in self.results:
                status = "[OK] Valid" if result['is_valid'] and not result['warnings'] else \
                    "[ERROR] Error" if result['errors'] else "[WARN] Warning"

                f.write(f"{status} - {result['name']}\n")
                f.write(f"Path: {result['path']}\n")
                f.write(
                    f"Format: {result['format']} | SVG: {result['svg_count']} file(s)\n")

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
            f.write("Validation Summary\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Total projects: {self.summary['total']}\n")
            f.write(f"Fully valid: {self.summary['valid']}\n")
            f.write(f"With warnings: {self.summary['has_warnings']}\n")
            f.write(f"With errors: {self.summary['has_errors']}\n")

        safe_print(f"\n[REPORT] Validation report exported: {output_file}")


def main() -> None:
    """Run the CLI entry point."""
    configure_utf8_stdio()
    if len(sys.argv) < 2:
        safe_print("PPT Master - Batch Project Validation Tool\n")
        safe_print("Usage:")
        safe_print("  conda run -n ppt-master python scripts/batch_validate.py <directory>")
        safe_print("  conda run -n ppt-master python scripts/batch_validate.py <dir1> <dir2> ...")
        safe_print("  conda run -n ppt-master python scripts/batch_validate.py --all")
        safe_print("\nExamples:")
        safe_print("  conda run -n ppt-master python scripts/batch_validate.py examples")
        safe_print("  conda run -n ppt-master python scripts/batch_validate.py projects")
        safe_print("  conda run -n ppt-master python scripts/batch_validate.py examples projects")
        safe_print("  conda run -n ppt-master python scripts/batch_validate.py --all")
        sys.exit(0)

    validator = BatchValidator()

    # Process arguments
    if '--all' in sys.argv:
        directories = ['examples', 'projects']
    else:
        directories = [arg for arg in sys.argv[1:] if not arg.startswith('--')]

    # Validate each directory
    for directory in directories:
        if Path(directory).exists():
            validator.validate_directory(directory)
        else:
            safe_print(f"[WARN] Skipping non-existent directory: {directory}\n")

    # Print summary
    validator.print_summary()

    # Export report (if specified)
    if '--export' in sys.argv:
        output_file = 'validation_report.txt'
        if '--output' in sys.argv:
            idx = sys.argv.index('--output')
            if idx + 1 < len(sys.argv):
                output_file = sys.argv[idx + 1]
        validator.export_report(output_file)

    # Return exit code
    if validator.summary['has_errors'] > 0:
        sys.exit(1)
    elif validator.summary['has_warnings'] > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
