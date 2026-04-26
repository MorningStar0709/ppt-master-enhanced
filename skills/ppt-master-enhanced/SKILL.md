---
name: ppt-master
description: >
  AI-driven multi-format SVG content generation system. Converts source documents
  (PDF/DOCX/URL/Markdown) into high-quality SVG pages and exports to PPTX through
  multi-role collaboration. Use when user asks to "create PPT", "make presentation",
  "生成PPT", "做PPT", "制作演示文稿", or mentions "ppt-master".
---

# PPT Master Skill

> AI-driven multi-format SVG content generation system. Converts source documents into high-quality SVG pages through multi-role collaboration and exports to PPTX.

**Core Pipeline**: `Source Document → Create Project → Template Option → Strategist → [Image_Generator] → Executor → SVG Review Gate → Post-processing → Export`

> [!CAUTION]
> ## 🚨 Global Execution Discipline (MANDATORY)
>
> **This workflow is a strict serial pipeline. The following rules have the highest priority — violating any one of them constitutes execution failure:**
>
> 1. **SERIAL EXECUTION** — Steps MUST be executed in order; the output of each step is the input for the next. Non-BLOCKING adjacent steps may proceed continuously once prerequisites are met, without waiting for the user to say "continue"
> 2. **BLOCKING = HARD STOP** — Steps marked ⛔ BLOCKING require a full stop; the AI MUST wait for an explicit user response before proceeding and MUST NOT make any decisions on behalf of the user
> 3. **NO CROSS-PHASE BUNDLING** — Cross-phase bundling is FORBIDDEN. (Note: this workflow has three blocking checkpoints — template selection in Step 3, Eight Confirmations in Step 4, and user SVG approval in Step 7. The AI MUST wait for explicit user confirmation at each blocking checkpoint.)
> 4. **GATE BEFORE ENTRY** — Each Step has prerequisites (🚧 GATE) listed at the top; these MUST be verified before starting that Step
> 5. **NO SPECULATIVE EXECUTION** — "Pre-preparing" content for subsequent Steps is FORBIDDEN (e.g., writing SVG code during the Strategist phase)
> 6. **NO SUB-AGENT SVG GENERATION** — Executor Step 6 SVG generation is context-dependent and MUST be completed by the current main agent end-to-end. Delegating page SVG generation to sub-agents is FORBIDDEN
> 7. **SEQUENTIAL PAGE GENERATION ONLY** — In Executor Step 6, after the global design context is confirmed, SVG pages MUST be generated sequentially page by page in one continuous pass. Grouped page batches (for example, 5 pages at a time) are FORBIDDEN
> 8. **NO EXPORT BEFORE REVIEW SIGN-OFF** — Before any post-processing or PPT export command runs, all SVGs MUST pass the SVG Review Gate, review artifacts MUST be updated, and the user MUST explicitly confirm that the SVG set is acceptable
> 9. **INTERACTIVE CHECKPOINTS MUST BE TRULY INTERACTIVE** — When the runtime provides an interactive question/choice tool, Step 3 template selection, Step 4 Eight Confirmations, and Step 7 SVG approval MUST use that tool. Plain text "reply with A/B" prompts are only a fallback when no interactive tool exists
> 10. **NO SHELL-REDIRECTION FILE WRITES FOR EXECUTION ARTIFACTS** — In Step 6 and Step 7, do NOT create or modify SVG / notes / review artifacts via shell redirection or PowerShell file-writing commands (`>`, `>>`, `Out-File`, `Set-Content`, `Add-Content`, `New-Item`). Use IDE/native file editing tools or repository Python helpers instead

> [!IMPORTANT]
> ## 🌐 Language & Communication Rule
>
> - **Response language**: Always match the language of the user's input and provided source materials. For example, if the user asks in Chinese, respond in Chinese; if the source material is in English, respond in English.
> - **Explicit override**: If the user explicitly requests a specific language (e.g., "请用英文回答" or "Reply in Chinese"), use that language instead.
> - **Template format**: The `design_spec.md` file MUST always follow its original English template structure (section headings, field names), regardless of the conversation language. Content values within the template may be in the user's language.

> [!IMPORTANT]
> ## 🔌 Compatibility With Generic Coding Skills
>
> - `ppt-master` is a repository-specific workflow skill, not a general application scaffold
> - Do NOT create or require `.worktrees/`, `tests/`, branch workflows, or other generic engineering structure by default
> - If another generic coding skill suggests repository conventions that conflict with this workflow, follow this skill first unless the user explicitly asks otherwise

> [!IMPORTANT]
> ## 🐍 Python Environment Constraint (MANDATORY)
>
> - All Python operations MUST use the Conda environment via `conda run -n ppt-master`
> - Correct: `conda run -n ppt-master python <script>.py`
> - Forbidden: `python <script>.py` / `python3 <script>.py` / `pip install ...` / `conda activate ppt-master; python ...`
> - Windows Trae terminal rule: use `conda run --no-capture-output -n ppt-master python ...` as the first choice, not as a retry. In that terminal session, set `PYTHONIOENCODING=utf-8` and `CONDA_NO_PLUGINS=true` before running Python commands

