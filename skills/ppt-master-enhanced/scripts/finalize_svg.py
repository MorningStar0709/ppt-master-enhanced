#!/usr/bin/env python3
"""
PPT Master - SVG Post-processing Tool (Unified Entry Point)

Processes SVG files from svg_output/ and outputs them to svg_final/.
By default, all processing steps are executed. You can also specify
individual steps via arguments.

This tool also supports a review-only preview mode that writes processed
artifacts to a separate directory (default: review/preview_finalized/) before
final export approval. That mode is intended only to improve preview
reliability during the SVG Review Gate and does not replace Step 8 export.

Usage:
    # Execute all processing steps (recommended, export path)
    conda run -n ppt-master python scripts/finalize_svg.py <project_directory>

    # Generate review-only preview artifacts before final approval
    conda run -n ppt-master python scripts/finalize_svg.py <project_directory> --review-preview

    # Execute only specific steps
    conda run -n ppt-master python scripts/finalize_svg.py <project_directory> --only embed-icons fix-rounded

Examples:
    conda run -n ppt-master python scripts/finalize_svg.py projects/my_project
    conda run -n ppt-master python scripts/finalize_svg.py examples/ppt169_demo --only embed-icons
    conda run -n ppt-master python scripts/finalize_svg.py examples/ppt169_demo --review-preview

Processing options:
    embed-icons   - Replace <use data-icon="..."/> with actual icon SVG
    crop-images   - Smart crop images based on preserveAspectRatio="slice"
    fix-aspect    - Fix image aspect ratio (prevent stretching during PPT shape conversion)
    embed-images  - Convert external images to Base64 embedded
    flatten-text  - Convert <tspan> to independent <text> (for special renderers)
    fix-rounded   - Convert <rect rx="..."/> to <path> (for PPT shape conversion)
"""

import os
import sys
import shutil
import argparse
import io
import re
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

# Import finalize helpers from the internal package.
sys.path.insert(0, str(Path(__file__).parent))
from runtime_utils import configure_utf8_stdio, safe_print
from svg_finalize.crop_images import process_svg_images as crop_images_in_svg
from svg_finalize.embed_icons import process_svg_file as embed_icons_in_file
from svg_finalize.embed_images import embed_images_in_svg
from svg_finalize.fix_image_aspect import fix_image_aspect_in_svg
from review_utils import get_review_gate_status


APPROVAL_BLOCKER_PREFIX = "Review approval status is "

LOCAL_FILE_SCHEME_PREFIX = "file:///"


def _non_approval_blockers(review_status) -> list[str]:
    """Keep all review blockers except the final approval-status blocker."""
    return [
        blocker
        for blocker in review_status.blockers
        if not blocker.startswith(APPROVAL_BLOCKER_PREFIX)
    ]


def _run_step(quiet: bool, func, *args, **kwargs):
    """Run helper functions without leaking stdout/stderr in quiet mode."""
    if not quiet:
        return func(*args, **kwargs)
    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        return func(*args, **kwargs)


def _is_external_href(href: str) -> bool:
    lowered = href.lower()
    return (
        lowered.startswith("data:")
        or lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("#")
    )


def _resolve_asset_target(source_svg: Path, href: str) -> Path | None:
    normalized_href = href.strip()
    if not normalized_href or _is_external_href(normalized_href):
        return None

    lowered = normalized_href.lower()
    if lowered.startswith(LOCAL_FILE_SCHEME_PREFIX):
        return Path(normalized_href[len(LOCAL_FILE_SCHEME_PREFIX):])

    if re.match(r"^[a-zA-Z]:[\\/]", normalized_href) or normalized_href.startswith("\\\\"):
        return Path(normalized_href)

    return (source_svg.parent / normalized_href).resolve()


