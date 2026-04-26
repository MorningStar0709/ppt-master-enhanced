# Executor Common Guidelines

> Style-specific content is in the corresponding `executor-{style}.md`. Technical constraints are in `shared-standards.md`. SVG review rules are centralized in `references/svg-review/`.

---

## 1. Template Adherence Rules

If template files exist in the project's `templates/` directory, the template structure must be followed:

| Page Type | Corresponding Template | Adherence Rules |
|-----------|----------------------|-----------------|
| Cover | `01_cover.svg` | Inherit background, decorative elements, layout structure; replace placeholder content |
| Chapter | `02_chapter.svg` | Inherit numbering style, title position, decorative elements |
| Content | `03_content.svg` | Inherit header/footer styles; **content area may be freely laid out** |
| Ending | `04_ending.svg` | Inherit background, thank-you message position, contact info layout |
| TOC | `02_toc.svg` | **Optional**: Inherit TOC title, list styles |

### Page-Template Mapping Declaration (Required Output)

Before generating each page, you must explicitly output which template (or "free design") is used:

```
📝 **Template mapping**: `templates/01_cover.svg` (or "None (free design)")
🎯 **Adherence rules / layout strategy**: [specific description]
```

- **Content pages**: Templates only define header and footer; the content area is freely laid out by the Executor
- **No template**: Generate entirely per the Design Specification & Content Outline

If the upstream decision was **using an existing template**, treat missing or incomplete project template assets as a blocking setup error:
- expected minimum: `templates/design_spec.md` plus at least one `templates/*.svg`
- if those files are missing, stop and run `project_manager.py apply-template <project_path> <template_name>` before generating any page
- do not downgrade to ad-hoc free design just because the template application step was skipped

---

## 2. Design Parameter Confirmation (Mandatory Step)

> Before generating the first SVG page, you **must review the key design parameters from the Design Specification & Content Outline** to ensure all subsequent generation strictly follows the spec.

Must output confirmation including: canvas dimensions, body font size, color scheme (primary/secondary/accent HEX values), font plan.

**Why is this step mandatory?** Prevents the "spec says one thing, execution does another" disconnect.

---

## 3. Execution Guidelines

**Rule semantics for this role**:

- `MUST`: non-skippable execution rule
- `RECOMMENDED`: quality preference, not a gate by itself
- `FORBIDDEN`: action is not allowed

- **Proximity principle**: Place related elements close together to form visual groups; increase spacing between unrelated groups to reinforce logical structure
- **Absolute spec adherence**: Strictly follow the color, layout, canvas format, and typography parameters in the spec
- **Follow template structure**: If templates exist, inherit the template's visual framework
- **Main-agent ownership**: SVG generation must be performed by the current main agent, not delegated to sub-agents, because each page depends on shared upstream context and cross-page visual continuity
- **Generation rhythm**: First lock the global design context, then generate pages sequentially one by one in the same continuous context; grouped page batches (for example, 5 pages at a time) are not allowed
- **Review rhythm**: Every page must be reviewed immediately after generation. Do not finish the whole deck first and review later.
- **Artifact write discipline**: Use IDE/native file editing tools or repository Python helpers to write `svg_output/*.svg`, `notes/*.md`, and `review/*.md`. On Windows/Trae, PowerShell file-writing commands and shell redirection are forbidden for these artifacts
- **Mandatory execution phases**:
  1. **Visual Construction + Review Phase**: Generate all SVG pages continuously in sequential page order, and complete per-page review before advancing
  2. **Logic Construction Phase**: After all SVG pages pass per-page review, batch-generate speaker notes to ensure narrative coherence (Narrative Continuity)
  3. **Whole-deck Review Gate**: Finalize review artifacts, obtain user approval, then proceed to post-processing
- **Generated-image accountability**: If AI-generated images exist in `images/`, you must explicitly decide for each one whether it is inserted, deferred, or unused. Do not leave generated images disconnected from the reviewed deck without saying so.
- **Capability-aware fallback**: If a missing icon/image would normally escalate to AI generation, first verify that image-generation capability actually exists in the current environment. If not, switch immediately to a stable non-AI fallback instead of speculative AI retries.
- **Technical specifications**: See [shared-standards.md](shared-standards.md) for SVG technical constraints and PPT compatibility rules
- **Visual depth**: Use filter shadows, glow effects, gradient fills, dashed strokes, and gradient overlays from shared-standards.md to create layered depth — flat pages without elevation or emphasis look unfinished

### SVG File Naming Convention