> [!IMPORTANT]
> ## 🪟 Windows / PowerShell Execution Preset (MANDATORY)
>
> - In Windows/Trae, before the first Python command in the workflow, set:
>   - `$env:PYTHONIOENCODING='utf-8'`
>   - `$env:CONDA_NO_PLUGINS='true'`
> - In Windows/Trae, treat `conda run --no-capture-output -n ppt-master python ...` as the default command form for `project_manager.py`, `review_manager.py`, and other commands that may read/write or print path/content information
> - Main workflow commands MUST be launched from the repository root. Do NOT switch into `skills/ppt-master-enhanced/scripts/` to run them
> - Use repository-relative paths only. Do NOT rewrite workflow commands to absolute filesystem paths
> - After `project_manager.py init`, the agent MUST capture and reuse the exact printed project path for all subsequent commands. Never infer the path from the raw `<project_name>`
> - `project_manager.py init` creates the standard project directories automatically (`svg_output/`, `svg_final/`, `images/`, `notes/`, `review/`, `templates/`, `sources/`, `exports/`). Do NOT manually create them with shell commands
> - In PowerShell, do NOT introduce Unix-only command habits such as `mkdir -p ...` into the workflow. Use the workflow scripts and existing project structure instead
> - Internal workflow filenames are English-only. Project slugs, archived source filenames, generated Markdown filenames, SVG filenames, and exported filenames MUST stay within ASCII letters / digits / `_` / `-` / `.`

> [!IMPORTANT]
> ## 📁 English-Only Filename Rule (MANDATORY)
>
> - `project_name` passed to `project_manager.py init` MUST be an English slug such as `wireless_cloud_control_patent`
> - The workflow no longer treats Chinese or other non-ASCII filenames as a supported primary path
> - If the user provides source files with non-English filenames, the agent may still import them, but the workflow snapshot under `sources/` MUST use English-only normalized filenames
> - The agent MUST use the normalized English filenames printed by the scripts as the downstream machine-facing references
> - Do NOT introduce ad-hoc helper scripts or `python -c` write commands for routine project operations when a repository helper exists (for example, batch review-state updates or `notes/total.md` upserts)

> [!IMPORTANT]
> ## 🗂️ Project Naming Rule (MANDATORY)
>
> - Project directories MUST use the stable form `projects/<project_name>_<format>`
> - Project directories MUST NOT include a creation date or timestamp
> - Rationale: the project directory is the machine-facing stable identifier for the whole workflow, so adding a date creates unnecessary path ambiguity across turns and retries
> - Creation time belongs in metadata such as `README.md`, not in the project directory name
> - Exported PPTX filenames MAY keep timestamps under `exports/` because exports are historical output snapshots, not the project identity
> - If `init` reports that the target project directory already exists, the agent MUST stop guessing. It must either reuse that exact project path or choose a different English project slug explicitly

> [!IMPORTANT]
> ## 🧭 Rule Semantics
>
> Interpret workflow language using these semantics:
>
> - **MUST / MANDATORY / REQUIRED / FORBIDDEN** — hard rule, no discretion
> - **⛔ BLOCKING** — stop and wait for explicit user input
> - **DECISION REQUIRED** — the workflow cannot continue until one valid option is chosen
> - **CONDITIONAL** — execute only when the stated trigger condition is true
> - **RECOMMENDED / Default** — preferred behavior, but not a gate unless also marked above

> [!IMPORTANT]
> ## 🧩 Interactive Checkpoint Source Of Truth (MANDATORY)
>
> - All blocking interactive checkpoint cards in the main PPT workflow MUST use `references/interactive-checkpoint-guidelines.md` as the single source of truth
> - Before rendering Step 3 template selection, Step 4 Eight Confirmations, or Step 7 final approval, the agent MUST re-read `references/interactive-checkpoint-guidelines.md`
> - The agent MUST NOT generate checkpoint cards from memory, from partial paraphrase, or by mixing multiple prompt styles
> - For these checkpoints, only the body/recommendation content may vary; titles, prompts, main options, and supplement prompts MUST remain fixed exactly as defined in that reference
> - If another reference says “preferred”, “recommended”, or gives an example that conflicts with the fixed checkpoint template, `references/interactive-checkpoint-guidelines.md` wins

