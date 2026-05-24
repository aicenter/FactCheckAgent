# Step 5: Verify the Draft

Recall these files:
- `work/draft.md` — the draft to verify
- `guides/verification_checklist.md` — the checklist to evaluate against
- `guides/style_guide.md` — for reference on style rules
- `guides/source_ranking.csv` — for reference on source quality

Write your evaluation to `work/verification.md`.

## What to Do

Go through every item in the verification checklist. For each item, write:

```
- [ ] **Item name**: [brief explanation] (PASS / FAIL)
```

Use `guides/style_guide.md` and `guides/source_ranking.csv` to judge items where needed. For the link spot-check, actually fetch 2-3 links to verify they work and contain the cited information.

### If all items PASS:
Write `## Result: PASS` at the end of verification.md.

### If any items FAIL:
1. Fix the specific issues directly in `work/draft.md` — edit only what needs changing.
2. If the fix requires better sources, update `work/refined_sources.md` (and search for new sources if needed).
3. After fixing, re-evaluate only the previously failed items.
4. Repeat until all items pass, then write `## Result: PASS` at the end of verification.md.

You may use web search to verify links or find replacement sources for failed items.
