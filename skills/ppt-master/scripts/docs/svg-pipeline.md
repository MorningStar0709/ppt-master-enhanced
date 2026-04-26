# SVG Pipeline Tools

These tools cover review gating, post-processing, SVG validation, speaker notes, and PPTX export.

## Recommended Pipeline

Run the pipeline in this order:

1. Generate SVG pages sequentially
2. Review each page immediately after generation
3. Complete the whole-deck SVG Review Gate
4. Obtain explicit user approval for export
5. Run the post-processing commands one by one

Step 1. Split speaker notes:

```bash
conda run -n ppt-master python scripts/total_md_split.py <project_path>
```

Step 2. After Step 1 completes successfully, run SVG post-processing:

```bash
conda run -n ppt-master python scripts/finalize_svg.py <project_path>
```

Step 3. After Step 2 completes successfully, export PPTX:

```bash
conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -s final
```

Do not run the commands above until review artifacts are complete and the user has approved export.

Execution discipline:

- `total_md_split.py`, `finalize_svg.py`, and `svg_to_pptx.py` all fail when the SVG Review Gate has not passed
- Step 6 / Step 7 artifacts must be written with IDE/native file editing tools or repository Python helpers, not shell redirection
- On Windows/Trae, do not use PowerShell write commands to create `svg_output/*.svg`, `notes/*.md`, or `review/*.md`
- Use `review/review_state.json` as the machine source of truth; `review_log.md`, `fix_tasks.md`, and `user_confirmation.md` are rendered reports

## SVG Review Gate

Before post-processing, complete the review gate described in `docs/svg-review.md` and `references/svg-review/`.

Related references:

- `references/svg-review/standards.md`
- `references/svg-review/playbook.md`
- `references/svg-review/priority-rules.md`
- `templates/review/`

## `finalize_svg.py`

Unified post-processing entry point. This is the preferred way to run SVG cleanup.

It aggregates:
- `embed_icons.py`
- `crop_images.py`
- `fix_image_aspect.py`
- `embed_images.py`
- `flatten_tspan.py`
- `svg_rect_to_path.py`

Gate behavior:
- blocks execution until review artifacts exist, per-page review coverage is complete, evidence is internally consistent, and export approval is recorded

## `svg_to_pptx.py`

Convert project SVGs into PPTX.

```bash
conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -s final
conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -s final --only native
conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -s final --only legacy
conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -s final --no-notes
conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -t none
conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -s final --auto-advance 3
```

Behavior:
- Default output: export snapshot pair in `exports/` — `<project_name>_<timestamp>.pptx` (native editable) + `<project_name>_<timestamp>_svg.pptx` (SVG snapshot)
- Those timestamps belong only to export history. The project directory itself remains a stable non-timestamped path
- In the default workflow, the source directory for export MUST be `svg_final/`
- Speaker notes are embedded automatically unless `--no-notes` is used

Review rule:

- exporting is blocked until the SVG Review Gate is complete and user approval has been received
- `--only native` and `--only legacy` are advanced standalone/debug options, not part of the default export workflow

Dependency:

```bash
conda run -n ppt-master pip install python-pptx
```

## `total_md_split.py`

Split `total.md` into per-slide note files.

```bash
conda run -n ppt-master python scripts/total_md_split.py <project_path>
conda run -n ppt-master python scripts/total_md_split.py <project_path> -o <output_directory>
conda run -n ppt-master python scripts/total_md_split.py <project_path> -q
```

Requirements:
- Each section begins with `# `
- Heading text matches the SVG filename
- Sections are separated by `---`
- The SVG Review Gate must already pass before this command runs

## `svg_quality_checker.py`

Validate SVG technical compliance.

```bash
conda run -n ppt-master python scripts/svg_quality_checker.py examples/project/svg_output/01_cover.svg
conda run -n ppt-master python scripts/svg_quality_checker.py examples/project/svg_output
conda run -n ppt-master python scripts/svg_quality_checker.py examples/project
conda run -n ppt-master python scripts/svg_quality_checker.py examples/project --format ppt169
conda run -n ppt-master python scripts/svg_quality_checker.py examples/project --summary-only
conda run -n ppt-master python scripts/svg_quality_checker.py examples/project --summary-only --check-icons
conda run -n ppt-master python scripts/svg_quality_checker.py examples/project --json
conda run -n ppt-master python scripts/svg_quality_checker.py --all examples
conda run -n ppt-master python scripts/svg_quality_checker.py examples/project --export
```

Checks include:
- XML parse validity
- `viewBox`
- banned elements
- width/height consistency
- line-break structure
- unresolved `<use>` / icon placeholder preview risks
- optional local `data-icon` target validation when `--check-icons` is enabled

Boundary:

- `svg_quality_checker.py` checks technical compliance
- with `--check-icons`, it also acts as a lightweight asset-reference guardrail
- it is **not** a replacement for layout review, symptom diagnosis, or user export approval

## `svg_layout_checker.py`

Detect obvious geometry issues before review gate approval.

```bash
conda run --no-capture-output -n ppt-master python scripts/svg_layout_checker.py examples/project/svg_output/01_cover.svg
conda run --no-capture-output -n ppt-master python scripts/svg_layout_checker.py examples/project
conda run --no-capture-output -n ppt-master python scripts/svg_layout_checker.py examples/project --summary-only
conda run --no-capture-output -n ppt-master python scripts/svg_layout_checker.py examples/project --json
```

