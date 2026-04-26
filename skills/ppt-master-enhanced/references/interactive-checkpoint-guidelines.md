# Interactive Checkpoint Guidelines

This document defines the preferred UX shape for blocking checkpoint questions in the PPT Master workflow so that interactive prompts stay consistent across runs, agents, and tools.

This file is the single source of truth for Step 3 / Step 4 / Step 7 checkpoint cards in the main PPT workflow. If any other document provides examples, summaries, or softer wording, this file overrides them.

---

## 1. Core Principle

Blocking checkpoints are **decision confirmations**, not open-ended surveys.

The UI should help the user complete one valid workflow decision with the smallest reasonable number of actions. Do not turn a bundled confirmation step into a fragmented multi-question questionnaire unless the workflow truly requires separate decisions.

---

## 2. Checkpoint Types

### A. Single-decision checkpoint

Use when the workflow needs one final decision before continuing.

Examples:

- Template selection
- Eight Confirmations bundled approval
- Final SVG approval

Preferred interaction shape:

- one main decision card
- one recommended option
- one explicit "I want to modify" option when modification is valid
- optional follow-up supplement input only after the main decision card

Do not split a single-decision checkpoint into multiple parallel decision cards unless each card is independently required to proceed.

---

### B. Multi-decision checkpoint

Use only when the workflow genuinely requires multiple independent selections, and each selection affects a different downstream branch.

This is rare in the main PPT workflow.

Do not use the multi-decision pattern just because the recommendation contains multiple fields.

---

## 3. Eight Confirmations Standard UX

The Eight Confirmations step is a **bundled blocking checkpoint**. It should be presented as one consolidated recommendation package, not as a set of mini-choices.

### Required structure

#### Card 1: Main confirmation card

Title:

- `8项确认`

Body:

- list all 8 recommended parameters explicitly
- preserve enough detail that the user can approve without opening another explanation

Primary options:

- `确认全部推荐（推荐）`
- `我想调整部分参数`

#### Card 2: Optional supplement card

Title:

- `其他补充`

Body:

- invite optional extra context only
- this card must not replace the main confirmation decision

Recommended prompt:

- `是否有更多的补充信息需要提供？（可选）`

### Why this is the preferred shape

- It matches the workflow semantics: one bundled confirmation gate
- It minimizes user hesitation
- It avoids giving the false impression that the user must individually choose among grouped categories
- It keeps "modify" distinct from "supplement"

---

## 4. Patterns To Avoid

### Avoid pattern 1: grouped pseudo-multi-select

Example of the wrong shape:

- `画布格式与页数`
- `设计风格与色系`
- `图标与排版`
- `图片方案`

Why it is weak:

- it hides the fact that this is the Eight Confirmations checkpoint
- it looks like the user must evaluate grouped sub-choices
- it weakens the bundled-confirmation semantics

This grouped summary may be used as a visual recap, but not as the primary blocking decision UI.

### Avoid pattern 2: only "确认 / 其他"

Why it is incomplete:

- `其他` is too vague
- users often want to adjust only 1-2 parameters, not replace the whole package

Use:

- `确认全部推荐（推荐）`
- `我想调整部分参数`

instead.

### Avoid pattern 3: supplement card replacing the main decision

`其他补充` is optional context collection, not the approval itself.

Do not let the user skip the main checkpoint decision and move forward only by filling a supplement field.

---

## 5. Template Selection Standard UX

Template selection is also a single-decision checkpoint.

Fixed main card:

- title: `模板选择`
- prompt: `请确认本次 PPT 是使用现有模板，还是采用自由设计。`
- options:
  - `使用现有模板`
  - `自由设计`

Required body content before the user decides:

- briefly list the relevant available template candidates from `templates/layouts/layouts_index.json`
- include a concrete recommendation based on the current topic/content
- explain in one short paragraph why that recommendation is preferred
- keep this recommendation in the card body; do not move it into a separate follow-up card

Default recommendation rule:

- if the topic clearly matches an existing template family, recommend that specific template first
- otherwise recommend free design in the card body