File naming format: `<number>_<page_name>.svg`

- **Chinese content** → still use ASCII/English-safe filenames: `01_cover.svg`, `02_agenda.svg`, `03_core_advantages.svg`
- **English content** → English naming: `01_cover.svg`, `02_agenda.svg`, `03_key_benefits.svg`
- **Number rules**: Two-digit numbers, starting from 01
- **Page name**: Concise and descriptive, matching the page title in the Design Specification & Content Outline

---

## 4. Page-by-page Self-review Protocol

After generating each page, the Executor must pause and complete a structured self-review before moving to the next page.

### Mandatory Inputs

- `references/svg-review/quick-reference.md`
- `references/svg-review/page-type-matrix.md`
- `references/svg-review/priority-rules.md`
- `references/page-diagnostic-output-template.md`

### Required Review Actions Per Page

1. Identify the page type
2. Describe visible symptoms before writing any fix
3. Classify the likely root-cause layer using `references/svg-review/`
4. Check whether any `P0` / unresolved `P1` blocking rule is triggered
5. Assign `P0 / P1 / P2`
6. Decide whether the page may pass or must be revised immediately
7. Define structural fix actions only after the diagnostic fields above are complete
8. If the page is an architecture / system / layered relationship page, read `references/architecture-slide-rules.md` and review relationship clarity, density balance, and connector sufficiency before passing it

### Required Per-page Review Output

For each page, the Executor must explicitly output the full diagnostic structure from `references/page-diagnostic-output-template.md`.

The old short summary is not sufficient by itself. The per-page review output MUST diagnose before prescribing fixes, and MUST keep visible symptoms separate from inferred root causes.

```markdown
## Page Diagnostic Output
- File:
- Page type:
- Intended message:
- Visible symptoms:
- Root-cause layer:
- Blocking rule check:
- Priority:
- Pass decision:
- Required fixes:
- Review note:
```

Additional mandatory rules:

- `Page type` must be declared before any diagnosis
- `Visible symptoms` must contain only visible phenomena, not repair instructions
- `Root-cause layer` must use the dominant failure layer instead of mixing all possible causes together
- `Pass decision` may only be `pass` or `revise immediately`
- `Required fixes` must be structural actions; vague statements such as "tweak slightly" are not acceptable
- `Review note` should be a compact sentence that can be reused in `review_state.json`

If the page is primarily an architecture / system / layered relationship diagram, append the architecture-specific extension from `references/page-diagnostic-output-template.md`:

```markdown
- Primary flow direction:
- Relationship clarity:
- Connector sufficiency:
- Density balance:
- Overloaded region:
```

For architecture pages, do not default to equal-width redistribution, coordinate smoothing, or font shrinking before diagnosing relationship structure and density balance.

### Failure Handling Rule

- If a page has any `P0`, it MUST be revised immediately and may not proceed
- If a page has any unresolved `P1`, it should not proceed unless the issue is explicitly downgraded by the review rules and recorded with justification
- `P2` items may be carried into the whole-deck review only when they do not threaten layout stability or export safety

---

## 5. Per-page Review Checklist

Every page review should at minimum confirm:

- [ ] The page follows the Design Specification's canvas, color, and typography parameters
- [ ] The page follows the chosen template mapping or justified free-design strategy
- [ ] Layout stability, grid alignment, and visual hierarchy are acceptable
- [ ] Any issue found is classified and recorded with `P0 / P1 / P2`
- [ ] Any image area expected on the page is in the correct state: inserted and visible, or intentionally marked as placeholder with justification

### Architecture Page Mandatory Check

For architecture / system / layered relationship pages, additionally confirm:

- [ ] The primary flow direction is obvious
- [ ] Relationships are explicit, not implied only by stacking
- [ ] Mirrored regions are balanced in information density
- [ ] No region is overloaded enough that it should be split or reduced
- [ ] The page reads as an architecture diagram, not a module catalog

---

## 6. Review Artifact Update Rule

During page generation, maintain review artifacts under `<project_path>/review/`:

- `review/review_state.json` — machine source of truth for page reviews, fix tasks, and approval state
- `review/review_log.md` — rendered page-by-page review report
- `review/fix_tasks.md` — rendered outstanding-fix report
- `review/user_confirmation.md` — rendered whole-deck approval report

Rules:

