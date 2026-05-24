#!/usr/bin/env python3
"""
Fact-checking pipeline v2 for Demagog.cz claims.

Uses OpenAI Codex app server with a multi-step pipeline:
1. INTERPRET — analyze the claim (no web search)
2. SEARCH — find sources (web search)
3. REFINE — filter and improve sources
4. DRAFT — write the report
5. VERIFY — check against verification checklist
6. FINALIZE — produce final output

Each step runs as a turn in a single Codex session.
Intermediate results are written to files by the agent.
"""

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from typing import Literal
import regex
import requests
from glob import glob
from pathlib import Path

try:
    from openai_codex_sdk import Codex
except ImportError:
    print("ERROR: openai-codex-sdk not installed. Install with: pip install openai-codex-sdk")
    sys.exit(1)


# --- Configuration ---
DEFAULT_MODEL = "gpt-5.4"
GRAPHQL_ENDPOINT = "https://demagog.cz/graphql"

# Pricing per million tokens (USD) and per web search query
MODEL_PRICING = {
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00, "web_search": 0.01},
}
DEFAULT_PRICING = {"input": 2.50, "cached_input": 0.25, "output": 15.00, "web_search": 0.01}

GRAPHQL_QUERY = """
{
  statements(
    limit: 50
    sortSourcesInReverseChronologicalOrder: true
    includeUnpublished: true
  ) {
    id
    sourceSpeaker {
      firstName
      lastName
      role
    }
    content
    assessment{
      evaluationStatus
      shortExplanation
      veracity {
        name
      }
    }
    source {
      id
      releasedAt
      name
      medium {
        name
      }
      sourceUrl
      transcript
    }
    statementTranscriptPosition {
      startLine
      startOffset
      endLine
      endOffset
    }
  }
}
"""

# --- Paths ---
SCRIPT_DIR = Path(__file__).parent.resolve()
PROMPTS_DIR = SCRIPT_DIR / "prompts"
GUIDES_DIR = SCRIPT_DIR / "guides"


def install_sdk_compat_patches():
    """Patch SDK item parsing for app-server payload changes.

    Recent app-server builds may emit `file_change` items with
    `status="in_progress"` before completion. Older SDK versions only accept
    `completed|failed`, which causes turn parsing to abort mid-step.
    """
    try:
        import openai_codex_sdk.types as sdk_types
        import openai_codex_sdk.parsing as sdk_parsing
    except ImportError:
        return

    class CompatFileChangeItem(sdk_types.FileChangeItem):
        status: Literal["in_progress", "completed", "failed"]

    sdk_types.FileChangeItem = CompatFileChangeItem
    sdk_parsing._ITEM_MODELS["file_change"] = CompatFileChangeItem


install_sdk_compat_patches()


def fetch_claims(auth_token=None):
    """Fetch claims from the Demagog GraphQL API."""
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = auth_token

    response = requests.post(
        GRAPHQL_ENDPOINT,
        json={"query": GRAPHQL_QUERY},
        headers=headers,
    )
    response.raise_for_status()
    data = response.json()

    statements = data["data"]["statements"]
    filtered = [
        s
        for s in statements
        if s["source"]["transcript"] != ""
        and s["assessment"]["evaluationStatus"] != "approved"
    ]
    return filtered


def line_match_ratio(line, claim):
    """Calculate how well a line matches a claim based on word overlap."""
    lh = set(line.lower().split(" "))
    match_count = sum(1 for w in claim.lower().split(" ") if w in lh)
    words = claim.split(" ")
    return match_count / len(words) if words else 0


def fetch_context(statement_record):
    """Extract context around the claim from the transcript."""
    if (
        "transcript" not in statement_record["source"]
        or statement_record["source"]["transcript"] == ""
    ):
        return None

    claim = statement_record["content"]
    claim_cleaned = claim.replace(" (...) ", ".*")
    claim_cleaned = regex.sub(r"\(.*?\)", "", claim_cleaned)
    claim_cleaned = regex.sub(r"\s+", " ", claim_cleaned).strip()

    transcript = statement_record["source"]["transcript"].replace("\r", "")
    transcript_lines = [l.strip() for l in transcript.split("\n") if l.strip()]

    match_ratios = [line_match_ratio(line, claim_cleaned) for line in transcript_lines]
    matched_line_index = match_ratios.index(max(match_ratios))

    context_lines = transcript_lines[
        max(0, matched_line_index - 10) : matched_line_index + 3
    ]
    return "\n".join(context_lines)


