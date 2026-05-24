# Fact-Check Agent v2 — Architecture

## Overview

A multi-step fact-checking pipeline designed for the OpenAI Codex app server. Unlike v1's rigid two-turn structure (research + post-processing), v2 decomposes the work into 6 focused steps within a single Codex session, with intermediate results written to files that serve as the handoff mechanism between steps.

## Design Principles

1. **Files as state, not conversation memory.** Each step reads its inputs from files and writes its outputs to files. This makes the pipeline resilient to context compaction and fully debuggable — when a fact-check goes wrong, you can inspect the intermediate file to pinpoint which step failed.

2. **Separation of concerns.** Source finding, source quality assessment, writing, and verification are distinct steps with distinct instructions. This directly addresses the top annotator complaints from v1 (bad sources, wrong format, excessive length).

3. **External configuration over prompt-embedded rules.** Source rankings, style guide, and verification checklist are separate files that the agent reads on demand, making them editable by non-developers (e.g., fact-checkers themselves) without touching code.

4. **Single Codex session, single model.** All steps run in one continuous session. The Codex app server handles context compaction automatically; the file-based state ensures no information is lost if compaction occurs.

5. **Iterative, not rigid.** The steps define the default progression and the artifacts to produce, but the agent can go back and update any earlier artifact when a later step reveals it is insufficient. Updates are incremental — the agent edits what needs changing, not redoing work from scratch. After updating an earlier artifact, it continues forward and updates downstream artifacts as needed.

## Pipeline Steps

```
Step 1: INTERPRET   → work/claim_interpretation.md
Step 2: SEARCH      → work/raw_sources.md
Step 3: REFINE      → work/refined_sources.md
Step 4: DRAFT       → work/draft.md
Step 5: VERIFY      → work/verification.md
Step 6: FINALIZE    → output/report.md, output/brief_report.md
```

### Step 1: INTERPRET (limited web search)

**Input:** Claim text, speaker, source metadata, transcript context
**Output:** `work/claim_interpretation.md`
**Purpose:** Understand what the claim says before searching for anything.

The agent identifies:
- The claim's sub-parts (atomic factual statements)
- Possible interpretations of ambiguous phrasing
- Which interpretation(s) to verify and why
- What evidence would confirm or refute each sub-claim
- What type of primary sources to look for (statistics, legislation, official documents)

This step uses limited web search — only to clarify the claim's context (e.g., look up specific legislation, events, or entities mentioned). The focus is on reasoning about what to look for, preventing the v1 problem of searching for the wrong thing or over-decomposing trivial claims.

### Step 2: SEARCH (web search)

**Input:** `work/claim_interpretation.md`, claim metadata
**Output:** `work/raw_sources.md`
**Purpose:** Find all relevant sources using web search.

The agent searches for evidence for each sub-claim identified in step 1. It records:
- URL
- Source name and type (primary/secondary, media/official/database)
- Date of publication
- Key quote or data point from the source
- Which sub-claim it relates to

The agent is instructed to cast a wide net — find more sources than needed, including primary sources. No quality filtering yet.

### Step 3: REFINE (web search allowed for finding primary sources)

**Input:** `work/raw_sources.md`, `guides/source_ranking.csv`
**Output:** `work/refined_sources.md`
**Purpose:** Filter, rank, and improve the source list.

The agent reads the source ranking CSV and:
1. **Removes** sources from the blocklist (tier 5: Blesk, Wikipedia, Demagog.cz, etc.)
2. **Replaces** secondary sources with primary ones where possible (e.g., a Blesk article citing ČSÚ data → find the ČSÚ page directly)
3. **Validates links** by checking that each URL is accessible and contains the claimed information
4. **Checks temporal validity** — flags sources published after the claim date
5. **Prefers Czech sources** over foreign-language equivalents
6. **Ensures** at least one primary or tier-1 source per sub-claim

Output format: same as raw_sources.md but with quality annotations and replacements noted.

### Step 4: DRAFT (no web search)

**Input:** `work/refined_sources.md`, `work/claim_interpretation.md`, `guides/style_guide.md`
**Output:** `work/draft.md`
**Purpose:** Write the fact-check report following the Demagog style guide.

The agent reads the style guide and writes a complete report in Czech. Key constraints enforced at this stage:
- 3-6 paragraphs for the explanation (hard limit)
- Inline hyperlinks on keywords, never on media names
- All foreign quotes translated to Czech
- Simple, accessible language
- Neutral tone
- Verdict consistent with sub-claim analysis

### Step 5: VERIFY (web search allowed for link checking)

**Input:** `work/draft.md`, `guides/style_guide.md`, `guides/verification_checklist.md`
**Output:** `work/verification.md`
**Purpose:** Systematic quality check against the checklist.

