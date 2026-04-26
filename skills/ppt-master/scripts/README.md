# PPT Master Toolset

This directory contains user-facing scripts for conversion, project setup, SVG processing, export, and image generation.

## Directory Layout

- Top-level `scripts/`: runnable entry scripts
- `scripts/source_to_md/`: source-document → Markdown converters (`pdf_to_md.py`, `doc_to_md.py`, `ppt_to_md.py`, `web_to_md.py`, `web_to_md.cjs`)
- `scripts/image_backends/`: internal provider implementations used by `image_gen.py`
- `scripts/template_import/`: internal PPTX reference-preparation helpers used by `pptx_template_import.py`
- `scripts/svg_finalize/`: internal post-processing helpers used by `finalize_svg.py`
- `scripts/docs/`: topic-focused script documentation
- `scripts/assets/`: static assets consumed by scripts

## Quick Start

Typical end-to-end workflow:

```bash
conda run -n ppt-master python scripts/source_to_md/pdf_to_md.py <file.pdf>
# or
conda run -n ppt-master python scripts/source_to_md/ppt_to_md.py <deck.pptx>
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/project_manager.py init <project_name> --format ppt169 --dir projects
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/project_manager.py import-sources "<project_path>" "<source_files...>" --copy
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/project_manager.py apply-template "<project_path>" <template_name>
# Reuse the exact project path printed by init; do not infer it from <project_name>
# init already creates svg_output/, notes/, review/, templates/, sources/, exports/, etc.
# Apply a library layout template here only when Step 3 selected "use template"
# Generate SVG pages and complete per-page review / whole-deck review gate first
conda run -n ppt-master python scripts/total_md_split.py <project_path>
conda run -n ppt-master python scripts/finalize_svg.py <project_path>
conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -s final
```

Execution discipline:

- Generate Step 6 SVG / notes / review artifacts with IDE/native file editing tools or repository Python helpers, not shell redirection
- On Windows/Trae, do not use `>`, `>>`, `Out-File`, `Set-Content`, `Add-Content`, or `New-Item` to create `svg_output/*.svg`, `notes/*.md`, or `review/*.md`
- Launch the main workflow from the repository root; do not switch into `skills/ppt-master/scripts/` first
- Use English-only project slugs and rely on `import-sources` to normalize archived filenames under `sources/` to English-only names
- After `project_manager.py init`, always propagate the exact printed project path to later commands; the actual directory name is `projects/<project_name>_<normalized_format>`
- Project directories do not carry timestamps; that is intentional so the project path stays stable across retries and later turns
- Export filenames under `exports/` do carry timestamps; that is also intentional because exports are historical artifacts, not the stable project identifier
- If the target project directory already exists, do not invent a guessed variant; either reuse that exact project path or choose a different project slug explicitly
- Do not manually create the standard project directories after `init`; PowerShell-specific directory commands are outside the normal workflow and add avoidable noise

Repository update:

```bash
conda run -n ppt-master python scripts/update_repo.py
```

## Script Index

| Area | Primary scripts | Documentation |
|------|-----------------|---------------|
| Conversion | `source_to_md/pdf_to_md.py`, `source_to_md/doc_to_md.py`, `source_to_md/ppt_to_md.py`, `source_to_md/web_to_md.py`, `source_to_md/web_to_md.cjs` | [docs/conversion.md](./docs/conversion.md) |
| Project management | `project_manager.py`, `review_manager.py`, `batch_validate.py`, `generate_examples_index.py`, `error_helper.py`, `pptx_template_import.py` | [docs/project.md](./docs/project.md) |
| Asset lookup | `asset_lookup.py` | [docs/project.md](./docs/project.md) |
| SVG pipeline | `finalize_svg.py`, `svg_to_pptx.py`, `total_md_split.py`, `svg_quality_checker.py`, `svg_layout_checker.py`, `icon_reference_checker.py`, `preview_svg_deck.py` | [docs/svg-pipeline.md](./docs/svg-pipeline.md), [docs/svg-review.md](./docs/svg-review.md) |
| Image tools | `image_gen.py`, `analyze_images.py`, `gemini_watermark_remover.py` | [docs/image.md](./docs/image.md) |
| Repo maintenance | `update_repo.py` | README install/update section |
| Troubleshooting | validation, preview, review gate, export, dependency issues | [docs/troubleshooting.md](./docs/troubleshooting.md) |

## High-Frequency Commands

Conversion:

