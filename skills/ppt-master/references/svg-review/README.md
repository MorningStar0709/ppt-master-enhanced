# SVG Review Reference

This directory is the long-term reference hub for SVG review inside `ppt-master`.

## Purpose

Use these documents to reduce SVG rework before PPT export:

- identify layout symptoms accurately
- diagnose root causes instead of guessing
- record review findings in a reusable format
- enforce the rule: review first, export later

## Recommended Reading Order

1. `quick-reference.md` — fast on-the-job reminder during page generation
2. `page-type-matrix.md` — page-type symptom and fix lookup
3. `priority-rules.md` — decide whether the page can pass
4. `standards.md` — full review standards and acceptance rules
5. `playbook.md` — end-to-end execution loop after issues are found

## Responsibilities

- `standards.md`: defines symptoms, root-cause layers, pass criteria, and review closure
- `playbook.md`: defines the execution and verification loop
- `quick-reference.md`: compressed field guide for live generation
- `page-type-matrix.md`: page-type specific symptom-to-fix guidance
- `priority-rules.md`: defines `P0 / P1 / P2` and blocking rules

## Execution Rule

These references apply in two layers:

1. **Per-page self-review** during Executor generation
2. **Whole-deck review gate** before `total_md_split.py`, `finalize_svg.py`, and `svg_to_pptx.py`

## Review Artifacts

The Executor should keep review evidence under `<project_path>/review/`:

- `review_state.json`
- `review_log.md`
- `fix_tasks.md`
- `user_confirmation.md`
