"""
Evaluation Pipeline — Measures how well our compliance checker and
situation classifier perform against ground truth labels.

This is how we know the system is actually WORKING, not just running.
We compare predicted results against hand-labeled ground truth
(data/ground_truth.json) and compute standard ML metrics.

Metrics computed:
  - Compliance: Precision, Recall, F1 (per-rule and aggregate)
  - Situation: Accuracy + Confusion Matrix

Run via: python src/run_assessment.py --eval
"""

import json
import logging
from typing import List, Dict
from collections import defaultdict

from src.models import ComplianceResult, SituationResult, EvalMetrics, EvalReport
from src.config import DATA_DIR

logger = logging.getLogger(__name__)


def load_ground_truth() -> dict:
    """Load hand-labeled ground truth from data/ground_truth.json."""
    path = DATA_DIR / "ground_truth.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Ground truth file not found at {path}. "
            f"Create it to enable evaluation."
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logger.info(
        f"Loaded ground truth: {len(data.get('compliance', {}))} compliance labels, "
        f"{len(data.get('situation', {}))} situation labels"
    )
    return data


# ---------------------------------------------------------------------------
# Compliance evaluation
# ---------------------------------------------------------------------------

def evaluate_compliance(
    results: List[ComplianceResult],
    ground_truth: dict,
) -> EvalMetrics:
    """
    Evaluate compliance checker against ground truth.
    
    We compute metrics at the RULE level:
      - True Positive: We flagged a rule that IS in the expected violations.
      - False Positive: We flagged a rule that is NOT in expected violations.
      - False Negative: We missed a rule that IS in expected violations.
    
    This tells us:
      - Precision: "When we flag something, are we right?"
      - Recall: "Are we catching everything we should?"
      - F1: Balance of both.
    """
    gt_compliance = ground_truth.get("compliance", {})
    
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for result in results:
        conv_id = result.conversation_id
        if conv_id not in gt_compliance:
            logger.warning(f"No ground truth for {conv_id}, skipping eval")
            continue

        expected = gt_compliance[conv_id]
        expected_violations = set(expected.get("expected_violations", []))
        predicted_violations = set(v.rule_id for v in result.violations)

        # Count TP, FP, FN for this conversation
        tp = expected_violations & predicted_violations
        fp = predicted_violations - expected_violations
        fn = expected_violations - predicted_violations

        true_positives += len(tp)
        false_positives += len(fp)
        false_negatives += len(fn)

        # Log details for each conversation
        if tp:
            logger.debug(f"{conv_id}: Correctly flagged: {tp}")
        if fp:
            logger.warning(f"{conv_id}: False positives (over-flagged): {fp}")
        if fn:
            logger.warning(f"{conv_id}: False negatives (missed): {fn}")
        if not (tp or fp or fn):
            logger.debug(f"{conv_id}: Correctly identified as clean")

    # Compute metrics (handle division by zero)
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 1.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    metrics = EvalMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )

    logger.info(
        f"Compliance eval: P={precision:.2f} R={recall:.2f} F1={f1:.2f} "
        f"(TP={true_positives}, FP={false_positives}, FN={false_negatives})"
    )
    return metrics


# ---------------------------------------------------------------------------
# Situation classification evaluation
# ---------------------------------------------------------------------------

def evaluate_situation(
    results: List[SituationResult],
    ground_truth: dict,
) -> tuple:
    """
    Evaluate situation classifier against ground truth.
    
    Computes:
      - Overall accuracy (correct / total)
      - Confusion matrix (3x3: product_loss, substandard_service, other)
    
    Returns: (accuracy, correct_count, total_count, confusion_matrix_dict)
    """
    gt_situation = ground_truth.get("situation", {})
    
    correct = 0
    total = 0
    categories = ["product_loss", "substandard_service", "other"]
    confusion = defaultdict(lambda: defaultdict(int))

    for result in results:
        conv_id = result.conversation_id
        if conv_id not in gt_situation:
            logger.warning(f"No situation ground truth for {conv_id}, skipping")
            continue

        expected_class = gt_situation[conv_id].get("classification", "other")
        predicted_class = result.classification
        total += 1

        # Update confusion matrix
        confusion[expected_class][predicted_class] += 1

        if predicted_class == expected_class:
            correct += 1
            logger.debug(f"{conv_id}: Correct — '{predicted_class}'")
        else:
            logger.warning(
                f"{conv_id}: WRONG — predicted '{predicted_class}', "
                f"expected '{expected_class}'"
            )

    accuracy = correct / total if total > 0 else 0.0

    # Convert confusion matrix to a regular dict for JSON serialization
    confusion_dict = {
        actual: {pred: confusion[actual][pred] for pred in categories}
        for actual in categories
    }

    logger.info(f"Situation eval: Accuracy={correct}/{total} ({accuracy:.0%})")
    return accuracy, correct, total, confusion_dict


# ---------------------------------------------------------------------------
# Full evaluation pipeline
# ---------------------------------------------------------------------------

def run_evaluation(
    compliance_results: List[ComplianceResult],
    situation_results: List[SituationResult],
) -> EvalReport:
    """
    Run the complete evaluation pipeline and produce a report.
    
    This is the main entrypoint for evaluation. It loads ground truth,
    runs both evaluations, and packages everything into an EvalReport.
    """
    logger.info("=" * 60)
    logger.info("STARTING EVALUATION PIPELINE")
    logger.info("=" * 60)

    ground_truth = load_ground_truth()

    # Evaluate compliance
    compliance_metrics = evaluate_compliance(compliance_results, ground_truth)

    # Evaluate situation classification
    accuracy, correct, total, confusion = evaluate_situation(
        situation_results, ground_truth
    )

    report = EvalReport(
        compliance_metrics=compliance_metrics,
        situation_accuracy=accuracy,
        situation_correct=correct,
        situation_total=total,
        confusion_matrix=confusion,
    )

    logger.info("=" * 60)
    logger.info("EVALUATION COMPLETE")
    logger.info("=" * 60)

    return report


def print_eval_report(report: EvalReport) -> None:
    """Pretty-print the evaluation report to stdout."""
    c = report.compliance_metrics

    print("\n" + "=" * 60)
    print("  EVALUATION REPORT")
    print("=" * 60)

    print("\n--- Compliance Detection ---\n")
    print(f"  Precision : {c.precision:.4f}")
    print(f"  Recall    : {c.recall:.4f}")
    print(f"  F1 Score  : {c.f1:.4f}")
    print(f"  TP={c.true_positives}  FP={c.false_positives}  FN={c.false_negatives}")

    print(f"\n--- Situation Classification ---\n")
    print(f"  Accuracy  : {report.situation_correct}/{report.situation_total} ({report.situation_accuracy:.0%})")

    # Print confusion matrix
    categories = ["product_loss", "substandard_service", "other"]
    abbr = {"product_loss": "PL", "substandard_service": "SS", "other": "OT"}

    print(f"\n  Confusion Matrix:")
    print(f"  {'':>18} {'Predicted':^24}")
    header = "  " + f"{'':>18}" + "".join(f"{abbr[c]:>8}" for c in categories)
    print(header)
    for actual in categories:
        row = f"  {'Actual ' + abbr[actual]:>18}"
        for pred in categories:
            val = report.confusion_matrix.get(actual, {}).get(pred, 0)
            row += f"{val:>8}"
        print(row)

    print("\n" + "=" * 60)
