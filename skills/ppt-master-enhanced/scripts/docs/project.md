# Project Tools

Project tools create, validate, and inspect the standard PPT Master workspace.

## `project_manager.py`

Main entry point for project setup and validation.

```bash
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py init <project_name> --format ppt169 --dir projects
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py import-sources <project_path> <source1> [<source2> ...] --copy
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py apply-template <project_path> <template_name>
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py validate <project_path>
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py info <project_path>
```

Notes:
- In the main PPT workflow, user-provided source files SHOULD be imported with `--copy` so the original file remains in place
- Launch the main workflow from the repository root and keep Step 2 on the single command form shown above
- `<project_name>` MUST be an English slug such as `wireless_cloud_control_patent`
- After `init`, the real project directory is `projects/<project_name>_<normalized_format>`; always reuse the exact printed path from the command output instead of inferring it
- When terminal output is truncated, read `skills/ppt-master-enhanced/.runtime/command_reports/project_manager_<command>_last.json` instead of guessing the last result
- Project directories intentionally do not include timestamps; the directory is the stable machine identifier, while creation time remains metadata
- Exported PPTX files under `exports/` intentionally do include timestamps so repeated exports preserve history without mutating the project identity
- If `init` says the project directory already exists, reuse that exact project path or choose a new slug explicitly; do not guess fallback paths
- `init` already creates the standard directories (`svg_output/`, `svg_final/`, `images/`, `notes/`, `review/`, `templates/`, `sources/`, `exports/`); do not manually create them with shell commands
- `apply-template` is the preferred Step 3 follow-up when the user selects a library layout template
- `apply-template` copies template SVG files and `design_spec.md` into `templates/`, and routes template PNG/JPG/WebP assets into `images/`
- Re-run `apply-template` with `--force` only when you intentionally want to overwrite existing project template files
- `import-sources` normalizes archived filenames under `sources/` to English-only names for downstream machine use
- Files outside the repo are copied into `sources/` by default
- With `--move`, files outside the repo are moved into `sources/`
- Files already inside the repo are moved into `sources/` by default (with a stderr
  note), to avoid leaving unintended artifacts that could be committed by mistake.
  Pass `--copy` to force a copy for in-repo sources instead.
- Reserve `--move` for explicit "project takes ownership of the original" scenarios or intentional cleanup of transient in-repo artifacts
- `--move` and `--copy` are mutually exclusive.
- New projects also initialize `review/` with a minimal `review_state.json` plus rendered review artifacts

Common formats:
- `ppt169`
- `ppt43`
- `xiaohongshu`
- `moments`
- `story`
- `banner`
- `a4`

Examples:

```bash
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py init my_presentation --format ppt169 --dir projects
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py import-sources "projects/my_presentation_ppt169" "source.md" --copy
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py validate "projects/my_presentation_ppt169"
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py info "projects/my_presentation_ppt169"
```

## `review_manager.py`

Initialize and inspect review artifacts, then mark the deck approved for export.

```bash
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/review_manager.py init <project_path>
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/review_manager.py sync <project_path>
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/review_manager.py render <project_path>
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/review_manager.py set-page <project_path> --file 01_cover.svg --priority none --reviewed yes --note "layout pass"
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/review_manager.py status <project_path> --compact
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/review_manager.py verify <project_path> --json
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/review_manager.py approve <project_path> --by <name>
```

Typical use:

- `init`: seed or repair `review_state.json` and rendered Markdown artifacts for an existing project
- `sync`: migrate legacy Markdown review artifacts into `review_state.json`
- `render`: regenerate `review_log.md`, `fix_tasks.md`, and `user_confirmation.md` from `review_state.json`
- `set-page`: record one page with only four gate fields: file, reviewed yes/no, priority, and note
- `status`: summarize open `P0 / P1 / P2` pages, page-review coverage, and current approval state; add `--compact` for concise output
- `verify`: unified Step 7 technical gate entry. It first prepares the Step 7 review SVG source under `review/preview_finalized/`, then fails fast when non-approval review evidence is incomplete, review-source build fails, technical SVG validation on `svg_output/` finds blocking issues, layout geometry validation on `svg_output/` finds blocking issues, icon references in `svg_output/` contain missing local `data-icon` targets, or preview generation fails. If all technical checks pass but the user has not approved yet, `verify` still returns success while reporting that export remains blocked pending approval; add `--json` for machine-readable output, or use `--skip-*` flags only for targeted debugging
- `approve`: write machine-readable approval into `review_state.json` and re-render `review/user_confirmation.md`
- `approve` also refreshes `review/verify_report.json`; manual `verify` rerun is needed only if that refresh step fails