## Main Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `${SKILL_DIR}/scripts/source_to_md/pdf_to_md.py` | PDF to Markdown |
| `${SKILL_DIR}/scripts/source_to_md/doc_to_md.py` | Documents to Markdown — native Python for DOCX/HTML/EPUB/IPYNB, pandoc fallback for legacy formats (.doc/.odt/.rtf/.tex/.rst/.org/.typ) |
| `${SKILL_DIR}/scripts/source_to_md/ppt_to_md.py` | PowerPoint to Markdown |
| `${SKILL_DIR}/scripts/source_to_md/web_to_md.py` | Web page to Markdown |
| `${SKILL_DIR}/scripts/source_to_md/web_to_md.cjs` | Node.js fallback for WeChat / TLS-blocked sites (use only if `curl_cffi` is unavailable; `web_to_md.py` now handles WeChat when `curl_cffi` is installed) |
| `${SKILL_DIR}/scripts/project_manager.py` | Project init / validate / manage |
| `${SKILL_DIR}/scripts/analyze_images.py` | Image analysis |
| `${SKILL_DIR}/scripts/image_gen.py` | AI image generation (multi-provider) |
| `${SKILL_DIR}/scripts/icon_reference_checker.py` | Validate `data-icon` references against local icon libraries |
| `${SKILL_DIR}/scripts/svg_quality_checker.py` | SVG quality check |
| `${SKILL_DIR}/scripts/svg_layout_checker.py` | SVG layout geometry check |
| `${SKILL_DIR}/scripts/svg_text_container_checker.py` | Text-vs-container overflow check |
| `${SKILL_DIR}/scripts/preview_svg_deck.py` | Whole-deck browser preview generation |
| `${SKILL_DIR}/scripts/total_md_split.py` | Speaker notes splitting |
| `${SKILL_DIR}/scripts/finalize_svg.py` | SVG post-processing (unified entry) |
| `${SKILL_DIR}/scripts/svg_to_pptx.py` | Export to PPTX |

For complete tool documentation, see `${SKILL_DIR}/scripts/README.md`.

## Template Index

| Index | Path | Purpose |
|-------|------|---------|
| Layout templates | `${SKILL_DIR}/templates/layouts/layouts_index.json` | Query available page layout templates |
| Visualization templates | `${SKILL_DIR}/templates/charts/charts_index.json` | Query available visualization SVG templates (charts, infographics, diagrams, frameworks) |
| Icon library | `${SKILL_DIR}/templates/icons/` | Search on demand via `scripts/asset_lookup.py` or targeted file search (libraries: `chunk/`, `tabler-filled/`, `tabler-outline/`). Use `scripts/asset_lookup.py icons library/name --exact` for the single exact check, then one semantic lookup pass with at most 3 keywords; if still unresolved, switch to AI generation / external sourcing instead of looping |
| Review templates | `${SKILL_DIR}/templates/review/` | Reuse SVG review log, fix task, and user confirmation templates |

## Standalone Workflows

| Workflow | Path | Purpose |
|----------|------|---------|
| `create-template` | `workflows/create-template.md` | Standalone template creation workflow |

---

## Workflow

### Step 1: Source Content Processing

🚧 **GATE**: User has provided source material (PDF / DOCX / EPUB / URL / Markdown file / text description / conversation content — any form is acceptable).

When the user provides non-Markdown content, convert immediately:

| User Provides | Command |
|---------------|---------|
| PDF file | `conda run -n ppt-master python ${SKILL_DIR}/scripts/source_to_md/pdf_to_md.py <file>` |
| DOCX / Word / Office document | `conda run -n ppt-master python ${SKILL_DIR}/scripts/source_to_md/doc_to_md.py <file>` |
| PPTX / PowerPoint deck | `conda run -n ppt-master python ${SKILL_DIR}/scripts/source_to_md/ppt_to_md.py <file>` |
| EPUB / HTML / LaTeX / RST / other | `conda run -n ppt-master python ${SKILL_DIR}/scripts/source_to_md/doc_to_md.py <file>` |
| Web link | `conda run -n ppt-master python ${SKILL_DIR}/scripts/source_to_md/web_to_md.py <URL>` |
| WeChat / high-security site | `conda run -n ppt-master python ${SKILL_DIR}/scripts/source_to_md/web_to_md.py <URL>` (requires `curl_cffi`; falls back to `node web_to_md.cjs <URL>` only if that package is unavailable) |
| Markdown | Read directly |

**✅ Checkpoint — Confirm source content is ready, proceed to Step 2.**

---

### Step 2: Project Initialization

🚧 **GATE**: Step 1 complete; source content is ready (Markdown file, user-provided text, or requirements described in conversation are all valid).

```bash
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py init <project_name> --format <format> --dir projects
```

Format options: `ppt169` (default), `ppt43`, `xhs`, `story`, etc. For the full format list, see `references/canvas-formats.md`.

> ⚠️ **Single command rule**: In the main workflow, use the repository-root invocation form above. Do NOT change into the `scripts/` directory and do NOT invent an alternative launch shape for Step 2.

> ⚠️ **Project slug rule**: `<project_name>` MUST already be an English slug. Do NOT pass Chinese, spaces, or mixed-language titles here.

