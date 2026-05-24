# Demagog Fact-Checking Tool

AI-powered fact-checking tool for verifying claims from Czech politicians. The tool uses large language models with web search capabilities to research claims and generate structured fact-check reports.

## Features

- Fetches claims from the Demagog.cz GraphQL API
- Extracts context from source transcripts
- Runs AI-powered fact-checking with web search
- Post-processes reports to match Demagog style guidelines
- Generates brief reports for human annotators

## Installation

1. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure API credentials:
   ```bash
   # Edit env.sh and fill in your API keys
   nano ../env.sh

   # Then source the file
   source ../env.sh
   ```

## Optional: Gemini Support

To use Google Gemini models instead of OpenAI, install the additional dependency:
```bash
pip install google-genai>=1.0.0
```

Then set the `GEMINI_API_KEY` in `env.sh`.

## Usage

### Basic Usage

Process all new claims from the Demagog API:
```bash
python fact_check.py
```

### Command Line Options

```
--model MODEL           Model to use (default: gpt-5.1)
                        OpenAI: gpt-5.1, o1, o3-mini, o4-mini, etc.
                        Gemini: gemini-2.5-flash, gemini-2.5-pro, deep-research-pro-preview-12-2025

--reasoning-effort      Reasoning effort level: low, medium, high (default: high)

--output-dir DIR        Directory to store results (default: auto-generated)

--statement-ids ID ...  Process specific statement IDs only

--force                 Reprocess statements even if output files exist

--dry-run               Show what would be processed without actually processing

--min-id ID             Only process statements with ID higher than this value
```

### Examples

Process with a specific model:
```bash
python fact_check.py --model gpt-5.1
```

Process specific statements:
```bash
python fact_check.py --statement-ids 12345 12346 12347
```

Dry run to see what would be processed:
```bash
python fact_check.py --dry-run
```

Resume processing in an existing output directory:
```bash
python fact_check.py --output-dir outputs/gpt5.1_h_20250126_120000
```

## Output

Results are saved to the `outputs/` directory with the following structure:

```
outputs/
└── gpt5.1_h_20250126_120000/
    ├── demagog_raw.json                    # Raw API response
    ├── fact_check_id12345.md               # Full fact-check report
    ├── brief_fact_check_id12345.md         # Brief report for annotators
    └── demagog_deep_research_log_id12345.json  # AI agent logs
```

### Output Files

- **fact_check_id*.md**: Full fact-check report including:
  - Original statement
  - Raw AI research output with sources
  - Post-processed report in Demagog style
  - Prompt and model information

- **brief_fact_check_id*.md**: Simplified report for annotators containing:
  - Original statement
  - Post-processed fact-check report ready for review

## Project Structure

```
.
├── fact_check.py                      # Main CLI script
├── providers.py                       # AI provider abstraction (OpenAI, Gemini)
├── prompts/
│   ├── raw_factcheck_system.jinja     # System prompt for research
│   ├── raw_factcheck_user.jinja       # User prompt template
│   └── style_postprocessing.jinja     # Style guidelines for post-processing
├── demagog_explanation_examples_petr.txt  # Style examples
├── env.sh                             # Environment variables
├── requirements.txt                   # Python dependencies
└── README.md                          # This file
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_ORG_ID` | OpenAI organization ID |
| `GEMINI_API_KEY` | Google Gemini API key (optional) |
| `DEMAGOG_AUTH_TOKEN` | Demagog.cz API authorization token |