def _rebase_local_asset_hrefs(source_svg: Path, output_svg: Path) -> int:
    """Rewrite local asset hrefs so copied SVGs keep working from the new directory."""
    content = output_svg.read_text(encoding="utf-8")
    source_content = source_svg.read_text(encoding="utf-8")
    replacements = 0

    def replace_match(match: re.Match[str]) -> str:
        nonlocal replacements
        original_href = match.group(2)
        target_path = _resolve_asset_target(source_svg, original_href)
        if target_path is None:
            return match.group(0)

        try:
            relative_href = os.path.relpath(target_path, output_svg.parent).replace("\\", "/")
        except ValueError:
            relative_href = target_path.as_posix()

        if relative_href == original_href:
            return match.group(0)

        replacements += 1
        return f'{match.group(1)}="{relative_href}"'

    updated_content = re.sub(
        r'((?:xlink:)?href)=["\']([^"\']+)["\']',
        replace_match,
        source_content,
    )

    if replacements > 0:
        output_svg.write_text(updated_content, encoding="utf-8")

    return replacements


def _normalize_copied_svg_asset_paths(source_dir: Path, output_dir: Path) -> int:
    """Keep copied SVG asset references portable after moving into a new sibling directory."""
    rewritten_refs = 0
    for output_svg in output_dir.glob("*.svg"):
        source_svg = source_dir / output_svg.name
        if not source_svg.exists():
            continue
        rewritten_refs += _rebase_local_asset_hrefs(source_svg, output_svg)
    return rewritten_refs


def process_flatten_text(svg_file: Path, verbose: bool = False) -> bool:
    """Flatten text in a single SVG file (in-place modification)"""
    try:
        from svg_finalize.flatten_tspan import flatten_text_with_tspans
        from xml.etree import ElementTree as ET

        tree = ET.parse(str(svg_file))
        changed = flatten_text_with_tspans(tree)

        if changed:
            tree.write(str(svg_file), encoding='unicode', xml_declaration=False)
            if verbose:
                safe_print(f"   [OK] {svg_file.name}: text flattened")
        return changed
    except Exception as e:
        if verbose:
            safe_print(f"   [ERROR] {svg_file.name}: {e}")
        return False


def process_rounded_rect(svg_file: Path, verbose: bool = False) -> int:
    """Convert rounded rectangles in a single SVG file (in-place modification)"""
    try:
        from svg_finalize.svg_rect_to_path import process_svg

        with open(svg_file, 'r', encoding='utf-8') as f:
            content = f.read()

        processed, count = process_svg(content, verbose=False)

        if count > 0:
            with open(svg_file, 'w', encoding='utf-8') as f:
                f.write(processed)
            if verbose:
                safe_print(f"   [OK] {svg_file.name}: {count} rounded rectangle(s)")
        return count
    except Exception as e:
        if verbose:
            safe_print(f"   [ERROR] {svg_file.name}: {e}")
        return 0