> ⚠️ **Project path rule**: `project_manager.py init` creates the real project directory as `projects/<project_name>_<normalized_format>`. The agent MUST read and reuse the exact printed path returned by `init`; do NOT guess it and do NOT continue using the raw `<project_name>` as the project path.
> - If terminal output is truncated or swallowed, read `skills/ppt-master-enhanced/.runtime/command_reports/project_manager_init_last.json`, `skills/ppt-master-enhanced/.runtime/command_reports/project_manager_import-sources_last.json`, or `skills/ppt-master-enhanced/.runtime/command_reports/project_manager_validate_last.json` instead of retrying blindly.

> ⚠️ **Directory initialization rule**: After `init`, do NOT manually create `svg_output/`, `notes/`, `review/`, or other standard folders. They already exist.

Import source content (choose based on the situation):

| Situation | Action |
|-----------|--------|
| Has source files (PDF/MD/etc.) | `conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py import-sources "<project_path>" "<source_files...>" --copy` |
| User provided text directly in conversation | No import needed — content is already in conversation context; subsequent steps can reference it directly |

> ⚠️ **Default to `--copy` for user-provided source files**: Files explicitly provided by the user (original PDF / MD / images) MUST be archived into `sources/` as project copies unless the user explicitly asks to relocate the originals.
> - Markdown files generated in Step 1, original PDFs, original MDs — by default import them into the project via `import-sources --copy`
> - Intermediate artifacts (e.g., `_files/` directories) are handled automatically by `import-sources`
> - The archived copy in `sources/` is the workflow snapshot; the original source should normally remain at its original location
> - `import-sources` MUST normalize archived filenames under `sources/` to English-only names for downstream machine use
> - Use `--move` only when the user explicitly wants the project to take ownership of the original files, or when cleaning up in-repo transient artifacts is intentional and understood

Validate immediately after import:

```bash
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py validate "<project_path>"
```

**✅ Checkpoint — Confirm project structure created successfully, `sources/` contains all source files, converted materials are ready. Proceed to Step 3.**

---

### Step 3: Template Selection

🚧 **GATE**: Step 2 complete; project directory structure is ready.

**Decision type**: `DECISION REQUIRED`

⛔ **BLOCKING**: If the user has not yet clearly expressed whether to use a template, you MUST present options and **wait for an explicit user response** before proceeding. If the user has previously stated "no template" or specified a particular template, skip this prompt and proceed directly.

🚧 **GATE — Mandatory read before rendering this checkpoint**:
```
Read references/interactive-checkpoint-guidelines.md
```

> **Interactive checkpoint rule**: When an interactive question tool is available, use it for this checkpoint instead of a plain text "reply with A/B" prompt. The preferred UX is one continuous checkpoint:
> 1. choose **template vs free design**
> 2. if template is chosen, collect the **specific template name/style** in the same interactive exchange or immediately chained interactive prompt
> Do not stop after collecting only `A/B` when a concrete template choice is still required.
> Before the user decides, the main card body MUST already include a concise list of relevant available templates plus one explicit recommendation and rationale derived from `layouts_index.json`.
> Use the fixed user-facing template:
> - title: `模板选择`
> - prompt: `请确认本次 PPT 是使用现有模板，还是采用自由设计。`
> - options: `使用现有模板`, `自由设计`
> - optional supplement title: `模板补充`
> - optional supplement prompt: `如选择模板，请补充模板名称、风格关键词或参考案例。（可选）`
> - Step 3 MUST NOT reuse Step 4's generic supplement card (`其他补充` / `是否有更多的补充信息需要提供？（可选）`)

**⚡ Early-exit**: If the user has already stated "no template" / "不使用模板" / "自由设计" (or equivalent) at any prior point in the conversation, **do NOT query `layouts_index.json`** — skip directly to Step 4. This avoids unnecessary token consumption.

**Template recommendation flow** (only when the user has NOT yet decided):
Query `${SKILL_DIR}/templates/layouts/layouts_index.json` to list available templates and their style descriptions.
**When presenting options, you MUST provide a professional recommendation based on the current PPT topic and content** (recommend a specific template or free design, with reasoning). By default, **lean toward free design** unless the content clearly benefits from a fixed structural preset (e.g., consulting report, annual report, academic paper). Then ask the user:

> Place the recommendation only in the card body. Do NOT rewrite the checkpoint title, prompt, or option labels into free-form variants.
> The user should be able to see "what existing templates are relevant" and "which one is recommended" before making the first Step 3 choice. Do not defer the template list/recommendation until after the user has already selected `使用现有模板`.
> If the user enters a style keyword such as `谷歌风格` in the Step 3 supplement, interpret it as the intended concrete template/style for Step 3.

After the user confirms option A, apply the selected library template with the repository helper:

```bash
conda run --no-capture-output -n ppt-master python skills/ppt-master-enhanced/scripts/project_manager.py apply-template "<project_path>" <template_name>
```

> `apply-template` is the preferred Step 3 execution path. It copies template SVG files and `design_spec.md` into `<project_path>/templates/`, and routes any required PNG/JPG/WebP assets into `<project_path>/images/`.
> Re-run with `--force` only when you intentionally want to overwrite existing project template files.
> Do not manually create `templates/` or `images/` here; `project_manager.py init` already created the standard project structure.