Quick reading rule for layout warnings:
- if whole-page preview is correct and the warning comes from multi-line `<tspan>` width estimation or a decorative translated bar group, treat it as checker noise first
- if the warning matches visible overflow, off-canvas cards, or true coordinate mismatch, treat it as a real SVG defect

## `asset_lookup.py`

Targeted chart and icon lookup for low-token workflows.

```bash
conda run -n ppt-master python scripts/asset_lookup.py charts roadmap
conda run -n ppt-master python scripts/asset_lookup.py charts comparison --limit 5
conda run -n ppt-master python scripts/asset_lookup.py icons chunk/signal --exact
conda run -n ppt-master python scripts/asset_lookup.py icons home --library chunk
conda run -n ppt-master python scripts/asset_lookup.py icons chart --library tabler-outline
```

Typical use:

- `charts`: return only the most relevant visualization candidates instead of reading the full `charts_index.json`
- `icons --exact`: validate one exact icon reference in `library/name` format before using it in SVG
- `icons`: search one icon library by keyword without relying on shell-specific file search commands

## `icon_reference_checker.py`

Validate `data-icon="library/name"` placeholders in generated SVG files against the local icon library.

```bash
conda run --no-capture-output -n ppt-master python scripts/icon_reference_checker.py <svg_file>
conda run --no-capture-output -n ppt-master python scripts/icon_reference_checker.py <project_path>
conda run --no-capture-output -n ppt-master python scripts/icon_reference_checker.py <project_path> --summary-only
conda run --no-capture-output -n ppt-master python scripts/icon_reference_checker.py <project_path> --json
```

Typical use:

- Run after SVG generation to catch nonexistent icon references early
- Use `--summary-only` for a fast gate check during iteration
- Use `--json` when another tool or workflow needs machine-readable results
- Treat missing icon references as a signal to stop local icon guessing and switch to a verified substitute, AI-generated asset, external resource, or placeholder

## `project_utils.py`

Shared helper module used by other scripts.

Typical use:

```python
from project_utils import get_project_info, validate_project_structure
```

You can also run it directly for quick checks:

```bash
conda run -n ppt-master python scripts/project_utils.py <project_path>
```

## `batch_validate.py`

Batch-check project structure and compliance.

```bash
conda run -n ppt-master python scripts/batch_validate.py examples
conda run -n ppt-master python scripts/batch_validate.py examples projects
conda run -n ppt-master python scripts/batch_validate.py --all
conda run -n ppt-master python scripts/batch_validate.py examples --export
```

Use this for repository-wide health checks before release or cleanup. It now combines:
- project structure validation
- `viewBox` consistency
- SVG technical validation
- layout geometry validation
- icon reference validation
- review gate readiness
- preview-source inspectability

## `generate_examples_index.py`

Rebuild `examples/README.md` automatically.

```bash
conda run -n ppt-master python scripts/generate_examples_index.py
conda run -n ppt-master python scripts/generate_examples_index.py examples
```

## `pptx_template_import.py`

Unified PPTX preparation entry point for `/create-template`.

```bash
conda run -n ppt-master python scripts/pptx_template_import.py <template.pptx>
conda run -n ppt-master python scripts/pptx_template_import.py <template.pptx> -o <output_dir>
conda run -n ppt-master python scripts/pptx_template_import.py <template.pptx> --manifest-only
conda run -n ppt-master python scripts/pptx_template_import.py <template.pptx> --keep-raw
conda run -n ppt-master python scripts/pptx_template_import.py <template.pptx> --skip-manifest
```

Notes:
- Extracts reusable media assets from `ppt/media/`
- Summarizes slide size, theme colors, and font metadata
- Infers background image inheritance across slide, layout, and master
- Generates `manifest.json`, `analysis.md`, `assets/`, cleaned slide SVGs, and `reference_svg_selection.json`
- Native SVG export is Windows-only because it uses installed Microsoft PowerPoint
- On macOS, the script falls back to exporting PDF via Keynote and then converts PDF pages to SVG
- Writes cleaned SVG files to `svg/` after externalizing inline Base64 image payloads
- Required in `/create-template` whenever the reference source is `.pptx`
- Default output directory is `<pptx_stem>_template_import/`
- Use `--manifest-only` when you explicitly want only the lightweight import output without slide SVG export
- Intended for template reference preparation, not for final 1:1 template delivery

Implementation note:
- Internal helpers for this workflow live under `scripts/template_import/`

## `error_helper.py`

Show standardized fixes for common project errors.

```bash
conda run -n ppt-master python scripts/error_helper.py
conda run -n ppt-master python scripts/error_helper.py missing_readme
conda run -n ppt-master python scripts/error_helper.py missing_readme project_path=my_project
```


