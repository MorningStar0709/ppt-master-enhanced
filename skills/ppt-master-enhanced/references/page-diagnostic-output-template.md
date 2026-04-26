# Page Diagnostic Output Template

Use this template for every per-page self-review in the Executor phase.

The purpose of this template is to force diagnosis before repair:

1. identify the page type first
2. describe visible symptoms only
3. classify the root-cause layer
4. determine blocking severity
5. decide pass vs immediate revision
6. define structural fix actions last

Do not jump directly from a visible symptom to coordinate tweaking, equal-width redistribution, or font-size reduction. Diagnose the structural issue first.

---

## Output Order Rule

The review output MUST follow the field order below.

- `Page type` must be decided before any symptom or fix is written
- `Visible symptoms` must describe what is visibly wrong, without mixing in inferred causes
- `Root-cause layer` must explain which layer most likely created the problem
- `Blocking rule check` must state whether `P0` or `P1` was triggered
- `Pass decision` must be either `pass` or `revise immediately`
- `Required fixes` must describe structural repair actions, not vague micro-adjustments
- `Review note` must be a compact one-line conclusion suitable for `review_state.json`

---

## Allowed Page Type Labels

Choose the closest primary page type:

- `cover`
- `toc`
- `content`
- `comparison`
- `timeline`
- `architecture`
- `process`
- `data-chart`
- `mixed-information`

If a page blends multiple forms, still choose one dominant type rather than listing several equal types.

---

## Allowed Root-cause Layers

Choose the most likely dominant layer:

- `XML / syntax`
- `SVG technical rule`
- `geometry / coordinate system`
- `layout / spacing / overflow`
- `hierarchy / emphasis`
- `page-type mismatch`
- `architecture relationship clarity`
- `content density / information selection`

If multiple layers are involved, list the primary layer first and keep the explanation concise.

---

## Standard Template

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

Field requirements:

- `File`: exact SVG filename
- `Page type`: must use one label from the allowed page type list
- `Intended message`: one short sentence describing what the page is supposed to communicate
- `Visible symptoms`: visible facts only; do not write repair ideas here
- `Root-cause layer`: choose from the allowed root-cause layers
- `Blocking rule check`: explicitly state whether `P0` or unresolved `P1` is triggered
- `Priority`: `P0`, `P1`, or `P2`
- `Pass decision`: only `pass` or `revise immediately`
- `Required fixes`: structural actions such as reframe hierarchy, reduce density, rebuild flow path, split overloaded region, strengthen connector logic, or recompose the layout
- `Review note`: compressed conclusion for the machine review state, ideally one sentence

---

## Architecture-page Required Extension

If `Page type` is `architecture`, or the page is primarily a system / layered / relationship diagram, append the following fields after `Review note`:

```markdown
- Primary flow direction:
- Relationship clarity:
- Connector sufficiency:
- Density balance:
- Overloaded region:
```

Architecture-page interpretation rules:

- `Primary flow direction`: identify whether the page reads as `top-down`, `left-right`, `hub-spoke`, or `unclear`
- `Relationship clarity`: judge whether the layer-to-layer logic is understandable on a quick scan
- `Connector sufficiency`: judge whether arrows, channels, or connector lines are explicit enough
- `Density balance`: judge whether mirrored or peer regions carry comparable information load
- `Overloaded region`: explicitly name the overloaded band, panel, or cluster; write `none` only if that judgement is justified

For architecture pages, prioritize structural diagnosis over cosmetic balancing:

- do not default to equal-width redistribution
- do not default to shrinking text
- do not treat decorative filling as a valid balance fix
- if relationships are unclear, diagnose structure before geometry
- if one area needs `...` or too many endpoint cards, diagnose overload before spacing

---

## Minimal Example

```markdown
## Page Diagnostic Output
- File: 07_system_architecture.svg
- Page type: architecture
- Intended message: Explain how the cloud control layer coordinates edge devices through the network layer.
- Visible symptoms: The right endpoint region is much denser than the left side, the transmission band does not visibly connect all layers, and several modules read as a catalog rather than a flow.
- Root-cause layer: architecture relationship clarity
- Blocking rule check: Triggers P1 because relationship clarity is insufficient for an architecture page.
- Priority: P1
- Pass decision: revise immediately
- Required fixes: Rebuild the primary left-right flow path, reduce endpoint card count into grouped summaries, and make the transmission band function as an explicit connector layer.
- Review note: P1 architecture page; relationship path is unclear and endpoint region is overloaded.
- Primary flow direction: left-right
- Relationship clarity: weak
- Connector sufficiency: insufficient
- Density balance: right-heavy
- Overloaded region: endpoint device cluster
```