After the user confirms option B (free design), proceed directly to Step 4.

> To create a new global template, read `workflows/create-template.md`

**✅ Checkpoint — User has responded with template selection, template applied (if option A). Proceed to Step 4.**

---

### Step 4: Strategist Phase (MANDATORY — cannot be skipped)

🚧 **GATE**: Step 3 complete; user has confirmed template selection.

First, read the role definition:
```
Read references/strategist.md
```

> ⚠️ **Mandatory gate in `strategist.md`**: Before writing `design_spec.md`, Strategist MUST `read_file templates/design_spec_reference.md` and produce the spec following its full I–XI section structure. See `strategist.md` Section 1 for the explicit gate rule.

**Must complete the Eight Confirmations** (full template structure in `templates/design_spec_reference.md`):

⛔ **BLOCKING**: The Eight Confirmations MUST be presented to the user as a bundled set of recommendations, and you MUST **wait for the user to confirm or modify** before outputting the Design Specification & Content Outline. This is the second blocking checkpoint in the workflow (after template selection, before SVG Review Gate approval). Once confirmed, all subsequent non-blocking steps should auto-continue within the same workflow, including Image_Generator when it is triggered.

🚧 **GATE — Mandatory read before rendering this checkpoint**:
```
Read references/interactive-checkpoint-guidelines.md
```

> **Interactive checkpoint rule**: When an interactive question tool is available, use it to collect the bundled confirmations instead of scattering plain text questions across multiple turns.
>
> **Preferred UX shape for Eight Confirmations**: Treat this checkpoint as **one bundled confirmation decision**, not a multi-select questionnaire. The recommended interactive structure is:
> 1. one main card titled `8项确认`
> 2. use the fixed prompt `请确认以下 8 项设计参数（可直接使用推荐值）：`
> 3. explicitly list all 8 recommended parameters
> 4. provide exactly two main actions: `确认全部推荐（推荐）` and `我想调整部分参数`
> 5. if the runtime supports an optional supplement field/card, place it separately as `其他补充` with the fixed prompt `是否有更多的补充信息需要提供？（可选）`
> 6. the title, prompt, and option labels are fixed workflow strings; only the parameter values may vary
> Do not replace the main bundled confirmation with grouped category cards such as “画布格式与页数 / 设计风格与色系 / 图标与排版 / 图片方案”.

1. Canvas format
2. Page count range
3. Target audience
4. Style objective
5. Color scheme
6. Icon usage approach
7. Typography plan
8. Image usage approach

If the user has provided images, run the analysis script **before outputting the design spec** (do NOT directly read/open image files — use the script output only):
```bash
conda run -n ppt-master python ${SKILL_DIR}/scripts/analyze_images.py <project_path>/images
```

> ⚠️ **Image handling rule**: The AI must NEVER directly read, open, or view image files (`.jpg`, `.png`, etc.). All image information must come from the `analyze_images.py` script output or the Design Specification's Image Resource List.

**Output**: `<project_path>/design_spec.md`

**✅ Checkpoint — Phase deliverables complete, auto-proceed to next step**:
```markdown
## ✅ Strategist Phase Complete
- [x] Eight Confirmations completed (user confirmed)
- [x] Design Specification & Content Outline generated
- [ ] **Next**: Auto-proceed to [Image_Generator / Executor] phase
```

---

### Step 5: Image_Generator Phase (Conditional)

🚧 **GATE**: Step 4 complete; Design Specification & Content Outline generated and user confirmed.

**Decision type**: `CONDITIONAL`

> **Capability-first rule**: Image generation fallback is allowed only when a usable image backend is actually configured and callable. Do not assume that AI generation is available just because a missing asset would benefit from it.

> **Trigger condition**: Image approach includes "AI generation". If not triggered, skip directly to Step 6 (Step 6 GATE must still be satisfied).

Read `references/image-generator.md`

1. Extract all images with status "pending generation" from the design spec
2. Generate prompt document → `<project_path>/images/image_prompts.md`
3. Generate images (CLI tool recommended):
   ```bash
   conda run -n ppt-master python ${SKILL_DIR}/scripts/image_gen.py "prompt" --backend <provider> --aspect_ratio 16:9 --image_size 1K -o <project_path>/images
   ```

> **Mandatory preflight before first AI image attempt**:
> 1. confirm whether the user explicitly selected AI image generation, or whether AI generation is being invoked as an asset fallback
> 2. verify that a usable backend is configured (`IMAGE_BACKEND` plus the required provider credentials), ideally via `image_gen.py --list-backends` and the real backend selection path
> 3. if no usable backend exists, stop automatic AI generation immediately and switch to a non-AI fallback

> **No-capability fallback rule**: When no usable image backend exists, the agent MUST NOT silently retry random providers or keep attempting automatic AI generation. It MUST switch to one of:
> - verified local substitute
> - external sourcing when workflow context allows it
> - user manual generation from `images/image_prompts.md`
> - labeled placeholder
> - layout redesign that removes hard dependency on the missing asset