Checks include:
- elements outside the canvas
- translated card groups that still use page-level text coordinates
- obvious text / card geometry mismatches

Interpretation notes:
- `svg_layout_checker.py` is intentionally conservative; warnings are prompts for review, not automatic export blockers by themselves
- Multi-line `<tspan>` text should be interpreted per line, not by concatenating the whole paragraph into one width estimate
- `translate()` groups that only contain a narrow decorative rect or underline should not be treated as true container-coordinate mismatches
- Visible card/panel overflow beyond the page canvas is still a meaningful warning and should normally be fixed in the SVG

Recommended self-check order:
1. `svg_quality_checker.py --check-icons`
2. `svg_layout_checker.py`
3. `preview_svg_deck.py`
4. page review + `review_manager.py set-page`

Unified gate:

```bash
conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify <project_path> --compact
```

This single entry now re-checks review evidence, builds a unified Step 7 review SVG source under `review/preview_finalized/`, runs technical SVG compliance, layout geometry, and icon references against the reviewed raw SVG set under `svg_output/`, and generates browser preview from the review source.

## `preview_svg_deck.py`

Generate a fixed-canvas HTML preview page for a chosen SVG source directory under the project.

```bash
conda run --no-capture-output -n ppt-master python scripts/preview_svg_deck.py <project_path> -s svg_final
conda run --no-capture-output -n ppt-master python scripts/preview_svg_deck.py <project_path> -s review/preview_finalized
```

Use this when direct browser inspection of standalone SVG files is too weak or too noisy.

Approval-time preview rule:
- `review_manager.py verify` must prepare `review/preview_finalized/` first
- Step 7 review must use `review/preview_deck.html` generated from `review/preview_finalized/`
- Serve the project root when opening the preview HTML, otherwise relative asset paths can break
- `scripts/finalize_svg.py <project_path> --review-preview` remains the lower-level helper that prepares that review-only SVG directory
- The review-only directory is a Step 7 preview aid only; it does not replace the real Step 8 `finalize_svg.py` export pass

## `svg_position_calculator.py`

Analyze or pre-calculate chart coordinates.

Common commands:

```bash
conda run -n ppt-master python scripts/svg_position_calculator.py analyze <svg_file>
conda run -n ppt-master python scripts/svg_position_calculator.py interactive
conda run -n ppt-master python scripts/svg_position_calculator.py calc bar --data "East:185,South:142"
conda run -n ppt-master python scripts/svg_position_calculator.py calc pie --data "A:35,B:25,C:20"
conda run -n ppt-master python scripts/svg_position_calculator.py from-json config.json
```

Use this when chart geometry needs to be verified before or after AI generation.

## Advanced Standalone Tools

### `flatten_tspan.py`

```bash
conda run -n ppt-master python scripts/svg_finalize/flatten_tspan.py examples/<project>/svg_output
conda run -n ppt-master python scripts/svg_finalize/flatten_tspan.py path/to/input.svg path/to/output.svg
```

### `svg_rect_to_path.py`

```bash
conda run -n ppt-master python scripts/svg_finalize/svg_rect_to_path.py <project_path>
conda run -n ppt-master python scripts/svg_finalize/svg_rect_to_path.py <project_path> -s final
conda run -n ppt-master python scripts/svg_finalize/svg_rect_to_path.py path/to/file.svg
```

Use when rounded corners must survive PowerPoint shape conversion.

### `fix_image_aspect.py`

```bash
conda run -n ppt-master python scripts/svg_finalize/fix_image_aspect.py path/to/slide.svg
conda run -n ppt-master python scripts/svg_finalize/fix_image_aspect.py 01_cover.svg 02_toc.svg
conda run -n ppt-master python scripts/svg_finalize/fix_image_aspect.py --dry-run path/to/slide.svg
```

Use when embedded images stretch after PowerPoint shape conversion.

### `embed_icons.py`

```bash
conda run -n ppt-master python scripts/svg_finalize/embed_icons.py output.svg
conda run -n ppt-master python scripts/svg_finalize/embed_icons.py svg_output/*.svg
conda run -n ppt-master python scripts/svg_finalize/embed_icons.py --dry-run svg_output/*.svg
```

Replaces `<use data-icon="chunk/name" .../>`, `<use data-icon="tabler-filled/name" .../>` and `<use data-icon="tabler-outline/name" .../>` placeholders with actual SVG path elements. Use for manual icon embedding checks outside `finalize_svg.py`.

## PPT Compatibility Rules

Use PowerPoint-safe transparency syntax:

| Avoid | Use instead |
|------|-------------|
| `fill=\"rgba(...)\"` | `fill=\"#hex\"` + `fill-opacity` |
| `<g opacity=\"...\">` | Set opacity on each child |
| `<image opacity=\"...\">` | Overlay with a mask layer |

PowerPoint also has trouble with:
- marker-based arrows
- unsupported filters
- direct SVG features not mapped to DrawingML

## Review Notes

- use `svg_final/` only for post-approval export judgement; during Step 7 approval use `review/preview_deck.html` backed by `review/preview_finalized/`
- use browser whole-page preview instead of judging from the raw `.svg` viewport
- review first, export later
