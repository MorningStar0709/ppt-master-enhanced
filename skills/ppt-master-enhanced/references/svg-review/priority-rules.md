# SVG Review Priority Rules

## 1. Purpose

Use this document to assign `P0 / P1 / P2` consistently and decide whether a page may pass review or whether export may proceed.

## 2. Core Rule

Priority is based on delivery impact, not on how difficult the fix is.

Judge with these questions:

1. Does it break information readability?
2. Does it break page structure?
3. Does it create preview / export instability?
4. Does it significantly increase rework risk?

## 3. Priority Definitions

| Level | Meaning | Required Action |
|------|---------|-----------------|
| `P0` | Blocking issue | Must fix immediately; page cannot pass and deck cannot export |
| `P1` | Clearly quality-damaging issue | Should be fixed in the current cycle before export |
| `P2` | Acceptable but polish-worthy issue | May be logged and handled as final polish |

## 4. `P0` Rules

Assign `P0` when any of the following applies:

- text or labels truly overflow and hurt reading
- key content is covered
- the core page structure is wrong
- process arrows or logic are incorrect
- preview and export expectations clearly diverge
- the issue would mislead the audience

Handling:

- revise immediately
- re-check the page
- update the review log
- do not advance or export

## 5. `P1` Rules

Assign `P1` when:

- text does not overflow but is clearly too close to edges
- multi-column or multi-block layout obviously drifts
- local collision or connector depth makes the page unstable
- the page remains understandable but visibly unprofessional

Handling:

- fix in the current cycle whenever possible
- do not leave unresolved `P1` for export

## 6. `P2` Rules

Assign `P2` when:

- spacing is slightly uneven but still readable
- rhythm is not ideal but structure is stable
- a small detail could be improved without affecting clarity

Handling:

- log it clearly
- treat it as polish only
- do not let accumulated `P2` issues become structural risk

## 7. Symptom Defaults

| Symptom | Default Priority | Escalate When |
|--------|------------------|---------------|
| Overflow | `P1` | escalate to `P0` if readability breaks |
| Edge crowding | `P2` | escalate to `P1` if clearly unstable |
| Collision | `P1` | escalate to `P0` if structure or meaning breaks |
| Overlap | `P1` | escalate to `P0` if key content is covered |
| Misalignment | `P1` | escalate to `P0` if whole-page structure breaks |
| Visual imbalance | `P2` | escalate to `P1` if key message is weakened |
| Viewport misread | no priority yet | confirm whether it is a real issue first |

## 8. Pass / Block Rule

- Any `P0` means the page is blocked
- Unresolved `P1` means the deck should not proceed to export
- `P2` may remain only if explicitly documented as non-blocking
