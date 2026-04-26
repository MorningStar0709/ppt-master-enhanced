# Architecture Slide Rules

Use this reference whenever a page is primarily an architecture / system / layered relationship diagram rather than a normal content page.

---

## 1. Goal

An architecture slide must make the relationship readable before the details are read.

If the audience cannot answer "which layer talks to which layer" within a quick scan, the page is not ready.

---

## 2. Mandatory Structure Rules

- The page MUST have a clear primary flow direction: top-down, left-right, or hub-spoke.
- The page MUST show explicit relationships using connectors, arrows, or clearly aligned flow channels.
- The page MUST separate layers or zones visually. Stacked modules without relationship cues are not acceptable.
- The page MUST have one dominant story. Do not mix "architecture", "feature catalog", and "benefit summary" equally on the same page.
- The page MUST keep mirrored regions balanced. If left and right panels have the same visual weight, their information density should be similar.

---

## 3. Density Limits

- Do not place more than 4 primary modules inside one peer region unless a repeated grid is the point of the page.
- Do not place more than 3 hierarchy levels on a single architecture page unless the middle level is visually simplified into one transport band.
- If a region needs `...`, the region is probably overloaded and should be reduced or split.
- If one region needs much more text than the others, the page should be restructured or split instead of shrinking everything.

---

## 4. Relationship-First Rule

Build in this order:

1. lock the layer structure
2. place the primary connectors / flow path
3. place the core modules
4. add short labels
5. add secondary descriptive text only if space still supports it

Never start by filling every module with text and then "find space" for the relationships later.

---

## 5. Balance Rules

- Equal-sized panels should not carry obviously unequal cognitive load.
- If one side has more modules, reduce per-module detail or rebalance the opposite side.
- Decorative icons must not be used as fake content weight to fill structural emptiness.
- A transport band such as "5G", "API", or "Message Bus" must visually connect the layers it claims to connect.

---

## 6. Common Failure Patterns

### Failure A: Module Catalog Disguised as Architecture

Symptoms:
- many boxes
- few or no connectors
- page reads like inventory, not flow

Fix:
- reduce module count
- add primary relationship path
- demote non-critical boxes into grouped summaries

### Failure B: Right-Heavy or Left-Heavy Density

Symptoms:
- one side has noticeably more boxes or longer text
- mirrored panels feel unbalanced

Fix:
- rebalance module count
- shorten labels
- move excess detail to notes or another page

### Failure C: Layer Titles Exist but Layers Do Not Interact

Symptoms:
- cloud / network / edge / device are stacked
- but the data path is visually unclear

Fix:
- add explicit arrows, channels, or aligned connector lines
- make the transmission band function as a real relationship layer

### Failure D: Overloaded Terminal / Endpoint Area

Symptoms:
- many small endpoint cards squeezed into one band
- one tiny `...` card appears

Fix:
- keep only representative endpoints
- group the rest into a summary label
- use `2x2` or `2x3` patterns before using long single-row compression

---

## 7. Self-check Questions

Before passing an architecture page, answer:

1. Is the primary direction obvious in under 3 seconds?
2. Can a reader tell which layer sends data or control to which layer?
3. Are peer regions balanced in density and rhythm?
4. Is any region overloaded enough that it should be split?
5. If 20% of the boxes disappeared, would the page become clearer?

If questions 2, 3, or 4 fail, the page should not pass as-is.

---

## 8. Review Output Guidance

When an architecture page is reviewed, mention at least:

- relationship clarity
- density balance
- whether connectors are explicit enough
- whether any region is overloaded
