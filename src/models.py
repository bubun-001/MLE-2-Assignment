"""
Data models for the compliance assessment pipeline.

These dataclasses define the shape of data flowing through the system —
from raw conversations to compliance results and situation classifications.
They serve as our "contracts" so every module speaks the same language.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Enums — keep severity and categories type-safe instead of raw strings
# ---------------------------------------------------------------------------

class Severity(Enum):
    """How serious a compliance violation is. Maps to weighted scores."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def weight(self) -> int:
        """Numeric weight for scoring — critical violations matter 10x more than low ones."""
        return {
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 5,
            Severity.CRITICAL: 10,
        }[self]


class SituationCategory(Enum):
    """What kind of situation the customer is in."""
    PRODUCT_LOSS = "product_loss"
    SUBSTANDARD_SERVICE = "substandard_service"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Compliance models
# ---------------------------------------------------------------------------

@dataclass
class ComplianceViolation:
    """A single rule violation found in a specific message."""
    rule_id: str
    category: str
    severity: str
    description: str
    matched_keyword: str
    message_index: int          # Which message in the conversation (0-indexed)
    message_role: str           # "agent" or "customer"
    message_snippet: str        # First 120 chars of the offending message for context

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "matched_keyword": self.matched_keyword,
            "message_index": self.message_index,
            "message_role": self.message_role,
            "message_snippet": self.message_snippet,
        }


@dataclass
class ComplianceResult:
    """
    Full compliance check result for one conversation.
    
    Contains all violations found, a weighted score, and a pass/fail verdict.
    A conversation is "compliant" only if it has zero violations.
    """
    conversation_id: str
    is_compliant: bool
    violations: List[ComplianceViolation] = field(default_factory=list)
    compliance_score: int = 0       # Sum of severity weights — lower is better, 0 = perfect
    checked_rules: int = 0          # How many rules were evaluated
    messages_checked: int = 0       # How many messages were scanned

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "is_compliant": self.is_compliant,
            "compliance_score": self.compliance_score,
            "checked_rules": self.checked_rules,
            "messages_checked": self.messages_checked,
            "violation_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations],
        }


# ---------------------------------------------------------------------------
# Situation classification models
# ---------------------------------------------------------------------------

@dataclass
class SituationEvidence:
    """A piece of evidence supporting a situation classification."""
    phrase: str                 # The phrase that matched
    message_index: int          # Which message it came from
    role: str                   # Who said it — usually "customer"

    def to_dict(self) -> dict:
        return {
            "phrase": self.phrase,
            "message_index": self.message_index,
            "role": self.role,
        }


@dataclass
class SituationResult:
    """
    Customer situation classification for one conversation.
    
    Tells us whether the customer experienced an actual product/service loss,
    received substandard service, or has a different issue (e.g. hardship).
    """
    conversation_id: str
    classification: str             # "product_loss", "substandard_service", or "other"
    has_product_loss: bool
    has_substandard_service: bool
    situation_other: bool
    confidence: str                 # "high", "medium", or "low"
    evidence: List[SituationEvidence] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "classification": self.classification,
            "has_product_loss": self.has_product_loss,
            "has_substandard_service": self.has_substandard_service,
            "situation_other": self.situation_other,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Evaluation models
# ---------------------------------------------------------------------------

@dataclass
class EvalMetrics:
    """Precision / Recall / F1 for compliance detection."""
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int

    def to_dict(self) -> dict:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


@dataclass
class EvalReport:
    """Full evaluation report combining compliance and situation metrics."""
    compliance_metrics: EvalMetrics
    situation_accuracy: float
    situation_correct: int
    situation_total: int
    confusion_matrix: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "compliance": self.compliance_metrics.to_dict(),
            "situation": {
                "accuracy": round(self.situation_accuracy, 4),
                "correct": self.situation_correct,
                "total": self.situation_total,
                "confusion_matrix": self.confusion_matrix,
            },
        }