def finalize_project(
    project_dir: Path,
    options: dict[str, bool],
    dry_run: bool = False,
    quiet: bool = False,
    compress: bool = False,
    max_dimension: int | None = None,
    output_dir_name: str = "svg_final",
) -> bool:
    """
    Finalize SVG files in the project

    Args:
        project_dir: Project directory path
        options: Processing options dictionary
        dry_run: Preview only, do not execute
        quiet: Quiet mode, reduce output
        compress: Compress images before embedding
        max_dimension: Downscale images exceeding this dimension
    """
    svg_output = project_dir / 'svg_output'
    output_dir = project_dir / output_dir_name
    icons_dir = Path(__file__).parent.parent / 'templates' / 'icons'

    # Check if svg_output exists
    if not svg_output.exists():
        safe_print(f"[ERROR] svg_output directory not found: {svg_output}")
        return False

    if output_dir.resolve() == svg_output.resolve():
        safe_print("[ERROR] Output directory must not be svg_output")
        return False

    # Get list of SVG files
    svg_files = list(svg_output.glob('*.svg'))
    if not svg_files:
        safe_print(f"[ERROR] No SVG files in svg_output")
        return False

    if not quiet:
        print()
        safe_print(f"[DIR] Project: {project_dir.name}")
        safe_print(f"[FILE] {len(svg_files)} SVG file(s)")

    if dry_run:
        safe_print("[PREVIEW] Preview mode, no operations will be performed")
        return True

    # Step 1: Copy directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(svg_output, output_dir)

    rewritten_refs = _normalize_copied_svg_asset_paths(svg_output, output_dir)

    if not quiet:
        print()
        if rewritten_refs > 0:
            safe_print(
                f"[PATH] Rebased {rewritten_refs} local asset reference(s) for {output_dir_name}/"
            )

    # Step 2: Embed icons
    if options.get('embed_icons'):
        if not quiet:
            safe_print("[1/6] Embedding icons...")
        icons_count = 0
        for svg_file in output_dir.glob('*.svg'):
            count = _run_step(quiet, embed_icons_in_file, svg_file, icons_dir, dry_run=False, verbose=False)
            icons_count += count
        if not quiet:
            if icons_count > 0:
                safe_print(f"      {icons_count} icon(s) embedded")
            else:
                safe_print("      No icons")

    # Step 3: Smart crop images (based on preserveAspectRatio="slice")
    if options.get('crop_images'):
        if not quiet:
            safe_print("[2/6] Smart cropping images...")
        crop_count = 0
        crop_errors = 0
        for svg_file in output_dir.glob('*.svg'):
            count, errors = _run_step(quiet, crop_images_in_svg, str(svg_file), dry_run=False, verbose=False)
            crop_count += count
            crop_errors += errors
        if not quiet:
            if crop_count > 0:
                safe_print(f"      {crop_count} image(s) cropped")
            else:
                safe_print("      No cropping needed (no images with slice attribute)")

    # Step 4: Fix image aspect ratio (prevent stretching during PPT shape conversion)
    if options.get('fix_aspect'):
        if not quiet:
            safe_print("[3/6] Fixing image aspect ratios...")
        aspect_count = 0
        for svg_file in output_dir.glob('*.svg'):
            count = _run_step(quiet, fix_image_aspect_in_svg, str(svg_file), dry_run=False, verbose=False)
            aspect_count += count
        if not quiet:
            if aspect_count > 0:
                safe_print(f"      {aspect_count} image(s) fixed")
            else:
                safe_print("      No images")

    # Step 5: Embed images
    if options.get('embed_images'):
        if not quiet:
            safe_print("[4/6] Embedding images...")
        images_count = 0
        for svg_file in output_dir.glob('*.svg'):
            count, _ = _run_step(
                quiet,
                embed_images_in_svg,
                str(svg_file),
                dry_run=False,
                compress=compress,
                max_dimension=max_dimension,
            )
            images_count += count
        if not quiet:
            if images_count > 0:
                safe_print(f"      {images_count} image(s) embedded")
            else:
                safe_print("      No images")

    # Step 6: Flatten text
    if options.get('flatten_text'):
        if not quiet:
            safe_print("[5/6] Flattening text...")
        flatten_count = 0
        for svg_file in output_dir.glob('*.svg'):
            if process_flatten_text(svg_file, verbose=False):
                flatten_count += 1
        if not quiet:
            if flatten_count > 0:
                safe_print(f"      {flatten_count} file(s) processed")
            else:
                safe_print("      No processing needed")

    # Step 7: Convert rounded rects to Path
    if options.get('fix_rounded'):
        if not quiet:
            safe_print("[6/6] Converting rounded rects to Path...")
        rounded_count = 0
        for svg_file in output_dir.glob('*.svg'):
            count = process_rounded_rect(svg_file, verbose=False)
            rounded_count += count
        if not quiet:
            if rounded_count > 0:
                safe_print(f"      {rounded_count} rounded rectangle(s) converted")
            else:
                safe_print("      No rounded rectangles")

    # Done
    if not quiet:
        print()
        safe_print("[OK] Done!")
        print()
        print("Next steps:")
        if output_dir_name == "svg_final":
            print(f"  conda run -n ppt-master python scripts/svg_to_pptx.py \"{project_dir}\" -s final")
        else:
            print(
                f"  conda run --no-capture-output -n ppt-master python scripts/preview_svg_deck.py "
                f"\"{project_dir}\" -s {output_dir_name}"
            )
            print("  review-only preview artifacts do not count as final export output")

    return True


def main() -> None:
    """Run the CLI entry point."""
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description='PPT Master - SVG Post-processing Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s projects/my_project           # Execute all processing (default)
  %(prog)s projects/my_project --only embed-icons fix-rounded
  %(prog)s projects/my_project -q        # Quiet mode
  %(prog)s projects/my_project --review-preview
  %(prog)s projects/my_project --output-dir review/preview_finalized

