# Fact-Checking Tool (v2)

AI-powered fact-checking pipeline for Czech political claims. This version runs a six-step Codex app-server workflow and stores all intermediate artifacts and per-step logs.

## Features

- Fetches claims from the Demagog.cz GraphQL API
- Runs a six-step fact-checking pipeline in one Codex session
- Uses file-based workflow state (`work/*.md`) for inspectability
- Applies external guides for style, verification, and source ranking
- Saves detailed per-step logs and per-claim cost/token summaries

## Installation

1. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install openai-codex-sdk requests regex
   ```

3. Configure API credentials:
   ```bash
   # Edit env.sh and fill in your API keys
   nano ../env.sh

   # Then source the file
   source ../env.sh
   ```

## Usage

### Basic Usage

Process all new claims from the Demagog API:
```bash
python fact_check.py
```

### Command Line Options

```
--model MODEL           Codex model to use (default: gpt-5.4)

--experiment-dir DIR    Directory to store results (default: auto-generated)

--auth-token TOKEN      Demagog API token (or DEMAGOG_AUTH_TOKEN env var)

--statement-ids ID ...  Process specific statement IDs only

--force                 Reprocess statements even if output exists

--dry-run               Show what would be processed without running

--min-id ID             Only process statement IDs >= this value
```

### Examples

Run with default model and auto experiment directory:
```bash
python fact_check.py
```

Process only selected claims:
```bash
python fact_check.py --statement-ids 24701 24702 24703
```

Resume into an existing experiment directory:
```bash
python fact_check.py --experiment-dir experiments/v2_gpt-5.4_20260421_113102
```

Collect flattened final reports for dataset tooling:
```bash
./collect_reports.sh experiments/v2_gpt-5.4_20260421_113102
```

Recompute summary token/cost fields from step logs:
```bash
python recompute_summary_costs.py
```

## Output

Results are saved under the experiment directory:

```
experiments/
└── v2_gpt-5.4_20260421_113102/
    ├── demagog_raw.json
    ├── reports/
    │   └── report<ID>.md                 # (after collect_reports.sh)
    └── id<ID>/
        ├── AGENTS.md
        ├── metadata.json
        ├── guides/                       # copied from fact_check_v2/guides/
        ├── output/
        │   └── report.md                 # final fact-check
        └── work/
            ├── claim_interpretation.md
            ├── raw_sources.md
            ├── refined_sources.md
            ├── draft.md
            ├── verification.md
            ├── step1_interpret_log.json
            ├── step2_search_log.json
            ├── step3_refine_log.json
            ├── step4_draft_log.json
            ├── step5_verify_log.json
            ├── step6_finalize_log.json
            └── summary.json
```

### Output Files

- **`output/report.md`**: final fact-check report for one claim
- **`work/step*_log.json`**: per-step detailed execution logs (tokens, searches, actions)
- **`work/summary.json`**: per-claim wall time, token usage, and cost estimate
- **`reports/report<ID>.md`**: flattened final report files used by dataset compilation

## Project Structure

```
.
├── fact_check.py                   # Main v2 orchestrator
├── architecture.md                 # v2 design and step rationale
├── codex_instructions.md           # Codex agent preamble copied per claim
├── collect_reports.sh              # Flatten id*/output/report.md into reports/
├── recompute_summary_costs.py      # Recompute summary token/cost fields
├── prompts/
│   ├── step1_interpret.md
│   ├── step2_search.md
│   ├── step3_refine.md
│   ├── step4_draft.md
│   ├── step5_verify.md
│   └── step6_finalize.md
├── guides/
│   ├── style_guide.md
│   ├── verification_checklist.md
│   ├── source_ranking.csv
│   ├── examples.txt
│   └── prirucka.md
└── README.md
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (required) |
| `DEMAGOG_AUTH_TOKEN` | Demagog.cz API authorization token (required for API fetch mode) |

