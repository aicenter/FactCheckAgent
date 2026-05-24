#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


MODEL_PRICING = {
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00, "web_search": 0.01},
}
DEFAULT_PRICING = {"input": 2.50, "cached_input": 0.25, "output": 15.00, "web_search": 0.01}


def step_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"step(\d+)_", path.name)
    if match:
        return int(match.group(1)), path.name
    return 999, path.name


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recompute_summary(summary_path: Path, dry_run: bool) -> tuple[bool, str]:
    work_dir = summary_path.parent
    step_logs = sorted(work_dir.glob("step*_log.json"), key=step_sort_key)
    if not step_logs:
        return False, "no_step_logs"

    summary = load_json(summary_path)
    steps = [load_json(path) for path in step_logs]
    last = steps[-1]

    input_tokens = int(last.get("input_tokens", 0) or 0)
    cached_tokens = int(last.get("cached_input_tokens", 0) or 0)
    output_tokens = int(last.get("output_tokens", 0) or 0)
    non_cached_input = max(0, input_tokens - cached_tokens)

    observed_web_searches = int(sum(int(step.get("web_searches", 0) or 0) for step in steps))
    observed_cumulative_step_output_tokens = int(
        sum(int(step.get("output_tokens", 0) or 0) for step in steps)
    )

    model = summary.get("model", "")
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    input_cost = non_cached_input * pricing["input"] / 1_000_000
    cached_input_cost = cached_tokens * pricing["cached_input"] / 1_000_000
    output_cost = output_tokens * pricing["output"] / 1_000_000
    web_search_cost = observed_web_searches * pricing["web_search"]
    total_cost = input_cost + cached_input_cost + output_cost + web_search_cost

    summary["usage_estimate_basis"] = "final_turn_cumulative_usage"
    summary["estimated_input_tokens"] = input_tokens
    summary["estimated_cached_input_tokens"] = cached_tokens
    summary["estimated_non_cached_input_tokens"] = non_cached_input
    summary["estimated_output_tokens"] = output_tokens
    summary["observed_web_searches"] = observed_web_searches
    summary["observed_cumulative_step_output_tokens"] = observed_cumulative_step_output_tokens
    summary["estimated_input_cost_usd"] = round(input_cost, 6)
    summary["estimated_cached_input_cost_usd"] = round(cached_input_cost, 6)
    summary["estimated_output_cost_usd"] = round(output_cost, 6)
    summary["estimated_web_search_cost_usd"] = round(web_search_cost, 6)
    summary["estimated_cost_usd"] = round(total_cost, 6)

    # Backwards-compatible fields used by older runs.
    summary["context_input_tokens"] = input_tokens
    summary["context_cached_input_tokens"] = cached_tokens
    summary["total_output_tokens"] = output_tokens
    summary["total_web_searches"] = observed_web_searches

    if not dry_run:
        save_json(summary_path, summary)
    return True, "updated"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recompute fact_check_v2 summary token/cost fields from cumulative step logs."
    )
    parser.add_argument(
        "--experiments-root",
        default="fact_check_v2/experiments",
        help="Root directory containing v2 experiment folders.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be updated.",
    )
    args = parser.parse_args()

    root = Path(args.experiments_root)
    summary_paths = sorted(root.glob("v2_*/id*/work/summary.json"))

    updated = 0
    skipped_no_steps = 0
    for summary_path in summary_paths:
        ok, reason = recompute_summary(summary_path, dry_run=args.dry_run)
        if ok:
            updated += 1
        elif reason == "no_step_logs":
            skipped_no_steps += 1

    mode = "DRY RUN" if args.dry_run else "UPDATED"
    print(f"{mode}: {updated} summary files")
    if skipped_no_steps:
        print(f"SKIPPED (no step logs): {skipped_no_steps}")


if __name__ == "__main__":
    main()