- Prefer `review_manager.py set-page ...` to update the minimal gate state after each page review
- Keep the gate state minimal: page filename, reviewed yes/no, priority, and one compact note are enough
- The compact note should be derived from the `Review note` field of the page diagnostic output
- Re-render the Markdown reports from `review_state.json` whenever page review state changes
- Do not wait until the end of the deck to reconstruct review evidence from memory
- Do not use shell redirection or PowerShell write commands to maintain review artifacts on Windows/Trae
- If a page contains an image region, the review note should make clear whether the final image is already inserted, temporarily placeholder-only, or visually missing and requires revision

---

## 7. Whole-deck Review Gate

After all pages and `notes/total.md` are complete, the Executor must complete a final whole-deck review before any post-processing command runs.

Whole-deck review must confirm:

- all per-page review records are complete
- every SVG in `svg_output/` has exactly one corresponding review record
- deck summary matches the per-page records
- no `P0` remains
- no unresolved `P1` remains before export
- any retained `P2` is clearly logged
- browser whole-page preview and final intended export judgement are aligned
- generated images intended for use are actually referenced by the reviewed SVG set
- the user-visible preview is not falsely hiding images or icons in a way that could invalidate approval

If preview visibility is misleading:

- stop and fix the preview basis or asset integration issue before requesting user approval
- use one unified Step 7 review source under `review/preview_finalized/`; mixed raw-vs-final approval targets are forbidden
- approval-time preview must come from `review/preview_deck.html` backed by `review/preview_finalized/` and served from the project root
- do not convert a known preview defect into a user-approval responsibility

⛔ Do not run `total_md_split.py`, `finalize_svg.py`, or `svg_to_pptx.py` before the user explicitly approves the reviewed SVG set.

---

## 8. Icon Usage

Four approaches: **A: Emoji** (`<text>🚀</text>`) | **B: AI-generated** (SVG basic shapes) | **C: Built-in library** (`templates/icons/` 6700+ icons, recommended) | **D: Custom** (user-specified)

**Built-in icons — Placeholder method (recommended)**:

```xml
<!-- chunk (default — straight-line geometry, sharp corners, structured) -->
<use data-icon="chunk/home" x="100" y="200" width="48" height="48" fill="#005587"/>

<!-- tabler-filled (bezier-curve forms, smooth & rounded contours) -->
<use data-icon="tabler-filled/home" x="100" y="200" width="48" height="48" fill="#005587"/>

<!-- tabler-outline (light, line-art style — screen-only decks) -->
<use data-icon="tabler-outline/home" x="100" y="200" width="48" height="48" fill="#005587"/>
```

> No need to manually run `embed_icons.py`; `finalize_svg.py` post-processing tool will auto-embed icons.

**Three icon libraries**:

| Library | Style | Count | Prefix | When to use |
|---------|-------|-------|--------|-------------|
| `chunk` | fill · straight-line geometry (sharp corners, rectilinear) | 640 | `chunk/` | ✅ **Default** — most scenarios |
| `tabler-filled` | fill · bezier-curve forms (smooth, rounded contours) | 1000+ | `tabler-filled/` | When design calls for smooth, rounded, organic icon forms |
| `tabler-outline` | stroke/line | 5000+ | `tabler-outline/` | Screen-only decks needing a light, elegant aesthetic |

> ⚠️ **One presentation = one library.** Never mix icons from different libraries. If the chosen library lacks an exact icon, find the closest available alternative **within that same library** — do not cross into another library to fill the gap.

**Searching for icons** — use targeted lookup, not full catalog loading:
```bash
conda run -n ppt-master python scripts/asset_lookup.py icons chunk/signal --exact
conda run -n ppt-master python scripts/asset_lookup.py icons home --library chunk
conda run -n ppt-master python scripts/asset_lookup.py icons home --library tabler-filled
conda run -n ppt-master python scripts/asset_lookup.py icons chart --library tabler-outline
```

**Icon lookup shortcut**:

- Prefer `chunk` unless the deck explicitly selects another library
- Use `asset_lookup.py` for candidate discovery
- For larger examples and style guidance, see `templates/icons/README.md`

> ⚠️ **Icon validation rule**: If the Design Specification includes an icon inventory list, Executor may **only** use icons from that approved list. Before using any icon, verify it exists via `asset_lookup.py` or targeted file search. **Mixing icons from different libraries in the same presentation is FORBIDDEN** — use only the library specified in the Design Spec.

### Icon Resolution Protocol (Mandatory)

Do not enter repeated lookup loops for the same missing icon concept.

Use this exact resolution order:

