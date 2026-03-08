#!/usr/bin/env python3
"""
Compliance Assessment Pipeline — Main Entrypoint

Runs the full pipeline: loads data, checks compliance, classifies situations,
and optionally evaluates against ground truth.

Usage:
    # Basic run — compliance check + situation classification
    python src/run_assessment.py

    # Run with evaluation against ground truth
    python src/run_assessment.py --eval

    # Output structured JSON to output/
    python src/run_assessment.py --json

    # Check a specific conversation
    python src/run_assessment.py --conversation conv_003

    # Combine flags
    python src/run_assessment.py --eval --json --conversation conv_003

    # Enable LLM layer (requires OPENAI_API_KEY)
    OPENAI_API_KEY="sk-..." python src/run_assessment.py --llm
"""

import argparse
import json
import sys
import logging
from pathlib import Path

# Make sure we can import from src/ when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import setup_logging, DATA_DIR, OUTPUT_DIR, LLM_ENABLED
from src.compliance_checker import load_compliance_rules, check_compliance, check_all_conversations
from src.situation_classifier import classify_situation, classify_all_conversations
from src.evaluator import run_evaluation, print_eval_report
from src.llm_compliance import check_compliance_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ANSI color codes for terminal output
# ---------------------------------------------------------------------------
class Colors:
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


