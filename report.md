# Frontier LLMs as Fact-Checking Assistants: A Six-Month Study with Demagog.cz

## Abstract

We deploy two implementations of an LLM-based fact-checking agent on Czech political claims as they enter the editorial pipeline of [Demagog.cz](https://demagog.cz), and have professional fact-checkers annotate the outputs against a structured rubric. Over the period October 2025 – April 2026 we collected AI fact-checks for 191 claims across three agent generations: an early development split from the initial iterative build of v1 (AIdev, 31 claims; not a single stable system), a fixed v1 agent built on OpenAI gpt-5.1 (AIv1, 113 claims), and a six-step v2 agent built on gpt-5.4 routed through the OpenAI Codex app server (AIv2, 47 claims). In rows where annotators recorded an overall rating, 89 % of both v1 and v2 outputs are judged publishable (flawless or publishable after light/major edits). v2 reduces the rate of unreliable-source citations from 32 % to 0 % while improving exact verdict-label agreement with the published human fact-check from 55 % to 68 %. We release both agents, all logs, and the annotated dataset as research artefacts.

## 1. Introduction

A widely shared understanding of which factual claims are true and which are not is a load-bearing element of democratic deliberation. Professional fact-checking organisations support that understanding, but their throughput is severely limited by the labour-intensive nature of the work — a Demagog.cz fact-check of a single political claim typically takes several hours of editorial work, and the editorial pipeline backlog can extend across multiple days for any given debate or interview.

Recent progress in large language models with web-search and code-execution tooling has made it plausible to automate large parts of this workflow. Frontier models can now read a transcript, identify the verifiable factual sub-claims, search the public web for supporting and contradicting evidence, write a draft fact-check in a specific editorial style, and check that draft against a rubric — all without human intervention. The question is no longer whether they can produce something, but whether what they produce is useful to a working fact-checker, and what specifically still goes wrong.

This report describes a six-month deployment study answering that question. Our contributions are:

- **Two open-source agents.** A simple two-call agent (v1) demonstrating a no-frills baseline, and a richer six-step agent (v2) that operationalises the lessons from v1's failures. Both are released as standalone packages.
- **A realistic evaluation methodology.** The AI ran on each claim in parallel with the human fact-checker, before publication. This guarantees that AI and human had access to the same state of the public web, eliminating the most common pitfall in fact-checking benchmarks (training-time leakage of the published human verdict).
- **An annotated dataset.** 187 AI fact-checks paired with the corresponding published human fact-check, out of which over 130 is graded against an 45-question rubric by professional fact-checkers, plus 823 free-text annotator comments.
- **A failure-mode analysis.** Seven recurring failure clusters in v1, with frequency and severity, and a separate clustering of the smaller v2 annotation set showing what the architectural changes addressed and what they did not.

The headline finding is that even the simple v1 agent already produces drafts useful enough to start from in 86% of cases, and the more elaborate v2 agent eliminates the most embarrassing failure modes (tabloid sourcing, broken citation format, runaway length) while reducing per-claim human review burden. The dominant residual problem in v2 is editorial polish — phrasings the human would tighten, paragraphs that could be cut, the introductory paragraph framing the claim's context — rather than factual errors. Experienced humans also occationally find relevant sources that the AI missed.

## 2. Related work

Automated fact-checking has been an active research area for almost a decade. Traditional approaches have built special-purpose pipelines: claim-detection classifiers, evidence-retrieval rankers fine-tuned on labelled corpora, natural-language-inference models trained on snippet/claim pairs (FEVER, MultiFC, ClaimBuster, FullFact's automated assistant). These systems typically operate on individual short claims and produce structured veracity labels rather than narrative reports.

We deliberately take a different angle: we evaluate what happens when the role of the entire pipeline is taken over by a general-purpose frontier LLM equipped with web search, with no task-specific training. This is the regime most practitioners now have access to (API-based access to a frontier model, no fine-tuning), and it is the regime in which the "system" is the prompt and the workflow rather than the weights.

## 3. Method

### 3.1 The v1 agent

v1 is a two-call pipeline:

1. **Research.** The Demagog GraphQL API is queried for the in-progress claim, its speaker, and the source debate transcript. The claim is wrapped in a Czech-language system prompt instructing the model to break it into atomic sub-claims, search the web for evidence on each, prefer primary sources, look for contradicting evidence even after finding support, and output a structured citation-backed report. The call is made against the OpenAI Responses API with `web_search_preview` and `code_interpreter` tools enabled, and `reasoning_effort="high"`. The same agent code also supports Google Gemini and Google Deep Research models through a provider abstraction.
2. **Style post-processing.** The raw research output is fed back to the model with a separate Czech-language prompt that rewrites it into the Demagog house style: HTML paragraphs, a short ≤ 280-character summary (the *perex*), one of four verdict labels (`true` / `false` / `misleading` / `unverifiable`), inline keyword-anchored hyperlinks rather than footnotes. Real published fact-checks are included in the prompt as style examples.

### 3.2 The v2 agent

v2 is a six-step pipeline orchestrated as a single OpenAI Codex app-server session, with each step reading and writing markdown files:

```
Step 1 INTERPRET → `claim_interpretation.md` in each claim's work directory (limited web search)
Step 2 SEARCH    → `raw_sources.md` in each claim's work directory (wide-net web search)
Step 3 REFINE    → `refined_sources.md` in each claim's work directory (filter against `fact_check_v2/guides/source_ranking.csv`,
                                                                        upgrade secondary→primary, link-check)
Step 4 DRAFT     → `draft.md` in each claim's work directory (Czech HTML, 3–6 paragraphs hard cap)
Step 5 VERIFY    → `verification.md` in each claim's work directory (PASS/FAIL each item in
                                                                      `fact_check_v2/guides/verification_checklist.md`, fix in place)
Step 6 FINALIZE  → `report.md` in each claim's output directory
```

Three design choices distinguish v2 from v1:

- **Files as state.** Intermediate artefacts are read and written as markdown files; the agent's conversation memory is not the source of truth. This makes the pipeline resilient to context compaction (each step can re-read the relevant files) and allows independent inspection of where a fact-check went wrong.
- **External configuration.** The source-quality ranking, the style guide, the verification checklist, and the example fact-checks are separate files that the agent reads on demand. They are editable by non-developers (e.g. by a Demagog editor) without touching code or prompts.
- **Iterative.** The steps define a default progression but the agent can edit an earlier artefact when a later step uncovers a problem (e.g. step 4 discovers a missing source and re-runs step 2 with a narrower query).

The most important external configuration is `fact_check_v2/guides/source_ranking.csv`, which assigns 45 commonly seen domains to one of five tiers: 1 = primary / authoritative (`csu.gov.cz`, `psp.cz`, `zakonyprolidi.cz`, `vlada.cz`, public broadcasters, …), 2 = good commercial (`aktualne.cz`, `seznamzpravy.cz`, …), 3 = acceptable (`idnes.cz`, `denik.cz`, …), 4 = avoid (`echo24.cz`), 5 = never use (`blesk.cz`, `parlamentnilisty.cz`, `wikipedia.org`, `demagog.cz`, `forum24.cz`, …). Step 3 reads this file and is instructed to remove tier-5 citations entirely and replace them with primary sources where possible.

### 3.3 Provider notes: OpenAI vs. Gemini

We tested both OpenAI and Google Gemini providers in v1's two-call pipeline. With identical prompts and tools, gemini-3-pro-preview and gemini-3-flash-preview produced reports that were dramatically shorter (typical wall time ~1 minute vs. 8–10 minutes for gpt-5.1 with `reasoning_effort=high`), with much sparser citation lists, and frequently with *Vertex AI grounding redirect URLs* that the post-processing step then turned into hallucinated citations. We added a redirect-resolution helper to the Gemini provider (`fact_check_v1/providers.py:resolve_redirect_urls`), but the underlying problem — sparse evidence collection — was not addressable by prompting alone. Direct calls to Google's `deep-research-pro-preview-12-2025` model produced longer outputs but the orchestration model is sufficiently different that it did not slot into our v1 architecture without additional adapters.

These results are observational, not a controlled comparison: we did not invest in tuning Gemini-specific prompts. We believe Gemini and OpenAI frontier models are similarly capable for this task in principle, but they require different prompting strategies, and the v1 prompt set was developed against OpenAI's behaviour first. The released v1 codebase supports both providers.

### 3.4 Cost, latency, and operational profile

Per-claim resource consumption, aggregated across all claims used in the released dataset:

| Metric | v1 (gpt-5.1) | v2 (gpt-5.4 via Codex) |
|---|---:|---:|
| Wall time, mean | 370 s | 652 s |
| Wall time, median | 351 s | 605 s |
| Wall time, max | 903 s | 1126 s |
| Cost per claim, mean | $0.52 | $2.06 |
| Cost per claim, median | $0.52 | $2.10 |
| Cost per claim, max | $0.89 | $2.91 |
| Input tokens, mean | 87 k | 1729 k |
| Cached input tokens, mean | 4 k | 1380 k |
| Output tokens, mean | 18 k | 33 k |
| Web searches, mean | 19 | 34 |

The v1 wall time figures cover only the research call and exclude the ~30–60 s post-processing call; v1 cost is estimated from the raw response logs at OpenAI list pricing of $1.25 / $0.125 / $10.00 per million input / cached / output tokens plus $0.01 per web search, with an additional 12 k input + 3 k output overhead added to approximate the post-processing step. The v2 figures are read directly from per-claim summary JSON files written by the orchestrator and cover the full session including all six steps.

The v2 input-token figure is roughly twenty times v1's; this is largely cumulative context across the six steps, with the large gap between input (1.73 M) and cached input (1.38 M) showing that prompt caching covers most of the repeated context. The marginal *non-cached* input is about four times v1's (0.35 M vs. 0.08 M), and the combined effect places v2 at roughly 4× v1's per-claim cost. Both are still well below the marginal cost of a human editorial hour. Moreover, we put no effort into trying to reduce these numbers and we expect they can be reduced substantially with minimal impact on the quality of the output. 

**Operational requirements** for either version: an OpenAI account with API access to the relevant model (Codex app-server access additionally for v2), a Demagog GraphQL token (for the production claim-fetching path; the agents can also be run on a JSON file of pre-fetched claims), and roughly 10–20 minutes per claim of compute. No local GPU is required. Adapting the agents for a different fact-checking organisation requires translating the system prompts to the target language, replacing the example fact-checks (`fact_check_v1/demagog_explanation_examples_petr.txt` for v1; `fact_check_v2/guides/examples.txt` for v2), reviewing the source-tier CSV against the local media landscape, and pointing the GraphQL ingestion at the local content management system. The v2 design — external configuration files for everything that an editor would want to change — was specifically intended to make this transplant lightweight.

## 4. Data collection

The collection process was identical across all three agent generations:

1. The Demagog editorial team identifies a set of in-progress claims by selecting recent debates and interviews.
2. Human fact-checkers begin work on those claims.
3. We run the AI agent on each claim by querying the Demagog GraphQL API for unpublished entries with a non-empty source transcript (`includeUnpublished: true`, `evaluationStatus != approved`), supplying the model with the claim text, speaker, source URL, and a window of transcript context around the claim.
4. The AI output is saved to a per-experiment directory.
5. After the human fact-check is published, professional fact-checkers from Demagog annotate the AI output against a structured rubric (Excel checklist) and, for many claims, additionally with inline comments in a Word version of the AI report.
6. Once both human and AI versions exist, the pair plus annotations are added to the released dataset.

The collection runs from **October 2025 to April 2026**, with the actual run-timestamp ranges per agent generation shown below.

| Split | Claims | First AI run | Last AI run | Agent / model |
|---|---:|---|---|---|
| AIdev | 31 | 2025-10-14 | 2025-11-26 | early v1 variants, prompts evolving |
| AIv1 | 113 | 2025-12-08 | 2026-03-04 | v1, fixed implementation, gpt-5.1 |
| AIv2 | 47 | 2026-04-02 | 2026-04-21 | v2, gpt-5.4 |

The AIdev split exists because the first-version agent was still in active initial development and the v1 prompts/source examples were being iterated during October and November; rather than discard those early outputs, we preserve them as a separate split and use them primarily for inter-annotator agreement (each AIdev claim was annotated by both fact-checkers, while AIv1 and AIv2 outputs are typically annotated by one fact-checker each). AIdev is therefore explicitly not a single stable system evaluation; AIv1 is the correct fixed-system reference for v1.

The v2 collection was also subject to mid-stream evolution — the `guides/` files (style guide, source ranking, verification checklist) were edited several times during April 2026 in response to early annotator feedback, and small wording fixes were applied to the step prompts. We flag this as a confounder: v2 results in this report mix outputs produced under slightly different agent configurations.

Human fact-checks for **four claim IDs** (24347, 24521, 24532, 24633) are missing from the released dataset because Demagog ultimately did not publish those claims — typically because the editorial team decided the claim was not worth publishing or could not be verified. The AI outputs and annotations for those claims are still included.

## 5. The dataset

The released dataset lives under `dataset/` and is intended both as the supporting evidence for this report and as a standalone research artefact.

### 5.1 Contents

| File / folder | Role | Count |
|---|---|---:|
| `dataset/claims.json` | Per-claim metadata: ID, speaker, role, source debate URL and date, published Demagog assessment (verdict + full HTML explanation + 280-char short explanation), pointers to AI artefacts, agent version, originating experiment timestamp. | 191 |
| `dataset/checklist.csv` | One row per (claim, annotator); rubric questions as columns; values 0/1 or free text. | 164 |
| `dataset/annotations.json` | Free-text annotator comments. Each entry carries the claim ID, agent version, anonymised annotator label, source (`docx` for inline Word comments / checklist cell comments), and the comment text. | 823 |
| `dataset/AIv1/ai<ID>.{md,log}` | AI fact-check produced by v1 plus the full deep-research log. | 113 × 2 |
| `dataset/AIv2/ai<ID>.{md,log}` | AI fact-check produced by v2 plus the per-step log JSONs. | 47 × 2 |
| `dataset/AIdev/ai<ID>.{md,log}` | AI fact-check from the early pre-v1 variants. | 31 × 2 |

In the full project repository, a dataset build script rebuilds all released artefacts from raw experiment outputs and annotator deliverables.

### 5.2 What we do *not* release

**Source debate transcripts** are not redistributed. The Demagog API supplies them under terms that do not permit secondary publication. Each `dataset/claims.json` entry carries the original `source.sourceUrl` (link to the broadcaster's site) so that any consumer of the dataset can reconstruct the transcript from the original source if their use case requires it.

### 5.3 Annotator anonymisation

Annotator real names appear in the raw annotator deliverables (Office authorship metadata embedded in `.docx` and `.xlsx` source files) but are stripped from every released artefact that uses them as an attribute. The `annotator` field in `dataset/checklist.csv` and `dataset/annotations.json`, and the `comment_author` / `author` fields where those carried real names, all use stable opaque labels (`Annotator 1`, `Annotator 2`). The labels are stable across the dataset so that ratings can be paired across rows for inter-annotator-agreement analysis (Cohen's κ requires per-rater marginal label distributions, which requires consistent rater identity), but they do not identify the underlying individual.

### 5.4 Intended uses

The dataset is structured to support the following research tasks without further preprocessing:

- **Agent / prompt improvement studies.** Use the `dataset/annotations.json` comments and the `dataset/checklist.csv` rubric scores as feedback signals for evaluating prompt edits, agent restructurings, or tool changes against historical AI outputs.
- **Verdict-label prediction.** Train or evaluate models that predict the human verdict label (`true` / `false` / `misleading` / `unverifiable`) from the AI fact-check, the source URL, or the raw transcript context.
- **Source-quality classification.** Use `dataset/AI*/ai*.md` together with `fact_check_v2/guides/source_ranking.csv` as labelled training data for source-tier classifiers.
- **Citation-faithfulness checking.** Each AI fact-check contains in-context citations of URLs; the rubric and free-text comments include explicit per-claim assessments of citation faithfulness ("text si nevymýšlí informace, které ve zdrojích nejsou" — "the text does not invent information not present in sources", and the corresponding inverse).
- **Error-detection benchmarks.** The free-text annotations are span-pinned where they originate from Word comments, providing supervision for error-localisation models.
- **Inter-annotator agreement analyses.** The AIdev split has 11 claims annotated by both annotators, available as a comparison set.

Licensing terms for the released dataset and code are under finalisation with Demagog; the release is intended to be permissive enough to support academic and non-commercial research use.

## 6. Analysis

### 6.1 Inter-annotator agreement

Both annotators rated 11 of the 31 AIdev claims. Across the 51 binary rubric questions on which Cohen's κ is computable (≥ 5 paired observations and a non-degenerate marginal distribution), the mean and median κ are **0.19** and **0.15** respectively, with a range from −0.18 to 0.65; the mean observed agreement is **0.60**.

Numerically these κ values fall in the "slight" agreement band of the conventional Landis-Koch interpretation. The discrepancy with the 60 % observed agreement reflects that several rubric questions have heavily skewed marginals (90 %+ of fact-checks either do or do not exhibit the feature), which inflates chance agreement and depresses κ. We therefore caution against over-interpreting the headline κ as evidence that the rubric is unreliable; the more informative reading is per-question.

Questions with the **highest** κ are the ones that demand a relatively concrete editorial judgement on observable text properties:

| Question | κ | Observed |
|---|---:|---:|
| Kontext je relevantní pro pochopení výroku, ale výstup jej v úvodu vhodně nepředstavuje (relevant context is not adequately introduced) | 0.65 | 0.82 |
| Nezveřejnitelné, ale ušetřilo to lidskému fact-checkerovi nějaký čas (saved fact-checker time though not publishable) | 0.62 | 0.91 |
| Jde o složité téma, ale výstup jej v úvodu vhodně nepředstavuje (complex topic not introduced well) | 0.61 | 0.82 |
| V textu chybí některý klíčový zdroj (a key source is missing) | 0.56 | 0.82 |
| Odůvodnění nepoužívá nejaktuálnější zdroje… (does not use most recent pre-claim sources) | 0.49 | 0.73 |

Questions with the **lowest** κ are mostly questions where one annotator left the cell empty and the other filled it in (e.g. paired positive/negative phrasings of the same property), or which probe properties whose definition is genuinely contested:

| Question | κ | Observed |
|---|---:|---:|
| Nalezené zdroje se netýkají výhradně ověřovaného tématu (sources are not strictly on-topic) | −0.18 | 0.45 |
| Výrok jsem hodnotil(a) já (I rated this claim) | −0.14 | 0.73 |
| K hodnocení výroku je více dohledatelných zdrojů, ale v textu jsou uvedeny méně než dva (fewer than two sources used) | −0.10 | 0.45 |
| Z některého zdroje je chybně citována relevantní informace (a relevant source is misquoted) | −0.06 | 0.45 |
| Text si vymýšlí informace, které ve zdrojích nejsou (fabricated information) | −0.06 | 0.45 |

We report this as a property of the rubric and the small double-annotated sample, not as a claim about systematic disagreement.

### 6.2 Overall publishability ratings

The rubric concludes with a single five-level summary judgement: *flawless* / *publishable with light edits* / *publishable with major edits* / *not publishable but saved time* / *worse than nothing*. Distribution per split:

| Rating | AIdev | AIv1 | AIv2 |
|---|---:|---:|---:|
| Vše bez problémů, s hrdostí zveřejnitelné (flawless) | 1 (3 %) | 0 (0 %) | 1 (5 %) |
| Zveřejnitelné beze změn, ale bylo by vhodné provést úpravy (light edits) | 9 (25 %) | 36 (34 %) | 11 (50 %) |
| Zveřejnitelné po zásadnějších změnách (major edits) | 11 (31 %) | 50 (47 %) | 5 (23 %) |
| Nezveřejnitelné, ale ušetřilo to lidskému fact-checkerovi nějaký čas (saved time) | 3 (8 %) | 11 (10 %) | 1 (5 %) |
| Pro lidského fact-checkera by bylo lepší, kdyby to neexistovalo (waste of time) | 3 (8 %) | 1 (1 %) | 1 (5 %) |
| (no rating recorded) | 9 (25 %) | 9 (8 %) | 3 (14 %) |
| Total rows | 36 | 106 | 22 |

Two readings are warranted. **Across all rows**, publishable outcomes (flawless + light edits + major edits) are 81 % for v1 and 77 % for v2. **Conditioned on rows with a recorded overall rating**, publishable outcomes are 89 % for v1 (86/97) and 89 % for v2 (17/19); the "waste of time" rate is ~1 % for v1 and ~5 % for v2.

### 6.3 Headline quantitative metrics

Quantitative metrics are computed in `data_analysis.ipynb`, which is the single source of truth for all numeric results in this report. We track three programmatic metric families there: tier-5 source leak rate, document-length statistics, and AI-vs-human verdict-label agreement.

**Tier-5 source leak rate.** Every URL in every released AI fact-check is extracted (markdown link syntax + HTML `<a href>`) and looked up against the v2 source-ranking CSV. A fact-check counts as a "tier-5 leak" if it cites at least one tier-5 domain (Blesk, Parlamentní listy, Wikipedia, Demagog.cz, Forum24, etc.).

| Split | Files | Tier-5 leak rate |
|---|---:|---:|
| AIdev | 31 | 16.1 % |
| AIv1 | 113 | 31.9 % |
| AIv2 | 47 | **0.0 %** |

**Document length.** Mean and median paragraph counts per AI fact-check, plus the share of paragraphs with more than 5 sentences (the explicit cap in the v2 style guide):

| Split | Paragraphs / doc (mean) | Paragraphs / doc (median) | Sentences / paragraph (median) | % paragraphs > 5 sentences |
|---|---:|---:|---:|---:|
| AIdev | 9.6 | 9 | 3 | 17.5 % |
| AIv1 | 12.9 | 12 | 3 | 13.7 % |
| AIv2 | 5.1 | 5 | 3 | 12.0 % |

**Verdict-label agreement with the published human fact-check.** The four-class verdict label (`true`, `false`, `misleading`, `unverifiable`) is read from `dataset/claims.json` (`ai_verdict`) and compared to the published human verdict (`assessment.veracity.name`) for all claims where both labels are available.

| Split | Comparable verdicts | Exact-match accuracy |
|---|---:|---:|
| AIdev | 30 | 50 % |
| AIv1 | 110 | 55 % |
| AIv2 | 47 | **68 %** |

**Three qualitative mismatch examples (v2).**

- **Claim 24680** (`dataset/AIv2/ai24680.md`; human text in `dataset/claims.json`): AI says *unverifiable*, human says *true*. The AI report acknowledges one rejected parliamentary vote but marks the first vote and the "no roundtable" clause as insufficiently proven; the human fact-check cites both parliamentary vote records and rates the statement true.
- **Claim 24683** (`dataset/AIv2/ai24683.md`; human text in `dataset/claims.json`): AI says *misleading*, human says *false*. Both agree that the "almost all EU countries" framing is overstated; the divergence comes from thresholding (AI treats the Czech sub-claim as partially salvaging the statement, human treats the EU-wide claim as dominant and false).
- **Claim 24705** (`dataset/AIv2/ai24705.md`; human text in `dataset/claims.json`): AI says *false*, human says *true*. AI uses NATO's rounded percentages (CZ 2.00, BE 2.00, IT 2.01), while the human check recomputes from NATO base values with higher precision (CZ 2.0136, IT 2.0082, BE 1.9952), flipping the ordering.

### 6.4 Failure clusters in v1

The most thoroughly annotated split is AIv1, which yielded 503 free-text comments (151 inline Word comments + 352 rubric-pinned cell comments). The qualitative analysis below is a condensed restatement of `dataset/v1_annotations_analysis.md`; see that file for full context and source-attributed quotations. Frequency labels (Very High / High / Medium) reflect annotator-comment counts; severity labels reflect the editorial judgement of how badly the issue degrades publishability.

**Cluster 1 — Unreliable, secondary, and non-primary sources.** *Frequency: Very High. Severity: High.* The agent reached for tabloids (Blesk), aggregator sites (Parlamentní listy), opinion outlets (Forum24, Echo24 commentary), Wikipedia, foreign-language sources where Czech equivalents existed, and — embarrassingly — Demagog.cz itself. Sub-issues: (i) Wikipedia used in place of the primary sources Wikipedia cites; (ii) tabloids treated as factual sources; (iii) Slovak / Polish / English sources used when Czech equivalents existed; (iv) opinion / commentary articles treated as factual.

**Cluster 2 — Broken, incorrect, or insufficiently specific source links.** *Frequency: High. Severity: High.* URLs that 404, URLs that point to a different article than described, links to general databases (NALUS, Ministry of Finance "vývoj cenové regulace") rather than the specific record, video citations without a timestamp, PDF citations without a page number.

**Cluster 3 — Excessive length, repetition, and poor text structure.** *Frequency: Very High. Severity: Medium.* Paragraphs longer than the editorial standard, conclusions repeated twice, trivial sub-claims given full paragraphs, tangential international comparisons, perex (short summary) rephrased and repeated rather than complementing the body. Recurring annotator instruction: "stačil by jeden odstavec" ("one paragraph would be enough") / "celé hodnocení zestručnili cca na polovinu" ("shorten the whole fact-check by roughly half").

**Cluster 4 — Incorrect citation format (links on media names instead of keywords).** *Frequency: High. Severity: Medium.* The Demagog house style places hyperlinks on the key noun or verb being claimed, not on the media outlet name. v1 systematically violated this — `Podle [Blesku](url) inflace vzrostla` ("According to Blesk, inflation increased") instead of `Inflace [vzrostla](url) o 2,8 %` ("Inflation increased by 2.8%"). This is a stylistic but uniformly enforced rule and was the single most repeated annotator complaint at the rubric level.

**Cluster 5 — Factual errors: hallucinations, misquotations, and wrong data.** *Frequency: Medium. Severity: Critical.* The agent occasionally cited a source while describing content that was not in it; used data published *after* the date the claim was made (a category error in fact-checking); confused political roles (current vs. former); attributed a claim to the wrong country or the wrong speaker; and on rare occasion fabricated a quote.

**Cluster 6 — Incorrect verdict or flawed reasoning.** *Frequency: Medium. Severity: High.* The agent issued "misleading" verdicts on the basis of trivial linguistic distinctions while all underlying sub-claims were rated true; produced self-contradictory reasoning; inserted its own opinion or speculation about the speaker's intent; and failed to consider charitable interpretations of ambiguous claims.

**Cluster 7 — Language quality and readability issues.** *Frequency: Medium. Severity: Medium.* Untranslated English / German quotes; legal and economic jargon ("obiter dictum", "jádrová inflace" — "core inflation") used without explanation; awkward Czech sentence structures; non-neutral phrasings that read as advocacy rather than reportage.

The full per-comment evidence base for each cluster is in `dataset/v1_annotations_analysis.md`. Frequency rankings inform the v2 design decisions (§3.2) directly: clusters 1, 2, 4 motivated the source-refinement step and the externalised source ranking; cluster 3 motivated the hard 3–6 paragraph cap; clusters 5 and 6 motivated the verification step.

### 6.5 Failure clusters in v2

The v2 split contains 40 free-text annotator comments across 11 distinct claim IDs. **Almost all (39 of 40) come from a single annotator**; the v2 cluster analysis below should therefore be read as one annotator's view of an early v2 sample, not a stable population estimate. Comments were manually clustered into the categories below, with an explicit mapping back to the v1 clusters (§6.4):

| v2 cluster | Count | Share | Maps to v1 cluster |
|---|---:|---:|---|
| **A** Redundant / off-topic content; intro/conclusion polish | 14 | 35 % | 3 |
| **F** Evaluative or non-neutral language | 6 | 15 % | 7 |
| **B** Context / intro paragraph missing or inadequate | 5 | 12.5 % | partly 1+3 (different framing) |
| **D** CTK / media pass-through where primary source could have been found | 4 | 10 % | 1 |
| **E** Verdict / contrast hangs on a non-material distinction | 4 | 10 % | 6 |
| **C** Wrong content placed in / missing from short summary (perex) | 3 | 7.5 % | new (perex-specific) |
| **G** Single broken / non-specific link | 2 | 5 % | 2 |
| **H** Other (e.g. social media access limit) | 2 | 5 % | n/a (capability) |

What v2 visibly **fixed** relative to v1: tier-5 source leakage went to zero (programmatic measurement, §6.3), explicit complaints about media-name-anchored hyperlinks disappeared (Cluster 4 has no analogue in the v2 comments), and link-validity complaints fell from "high" to two single instances. These map directly to the v2 architectural choices that operationalised the v1 lessons.

What v2 did **not** fix: redundancy and editorial polish remain by far the most common complaint (35 % of v2 comments are some form of "this paragraph is unnecessary" or "this could be tightened"), even though the median document length is now half of v1's. The annotator standard is essentially "every sentence should be load-bearing", which the 3–6 paragraph cap helps with but does not enforce. Secondary-source pass-through (cluster D) — citing a CTK story republished in another paper rather than the original CTK wire — remains an issue that the source-tier ranking does not address (CTK *is* a tier-1 source in our ranking; the problem is the agent chooses a tier-2 republisher of CTK content rather than `ceskenoviny.cz`). A new failure mode specific to v2 is misuse of the *perex* (short summary) — putting the wrong information in or missing the "main argument" rule.

### 6.6 Limitations and threats to validity

We highlight the following limitations of the analysis above:

- **Single language, single country, single editorial style.** All claims are Czech political claims rated against Demagog's specific editorial methodology. Generalisation to other languages, jurisdictions, or fact-checking houses is plausible but not demonstrated.
- **Mid-stream agent evolution.** The AIdev split spans gradually evolving v1 prompts and the AIv2 split spans guide-file edits during April 2026. The "AIv1" split is the closest thing to a fixed-system evaluation; the AIdev and AIv2 splits should be read as observational rather than controlled.
- **Annotator pool size.** Two professional fact-checkers, with most claims annotated by one of them. The rubric was developed jointly with Demagog and is internally consistent, but per-annotator strictness differences are not modelled.
- **Sample size for v2.** 47 claims and 40 free-text comments is enough to identify dominant failure patterns and to make programmatic measurements robust, but not enough to support fine-grained rate estimates with tight confidence intervals.
- **Possible model contamination on older claims.** The Demagog.cz site is part of the public web. For claims whose human fact-check predates the model training cut-off, frontier models may have seen the published verdict during training. This is *not* an issue for our setup — by construction every AI fact-check in this dataset was produced before the corresponding human fact-check was published — but consumers reusing the released AI fact-checks against newer models should be aware of the risk.
- **AI-vs-human verdict matching remains a heuristic.** The verdict-accuracy numbers in §6.3 use the `ai_verdict` field in `dataset/claims.json`, inferred from each AI fact-check text. While this now covers the full corpus with available human verdicts, edge cases with unusual wording can still be misparsed.

## 7. Ethical considerations

LLMs are widely documented to carry political biases that map roughly onto a US-centric left/right axis but transfer in idiosyncratic ways to other political contexts. Czech politics maps onto these axes only loosely; we have not characterised the political-bias profile of either gpt-5.1 or gpt-5.4 on Czech-language political claims, and we caution that an automated fact-checker can encode systematic asymmetries that are invisible at the level of individual fact-checks.

Concretely, the released dataset is dominated by a small set of high-profile Czech politicians: Andrej Babiš (29 claims), Karel Havlíček (19), Lubomír Metnar (16), Vít Rakušan (16), Petr Pavel (15), Libor Vondráček (13), Petr Fiala (9). The two most-represented party affiliations are ANO (Babiš, Havlíček) and STAN (Rakušan); the dataset is *not* a balanced or representative sample of the Czech political spectrum, and per-party accuracy / strictness analyses on this dataset would be confounded by speaker selection. We make this distribution explicit so that consumers of the dataset can decide whether it fits their intended use.

The most operationally important ethical risk is **automation bias**: a fact-checker who reads a fluent, well-cited AI draft may rubber-stamp its verdict rather than independently verifying. The Demagog editorial workflow keeps a human in the loop on every published fact-check — the AI output is treated as a draft to be rewritten, not as a publication candidate — but the temptation to defer to a confident AI summary grows the better the agent gets. Mitigations include (i) requiring the human editor to record changes made to the AI draft (already standard at Demagog), (ii) periodically running the human-only workflow on a sample to detect drift, and (iii) reviewing inter-rater agreement between the AI and the human on contested claims.

Finally, this is a **drafting tool for trained fact-checkers**, not a substitute for them. Both v1 and v2 pass through claims they cannot adequately verify (e.g. claims requiring direct source contact, claims about events from the past 24 hours where the agent's web index is stale, value judgements that are not factual claims) without flagging the limitation as clearly as a trained editor would. We do not recommend deploying either version in any user-facing or autonomous capacity.

## 8. Conclusion

A general-purpose frontier LLM equipped with web search, when wrapped in a thin domain-specific scaffold, can produce Czech-language political fact-checks that professional fact-checkers usually consider publishable (81 % of v1 rows and 77 % of v2 rows, including major-edit cases). A more elaborate scaffold that operationalises the editorial lessons from the simpler version eliminates the most embarrassing failure modes — tabloid sourcing, runaway length, broken citation format — and improves verdict-label agreement with the published human verdict from 55 % to 68 %, at roughly 4× the per-claim cost. In both cases the cost is a tiny fraction of the marginal cost of a human editorial hour.

The dominant failure mode of the better agent is no longer factual error or source quality; it is editorial polish — paragraphs that could be cut, phrasings that could be tightened, framing of the claim's context. Whether the next architectural iteration can close this gap is an open question; on the strength of the trajectory from v1 to v2, we expect that further externalisation of editorial conventions into machine-readable rules (and possibly a fine-tuned editor-style model) would help.

Two follow-on experiments would substantially strengthen this report. First, a head-to-head human-vs-AI evaluation in which fact-checkers are blinded to the source of the draft they are editing, to remove the rater bias inherent in knowing the draft is from an AI. Second, a longitudinal evaluation tracking the published human edits to AI drafts, providing a richer signal than rubric scores. Both are feasible within the existing Demagog workflow.

We release both agents and the full annotated dataset to support such follow-on work and to enable independent analysis of bias and failure modes that we have not characterised here.

---

## Appendices

### Appendix A — Annotator rubric

The full rubric template is in the full project repository; per-question result tables across splits will be inserted here when the report is finalised. The underlying released data is `dataset/checklist.csv`.

### Appendix B — Prompt listings

**v1.** Three Jinja2 templates (`fact_check_v1/prompts/raw_factcheck_system.jinja`, `fact_check_v1/prompts/raw_factcheck_user.jinja`, `fact_check_v1/prompts/style_postprocessing.jinja`) plus the inline style examples in `fact_check_v1/demagog_explanation_examples_petr.txt`.

**v2.** Six step prompts (`fact_check_v2/prompts/step1_interpret.md` through `fact_check_v2/prompts/step6_finalize.md`), the agent preamble (`fact_check_v2/codex_instructions.md`), and the four guide files (`fact_check_v2/guides/style_guide.md`, `fact_check_v2/guides/verification_checklist.md`, `fact_check_v2/guides/source_ranking.csv`, `fact_check_v2/guides/examples.txt`).

All prompts and guide files are released verbatim with the agent code; this appendix is a pointer rather than a duplication.

### Appendix C — Dataset schema and file-layout reference

See `dataset/README.md` for the canonical schema and the file naming convention (every artefact is suffixed with the 6-digit Demagog claim ID; `dataset/claims.json` is the index). The schema of each JSON / CSV file is documented in the corresponding section of §5.

### Appendix D — Worked examples

We include three complete claim records to illustrate typical AI behaviour at the two ends of the quality scale and the dominant residual issues with the better agent. Annotator references are anonymised.

#### D.1 v1, "wasted time" — claim 24619

- **Speaker:** Karel Havlíček (Minister of Industry and Trade).
- **Date:** 2026-03-01.
- **Claim:** *"Když se na to podíváme s ohledem na elektřinu, tak jsme třetí nejlepší v tuto chvíli v Evropě (v meziměsíčním srovnání cen)."* (EN: "Looking at electricity, we are currently the third best in Europe in month-to-month price comparison.")
- **Human verdict:** True.
- **Files:** AI fact-check `dataset/AIv1/ai24619.md`; human fact-check in `dataset/claims.json` (ID 24619); AI log `dataset/AIv1/ai24619.log`.
- **Annotator comments (4 total):**
  - "je třeba čerpat z datasetů eurostatu" ("it is necessary to use Eurostat datasets") (cluster 1: should use Eurostat datasets directly)
  - "rozhovor holce a šichtařové považuje za analýzu" ("it treats an interview with Holcová and Šichtařová as an analysis") (cluster 6/7: agent treats an interview with two journalists as an analysis)
  - "používá zdroje z roku 2025" ("it uses sources from 2025") (cluster 5: temporally inappropriate sources)
  - "hodně divoký nazvat to analýzou" ("quite wild to call it an analysis") (cluster 7: language — "wild to call this an analysis")

This is the only v1 output in the dataset that received the "worse than nothing" rating, and the comments span four of the seven failure clusters in a single fact-check.

#### D.2 v1, "publishable with light edits" — claim 24455

- **Speaker:** Martin Kupka (Ministr dopravy).
- **Date:** 2025-11-28.
- **Claim:** *"Dneska zveřejnil Český statistický úřad – nezávislá instituce – data o tom, jak roste ekonomika a ta data ukazují na 2,8 % růstu HDP meziročně při srovnání dat třetích čtvrtletí."* (EN: "Today the Czech Statistical Office—an independent institution—published data showing 2.8% year-on-year GDP growth when comparing third-quarter data.")
- **Human verdict:** True.
- **Files:** AI fact-check `dataset/AIv1/ai24455.md`; human fact-check in `dataset/claims.json` (ID 24455).
- **Annotator comments (4 total):**
  - "Odkazy nejsou v textu na konkrétních slovech, ale až na konci vět. Rychlost kontroly zdroje to neovlivní." ("Links are not on specific words but only at sentence ends. It does not help source-checking speed.") (cluster 4: citation format)
  - "1) předělali bychom formát zdrojování  2) celé hodnocení zestručnili cca a polovinu" ("1) we would rework citation formatting 2) shorten the whole fact-check by about half") (clusters 4, 3: format + length)
  - "tohle se opakuje" (cluster 3: repetition)
  - (Annotator 2 comment confirming the publishable rating with light edits.)

This is a representative typical-case v1 output: the agent finds the right sources (ČSÚ — Czech Statistical Office — directly), produces a verdict that matches the human verdict, but violates the citation-format rule and runs roughly twice as long as a human fact-checker would write.

#### D.3 v2, "publishable with light edits" — claim 24694

- **Speaker:** Libor Vondráček (MP, chairman of Svobodní / The Free Citizens Party).
- **Date:** 2026-04-08.
- **Claim:** *"V roce 2022, když nastupovala nová vláda Petra Fialy, Miloš Zeman nejel na summit NATO v roce 2022."* (EN: "In 2022, when Petr Fiala's new government was taking office, Miloš Zeman did not go to the NATO summit in 2022.")
- **Human verdict:** True.
- **Files:** AI fact-check `dataset/AIv2/ai24694.md`; human fact-check in `dataset/claims.json` (ID 24694); AI log (per-step) `dataset/AIv2/ai24694.log`.
- **Annotator comments (9 total, all inline Word comments):**
  - "Tohle bych vynechal. Myslím, že je to jasné a takovéto vysvětlení není třeba." ("I would omit this. It is clear; this explanation is unnecessary.") (cluster A)
  - "Poslední odstavec nemá odpovídat na otázku. Je to shrnutí (vypíchnutí) důležitých zjištění, argumentace a vyhodnocení." ("The last paragraph should not answer the question; it should summarize key findings, argumentation, and evaluation.") (clusters A, F: structural rule about the closing paragraph)
  - "přirozeněji by znělo pravdivý" ("'pravdivý' would sound more natural") (cluster F: lexical naturalness)
  - "Velmi zjednodušený kontext. Mělo by tam být, na jakou otázku reaguje a co na ní odpovídá kromě samotného výroku." ("The context is overly simplified. It should state what question is being answered and what the answer is beyond the quote itself.") (cluster B: missing context)
  - "nepíšeme, co je jádro výroku. to by bylo trochu domýšlení" ("We do not write what the 'core' of the statement is; that is somewhat speculative.") (cluster F: editorial speculation about the speaker's intent)
  - "ten zdroj bych radši zakomponoval do předchozích vět. Takhle je to opakování" ("I would rather incorporate that source into previous sentences; this is repetitive.") (cluster A: redundancy)
  - "není třeba, lidé si to přečtou" ("not needed; readers will read it themselves") (cluster A)
  - "V závěrečném odstavci už nejsou odkazy třeba." ("Links are no longer necessary in the concluding paragraph.") (cluster A: structural rule)
  - "to je hodnotící" ("this is evaluative") (cluster F: evaluative language)

This v2 output is rated publishable with light edits and demonstrates the residual gap clearly: nine concrete editorial improvements, none of which concern factual error, source quality, or verdict correctness — all of them are about polish, structure, and natural Czech prose.

A fully clean v2 example available in the dataset is **claim 24680** (Vít Rakušan, 2026-03-19), which received the "Vše bez problémů, s hrdostí zveřejnitelné" ("No issues at all, publishable with pride") rating without inline comments; we include it as a reference point but do not annotate it here, since the absence of annotations is itself the point.

---

*Report draft prepared for review. Numeric results are maintained in `data_analysis.ipynb`; re-run that notebook after any dataset change to refresh figures.*