Processing options (for --only):
  embed-icons   Embed icons
  crop-images   Smart crop images (based on preserveAspectRatio)
  fix-aspect    Fix image aspect ratio (prevent stretching during PPT shape conversion)
  embed-images  Embed images
  flatten-text  Flatten text
  fix-rounded   Convert rounded rects to Path
        '''
    )

    parser.add_argument('project_dir', type=Path, help='Project directory path')
    parser.add_argument('--only', nargs='+', metavar='OPTION',
                        choices=['embed-icons', 'crop-images', 'fix-aspect', 'embed-images', 'flatten-text', 'fix-rounded'],
                        help='Execute only specified processing steps (default: all)')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Preview only, do not execute')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Quiet mode, reduce output')
    parser.add_argument('--compress', action='store_true',
                        help='Compress images before embedding (JPEG quality=85, PNG optimize)')
    parser.add_argument('--max-dimension', type=int, default=None,
                        help='Downscale images exceeding this dimension on either axis (e.g., 2560)')
    parser.add_argument(
        '--output-dir',
        default='svg_final',
        help='Output directory name under the project (default: svg_final)',
    )
    parser.add_argument(
        '--review-preview',
        action='store_true',
        help='Write review-only preview artifacts before final approval (default output: review/preview_finalized)',
    )

    args = parser.parse_args()

    if not args.project_dir.exists():
        safe_print(f"[ERROR] Project directory does not exist: {args.project_dir}")
        sys.exit(1)

    output_dir_name = args.output_dir
    if args.review_preview:
        if args.output_dir == 'svg_final':
            output_dir_name = 'review/preview_finalized'
        elif args.output_dir == 'svg_output':
            safe_print("[ERROR] --review-preview cannot write into svg_output")
            sys.exit(1)

    if not args.dry_run:
        review_status = get_review_gate_status(args.project_dir)
        if args.review_preview:
            preview_blockers = _non_approval_blockers(review_status)
            if preview_blockers:
                safe_print("[ERROR] Review preview generation is blocked by unresolved review issues.")
                for blocker in preview_blockers:
                    safe_print(f"  - {blocker}")
                safe_print("Resolve review blockers before generating a reliable pre-approval preview:")
                safe_print(f"  conda run --no-capture-output -n ppt-master python scripts/review_manager.py status \"{args.project_dir}\" --compact")
                safe_print(f"  conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify \"{args.project_dir}\" --compact")
                safe_print(f"  conda run --no-capture-output -n ppt-master python scripts/review_manager.py repair-focus \"{args.project_dir}\"")
                sys.exit(1)
        elif not review_status.export_allowed:
            safe_print("[ERROR] SVG Review Gate has not passed. Post-processing is blocked.")
            for blocker in review_status.blockers:
                safe_print(f"  - {blocker}")
            safe_print("Resolve review blockers or approve the project first:")
            safe_print(f"  conda run --no-capture-output -n ppt-master python scripts/review_manager.py status \"{args.project_dir}\" --compact")
            safe_print(f"  conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify \"{args.project_dir}\" --compact")
            safe_print(f"  conda run --no-capture-output -n ppt-master python scripts/review_manager.py repair-focus \"{args.project_dir}\"")
            sys.exit(1)

    # Determine processing options
    if args.only:
        # Execute only specified steps
        options = {
            'embed_icons': 'embed-icons' in args.only,
            'crop_images': 'crop-images' in args.only,
            'fix_aspect': 'fix-aspect' in args.only,
            'embed_images': 'embed-images' in args.only,
            'flatten_text': 'flatten-text' in args.only,
            'fix_rounded': 'fix-rounded' in args.only,
        }
    else:
        # Execute all by default
        options = {
            'embed_icons': True,
            'crop_images': True,
            'fix_aspect': True,
            'embed_images': True,
            'flatten_text': True,
            'fix_rounded': True,
        }

    success = finalize_project(args.project_dir, options, args.dry_run, args.quiet,
                               compress=args.compress,
                               max_dimension=args.max_dimension,
                               output_dir_name=output_dir_name)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