Fixed follow-up:

- if `使用现有模板` is chosen, collect the concrete template/style immediately in the same checkpoint flow
- this follow-up is only for template-specific supplement collection after the user has already chosen `使用现有模板`
- do not show the Step 4 generic supplement card (`其他补充` / `是否有更多的补充信息需要提供？（可选）`) in the Step 3 template-selection flow
- if the runtime supports a supplement card, use:
  - title: `模板补充`
  - prompt: `如选择模板，请补充模板名称、风格关键词或参考案例。（可选）`

Interpretation hint:

- if the user fills the supplement with a style keyword such as `谷歌风格`, treat it as a concrete template/style intent for Step 3 rather than as a generic free-form note

Do not stop after collecting only a high-level A/B response if a concrete template choice is still required.

---

## 6. Final SVG Approval Standard UX

Final SVG approval is a single-decision checkpoint.

Fixed main card:

- title: `全案审查结论`
- prompt: `当前 SVG 审查已完成。请确认是否认可当前审查结果，并进入后处理与导出。`
- options:
  - `确认通过，进入后处理/导出（推荐）`
  - `暂不导出，需要修改`

Optional supplement collection can appear after the approval decision, but must not replace it.

Fixed supplement card:

- title: `其他补充`
- prompt: `如需补充修改意见，请写在这里。（可选）`

Approval copy must explicitly cover:

- overall page quality
- AI-generated image suitability, if AI-generated images are part of this deck
- local image visibility, if local/user-provided images are used
- icon visibility, if icons/placeholders are part of the reviewed pages
- whether any blank region is intentional or still needs repair, if such regions exist

Avoid approval wording that asks only whether export should start, when the user may still be unsure whether generated assets were actually inserted or shown correctly.

---

## 7. Writing Style Rules

For all blocking checkpoint cards:

- make the checkpoint title explicit
- make the recommended option explicit
- use action-oriented labels
- avoid vague labels such as `其他`
- keep optional supplement input separate from the main decision
- prefer fewer, clearer choices over many grouped selections

---

## 8. Short Rule Summary

If a checkpoint is logically **one confirmation**, present it as:

1. one main decision card
2. fixed title and fixed option labels for that checkpoint
3. variable content only in the recommendation/body area
4. one optional fixed-template supplement card when needed

Do not present a bundled confirmation step as if it were a multi-select questionnaire.

---

## 9. Fixed-Template Rule

For the main PPT workflow, blocking checkpoint cards must use fixed user-facing labels. The agent may fill in recommendation content, parameter values, and short rationale, but must not freely rewrite checkpoint titles, option labels, or supplement prompts.

Implementation rule:

- before rendering any of these cards, re-read this file
- do not generate these cards from memory
- if the runtime tool requires structured fields, map them directly from the fixed values below without paraphrasing

### Step 3: Template Selection

- title: `模板选择`
- prompt: `请确认本次 PPT 是使用现有模板，还是采用自由设计。`
- options:
  - `使用现有模板`
  - `自由设计`
- body must include:
  - concise list of relevant available templates
  - one explicit recommendation with reason
- optional supplement title: `模板补充`
- optional supplement prompt: `如选择模板，请补充模板名称、风格关键词或参考案例。（可选）`

### Step 4: Eight Confirmations

- title: `8项确认`
- prompt: `请确认以下 8 项设计参数（可直接使用推荐值）：`
- options:
  - `确认全部推荐（推荐）`
  - `我想调整部分参数`
- optional supplement title: `其他补充`
- optional supplement prompt: `是否有更多的补充信息需要提供？（可选）`

### Step 7: Final SVG Approval

- title: `全案审查结论`
- prompt: `当前 SVG 审查已完成。请确认是否认可当前审查结果，并进入后处理与导出。`
- options:
  - `确认通过，进入后处理/导出（推荐）`
  - `暂不导出，需要修改`
- optional supplement title: `其他补充`
- optional supplement prompt: `如需补充修改意见，请写在这里。（可选）`