def load_prompt(step_name: str, **kwargs) -> str:
    """Load a step prompt template and fill in variables."""
    prompt_file = PROMPTS_DIR / f"{step_name}.md"
    template = prompt_file.read_text(encoding="utf-8")

    for key, value in kwargs.items():
        rendered = str(value) if value else "N/A"
        template = template.replace(f"{{{key}}}", rendered)
        template = template.replace(f"{{{{{key}}}}}", rendered)

    return template


def get_processed_ids(experiment_dir):
    """Get the set of statement IDs that have already been processed and the highest ID."""
    pattern = os.path.join(experiment_dir, "*/output/report.md")
    existing_files = glob(pattern)
    processed_ids = set()
    highest_id = None
    for f in existing_files:
        # Extract ID from directory name like id12345/output/report.md
        parts = Path(f).parts
        for part in parts:
            if part.startswith("id"):
                statement_id = part[2:]
                processed_ids.add(statement_id)
                try:
                    id_num = int(statement_id)
                    if highest_id is None or id_num > highest_id:
                        highest_id = id_num
                except ValueError:
                    pass
    return processed_ids, highest_id


def setup_claim_directory(experiment_dir: str, statement_id: str) -> Path:
    """Create the working directory structure for a single claim."""
    claim_dir = Path(experiment_dir) / f"id{statement_id}"
    (claim_dir / "work").mkdir(parents=True, exist_ok=True)
    (claim_dir / "output").mkdir(parents=True, exist_ok=True)

    # Copy guide files into the claim directory so the Codex agent can read them
    guides_dest = claim_dir / "guides"
    if guides_dest.exists():
        shutil.rmtree(guides_dest)
    shutil.copytree(GUIDES_DIR, guides_dest)

    return claim_dir


