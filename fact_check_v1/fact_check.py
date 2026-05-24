#!/usr/bin/env python3
"""
Standalone fact-checking script for Demagog.cz claims.

This script performs the main functionality from demagog_deep_res.ipynb:
1. Downloads new claims from the GraphQL API
2. Runs raw fact checks using OpenAI deep research
3. Post-processes the fact checks using style guidelines
4. Extracts simplified brief reports for annotators

By default, it processes all new claims that don't have output files yet.
"""

import argparse
import json
import os
import time
import regex
import requests
from glob import glob
from langchain_core.prompts import PromptTemplate

from providers import get_provider, detect_provider, DEFAULT_MODEL, FactCheckProvider


# --- Configuration ---
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_MODEL = "gpt-5.1"


def get_model_prefix(model: str) -> str:
    """Generate a concise but informative prefix from the model name.

    Examples:
        gpt-5.1 → gpt5.1
        gemini-2.5-flash → gem2.5f
        gemini-2.5-pro → gem2.5p
        deep-research-pro-preview-12-2025 → dr-pro
        o1 → o1
        o3-mini → o3m
    """
    model_lower = model.lower()

    if model_lower.startswith("deep-research-"):
        # deep-research-pro-preview-12-2025 → dr-pro
        parts = model_lower.split("-")
        variant = parts[2] if len(parts) > 2 else "pro"  # pro, flash, etc.
        return f"dr-{variant}"
    elif model_lower.startswith("gemini-"):
        # Extract version and variant: gemini-2.5-flash → gem2.5f
        parts = model_lower.split("-")
        version = parts[1] if len(parts) > 1 else ""
        variant = parts[2][0] if len(parts) > 2 else ""  # first letter of flash/pro/etc
        return f"gem{version}{variant}"
    elif model_lower.startswith("gpt-"):
        # gpt-5.1 → gpt5.1, gpt-4o → gpt4o
        return model_lower.replace("-", "")
    elif model_lower.startswith(("o1", "o3", "o4")):
        # o1 → o1, o3-mini → o3m
        parts = model_lower.split("-")
        variant = parts[1][0] if len(parts) > 1 else ""
        return f"{parts[0]}{variant}"
    else:
        # Fallback: remove dashes and take first 8 chars
        return model_lower.replace("-", "")[:8]
GRAPHQL_ENDPOINT = "https://demagog.cz/graphql"
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


def load_prompt_templates():
    """Load prompt templates from files."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    system_message_template = PromptTemplate.from_file(
        template_file=os.path.join(script_dir, "prompts/raw_factcheck_system.jinja"),
        template_format="jinja2"
    )

    user_message_template = PromptTemplate.from_file(
        template_file=os.path.join(script_dir, "prompts/raw_factcheck_user.jinja"),
        template_format="jinja2"
    )

    style_postprocessing_template = PromptTemplate.from_file(
        template_file=os.path.join(script_dir, "prompts/style_postprocessing.jinja"),
        template_format="jinja2"
    )

    return system_message_template, user_message_template, style_postprocessing_template


def fetch_claims(auth_token=None):
    """Fetch claims from the Demagog GraphQL API."""
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = auth_token

    response = requests.post(
        GRAPHQL_ENDPOINT,
        json={"query": GRAPHQL_QUERY},
        headers=headers
    )
    response.raise_for_status()
    data = response.json()

    # Filter for statements with transcripts that aren't approved yet
    statements = data['data']['statements']
    filtered = [
        s for s in statements
        if s['source']['transcript'] != '' and s['assessment']['evaluationStatus'] != 'approved'
    ]

    return filtered


def line_match_ratio(line, claim):
    """Calculate how well a line matches a claim based on word overlap."""
    lh = set(line.lower().split(' '))
    match_count = 0
    for w in claim.lower().split(' '):
        if w in lh:
            match_count += 1
    return match_count / len(claim.split(' ')) if claim.split(' ') else 0


def fetch_context(statement_record):
    """Extract context around the claim from the transcript."""
    if 'transcript' not in statement_record['source'] or statement_record['source']['transcript'] == '':
        return None

    claim = statement_record['content']
    # Replace ellipsis by wildcards and remove anything in brackets
    claim_cleaned = claim.replace(" (...) ", ".*")
    claim_cleaned = regex.sub(r'\(.*?\)', '', claim_cleaned)
    claim_cleaned = regex.sub(r'\s+', ' ', claim_cleaned).strip()

    # Find the line in the transcript with the cleaned claim
    transcript = statement_record['source']['transcript'].replace('\r', '')
    transcript_lines = transcript.split('\n')
    transcript_lines = [line.strip() for line in transcript_lines if line.strip()]

    # Find the line with the cleaned claim
    match_ratios = [line_match_ratio(line, claim_cleaned) for line in transcript_lines]
    matched_line_index = match_ratios.index(max(match_ratios))

    # Get surrounding lines as context
    context_lines = transcript_lines[max(0, matched_line_index - 10):matched_line_index + 3]
    context = "\n".join(context_lines)
    return context


def run_fact_check(provider: FactCheckProvider, claim, source=None, speaker=None,
                   context=None, reasoning_effort=DEFAULT_REASONING_EFFORT,
                   system_template=None, user_template=None):
    """Run fact check using the provider with web search."""
    system_message = system_template.format()
    user_message = user_template.format(
        source=source,
        speaker=speaker,
        context=context,
        claim=claim
    )

    full_prompt = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    response = provider.submit_and_wait(
        system_message=system_message,
        user_message=user_message,
        reasoning_effort=reasoning_effort
    )

    return response, full_prompt


def postprocess_fact_check(provider: FactCheckProvider, deep_research_output, claim,
                           style_template, demagog_examples,
                           reasoning_effort=DEFAULT_REASONING_EFFORT):
    """Post-process the deep research output using style guidelines."""
    style_prompt = style_template.format(examples=demagog_examples)

    user_message = f"""