> **No-silent-blank rule**: Missing image capability is never a valid reason to let a required visual region leave the workflow as an unexplained blank area.

> Recommended backend invocation: pass `--backend <provider>` explicitly on Windows/Trae to avoid stale-session environment ambiguity. `image_gen.py` reads the repository-root `.env` only; `.trae/.env` is not supported.
> Common provider examples: `<provider>=gemini`, `<provider>=openai`, `<provider>=qwen`, `<provider>=zhipu`, `<provider>=volcengine`, `<provider>=minimax`. See `references/image-generator.md` for the provider example table and support-tier guidance.

**✅ Checkpoint — Confirm all images are ready, proceed to Step 6**:
```markdown
## ✅ Image_Generator Phase Complete
- [x] Prompt document created
- [x] All images saved to images/
```

> ⚠️ **Important boundary**: `All images saved to images/` means the image assets exist, **not** that they have already been inserted into SVG pages or visually approved by the user. Image insertion, visibility validation, and user suitability confirmation happen downstream during Executor + SVG Review Gate.

---

### Step 6: Executor Phase

🚧 **GATE**: Step 4 (and Step 5 if triggered) complete; all prerequisite deliverables are ready.

**Execution type**: `MANDATORY`

Read the role definition based on the selected style:
```
Read references/executor-base.md          # REQUIRED: common guidelines
Read references/executor-general.md       # General flexible style
Read references/executor-consultant.md    # Consulting style
Read references/executor-consultant-top.md # Top consulting style (MBB level)
```

> Only need to read executor-base + one style file.
> Per-page self-review MUST also follow `references/page-diagnostic-output-template.md`.

**Design Parameter Confirmation (Mandatory)**: Before generating the first SVG, the Executor MUST review and output key design parameters from the Design Specification (canvas dimensions, color scheme, font plan, body font size) to ensure spec adherence. See executor-base.md Section 2 for details.

> ⚠️ **Main-agent only rule**: SVG generation in Step 6 MUST remain with the current main agent because page design depends on full upstream context (source content, design spec, template mapping, image decisions, and cross-page consistency). Do NOT delegate any slide SVG generation to sub-agents.
> ⚠️ **Generation rhythm rule**: After confirming the global design parameters, the Executor MUST generate pages sequentially, one page at a time, while staying in the same continuous main-agent context. Do NOT split Step 6 into grouped page batches such as 5 pages per batch.
> ⚠️ **Per-page review rule**: After generating each page, Executor MUST immediately perform a self-review before moving to the next page. This self-review MUST use `references/page-diagnostic-output-template.md`, keep visible symptoms separate from root-cause diagnosis, and determine pass vs immediate revision before proposing fixes. If the page still contains blocking review issues, it MUST be fixed in place and cannot be carried into the next page.
> ⚠️ **Artifact write rule**: On Windows/Trae, do NOT use PowerShell file-creation commands or shell redirection to write `svg_output/*.svg`, `notes/*.md`, or `review/*.md`. Use IDE/native file editing tools or repository Python helpers only.
> ⚠️ **Architecture-page rule**: When a page is primarily a system / layered / network / collaboration architecture diagram, Executor MUST read `references/architecture-slide-rules.md` before generating that page and must follow its density, relationship, and balance constraints.
> ⚠️ **Icon fallback rule**: Before using a local icon, verify that it exists. Use exactly one exact check and, if needed, one semantic lookup pass with at most 3 keywords. If that still does not yield an acceptable verified icon, stop local guessing and switch to AI-generated imagery, externally sourced imagery, or a labeled placeholder. Repeated blind icon lookup loops are FORBIDDEN.
> ⚠️ **Asset fallback stability rule**: If AI fallback would require an image backend that is not configured or not usable in the current environment, do not keep escalating through speculative AI attempts. Switch to a stable non-AI fallback path and record it clearly.
> ⚠️ **Image consumption rule**: If Step 5 produced AI-generated images, Executor MUST verify before sign-off that each image marked `Generated` in the Design Specification is either (a) actually referenced by the intended SVG page(s) and visually placed, or (b) explicitly recorded as generated-but-unused with justification. Do NOT silently leave generated images unused while the corresponding page still shows a blank placeholder or missing visual region.

**Visual Construction Phase**:
- Generate SVG pages sequentially, one page at a time, in one continuous pass → `<project_path>/svg_output/`
- After each page is generated, apply the per-page review protocol from `references/executor-base.md` and output the structured diagnostic defined in `references/page-diagnostic-output-template.md`
- When icon placeholders are used, run `conda run --no-capture-output -n ppt-master python ${SKILL_DIR}/scripts/icon_reference_checker.py <project_path> --summary-only` before whole-deck sign-off to catch missing local icon references without adding extra manual review steps

**Logic Construction Phase**:
- Generate speaker notes → `<project_path>/notes/total.md`