1. Run exactly one exact-name check in the selected library
2. If not found, run exactly one semantic lookup pass with at most 3 keywords via `asset_lookup.py`
3. Choose one verified substitute from the same library only from actual lookup results
4. If no acceptable local icon exists, stop local lookup and escalate to the next asset source:
   - AI-generated icon or illustrative image via `scripts/image_gen.py`
   - externally sourced image / icon when internet access and workflow context allow it
   - labeled placeholder when neither of the above is available yet
5. Record the final chosen asset in the Design Spec icon inventory or page review note

Forbidden behaviors:

- repeating the same missing filename guess multiple times
- retrying the same failed keyword search without changing strategy
- running multiple semantic lookup rounds for the same concept
- using more than 3 semantic keywords for one unresolved concept
- inventing unverified `data-icon="library/name"` values
- staying stuck in local icon search when the concept clearly has no good local match

Practical rule:

- local icon verification: one exact check only
- semantic fallback: one targeted lookup pass only
- semantic lookup budget: maximum 3 keywords
- if still unresolved: switch asset source immediately instead of looping

Verified icon inventory guidance:

- maintain a short validated icon list for the deck when icon usage is important
- icon names must match actual filenames exactly
- when a substitute is chosen, prefer semantic closeness over repeated searching for a perfect but nonexistent match

Example:

- requested concept: `5G icon`
- exact check: `conda run -n ppt-master python scripts/asset_lookup.py icons chunk/5g --exact`
- semantic lookup keywords: `signal`, `network`, `wireless`
- if no acceptable verified icon is found after that pass, stop icon lookup and switch to AI generation, external sourcing, or a labeled placeholder

---

## 9. Visualization Reference

When the Design Spec includes a **VII. Visualization Reference List**, read the referenced SVG templates from `templates/charts/` before drawing pages that use those visualization types. The path remains `templates/charts/` for backward compatibility.

🚧 **GATE — Mandatory read before first use**: When Executor encounters a visualization type listed in Section VII of the Design Spec for the first time, Executor **MUST** `read_file templates/charts/<chart_name>.svg` **before** generating that page. Extract the layout coordinates, card structure, spacing rhythm, and visual logic from the template as **creative reference and inspiration** — not as a strict copy. Then design the page independently using the project's own color scheme, typography, and content.

> **Workflow**: read template SVG → understand structure & spacing → design original SVG informed by the reference → do NOT replicate the template verbatim.
> **Reuse**: Once a visualization type has been read and understood, there is no need to re-read for subsequent pages of the same type.
> **Change**: Read the new template when the visualization type changes or the structure needs re-reference.

