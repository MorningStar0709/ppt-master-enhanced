# User Project Workspace

This directory is used for storing in-progress projects.

## Create a New Project

```bash
conda run --no-capture-output -n ppt-master python skills/ppt-master/scripts/project_manager.py init my_project --format ppt169
```

If paths, filenames, or content may include non-ASCII characters on Windows/Trae, set:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:CONDA_NO_PLUGINS='true'
```

## Directory Structure

A typical project usually contains the following:

```
project_name_format/
├── README.md
├── design_spec.md
├── sources/
│   ├── Raw files / URL archives / Converted Markdown
│   └── *_files/                  # Markdown companion resource directory (e.g., images)
├── images/                       # Image assets used by the project
├── notes/
│   ├── 01_xxx.md
│   ├── 02_xxx.md
│   └── total.md
├── review/
│   ├── review_state.json         # Machine source of truth for review gate
│   ├── review_log.md             # Rendered review report
│   ├── fix_tasks.md              # Rendered fix-task report
│   ├── user_confirmation.md      # Rendered export approval report
│   ├── preview_deck.html         # Step 7 approval-time HTML preview
│   └── preview_finalized/        # Unified Step 7 review SVG source prepared by review_manager.py verify
│       ├── 01_xxx.svg
│       └── ...
├── svg_output/
│   ├── 01_xxx.svg
│   └── ...
├── svg_final/
│   ├── 01_xxx.svg
│   └── ...
├── templates/                    # Project-level templates (if any)
├── exports/
│   ├── *.pptx
│   └── *_svg.pptx
└── image_analysis.csv            # Optional, image scan analysis results
```

Projects can remain at different stages and do not necessarily have all artifacts at once. For example:

- Only `sources/` archiving and the Design Specification & Content Outline (design_spec) are complete
- `svg_output/` and `review/review_state.json` have been generated, but post-processing has not yet been executed
- `svg_final/`, `notes/`, `review/`, and `exports/` are all complete

## Runtime Boundaries

- `skills/ppt-master/` stores the skill code, templates, and references
- `skills/ppt-master/.runtime/command_reports/` stores machine-readable "last command" receipts for helper CLIs such as `project_manager.py` and `asset_lookup.py`
- `projects/<project>/review/` stores project-specific review state such as `review_state.json`, `verify_report.json`, and approval artifacts

## Review Workflow Notes

- Use `review/review_state.json` as the machine source of truth for the SVG Review Gate
- `review_log.md`, `fix_tasks.md`, and `user_confirmation.md` are rendered reports derived from `review_state.json`
- `review_manager.py verify` first prepares `review/preview_finalized/` as the only Step 7 review SVG directory, then renders `review/preview_deck.html` from that directory
- Technical SVG checks, layout checks, and icon-reference checks still validate the reviewed raw SVG set under `svg_output/`
- Step 7 approval should be based on `review/preview_deck.html`, not on raw `svg_output/` or formal `svg_final/`
- Run post-processing only after the review gate passes and the user explicitly approves export

## Notes

- Contents under this directory are excluded by `.gitignore`
- Completed projects can be moved to the `examples/` directory for sharing
- Files outside the workspace are copied by default; files within the workspace are moved directly to the project's `sources/`
- Image generation config is read from the repository-root `.env` only; `.trae/.env` is not supported

