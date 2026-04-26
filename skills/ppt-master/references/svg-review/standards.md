# SVG Review Standards

## 1. Purpose

This document defines reusable SVG layout review standards for the `ppt-master` workflow.

It applies when:

- SVG pages are generated sequentially for presentation delivery
- the output must remain stable in `svg_final/`, browser whole-page preview, and PPT export
- the goal is to reduce rework by fixing root causes early

## 2. Core Principles

Every review should follow these rules:

1. Check the real delivery target, not just the source SVG draft
2. Diagnose the root cause before choosing a fix
3. Fix structure before shrinking text
4. Prefer changing generation logic over one-off manual patching
5. Treat `svg_final + browser whole-page preview + PPT export` as the final closure loop

Do not:

- judge overflow by opening the raw `.svg` in an unscaled browser viewport
- start by shrinking font size
- move isolated coordinates without checking the grid
- skip review artifacts and rely on memory

## 3. Symptom vs Root Cause

Do not confuse visible symptoms with the actual layer that needs fixing.

### Common Symptoms

- overflow
- edge crowding
- collision
- overlap / covering
- misalignment
- visual imbalance

### Root-cause Layers

- **Copy layer**: the wording is too long or too dense for presentation reading
- **Container layer**: padding, width, height, or text anchor is wrong
- **Grid layer**: columns, gaps, top lines, center lines, or spacing rhythm are unstable
- **Layering / rendering layer**: draw order or connector termination is wrong
- **Pipeline / export layer**: `svg_output`, `svg_final`, preview, and PPT result diverge

## 4. Fix Order

Preferred order:

1. shorten the copy
2. split into multiple lines
3. resize or reposition the container
4. rebuild the grid
5. adjust draw order or connector termination
6. shrink font size only as a last resort

## 5. Common Error Matrix

| Error | Typical Symptom | Typical Root Cause | Preferred Fix | Avoid |
|------|------------------|--------------------|---------------|-------|
| Viewport misread | Looks cropped in raw browser view | Browser is not showing whole-page scale | Use whole-page preview | Judging from scrollbars |
| Copy overload | Small card contains long explanation | Copy density exceeds container capacity | Shorten, rewrite as keywords, split lines | Shrinking font first |
| Edge crowding | Text is inside box but too close to edge | Padding or height is insufficient | Add safe margin, enlarge container if needed | Treating "not overflowing" as pass |
| Column squeeze | Table columns fight for space | Column width, gap, or anchor is wrong | Recalculate column widths and anchors | Moving one cell only |
| Block drift | Two or three columns are not on one axis | Grid has no shared reference line | Rebuild the grid | Visual micro-adjustment only |
| Connector intrusion | Arrow enters target card | End point is too deep | Stop before target safe zone | Shortening by 1-2px and stopping |
| Layering issue | Arrow or center node gets covered | Draw order is wrong | Reorder layers | Moving coordinates only |
| Export mismatch | Browser looks fine but PPT shifts | Only source SVG was checked | Re-check `svg_final` and PPT export | Validating `svg_output` only |

## 6. Suggested Safety Standards

Reference values below assume a `1280 x 720` canvas. Scale proportionally for other canvas sizes.

### Horizontal Safe Margin

- page title: at least `24px`
- summary band: at least `20px`
- regular card body: at least `16px`
- small node text: at least `14px`
- table cell text: at least `12px`

### Vertical Bands

- title band to summary band: at least `12px`
- summary band to first body component: at least `16px`
- body area to footer: at least `20px`

### Text Line Guidance

- summary band: 1 line, at most 2
- card title: 1 line, at most 2
- card body: 2-3 lines
- small node body: ideally 2 lines, at most 3
- list item explanation: ideally 1-2 lines

### Connector Rule

- connectors must not enter the target content area
- arrow tips should stop `8-12px` before the target boundary
- last node must not keep a forward arrow when no next step exists

## 7. Acceptance Standard

A page is only considered stable when:

- the symptom is removed from the intended delivery stage
- no new structural problem is introduced
- the fix is reflected in generation logic or a justified reusable pattern

A deck is only considered ready for export when:

- no `P0` remains
- no unresolved `P1` remains
- retained `P2` issues are documented and explicitly non-blocking
- the user approves the reviewed SVG set before export