**✅ Checkpoint — Confirm all SVGs and notes are fully generated, each page has been self-reviewed, and review artifacts are populated. Proceed to Step 7 SVG Review Gate**:
```markdown
## ✅ Executor Phase Complete
- [x] All SVGs generated to svg_output/
- [x] Per-page self-review completed during generation
- [x] Review artifacts updated under review/
- [x] Speaker notes generated at notes/total.md
```

---

### Step 7: SVG Review Gate

🚧 **GATE**: Step 6 complete; all SVGs generated to `svg_output/`; speaker notes `notes/total.md` generated.

**Execution type**: `MANDATORY`

Before any post-processing command, the AI MUST complete a dedicated review gate:

1. Re-check the full SVG set using `references/svg-review/`
2. Run the unified deck verification entry so that review evidence, Step 7 preview-source preparation under `review/preview_finalized/`, `design_spec.md` Content Outline vs `svg_output/` deck accountability, SVG technical compliance, layout geometry, local icon references, and browser preview generation are checked together:
```bash
conda run --no-capture-output -n ppt-master python ${SKILL_DIR}/scripts/review_manager.py verify <project_path> --compact
```

> **Revision-loop gate rule**: When the user has provided final-review modification feedback and the project has entered a structured revision loop, the agent MUST manage `review/revision_round.json` via `scripts/revision_manager.py`. This revision loop is agent-operated bookkeeping, not a page-by-page human approval flow. While that revision round remains active, whole-deck `review_manager.py verify` stays blocked only while listed pages are still unresolved (`todo` / `in_progress`). Once all listed pages are resolved (`ready_for_review` or `approved`), whole-deck verify may continue; `revision_manager.py prepare-verify <project_path>` is optional bookkeeping, not a human gate.
> **Human/agent boundary**: In this revision loop, the user should only review the current approval surface and provide page-level change requests. The agent is responsible for structuring that feedback into revision tasks, updating round/page states, running local checks, and re-entering the whole-deck gate when allowed.

> `verify` is the Step 7 technical gate. It may succeed before user approval is recorded; in that case Step 8 export is still blocked until approval, but the deck should not be treated as a technical failure. The same gate also checks whether `design_spec.md` Section IX declares the same slide set that `svg_output/` actually contains.
> If `verify` fails or terminal output is incomplete, read `<project_path>/review/verify_report.json` before attempting further repair work.
> For the shortest actionable repair queue, prefer:
> `conda run --no-capture-output -n ppt-master python ${SKILL_DIR}/scripts/review_manager.py repair-focus <project_path>`
   Debug-only skip flags are available when isolating a failure: `--skip-quality-check`, `--skip-layout-check`, `--skip-icon-check`, `--skip-preview-check`. Do not use them in the normal main workflow.
3. Finalize the minimal review state under `<project_path>/review/`
4. Ensure every SVG page is reviewed and no blocking issues remain (`P0` forbidden, unresolved `P1` blocks export)
5. Maintain `review/review_state.json` as the machine source of truth; the minimal gate only needs page filename, reviewed yes/no, priority, and a compact note
6. Use rendered Markdown files under `review/` as reports, not as the authoritative gate input
7. Prepare `review/user_confirmation.md` from the current review state
8. Explicitly confirm asset visibility and completeness before asking for export approval, but only for the asset types that are actually present in the deck:
   - if AI-generated images were supposed to be used, they are actually inserted into the target page(s)
   - if local/user-provided images are used, they are visible in the preview the user sees
   - if icon placeholders or local icons are used, they are not being mistaken for final rendered icons
   - if a page contains a blank/placeholder visual region, it is either intentionally retained or explicitly blocked for revision

> **Reliable preview rule**: Do not ask the user for final export approval if the preview they are seeing is known to be visually incomplete or misleading for image/icon visibility. In Step 7, `review_manager.py verify` MUST first build one unified review SVG source under `review/preview_finalized/`: when preview-safe processing is needed it embeds icons/images and applies the normal review-time fixes there; when such processing is unnecessary it still copies the current `svg_output/` pages into that review directory. The approval-time preview basis is then `review/preview_deck.html` generated from `review/preview_finalized/`, served from the project root. This review-only directory exists only to provide a stable approval surface; it is not Step 8 post-processing and does not count as final export output. Technical SVG checks, layout checks, and icon-reference checks still validate the reviewed raw SVG set under `svg_output/`; they are not redefined to treat `review/preview_finalized/` as the authoritative machine gate source.

⛔ **BLOCKING**: Present the final review conclusion to the user and wait for explicit confirmation before running any of the commands in Step 8.

🚧 **GATE — Mandatory read before rendering this checkpoint**:
```
Read references/interactive-checkpoint-guidelines.md
```