The agent reads the verification checklist and evaluates each item as PASS or FAIL with a brief explanation. If any item fails, it also produces a corrected version of the draft.

The checklist covers:
- Source quality (no blocklisted sources, primary sources present)
- Citation format (links on keywords, not media names)
- Factual accuracy (each citation matches its source)
- Text quality (paragraph length, no repetition, no redundant sections)
- Verdict logic (consistent with sub-claim analysis, not based on trivial inaccuracies)
- Language quality (no jargon, no foreign quotes, neutral tone)

### Step 6: FINALIZE

**Input:** `work/verification.md`, `work/draft.md`
**Output:** `output/report.md`, `output/brief_report.md`
**Purpose:** Produce final outputs.

If verification passed: copy draft to final output, extract brief report (max 280 chars summary + explanation).
If verification failed: the corrected draft from step 5 becomes the final output.

## File Structure

```
fact_check_v2/
  architecture.md           # This file
  fact_check.py             # Orchestrator: fetches claims, runs Codex sessions
  codex_instructions.md     # Instructions sent to Codex at session start
  guides/
    style_guide.md          # Demagog writing style guide (read by agent in steps 4-5)
    verification_checklist.md  # Checklist for step 5
    source_ranking.csv      # Source quality tiers (read by agent in step 3)
    examples.md             # Example fact-checks showing desired output
  prompts/
    step1_interpret.md      # Prompt for claim interpretation
    step2_search.md         # Prompt for source search
    step3_refine.md         # Prompt for source refinement
    step4_draft.md          # Prompt for writing the draft
    step5_verify.md         # Prompt for verification
    step6_finalize.md       # Prompt for final output
```

## Orchestration

The Python orchestrator (`fact_check.py`) handles:
1. Fetching claims from the Demagog GraphQL API (same as v1)
2. Extracting transcript context (same as v1)
3. Creating a working directory for each claim
4. Starting a Codex app server session
5. Sending each step's prompt as a user turn, waiting for completion
6. Optionally triggering manual compaction between steps (`thread/compact/start`)
7. Collecting final outputs

The orchestrator does NOT do any LLM calls itself — all intelligence is in the Codex session. The orchestrator is a thin loop:

```python
for step in [step1, step2, step3, step4, step5, step6]:
    prompt = load_prompt(step, claim_data)
    send_to_codex_session(prompt)
    wait_for_completion()
    # optionally: trigger compaction
```

## Configuration Files

### source_ranking.csv

```csv
domain,tier,note
csu.gov.cz,1,Czech Statistical Office
czso.cz,1,Czech Statistical Office (alt domain)
psp.cz,1,Parliament of the Czech Republic
zakonyprolidi.cz,1,Legislation database
mfcr.cz,1,Ministry of Finance
vlada.cz,1,Government of the Czech Republic
nku.cz,1,Supreme Audit Office
volby.cz,1,Official election results
eurostat.ec.europa.eu,1,Eurostat
irozhlas.cz,1,Czech Radio (public)
ct24.ceskatelevize.cz,1,Czech Television (public)
ceskenoviny.cz,1,CTK news agency
denik.cz,3,Regional newspaper
idnes.cz,3,Commercial news
aktualne.cz,2,Commercial news (higher quality)
seznamzpravy.cz,2,Commercial news (higher quality)
blesk.cz,5,Tabloid — NEVER USE
parlamentnilisty.cz,5,Unreliable — NEVER USE
wikipedia.org,5,Encyclopedia — NEVER USE directly
demagog.cz,5,Self-reference — NEVER USE
forum24.cz,5,Opinion site — NEVER USE
echo24.cz,4,Opinion-heavy — avoid
```

Tier meanings: 1=primary/authoritative, 2=good secondary, 3=acceptable secondary, 4=avoid if possible, 5=blocked.

### Differences from v1

| Aspect | v1 | v2 |
|--------|----|----|
| Steps | 2 (research + postprocess) | 6 (interpret, search, refine, draft, verify, finalize) |
| Source quality | Vague prompt instruction | Explicit CSV ranking + dedicated refinement step |
| Citation format | Instruction in prompt | Style guide file + verification checklist |
| Debugging | Opaque JSON log | 6 intermediate .md files |
| Length control | None | Hard limits in style guide + verification |
| Verdict quality | Single-pass | Interpretation step + verification consistency check |
| Configuration | Baked into Jinja templates | External files editable by fact-checkers |
| Runtime | OpenAI/Gemini API directly | Codex app server session |
| Context handling | N/A (2 independent calls) | Codex auto-compaction + file-based state |
