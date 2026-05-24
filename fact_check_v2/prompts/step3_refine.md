# Step 3: Refine Sources

Recall these files:
- `work/raw_sources.md` — your collected sources
- `guides/source_ranking.csv` — quality tiers for known domains
- `work/claim_interpretation.md` — to check date constraints

Write your refined source list to `work/refined_sources.md`.

## What to Do

Go through each source in raw_sources.md and apply the following checks:

### 1. Quality Filter
Look up each source's domain in source_ranking.csv.
- **Tier 5 (blocked):** Remove the source entirely. If it contained important information, search for the same information from a tier 1-2 source. Record the replacement.
- **Tier 4 (avoid):** Try to find a better source. If no replacement exists, keep it but flag it.
- **Tier 3 (acceptable):** Keep, but if a tier 1-2 source has the same information, prefer that.
- **Tier 1-2:** Keep.
- **Unknown domain:** Assess manually — is it an official institution, a reputable media outlet, or something questionable?

### 2. Primary Source Check
For each secondary source (media article), check:
- Does it cite a primary source (official statistics, legislation, official document)?
- If yes, can you find that primary source directly? Search for it.
- Replace the secondary citation with the primary source.

### 3. Link Validation
For each source, verify:
- The URL is accessible (try to fetch it)
- The URL contains the information you cited
- If a link is broken, search for an alternative URL or an archived version (web.archive.org)

### 4. Temporal Check
- Flag any source published after the claim date
- Mark whether it's used as evidence (not allowed) or as later context (allowed if clearly noted)

### 5. Language Check
- Flag foreign-language sources
- If a Czech source has the same information, replace the foreign source

### 6. Coverage Check
- Ensure at least one tier-1 source exists for the main claim
- Ensure each non-trivial sub-claim has at least one source
- If any sub-claim has no source, note it as potentially unverifiable

## Output Format

Use the same format as raw_sources.md, but add:
- **Tier:** [1-5 or unknown]
- **Status:** kept / replaced / removed / flagged
- **Notes:** [any issues or replacement details]

At the end, add a summary section listing any sub-claims that lack adequate sources.
