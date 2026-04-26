# SVG Review Workflow

## Purpose

This document explains the SVG review mechanism used before post-processing and PPT export.

It complements:

- `docs/svg-pipeline.md` for pipeline order
- `references/svg-review/` for review rules
- `templates/review/` for review artifacts

## Review Stages

### 1. Per-page Self-review

After each SVG page is generated, apply the protocol in:

- `references/svg-review/quick-reference.md`
- `references/svg-review/page-type-matrix.md`
- `references/svg-review/priority-rules.md`

### 2. Whole-deck Review Gate

After all pages and `notes/total.md` are complete, finalize review records and prepare export approval.

## Review Artifacts

Store review evidence in `<project_path>/review/`:

- `review_state.json`
- `review_log.md`
- `fix_tasks.md`
- `user_confirmation.md`
- `revision_round.json` (when a user-driven revision loop is active)

Recommended templates live under `templates/review/`.
Legacy `review_state.json` files that still use top-level `review_state` / `summary` fields are auto-normalized into the current `pages` + `approval` schema on the next helper-driven write.

CLI helper:

```bash
conda run --no-capture-output -n ppt-master python scripts/review_manager.py init <project_path>
conda run --no-capture-output -n ppt-master python scripts/review_manager.py sync <project_path>
conda run --no-capture-output -n ppt-master python scripts/review_manager.py set-page <project_path> --file 01_cover.svg --priority none --reviewed yes --note "layout pass"
conda run --no-capture-output -n ppt-master python scripts/review_manager.py set-pages <project_path> --json-file review_updates.json
conda run --no-capture-output -n ppt-master python scripts/review_manager.py status <project_path> --compact
conda run --no-capture-output -n ppt-master python scripts/review_manager.py verify <project_path> --json
conda run --no-capture-output -n ppt-master python scripts/review_manager.py repair-focus <project_path>
conda run --no-capture-output -n ppt-master python scripts/review_manager.py next-action <project_path> --json
conda run --no-capture-output -n ppt-master python scripts/review_manager.py approve <project_path> --by <name>
conda run --no-capture-output -n ppt-master python scripts/revision_manager.py create-round <project_path> --json-file revision_tasks.json --title "round 1"
conda run --no-capture-output -n ppt-master python scripts/revision_manager.py scaffold-tasks <project_path> --files 03_architecture.svg 06_patent_innovation.svg
conda run --no-capture-output -n ppt-master python scripts/revision_manager.py set-page <project_path> --file 03_architecture.svg --status ready_for_review
conda run --no-capture-output -n ppt-master python scripts/revision_manager.py prepare-verify <project_path> --by <name>
conda run --no-capture-output -n ppt-master python scripts/revision_manager.py close-round <project_path>
```

`review_manager.py verify` is now the unified review gate entry. By default it also runs:
- review-source build to `review/preview_finalized/`
- Content Outline accountability between `design_spec.md` Section IX and `svg_output/*.svg`
- SVG technical validation on the reviewed raw SVG set under `svg_output/`
- layout geometry validation on the reviewed raw SVG set under `svg_output/`
- text-vs-container overflow validation on the reviewed raw SVG set under `svg_output/`
- icon-reference validation on the reviewed raw SVG set under `svg_output/`
- preview page generation to `review/preview_deck.html`

Use `--skip-*` flags only when you intentionally need to bypass one of these checks for debugging.

### Structured Revision Loop

When the user gives a final-review feedback bundle, do not jump directly back to whole-deck verify.
The human-facing loop should stay simple:

1. the user reviews the current approval surface and gives modification feedback
2. the agent structures that feedback into a revision round
3. the agent executes page fixes, local checks, and round-state updates
4. the user reviews the refreshed approval surface again only at the next final review pass

The revision commands below are agent-facing internal mechanics, not extra steps the user is expected to manage manually.

Preferred loop:

