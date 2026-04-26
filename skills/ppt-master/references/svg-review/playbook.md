# SVG Review Playbook

## 1. Purpose

This playbook defines the execution loop for SVG review inside `ppt-master`.

Use it when:

- a page has just been generated and needs immediate self-review
- a whole deck is ready for the final SVG Review Gate
- you need to turn review findings into structured fix work

## 2. Standard Review Loop

### Step 1. Confirm the Review Object

Check the right artifact for the right stage:

- per-page generation stage: review the newly generated page and note likely downstream risk
- pre-export gate: treat `svg_final/`, browser whole-page preview, and expected PPT result as the main targets

### Step 2. Identify the Symptom

Classify the visible issue first:

- overflow
- edge crowding
- collision
- overlap
- misalignment
- visual imbalance
- viewport misread

### Step 3. Identify the Root-cause Layer

Decide which layer is really responsible:

- copy
- container
- grid
- layering / rendering
- pipeline / export

### Step 4. Assign Priority

Use `priority-rules.md`:

- `P0`: blocking
- `P1`: should be fixed in the current cycle
- `P2`: can be logged for polish only

### Step 5. Write the Review Evidence

Update:

- `review/review_state.json`
- then render `review/review_log.md` and `review/fix_tasks.md` from the current state

Do not delay this until the end of the deck.

### Step 6. Fix at the Right Level

Preferred fix direction:

- generation logic
- reusable helper or layout rule
- content simplification

Avoid:

- one-off edits in final assets as the default fix path
- repeated local coordinate nudging without grid logic

### Step 7. Re-check and Close

After revision:

- re-check the same page
- ensure no new issue is introduced
- update the review state and re-render the reports

## 3. Whole-deck Review Gate

After all pages are generated:

1. consolidate page-by-page review records
2. confirm no `P0` remains
3. close or justify all `P1` findings before export
4. summarize retained `P2` items if any
5. prepare `review/user_confirmation.md` from `review/review_state.json`
6. present the review summary to the user
7. wait for explicit approval before post-processing or export

## 4. Review Rhythm Rule

Required rhythm:

1. generate one page
2. review that page immediately
3. revise immediately if blocked
4. proceed to the next page only after pass
5. complete whole-deck review after all pages are done
6. get user approval
7. then run `total_md_split.py`
8. then run `finalize_svg.py`
9. then run `svg_to_pptx.py`

## 5. Completion Criteria

The review loop is complete only when all of the following are true:

- page-level review records exist
- outstanding fixes are tracked in `review_state.json` and reflected in `fix_tasks.md`
- final recommendation is stored in `review_state.json` and rendered into `user_confirmation.md`
- the user has explicitly approved proceeding to export