**Adaptation rules**:
- **Must preserve**: Visualization type (bar/line/pie/timeline/process/framework etc.) as specified in the Design Spec
- **Must adapt**: Data values, labels, colors (match the project's color scheme), and dimensions to fit the page layout
- **May adjust freely**: Visual composition, axis ranges, grid lines, legend position, spacing, decorative elements — creative freedom is encouraged as long as the chart remains accurate and readable
- **Must NOT**: Change visualization type without Design Spec justification, or omit data points / structural elements specified in the outline

> Visualization templates: `templates/charts/` (52 types). Index: `templates/charts/charts_index.json`

---

## 10. Image Handling

Handle images based on their status in the Design Specification's "Image Resource List":

| Status | Source | Handling |
|--------|--------|----------|
| **Existing** | User-provided | Reference images directly from `../images/` directory |
| **AI-generated** | Generated by Image_Generator | Images already in `../images/`, reference directly |
| **Placeholder** | Not yet prepared | Use dashed border placeholder |

**Reference**: `<image href="../images/xxx.png" ... preserveAspectRatio="xMidYMid slice"/>`

**Placeholder**: Dashed border `<rect stroke-dasharray="8,4" .../>` + description text

Mandatory handling rules:

- `AI-generated` means the image file should already exist in `images/`; it does **not** mean the page may skip insertion
- if a generated image is intended for a page, insert it before page sign-off
- if a generated image is rejected or deferred, document that explicitly and keep the placeholder intentionally labeled
- do not let a page pass review with an unexplained blank image region after the image was already generated
- if no usable AI backend exists for a missing required image, do not keep trying automatic generation; use manual generation, external sourcing, labeled placeholder, or layout redesign

Fallback priority for missing visual assets:

1. verified local substitute
2. layout redesign that removes hard dependency
3. AI generation only when capability is verified
4. external sourcing when workflow context allows it
5. labeled placeholder as the final stable fallback

Rule: a labeled placeholder is acceptable as an explicit reviewed fallback; an unexplained blank region is not

---

## 11. Font Usage

Apply corresponding fonts for different text roles based on the font plan in the Design Specification & Content Outline:

| Role | Chinese Recommended | English Recommended |
|------|--------------------|--------------------|
| Title font | Microsoft YaHei / KaiTi / SimHei | Arial / Georgia |
| Body font | Microsoft YaHei / SimSun | Calibri / Times |
| Emphasis font | SimHei | Arial Black / Consolas |
| Annotation font | Microsoft YaHei / SimSun | Arial / Times |

---

## 12. Speaker Notes Generation Framework

### Task 1. Generate Complete Speaker Notes Document

After **all SVG pages are generated and pass per-page review**, enter the "Logic Construction Phase" and generate the complete speaker notes document in `notes/total.md`.

**Why not generate page-by-page?** Batch-writing notes allows planning transitions like a script, ensuring coherent presentation logic.

**Format**: Each page starts with `# <number>_<page_title>`, separated by `---` between pages. Each page includes: script text (2-5 sentences), `Key points: ① ② ③`, `Duration: X minutes`. Except for the first page, each page's text starts with a `[Transition]` phrase.

**Basic stage direction markers** (common to all styles):

| Marker | Purpose |
|--------|---------|
| `[Pause]` | Whitespace after key content, letting the audience absorb |
| `[Transition]` | Standalone paragraph at the start of each page's text, bridging from the previous page |

> Each style may extend with additional markers (`[Interactive]`/`[Data]`/`[Scan Room]`/`[Benchmark]` etc.), see `executor-{style}.md`.

**Language consistency rule**: All structural labels and stage direction markers in speaker notes **MUST match the presentation's content language**. When the presentation content is non-English, localize every label — do NOT mix English labels with non-English content.

| English | 中文 | 日本語 | 한국어 |
|---------|------|--------|--------|
| `[Transition]` | `[过渡]` | `[つなぎ]` | `[전환]` |
| `[Pause]` | `[停顿]` | `[間]` | `[멈춤]` |
| `[Interactive]` | `[互动]` | `[問いかけ]` | `[상호작용]` |
| `[Data]` | `[数据]` | `[データ]` | `[데이터]` |
| `[Scan Room]` | `[观察]` | `[観察]` | `[관찰]` |
| `[Benchmark]` | `[对标]` | `[ベンチマーク]` | `[벤치마크]` |
| `Key points:` | `要点：` | `要点：` | `핵심 포인트:` |
| `Duration:` | `时长：` | `所要時間：` | `소요 시간:` |
| `Flex:` | `弹性：` | `調整：` | `조정:` |

> For languages not listed above, translate each label to the corresponding natural term in that language.

**Requirements**:

- Notes should be conversational and flow naturally
- Highlight each page's core information and presentation key points
- Users can manually edit and override in the `notes/` directory

### Task 2. Split Into Per-Page Note Files

Automatically split `notes/total.md` into individual speaker note files in the `notes/` directory.

**File naming convention**:

- **Recommended**: Match SVG names (e.g., `01_cover.svg` → `notes/01_cover.md`)
- **Compatible**: Also supports `slide01.md` format (backward compatibility)

---

## 13. Next Steps After Completion

> **Auto-continuation**: After the per-page reviewed SVG pages and Logic Construction Phase (all notes) are complete, the Executor must pass the whole-deck SVG Review Gate and obtain user approval before entering the post-processing pipeline.

Before asking for final approval, explicitly confirm to the user only the asset conditions that are relevant to the current deck:

- if AI-generated images were used, whether they have been inserted as intended
- if local/user-provided images or icons are used, whether they are visibly present in the reviewed deck
- if any blank/placeholder region remains, whether it is intentional

Do not frame the checkpoint as only “approve export” if the user has not yet had a fair chance to judge the relevant asset suitability for this deck.

**Post-processing & Export** (see [shared-standards.md](shared-standards.md)):

Step 1. Only after user approval: split speaker notes

```bash
conda run -n ppt-master python scripts/total_md_split.py <project_path>
```

Step 2. After Step 1 completes successfully: SVG post-processing

```bash
conda run -n ppt-master python scripts/finalize_svg.py <project_path>
```

Step 3. After Step 2 completes successfully: export PPTX

```bash
conda run -n ppt-master python scripts/svg_to_pptx.py <project_path> -s final
```

Output: `exports/<project_name>_<timestamp>.pptx` + `exports/<project_name>_<timestamp>_svg.pptx`

This timestamp applies only to export snapshots. It does not change the stable project directory name.