1. create `review/revision_round.json` from the user feedback via `revision_manager.py create-round`
2. revise only the listed pages
3. update each page to `ready_for_review` or `approved` via `revision_manager.py set-page`
4. once no listed page remains in `todo` / `in_progress`, run `review_manager.py verify <project_path>`
5. optionally run `revision_manager.py prepare-verify` as an agent-side bookkeeping marker before or after that verify

Strict gate behavior:

- an active revision round blocks whole-deck `review_manager.py verify`
- an active revision round also blocks Step 8 post-processing/export through the existing review gate while unresolved pages remain
- unresolved means page status is still `todo` or `in_progress`
- `ready_for_review` and `approved` are both treated as resolved agent-side states for whole-deck verify
- `prepare-verify` is optional metadata, not a human approval checkpoint
- after a successful whole-deck verify, the active round is auto-closed; `revision_manager.py close-round` remains only as a recovery/debug tool

Agent-first revision task input:

- Fastest path: generate a machine-friendly JSON skeleton with `revision_manager.py scaffold-tasks`
- Static example template: `templates/review/revision_tasks_template.json`
- Recommended workflow for agents: scaffold only the reviewed pages, fill the issue fields, then run `revision_manager.py create-round`
- Human reviewers should not need to touch `revision_tasks.json` directly in the normal loop

Minimal field guidance:

- `file`: target SVG filename under `svg_output/`
- `status`: start with `todo`
- `note`: short round-level or page-level constraint
- `allowed_changes`: allowed edit categories for the whole page entry (`layout`, `copy`, `visual`, `structure`, `assets`)
- `issues[]`: one item per user-visible finding
- `issues[].symptom`: visible problem observed in the final review pass
- `issues[].target`: the intended fixed state
- `issues[].priority`: `P0` / `P1` / `P2`
- `issues[].allowed_changes`: optional tighter change boundary for that issue

Example:

```bash
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/revision_manager.py scaffold-tasks <project_path> --files 03_architecture.svg 06_patent_innovation.svg --output revision_tasks.json
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/revision_manager.py create-round <project_path> --json-file revision_tasks.json --title "round 1"
```

When consuming `review/verify_report.json` for repair work, prefer this order:

1. `repair_focus`
2. `failure_details`
3. `warning_details`

`repair_focus` is the shortest agent-oriented queue. It deliberately de-emphasizes top-level gate bookkeeping blockers such as pending approval when lower-level SVG issues are already known and more actionable.
If you only need the compact queue and do not want to re-open the full JSON, use:
`conda run --no-capture-output -n ppt-master python scripts/review_manager.py repair-focus <project_path>`

For the smallest machine-oriented decision surface, prefer:
`conda run --no-capture-output -n ppt-master python scripts/review_manager.py next-action <project_path> --json`

`next-action --json` is the recommended agent entry because it already resolves:

- whether the current blocker is revision-round state, review-gate state, technical SVG issues, pending user approval, or export readiness
- whether the latest verify report should be consulted
- the shortest next command to run when one is appropriate

Freshness rule:

- treat `review/verify_report.json` as reusable only when it is newer than the current review inputs under `svg_output/*.svg`, `review/review_state.json`, and `review/revision_round.json`; otherwise `next-action` should return `run_verify`

### Validation Cadence Recommendation

When you are changing checker logic or review-gate scripts themselves, avoid repeatedly running the full project-level gate after every small edit.

Preferred validation order:

1. run the smallest possible check first (`py_compile`, one targeted unit test, or one minimal SVG fixture)
2. confirm the specific regression is fixed
3. run `review_manager.py verify <project_path>` only when you need an end-to-end gate decision

For icon-contract regressions, prefer the dedicated minimal regression test first:

```bash
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/tests/test_icon_contract.py
```

This keeps token usage and local iteration cost low while preserving the final Step 7 gate as the last end-to-end check.

Layout warning quick reference:

