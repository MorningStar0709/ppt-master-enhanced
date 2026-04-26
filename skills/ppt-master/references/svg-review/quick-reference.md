# SVG Review Quick Reference

## 1. One-line Rule

SVG review is not "fit the text into the box". It is:

- make copy obey container capacity
- make containers obey the page grid
- make the grid obey information hierarchy
- make the result pass review before export

## 2. Check Order

Always follow this order:

1. identify the intended review stage
2. classify the symptom
3. classify the root-cause layer
4. assign `P0 / P1 / P2`
5. decide pass or revise immediately

## 3. Symptom Categories

- overflow
- edge crowding
- collision
- overlap
- misalignment
- visual imbalance
- viewport misread

## 4. Root-cause Layers

- copy layer
- container layer
- grid layer
- layering / rendering layer
- pipeline / export layer

## 5. High-frequency Fixes

| Problem | Preferred Fix | Avoid First |
|--------|----------------|-------------|
| Long sentence in a small card | shorten, split, rewrite as keywords | shrink font |
| Text too close to edge | add padding or height | treat "inside the box" as pass |
| Table columns squeeze | recalculate widths, gaps, anchors | moving one cell only |
| Two columns drift | rebuild the grid | visual nudging only |
| Arrow enters target card | stop before safe zone | tiny manual shortening only |
| Center node is covered | change draw order | moving coordinates only |
| Summary band hits body area | rebuild vertical spacing bands | shrink text only |

## 6. Review Priority Rule

- `P0`: cannot pass to next page or export
- `P1`: should be fixed before passing
- `P2`: recordable polish item only

## 7. Per-page Pass Checklist

- [ ] page type identified
- [ ] symptom identified
- [ ] root-cause layer identified
- [ ] priority assigned
- [ ] review record updated
- [ ] page explicitly marked `pass` or `revise immediately`

## 8. Export Rule

Do not run:

- `total_md_split.py`
- `finalize_svg.py`
- `svg_to_pptx.py`

until:

- whole-deck review is complete
- review artifacts are up to date
- the user has explicitly approved export