> **Interactive checkpoint rule**: When an interactive question tool is available, use it for the final SVG approval instead of free-form text confirmation.
>
> **Approval wording rule**: The approval prompt MUST explicitly ask the user to confirm not only overall page quality, but also the relevant asset conditions for this deck. For example: AI-generated images if Step 5 was triggered, local images if the deck uses them, icons if icon placeholders/local icons are present, and blank/placeholder visual regions if any remain. Do not phrase the checkpoint as a pure “start export?” question when asset suitability is still in doubt.
> Use the fixed user-facing template:
> - title: `全案审查结论`
> - prompt base: `当前 SVG 审查已完成。请确认是否认可当前审查结果，并进入后处理与导出。`
> - options: `确认通过，进入后处理/导出（推荐）`, `暂不导出，需要修改`
> - optional supplement title: `其他补充`
> - optional supplement prompt: `如需补充修改意见，请写在这里。（可选）`
> The card title and option labels must stay fixed; asset-specific details belong in the body text only.

**✅ Checkpoint — Confirm the SVG review gate is complete and user approval has been received. Proceed to Step 8 post-processing**:
```markdown
## ✅ SVG Review Gate Complete
- [x] Whole-deck review completed
- [x] Review log finalized
- [x] Fix tasks finalized
- [x] User confirmation file prepared
- [x] User explicitly approved proceeding to post-processing/export
```

---

### Step 8: Post-processing & Export

🚧 **GATE**: Step 7 complete; user has explicitly approved the reviewed SVG set.

**Execution type**: `MANDATORY`

> ⚠️ The following three sub-steps MUST be **executed individually one at a time**. Each command must complete and be confirmed successful before running the next.
> ❌ **NEVER** put all three commands in a single code block or single shell invocation.

**Step 8.1** — Split speaker notes:
```bash
conda run -n ppt-master python ${SKILL_DIR}/scripts/total_md_split.py <project_path>
```

**Step 8.2** — SVG post-processing (icon embedding / image crop & embed / text flattening / rounded rect to path):
```bash
conda run -n ppt-master python ${SKILL_DIR}/scripts/finalize_svg.py <project_path>
```

**Step 8.3** — Export PPTX (embeds speaker notes by default):
```bash
conda run -n ppt-master python ${SKILL_DIR}/scripts/svg_to_pptx.py <project_path> -s final
# Output: exports/<project_name>_<timestamp>.pptx + exports/<project_name>_<timestamp>_svg.pptx
```

> ❌ **NEVER** use `cp` as a substitute for `finalize_svg.py` — it performs multiple critical processing steps
> ❌ **NEVER** export directly from `svg_output/` — MUST use `-s final` to export from `svg_final/`
> ❌ In the main workflow, do **NOT** add extra flags like `--only` unless the user explicitly requests debug or single-mode export
> ❌ **NEVER** run these commands before Step 7 review artifacts are complete and the user has approved export
> ✅ `total_md_split.py`, `finalize_svg.py`, and `svg_to_pptx.py` all enforce the SVG Review Gate. If any of them fails with review blockers, repair the review evidence instead of bypassing the gate

---

## Role Switching Protocol

Before switching roles, you **MUST first read** the corresponding reference file — skipping is FORBIDDEN. Output marker:

```markdown
## [Role Switch: <Role Name>]
📖 Reading role definition: references/<filename>.md
📋 Current task: <brief description>
```

---

## Reference Resources

| Resource | Path |
|----------|------|
| Shared technical constraints | `references/shared-standards.md` |
| Architecture slide rules | `references/architecture-slide-rules.md` |
| Interactive checkpoint guidelines | `references/interactive-checkpoint-guidelines.md` |
| Page diagnostic output template | `references/page-diagnostic-output-template.md` |
| Canvas format specification | `references/canvas-formats.md` |
| Image layout specification | `references/image-layout-spec.md` |
| SVG image embedding | `references/svg-image-embedding.md` |
| SVG review standards | `references/svg-review/standards.md` |
| SVG review playbook | `references/svg-review/playbook.md` |
| SVG review quick reference | `references/svg-review/quick-reference.md` |
| SVG review priority rules | `references/svg-review/priority-rules.md` |

---

## Notes

- In the main workflow, do not add extra flags like `--only` to the post-processing commands unless the user explicitly requests a debug or single-mode export
- Step 7 unified review source: `conda run --no-capture-output -n ppt-master python ${SKILL_DIR}/scripts/review_manager.py verify <project_path> --compact`
- Step 7 approval-time preview: run `review_manager.py verify`, then serve the project root and open `review/preview_deck.html`; Step 7 approval must be based on that HTML backed by `review/preview_finalized/`
- Post-approval export preview/debug: `conda run -n ppt-master python -m http.server -d <project_path> 8000` and inspect `svg_final/`
- **SVG review assets**: Keep review artifacts under `<project_path>/review/`; operational details live in `references/svg-review/` and `scripts/docs/svg-review.md`
- **Troubleshooting**: If generation hits layout overflow, export errors, or blank images, check `scripts/docs/troubleshooting.md`
- **CI status**: GitHub Actions workflow `ci-validation.yml` is kept in the repository, but it is not yet part of the formal required gate. Validate it separately before depending on it.


