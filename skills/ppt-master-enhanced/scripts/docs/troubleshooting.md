# Troubleshooting

## Validation Failed

1. Run:

```bash
conda run --no-capture-output -n ppt-master python scripts/project_manager.py validate "<project_path>"
```

2. Fix missing files or invalid directories reported by the validator.
3. Re-run validation before post-processing or export.

## SVG Preview Looks Wrong

1. Check the file path and filename.
2. Confirm naming conventions are consistent.
3. Preview via a local server if browser file loading is inconsistent. Serve the project root, not `review/` alone, so `review/preview_deck.html` can still reach the Step 7 review SVG source or `svg_final/`:

```bash
conda run --no-capture-output -n ppt-master python -m http.server --directory "<project_path>" 8000
```

4. Do not judge final layout quality from the raw `.svg` viewport alone. Whole-page preview and review records are the correct decision path.
5. Build the unified Step 7 review source first when you need a stable approval surface:

```bash
conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify <project_path> --compact
```

6. Open `review/preview_deck.html` through the project-root server. Do not treat “opening a raw `.svg` file directly in Trae/browser” as the approval-time review surface.
7. If you need the lower-level helper directly, `--review-preview` writes the same unified review SVG source used by Step 7:

```bash
conda run --no-capture-output -n ppt-master python scripts/finalize_svg.py "<project_path>" --review-preview
conda run --no-capture-output -n ppt-master python scripts/preview_svg_deck.py "<project_path>" -s review/preview_finalized
```

8. `review/preview_finalized/` exists only to improve Step 7 preview reliability. It does not count as final export processing, and the normal Step 8 approval gate still applies.

## SVG Output Looks Fine But Final Result Does Not

1. Compare `svg_output/` with `svg_final/`.
2. Re-check whether post-processing changed text, icons, images, or rounded shapes.
3. Use the SVG Review Gate before export instead of assuming the draft state is good enough.
4. If layout changed after post-processing, update the review log and fix the generation logic or the relevant SVG pipeline assumption.

## Layout Checker Warnings But Preview Looks Fine

1. Re-run the browser whole-page preview before editing the SVG just because of a warning.
2. Common checker false positives include:
   - multi-line `<tspan>` blocks previously being over-estimated as one long line
   - `translate()` groups that only wrap a decorative bar or underline
3. If the warning is only heuristic noise and the preview/export intent is clearly correct, improve the checker rule instead of forcing a cosmetic rewrite.
4. If the warning matches visible overflow, off-canvas cards, or genuine coordinate mismatches, treat it as a real layout defect and fix the SVG.

## Speaker Notes Do Not Split

Check `total.md`:
- headings must start with `# `
- heading text must match SVG filenames
- sections must be separated by `---`
- review evidence must already pass the SVG Review Gate

Then rerun:

```bash
conda run --no-capture-output -n ppt-master python scripts/total_md_split.py "<project_path>"
```

## PPT Export Quality Issues

Preferred sequence:

```bash
conda run --no-capture-output -n ppt-master python scripts/total_md_split.py "<project_path>"
conda run --no-capture-output -n ppt-master python scripts/finalize_svg.py "<project_path>"
conda run --no-capture-output -n ppt-master python scripts/svg_to_pptx.py "<project_path>" -s final
```

Do not export directly from `svg_output/` when `svg_final/` exists.

Also remember:

- do not export before whole-deck review is complete
- do not export before the user approves the reviewed SVG set

## Why Shrinking Font Size First Usually Fails

- Text crowding is often caused by copy density, container size, grid problems, or layering issues.
- Shrinking font size too early may hide the symptom while leaving the structure unstable.
- Preferred fix order:
  1. shorten the copy
  2. split into lines
  3. adjust the container
  4. rebuild the grid
  5. change draw order if needed
  6. shrink font as the last resort

## When To Rebuild The Grid

Rebuild the grid instead of micro-adjusting isolated elements when:

- two or more columns do not share a reference line
- table columns squeeze or drift repeatedly
- process cards are not centered as a group
- roadmap / three-phase content does not share one axis
- repeated local coordinate tweaks keep breaking nearby elements

## Review Gate Keeps Blocking Export

1. Check `review/review_state.json` first, then the rendered Markdown reports.
2. Confirm whether any `P0` or unresolved `P1` remains.
3. Revisit `references/svg-review/priority-rules.md` if the issue level is unclear.
4. Prepare `review/user_confirmation.md` only after blocking issues are closed.
5. Run `conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify <project_path> --compact` for concise blockers, or add `--json` for machine-readable output.

## Why Did Windows Fall Back To PowerShell File Writes

- Step 6 SVG generation does not have a single monolithic `generate_svg.py` entry point today; it is performed by the main agent using upstream context.
- That is **not** a license to use PowerShell file-writing commands for SVG / notes / review artifacts.
- On Windows/Trae, use IDE/native file editing tools or repository Python helpers for artifact writes, and reserve terminal Python commands for project setup, checking, post-processing, and export.

## Conda Run Looks Broken In Windows Terminals

- Prefer `conda run --no-capture-output -n ppt-master python ...` as the first choice on Windows.
- Set these once in the current terminal session before running Python commands:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:CONDA_NO_PLUGINS='true'
```

## Project Created In The Wrong Folder

- Run Step 2 from the repository root with `python skills/ppt-master-enhanced/scripts/project_manager.py ... --dir projects`
- Do not switch into `skills/ppt-master-enhanced/scripts/` before running `init`
- Reuse the printed `projects/...` path exactly; do not infer it from the original project title

## Why Project Directories Do Not Use Timestamps

- The project directory is the stable machine-facing identity for the workflow
- A timestamp in the project directory forces later steps to rediscover or guess the path, which creates ambiguity
- Creation time is recorded as metadata instead
- Timestamped names are reserved for exported PPTX files under `exports/`, where historical snapshots are desirable

## Why English-Only Filenames Are Required

- The workflow now treats English-only filenames as the machine-safe baseline
- Use an English project slug for `init`
- `import-sources` normalizes archived files under `sources/` to English-only names so downstream scripts, SVG references, and export steps stay stable

## Dependency Checklist

Most tools use the standard library. Install extra dependencies only when needed:

```bash
conda run -n ppt-master pip install -r requirements.txt
```

Important optional packages:
- `python-pptx` for PPTX export
- `Pillow` for image utilities
- `numpy` for watermark removal
- `PyMuPDF` for PDF conversion
- `google-genai` / `openai` for image generation backends