```bash
conda run -n ppt-master python scripts/source_to_md/pdf_to_md.py <file.pdf>
conda run -n ppt-master python scripts/source_to_md/ppt_to_md.py <deck.pptx>
conda run -n ppt-master python scripts/source_to_md/doc_to_md.py <file.docx>
conda run -n ppt-master python scripts/source_to_md/web_to_md.py <url>
```

Project setup:

```bash
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/project_manager.py init <project_name> --format ppt169 --dir projects
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/project_manager.py import-sources "<project_path>" "<source_files...>" --copy
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/project_manager.py apply-template "<project_path>" <template_name>
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/project_manager.py validate <project_path>
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/review_manager.py set-page <project_path> --file 01_cover.svg --priority none --reviewed yes --note "layout pass"
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/review_manager.py status <project_path> --compact
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/review_manager.py verify <project_path> --compact
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/review_manager.py verify <project_path> --json
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/review_manager.py sync <project_path>
conda run -n ppt-master python scripts/asset_lookup.py charts roadmap
conda run -n ppt-master python scripts/asset_lookup.py icons chunk/signal --exact
conda run -n ppt-master python scripts/asset_lookup.py icons chart --library chunk
```

Template source import:

```bash
conda run -n ppt-master python scripts/pptx_template_import.py <template.pptx>
conda run -n ppt-master python scripts/pptx_template_import.py <template.pptx> --manifest-only
```

Post-processing and export:

Step 1. Only run after the SVG Review Gate is complete and the user approved export:

```bash
conda run -n ppt-master python scripts/total_md_split.py <project_path>
```

Step 2. After Step 1 completes successfully:

```bash
conda run -n ppt-master python scripts/finalize_svg.py <project_path>
```

Step 3. After Step 2 completes successfully:

```bash
conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -s final
```

Preview and compact diagnostics:

```bash
conda run --no-capture-output -n ppt-master python scripts/preview_svg_deck.py <project_path>
conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify <project_path> --compact
conda run --no-capture-output -n ppt-master python scripts/svg_quality_checker.py <project_path> --summary-only --check-icons
conda run --no-capture-output -n ppt-master python scripts/icon_reference_checker.py <project_path> --summary-only
conda run --no-capture-output -n ppt-master python scripts/svg_layout_checker.py <project_path> --summary-only
```

Image generation:

```bash
conda run -n ppt-master python scripts/image_gen.py "A modern futuristic workspace"
conda run -n ppt-master python scripts/image_gen.py --list-backends
conda run -n ppt-master python scripts/analyze_images.py <project_path>/images
```

Repository update:

```bash
conda run -n ppt-master python scripts/update_repo.py
conda run -n ppt-master python scripts/update_repo.py --skip-pip
```

## Recommendations

- Keep one user-facing entry point per workflow at the top level of `scripts/`
- Move provider-specific or helper internals into subdirectories
- Prefer the unified entry points `project_manager.py`, `finalize_svg.py`, and `image_gen.py`
- Prefer `review_manager.py` for minimal page review recording, Markdown sync/render, evidence verification, and export approval
- Treat `review_manager.py verify` as the unified gate entry for review evidence, Step 7 review-source build under `review/preview_finalized/`, technical/layout/icon checks on the reviewed raw SVG set, and preview generation
- Prefer `asset_lookup.py` for targeted chart/icon lookup instead of full-index reads or shell-specific file search
- Prefer `icon_reference_checker.py` to catch missing `data-icon` references before review churn or export
- Prefer `svg_quality_checker.py --check-icons` when you want one technical-check command to also validate icon references
- Prefer `batch_validate.py` for repository-wide structure + quality + layout + icon + review-gate inspection
- Prefer `svg_final/` over `svg_output/` when exporting
- Treat `svg_quality_checker.py` as a technical validator, not as a substitute for SVG review
- Treat `svg_layout_checker.py` as a lightweight geometry guardrail before visual review
- Keep review artifacts under `<project_path>/review/` before export, with `review_state.json` as the machine source of truth and only minimal gate fields

## Related Docs

- [Conversion Tools](./docs/conversion.md)
- [Project Tools](./docs/project.md)
- [SVG Pipeline Tools](./docs/svg-pipeline.md)
- [SVG Review Workflow](./docs/svg-review.md)
- [Image Tools](./docs/image.md)
- [Troubleshooting](./docs/troubleshooting.md)
- [AGENTS Guide](../../../AGENTS.md)

_Last updated: 2026-04-19_