- preview correct + warning only from multi-line `<tspan>` width estimation -> prefer fixing the checker
- preview correct + warning only from a decorative translated bar/underline group -> prefer fixing the checker
- visible off-canvas cards/panels/labels -> fix the SVG
- visible misalignment or true local/global coordinate mismatch -> fix the SVG

Preview basis during Step 7:
- `review_manager.py verify` first prepares one unified review SVG source at `review/preview_finalized/`
- That directory is the only Step 7 review target: it contains copied `svg_output` pages plus any preview-safe processing needed for icons/images
- The approval-time HTML preview is `review/preview_deck.html`, generated from `review/preview_finalized/`
- Serve the project root when opening that HTML so both `review/` and the review SVG source are reachable
- Review-only finalized assets exist only to support trustworthy approval; they are not the formal Step 8 export output
- Technical/layout/icon checks remain anchored to the reviewed raw SVG set under `svg_output/`

## Export Gate Rule

Do not run `total_md_split.py`, `finalize_svg.py`, or `svg_to_pptx.py` until the review gate is complete and the user has approved.

This rule is `MANDATORY`, not a recommendation.

Enforcement boundary:

- `total_md_split.py`, `finalize_svg.py`, and `svg_to_pptx.py` all enforce the gate automatically
- the gate now checks both the minimal export conditions and the supporting deck-level diagnostics: every SVG page is reviewed, no page remains at `P0/P1`, export approval is present, the unified review SVG source builds successfully, technical/layout/icon checks on the reviewed raw SVG set are clean, and preview generation succeeds

## Artifact Write Rule

- During Step 6 / Step 7, generate `svg_output/*.svg`, `notes/*.md`, and `review/*.md` with IDE/native file editing tools or repository Python helpers
- On Windows/Trae, do **not** use shell redirection or PowerShell file-writing commands for these artifacts
- Treat `review_state.json` as the machine source of truth; render Markdown artifacts from it instead of using Markdown as the gate input
- Do not spend review time hand-editing long JSON fields; the long-term path is `SVG` first, minimal gate state second
- When multiple page reviews must be written, prefer `review_manager.py set-pages --json-file ...` instead of ad-hoc subprocess loops
- When `notes/total.md` needs one-page append/replace updates, prefer `notes_manager.py upsert-total ...` instead of `python -c` inline write commands

## Boundary With `svg_quality_checker.py`

- `svg_quality_checker.py` validates technical compliance
- `review_manager.py verify` also validates deck-level accountability that individual SVG checkers cannot infer, such as whether `design_spec.md` declares the same slide set that `svg_output/` actually contains
- `svg_layout_checker.py` validates obvious geometry and coordinate-system mistakes
- `svg_text_container_checker.py` validates whether text still fits its likely local card/container background
  - hard error: text clearly exceeds the assigned local container
  - warning only: text is too close to the edge, or may widen further in PPT export based on converter-style width estimation
- SVG review validates layout quality, readability, grid stability, and export readiness
- both are useful, but they solve different problems

## Layout Warning Notes

How to interpret `svg_layout_checker.py` warnings:

- Warnings are heuristics, not automatic proof that a page must be rejected
- Treat warnings as review prompts first, then confirm against the whole-page preview and actual slide intent

Current false-positive guards:

- Multi-line `<text>` blocks that use `<tspan>` are evaluated line by line instead of estimating width from the concatenated full paragraph
- `translate()` groups that only contain a narrow decorative bar or underline are not treated as container-coordinate mismatches

What should still be treated as meaningful warnings:

- cards, panels, or labels that visibly extend beyond the 1280x720 canvas
- translated groups where text coordinates genuinely look detached from the local card/container system
- large text blocks whose real rendered width or height is likely to exceed the intended safe area

Review rule:

- If `svg_layout_checker.py` warns but browser whole-page preview and intended export layout are both clearly correct, prefer fixing the checker heuristic rather than forcing a cosmetic SVG rewrite
- If the warning corresponds to a visible overflow or misalignment in preview, fix the SVG layout and re-run review