SEVERITY_COLORS = {
    "critical": Colors.RED + Colors.BOLD,
    "high": Colors.RED,
    "medium": Colors.YELLOW,
    "low": Colors.DIM,
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_conversations():
    """Load conversation data from the JSON file."""
    path = DATA_DIR / "conversations.json"
    if not path.exists():
        raise FileNotFoundError(f"Expected conversations at {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} conversations from {path}")
    return data


def filter_conversations(conversations, conv_id=None):
    """Optionally filter to a single conversation by ID."""
    if conv_id is None:
        return conversations
    filtered = [c for c in conversations if c["conversation_id"] == conv_id]
    if not filtered:
        logger.error(f"Conversation '{conv_id}' not found in data")
        print(f"Error: conversation '{conv_id}' not found. Available IDs:")
        for c in conversations:
            print(f"  - {c['conversation_id']}")
        sys.exit(1)
    return filtered


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def print_compliance_results(results):
    """Print compliance results with color-coded severity."""
    print(f"\n{Colors.BOLD}{'=' * 60}")
    print("  COMPLIANCE CHECK RESULTS")
    print(f"{'=' * 60}{Colors.RESET}\n")

    for result in results:
        conv_id = result.conversation_id
        if result.is_compliant:
            status = f"{Colors.GREEN}✓ COMPLIANT{Colors.RESET}"
            print(f"  {Colors.BOLD}{conv_id}{Colors.RESET}: {status}")
        else:
            status = f"{Colors.RED}✗ NON-COMPLIANT{Colors.RESET}"
            score_text = f"{Colors.DIM}(score: {result.compliance_score}){Colors.RESET}"
            print(f"  {Colors.BOLD}{conv_id}{Colors.RESET}: {status} {score_text}")
            for v in result.violations:
                color = SEVERITY_COLORS.get(v.severity, "")
                print(
                    f"    {color}[{v.severity.upper()}]{Colors.RESET} "
                    f"{v.rule_id} ({v.category}): "
                    f"matched '{v.matched_keyword}'"
                )
                if v.message_index >= 0:
                    print(f"    {Colors.DIM}  └─ message[{v.message_index}]: \"{v.message_snippet}...\"{Colors.RESET}")
        print()


def print_situation_results(results):
    """Print situation classification results with evidence."""
    print(f"\n{Colors.BOLD}{'=' * 60}")
    print("  CUSTOMER SITUATION CLASSIFICATION")
    print(f"{'=' * 60}{Colors.RESET}\n")

    category_colors = {
        "product_loss": Colors.RED,
        "substandard_service": Colors.YELLOW,
        "other": Colors.BLUE,
    }

    for result in results:
        color = category_colors.get(result.classification, "")
        confidence_text = f"{Colors.DIM}(confidence: {result.confidence}){Colors.RESET}"
        print(
            f"  {Colors.BOLD}{result.conversation_id}{Colors.RESET}: "
            f"{color}{result.classification}{Colors.RESET} {confidence_text}"
        )
        if result.evidence:
            for ev in result.evidence[:3]:  # Show top 3 evidence items
                print(f"    {Colors.DIM}└─ \"{ev.phrase}\" (msg[{ev.message_index}], {ev.role}){Colors.RESET}")
        if result.notes:
            print(f"    {Colors.CYAN}Note: {result.notes}{Colors.RESET}")
        print()


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def export_json(compliance_results, situation_results, eval_report=None):
    """Export structured results to JSON files in output/."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Compliance results
    compliance_path = OUTPUT_DIR / "compliance_results.json"
    with open(compliance_path, "w", encoding="utf-8") as f:
        json.dump(
            [r.to_dict() for r in compliance_results],
            f, indent=2, ensure_ascii=False,
        )
    logger.info(f"Compliance results written to {compliance_path}")

    # Situation results
    situation_path = OUTPUT_DIR / "situation_results.json"
    with open(situation_path, "w", encoding="utf-8") as f:
        json.dump(
            [r.to_dict() for r in situation_results],
            f, indent=2, ensure_ascii=False,
        )
    logger.info(f"Situation results written to {situation_path}")

    # Eval report (if available)
    if eval_report:
        eval_path = OUTPUT_DIR / "eval_report.json"
        with open(eval_path, "w", encoding="utf-8") as f:
            json.dump(eval_report.to_dict(), f, indent=2)
        logger.info(f"Eval report written to {eval_path}")

    print(f"\n{Colors.GREEN}✓ JSON results exported to {OUTPUT_DIR}{Colors.RESET}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compliance Assessment Pipeline — checks conversations for rule violations and classifies customer situations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--eval", action="store_true",
        help="Run evaluation against ground truth and report metrics",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Export structured JSON results to output/",
    )
    parser.add_argument(
        "--conversation", type=str, default=None,
        help="Check a specific conversation by ID (e.g. conv_003)",
    )
    parser.add_argument(
        "--llm", action="store_true",
        help="Enable LLM-based compliance checks (requires OPENAI_API_KEY)",
    )
    args = parser.parse_args()

    # --- Setup ---
    setup_logging()
    logger.info("Starting Compliance Assessment Pipeline")

    # --- Load data ---
    try:
        conversations = load_conversations()
        rules_data = load_compliance_rules()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    conversations = filter_conversations(conversations, args.conversation)

    # --- Check LLM availability ---
    if args.llm and not LLM_ENABLED:
        print(
            f"{Colors.YELLOW}Warning: --llm flag set but OPENAI_API_KEY not found. "
            f"Falling back to rule-based only.{Colors.RESET}"
        )

    # --- Run compliance checks ---
    compliance_results = check_all_conversations(conversations, rules_data)

    # Optionally run LLM layer and merge results
    if args.llm and LLM_ENABLED:
        logger.info("Running LLM compliance layer (Tier 2)")
        for i, conv in enumerate(conversations):
            llm_violations = check_compliance_llm(conv, rules_data)
            if llm_violations:
                # Merge LLM findings with rule-based findings, avoiding duplicates
                existing_rules = {v.rule_id for v in compliance_results[i].violations}
                for v in llm_violations:
                    if v.rule_id not in existing_rules:
                        compliance_results[i].violations.append(v)
                        compliance_results[i].is_compliant = False

    # --- Run situation classification ---
    situation_results = classify_all_conversations(conversations)

    # --- Print results ---
    print_compliance_results(compliance_results)
    print_situation_results(situation_results)

    # --- Run evaluation if requested ---
    eval_report = None
    if args.eval:
        eval_report = run_evaluation(compliance_results, situation_results)
        print_eval_report(eval_report)

    # --- Export JSON if requested ---
    if args.json:
        export_json(compliance_results, situation_results, eval_report)

    # --- Summary ---
    total = len(compliance_results)
    compliant = sum(1 for r in compliance_results if r.is_compliant)
    print(f"\n{Colors.BOLD}Summary:{Colors.RESET} {compliant}/{total} conversations are compliant.")
    if compliant < total:
        print(f"{Colors.RED}⚠ {total - compliant} conversation(s) have compliance violations.{Colors.RESET}")

    logger.info("Pipeline complete")
    print(f"\n{Colors.GREEN}Done.{Colors.RESET}")


if __name__ == "__main__":
    main()