async def process_statement(statement, experiment_dir: str, model: str):
    """Process a single statement through the 6-step pipeline."""
    statement_id = statement["id"]
    claim = statement["content"]
    speaker = f"{statement['sourceSpeaker']['firstName']} {statement['sourceSpeaker']['lastName']}, {statement['sourceSpeaker']['role']}"
    source = f"An article in {statement['source']['medium']['name']} released on {statement['source']['releasedAt']} available from {statement['source']['sourceUrl']}."
    context = fetch_context(statement)

    print(f"\n{'=' * 60}")
    print(f"Processing statement ID {statement_id}")
    print(f"Claim: {claim[:100]}...")

    # Set up directory
    claim_dir = setup_claim_directory(experiment_dir, statement_id)
    print(f"Working directory: {claim_dir}")

    # Save claim metadata
    metadata = {
        "statement_id": statement_id,
        "claim": claim,
        "speaker": speaker,
        "source": source,
        "context": context,
        "model": model,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (claim_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Write AGENTS.md into the claim directory so Codex picks it up as instructions
    codex_instructions = (SCRIPT_DIR / "codex_instructions.md").read_text(encoding="utf-8")
    (claim_dir / "AGENTS.md").write_text(codex_instructions, encoding="utf-8")

    # Define the 6 steps
    steps = [
        ("step1_interpret", {"claim": claim, "speaker": speaker, "source": source, "context": context}),
        ("step2_search", {}),
        ("step3_refine", {}),
        ("step4_draft", {}),
        ("step5_verify", {}),
        ("step6_finalize", {}),
    ]

    start_time = time.time()

    # Start Codex session (explicitly pass API key from environment)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  ERROR: OPENAI_API_KEY environment variable not set.")
        return claim_dir
    codex = Codex({"apiKey": api_key})
    thread = codex.start_thread({
        "model": model,
        "workingDirectory": str(claim_dir),
        "sandboxMode": "workspace-write",
        "webSearchEnabled": True,
        "approvalPolicy": "never",
    })

    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    total_web_searches = 0
    cumulative_output_tokens = 0
    last_input_tokens = 0
    last_cached_tokens = 0
    last_output_tokens = 0
    step_summaries = []

    for step_name, step_kwargs in steps:
        step_start = time.time()
        print(f"\n  Step: {step_name}...")

        prompt = load_prompt(step_name, **step_kwargs)

        try:
            turn = await thread.run(prompt)
            step_elapsed = time.time() - step_start

            # Extract token usage
            usage = turn.usage
            input_tokens = usage.input_tokens if usage else 0
            cached_tokens = usage.cached_input_tokens if usage else 0
            output_tokens = usage.output_tokens if usage else 0
            # Extract detailed item log from turn.items and count web searches
            items_log = []
            web_search_count = 0
            for item in (turn.items or []):
                item_type = type(item).__name__
                if item_type == "WebSearchItem":
                    web_search_count += 1
                item_entry = {"type": item_type}
                if hasattr(item, "text"):
                    item_entry["text"] = item.text
                if hasattr(item, "command"):
                    item_entry["command"] = item.command
                if hasattr(item, "exit_code"):
                    item_entry["exit_code"] = item.exit_code
                if hasattr(item, "output"):
                    item_entry["output"] = item.output[:2000] if item.output else None
                if hasattr(item, "file_path"):
                    item_entry["file_path"] = item.file_path
                if hasattr(item, "query"):
                    item_entry["query"] = item.query
                if hasattr(item, "url"):
                    item_entry["url"] = item.url
                if hasattr(item, "error"):
                    item_entry["error"] = item.error
                items_log.append(item_entry)

            # Track cumulative context (last step = full session context)
            last_input_tokens = input_tokens
            last_cached_tokens = cached_tokens
            last_output_tokens = output_tokens
            cumulative_output_tokens += output_tokens
            total_web_searches += web_search_count

            # Print step summary to stdout
            print(f"  Completed in {step_elapsed:.1f}s")
            print(f"  Tokens: {input_tokens:,} in (cached: {cached_tokens:,}) / {output_tokens:,} out")
            print(f"  Web searches: {web_search_count}")
            print(f"  Actions: {len(items_log)} items")

            step_summary = {
                "step": step_name,
                "elapsed_seconds": round(step_elapsed, 1),
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_tokens,
                "output_tokens": output_tokens,
                "web_searches": web_search_count,
                "num_items": len(items_log),
            }
            step_summaries.append(step_summary)

            # Write detailed step log
            log_file = claim_dir / "work" / f"{step_name}_log.json"
            log_data = {
                "step": step_name,
                "elapsed_seconds": round(step_elapsed, 1),
                "prompt_length": len(prompt),
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_tokens,
                "output_tokens": output_tokens,
                "web_searches": web_search_count,
                "final_response": turn.final_response,
                "items": items_log,
            }
            log_file.write_text(
                json.dumps(log_data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except KeyboardInterrupt:
            print(f"\n  Interrupted at step {step_name}!")
            raise
        except Exception as e:
            print(f"  ERROR in step {step_name}: {e}")
            error_file = claim_dir / "work" / f"{step_name}_error.txt"
            error_file.write_text(str(e), encoding="utf-8")
            break

    elapsed = time.time() - start_time

    # Estimate billed usage from the final turn's cumulative thread usage.
    # The SDK reports turn usage in a way that appears cumulative across the
    # thread, so summing step-level usage materially overcounts output and can
    # also distort input totals. We therefore treat the final turn's usage as
    # the best local estimate of billed token totals for the whole claim.
    non_cached_input = last_input_tokens - last_cached_tokens
    search_cost = total_web_searches * pricing["web_search"]
    input_cost = non_cached_input * pricing["input"] / 1_000_000
    cached_input_cost = last_cached_tokens * pricing["cached_input"] / 1_000_000
    output_cost = last_output_tokens * pricing["output"] / 1_000_000
    total_cost = (
        input_cost
        + cached_input_cost
        + output_cost
        + search_cost
    )

    # Print and save claim summary
    print(f"\n  {'─' * 40}")
    print(f"  Total time: {elapsed:.1f}s")
    print(
        f"  Estimated billed usage: {last_input_tokens:,} in "
        f"(cached: {last_cached_tokens:,}) / {last_output_tokens:,} out"
    )
    print(f"  Observed web searches: {total_web_searches}")
    print(f"  Estimated cost: ${total_cost:.4f}")

    summary = {
        "statement_id": statement_id,
        "model": model,
        "total_elapsed_seconds": round(elapsed, 1),
        "usage_estimate_basis": "final_turn_cumulative_usage",
        "estimated_input_tokens": last_input_tokens,
        "estimated_cached_input_tokens": last_cached_tokens,
        "estimated_non_cached_input_tokens": non_cached_input,
        "estimated_output_tokens": last_output_tokens,
        "observed_web_searches": total_web_searches,
        "observed_cumulative_step_output_tokens": cumulative_output_tokens,
        "estimated_input_cost_usd": round(input_cost, 6),
        "estimated_cached_input_cost_usd": round(cached_input_cost, 6),
        "estimated_output_cost_usd": round(output_cost, 6),
        "estimated_web_search_cost_usd": round(search_cost, 6),
        "estimated_cost_usd": round(total_cost, 6),
        "steps": step_summaries,
    }
    (claim_dir / "work" / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Clean up guides copied into the claim directory
    guides_dest = claim_dir / "guides"
    if guides_dest.exists():
        shutil.rmtree(guides_dest)

    # Check if output was produced
    report_file = claim_dir / "output" / "report.md"
    if report_file.exists():
        print(f"  Report saved to {report_file}")
    else:
        print(f"  WARNING: No report produced. Check work/ files for diagnostics.")

    return claim_dir


async def main():
    parser = argparse.ArgumentParser(
        description="Fact-check claims from Demagog.cz using Codex multi-step pipeline"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Codex model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--experiment-dir",
        help="Directory to store results (default: auto-generated)",
    )
    parser.add_argument(
        "--auth-token",
        help="Authorization token for the Demagog API (or set DEMAGOG_AUTH_TOKEN env var)",
    )
    parser.add_argument(
        "--statement-ids",
        nargs="+",
        help="Specific statement IDs to process",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing of statements even if output files exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually processing",
    )
    parser.add_argument(
        "--min-id",
        type=int,
        help="Only process statements with ID higher or equal to this value",
    )

    args = parser.parse_args()

    # Set up experiment directory
    if args.experiment_dir:
        experiment_dir = args.experiment_dir
    else:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        experiment_dir = f"experiments/v2_{args.model}_{timestamp}"

    os.makedirs(experiment_dir, exist_ok=True)
    print(f"Experiment directory: {experiment_dir}")

    # Fetch or load claims
    raw_file = os.path.join(experiment_dir, "demagog_raw.json")
    if args.experiment_dir and os.path.exists(raw_file):
        print(f"Reading claims from existing {raw_file}...")
        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        statements = data["data"]["statements"]
        print(f"Loaded {len(statements)} statements from file")
    else:
        auth_token = args.auth_token or os.environ.get("DEMAGOG_AUTH_TOKEN")
        print("Fetching claims from Demagog API...")
        statements = fetch_claims(auth_token)
        print(f"Found {len(statements)} statements with transcripts (not approved)")

        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(
                {"data": {"statements": statements}}, f, indent=4, ensure_ascii=False
            )
        print(f"Raw data saved to {raw_file}")

    # Filter statements
    if args.force:
        processed_ids = set()
        highest_id = None
    else:
        processed_ids, highest_id = get_processed_ids(experiment_dir)
        if processed_ids:
            print(
                f"Found {len(processed_ids)} already processed statements (highest ID: {highest_id})"
            )

    if args.min_id is not None:
        highest_id = args.min_id-1
        print(f"Using manually set minimum ID: {args.min_id}")

    if args.statement_ids:
        statements = [s for s in statements if s["id"] in args.statement_ids]
        print(f"Filtered to {len(statements)} statements matching specified IDs")
        new_statements = [s for s in statements if s["id"] not in processed_ids]
    else:
        if highest_id is not None:
            new_statements = [
                s
                for s in statements
                if int(s["id"]) > highest_id and s["id"] not in processed_ids
            ]
            print(f"Processing only IDs higher than {highest_id}")
        else:
            new_statements = statements

    print(f"Statements to process: {len(new_statements)}")

    if args.dry_run:
        print("\nDry run — would process:")
        for s in new_statements:
            print(f"  ID {s['id']}: {s['content'][:80]}...")
        return

    if not new_statements:
        print("No new statements to process.")
        return

    # Process each statement
    for i, statement in enumerate(new_statements, 1):
        print(f"\n{'=' * 60}")
        print(f"Processing {i}/{len(new_statements)}")
        try:
            await process_statement(
                statement=statement,
                experiment_dir=experiment_dir,
                model=args.model,
            )
        except KeyboardInterrupt:
            print("\nInterrupted by user. Exiting.")
            sys.exit(1)
        except Exception as e:
            print(f"  ERROR processing statement {statement['id']}: {e}")
            continue

    print(f"\n{'=' * 60}")
    print(f"Processing complete. Results saved to {experiment_dir}")


if __name__ == "__main__":
    asyncio.run(main())