Original claim: {claim}

Deep research output to be post-processed:
{deep_research_output}

Please rewrite this fact-check report following the style guidelines provided in the system message.
"""

    return provider.simple_completion(
        system_message=style_prompt,
        user_message=user_message,
        reasoning_effort=reasoning_effort
    )


def extract_brief_report(fact_check_file, brief_file):
    """Extract a simplified brief report for annotators."""
    with open(fact_check_file, "r", encoding="utf-8") as f:
        content = f.read()

    sections = {}
    current_section = None
    lines = content.splitlines()
    for line in lines:
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)

    statement_id = fact_check_file.split("fact_check_id")[-1].replace(".md", "")

    with open(brief_file, "w", encoding="utf-8") as f:
        f.write(f"# Brief Fact Check Report ID {statement_id}\n")
        f.write("\n## Statement\n")
        f.write("\n".join(sections.get("Statement", [])).strip() + "\n")
        f.write("\n## AI Fact Check Report to Annotate\n")
        f.write("\n".join(sections.get("Post-processed Fact Check Report", [])).strip() + "\n")


def get_processed_ids(output_dir):
    """Get the set of statement IDs that have already been processed and the highest ID."""
    pattern = os.path.join(output_dir, "fact_check_id*.md")
    existing_files = glob(pattern)
    processed_ids = set()
    highest_id = None
    for f in existing_files:
        # Extract ID from filename like fact_check_id12345.md
        basename = os.path.basename(f)
        if basename.startswith("fact_check_id") and basename.endswith(".md"):
            statement_id = basename[len("fact_check_id"):-len(".md")]
            processed_ids.add(statement_id)
            try:
                id_num = int(statement_id)
                if highest_id is None or id_num > highest_id:
                    highest_id = id_num
            except ValueError:
                pass
    return processed_ids, highest_id


def process_statement(provider: FactCheckProvider, statement, output_dir,
                      reasoning_effort, system_template, user_template,
                      style_template, demagog_examples):
    """Process a single statement through the fact-checking pipeline."""
    statement_id = statement['id']
    print(f"\nProcessing statement ID {statement_id}...")

    start_time = time.time()

    # Run fact check with web search
    response, full_prompt = run_fact_check(
        provider=provider,
        claim=statement['content'],
        source=f"An article in {statement['source']['medium']['name']} released on {statement['source']['releasedAt']} available from {statement['source']['sourceUrl']}.",
        speaker=f"{statement['sourceSpeaker']['firstName']} {statement['sourceSpeaker']['lastName']}, {statement['sourceSpeaker']['role']}",
        context=fetch_context(statement),
        reasoning_effort=reasoning_effort,
        system_template=system_template,
        user_template=user_template
    )
    end_time = time.time()

    # Save the response log
    logfile = os.path.join(output_dir, f"demagog_deep_research_log_id{statement_id}.json")
    with open(logfile, 'w', encoding='utf-8') as f:
        json.dump(response.raw_response, f, indent=2, ensure_ascii=False)

    # Save the fact check markdown
    fact_check_file = os.path.join(output_dir, f"fact_check_id{statement_id}.md")
    with open(fact_check_file, 'w', encoding='utf-8') as f:
        f.write(f"# Fact Check for Statement ID {statement_id}\n\n")
        f.write(f"## Statement\n{statement['content']}\n\n")
        f.write("---\n")
        f.write(f"## AI Fact Check\n{response.output_text}\n")
        f.write("---\n")
        f.write(f"## Prompt\n{json.dumps(full_prompt, ensure_ascii=False, indent=2)}\n\n")
        f.write(f"Model: {response.model}\n")
        f.write(f"Wall time: {end_time - start_time:.2f} seconds\n")

    print(f"  Fact check completed in {end_time - start_time:.2f} seconds")

    # Post-process the fact check
    print(f"  Post-processing statement ID {statement_id}...")
    postprocessed_content = postprocess_fact_check(
        provider=provider,
        deep_research_output=response.output_text,
        claim=statement['content'],
        style_template=style_template,
        demagog_examples=demagog_examples,
        reasoning_effort=reasoning_effort
    )

    # Append the post-processed section
    with open(fact_check_file, 'a', encoding='utf-8') as f:
        f.write("\n---\n")
        f.write("## Post-processed Fact Check Report\n")
        f.write(postprocessed_content)
        f.write("\n")

    print(f"  Post-processed section added")

    # Extract brief report
    brief_file = os.path.join(output_dir, f"brief_fact_check_id{statement_id}.md")
    extract_brief_report(fact_check_file, brief_file)
    print(f"  Brief report extracted")

    return fact_check_file


def main():
    parser = argparse.ArgumentParser(
        description="Fact-check claims from Demagog.cz using AI with web search"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model to use - provider is auto-detected from name (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--reasoning-effort",
        default=DEFAULT_REASONING_EFFORT,
        choices=["low", "medium", "high"],
        help=f"Reasoning effort level (default: {DEFAULT_REASONING_EFFORT})"
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to store results (default: auto-generated based on model and timestamp)"
    )
    parser.add_argument(
        "--auth-token",
        help="Authorization token for the Demagog API (or set DEMAGOG_AUTH_TOKEN env var)"
    )
    parser.add_argument(
        "--statement-ids",
        nargs="+",
        help="Specific statement IDs to process (default: all new statements)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing of statements even if output files exist"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually processing"
    )
    parser.add_argument(
        "--min-id",
        type=int,
        help="Only process statements with ID higher than this value (overrides auto-detection from output dir)"
    )

    args = parser.parse_args()

    # Detect provider from model name
    provider_name = detect_provider(args.model)

    # Set up output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        model_prefix = get_model_prefix(args.model)
        effort_prefix = args.reasoning_effort[0]
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        output_dir = f"outputs/{model_prefix}_{effort_prefix}_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Check if we should read from existing demagog_raw.json
    raw_file = os.path.join(output_dir, "demagog_raw.json")
    if args.output_dir and os.path.exists(raw_file):
        # Read claims from existing file
        print(f"Reading claims from existing {raw_file}...")
        with open(raw_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        statements = data['data']['statements']
        print(f"Loaded {len(statements)} statements from file")
    else:
        # Fetch claims from API
        auth_token = args.auth_token or os.environ.get("DEMAGOG_AUTH_TOKEN")
        print("Fetching claims from Demagog API...")
        statements = fetch_claims(auth_token)
        print(f"Found {len(statements)} statements with transcripts (not approved)")

        # Save raw data
        with open(raw_file, 'w', encoding='utf-8') as f:
            json.dump({"data": {"statements": statements}}, f, indent=4, ensure_ascii=False)
        print(f"Raw data saved to {raw_file}")

    # Get already processed IDs and highest ID (unless force flag is set)
    if args.force:
        processed_ids = set()
        highest_id = None
    else:
        processed_ids, highest_id = get_processed_ids(output_dir)
        if processed_ids:
            print(f"Found {len(processed_ids)} already processed statements (highest ID: {highest_id})")

    # Use --min-id if provided, otherwise use auto-detected highest_id
    if args.min_id is not None:
        highest_id = args.min_id
        print(f"Using manually set minimum ID: {highest_id}")

    # Filter by specific IDs if provided, or by highest ID threshold
    if args.statement_ids:
        # Explicit IDs requested - process those regardless of highest_id threshold
        statements = [s for s in statements if s['id'] in args.statement_ids]
        print(f"Filtered to {len(statements)} statements matching specified IDs")
        # Still skip already processed unless --force
        new_statements = [s for s in statements if s['id'] not in processed_ids]
    else:
        # Default: only process claims with IDs higher than the highest already processed
        if highest_id is not None:
            new_statements = [
                s for s in statements
                if int(s['id']) > highest_id and s['id'] not in processed_ids
            ]
            print(f"Processing only IDs higher than {highest_id}")
        else:
            # No existing files, process all
            new_statements = statements

    print(f"Statements to process: {len(new_statements)}")

    if args.dry_run:
        print("\nDry run - would process the following statements:")
        for s in new_statements:
            print(f"  ID {s['id']}: {s['content'][:80]}...")
        return

    if not new_statements:
        print("No new statements to process.")
        return

    # Initialize provider and load templates
    print(f"\nInitializing {provider_name} provider with model {args.model}...")
    provider = get_provider(args.model)

    print("Loading prompt templates...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    system_template, user_template, style_template = load_prompt_templates()

    # Load style examples
    examples_file = os.path.join(script_dir, "demagog_explanation_examples_petr.txt")
    with open(examples_file, encoding="utf-8") as f:
        demagog_examples = f.read()

    # Process each statement
    for i, statement in enumerate(new_statements, 1):
        print(f"\n{'='*60}")
        print(f"Processing {i}/{len(new_statements)}")
        try:
            process_statement(
                provider=provider,
                statement=statement,
                output_dir=output_dir,
                reasoning_effort=args.reasoning_effort,
                system_template=system_template,
                user_template=user_template,
                style_template=style_template,
                demagog_examples=demagog_examples
            )
        except Exception as e:
            print(f"  ERROR processing statement {statement['id']}: {e}")
            continue

    print(f"\n{'='*60}")
    print(f"Processing complete. Results saved to {output_dir}")


if __name__ == "__main__":
    main()
