"""
Situation Classifier — Detects what kind of issue the customer is facing.

Classifies each conversation into one of three categories:
  - PRODUCT_LOSS: Customer paid but never received the product/service,
    or was charged after cancellation.
  - SUBSTANDARD_SERVICE: Customer got the product/service but it was 
    broken, slow, or didn't meet expectations.
  - OTHER: Everything else — usually ability-to-pay (hardship, job loss, etc.)

Includes confidence scoring and evidence tracking so the classification
is explainable. Every decision can be traced back to specific phrases
in specific messages.
"""

import json
import hashlib
import logging
from typing import List, Tuple

from src.models import SituationResult, SituationEvidence
from src.config import CACHE_ENABLED

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache (same pattern as compliance_checker)
# ---------------------------------------------------------------------------
_cache: dict = {}


def _hash_conversation(conversation: dict) -> str:
    """SHA-256 hash of message content for cache key."""
    content = json.dumps(conversation.get("messages", []), sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Keyword dictionaries — these define what we look for in each category.
#
# Each phrase is something a customer might say. We scan ONLY customer
# messages because the situation is about the customer's experience,
# not what the agent says.
# ---------------------------------------------------------------------------

PRODUCT_LOSS_PHRASES = [
    # Customer never received what they paid for
    "never arrived",
    "never got",
    "never received",
    "didn't receive",
    "did not receive",
    "not delivered",
    # Customer was charged for something they cancelled or didn't use
    "charged after i cancelled",
    "charged after cancellation",
    "charging me after i cancelled",
    "charged and never got",
    "cancelled and i never got",
    "didn't use it",
    "paid for but never",
    # Refund requests due to non-delivery
    "full refund",
    "want a refund",
    "money back",
]

SUBSTANDARD_SERVICE_PHRASES = [
    # Product/service exists but doesn't work properly
    "never worked",
    "didn't work",
    "doesn't work",
    "not working",
    "features never worked",
    "features didn't work",
    # Slow or unreliable service
    "really slow",
    "slow and kept dropping",
    "kept dropping",
    "service was slow",
    "keeps crashing",
    # Poor quality
    "bad service",
    "poor service",
    "substandard",
    "poor quality",
    "not up to standard",
    # Complaints about lack of support
    "complained and got no response",
    "no response",
    "not paying for bad service",
    "support said they'd fix",
]


def _find_evidence(messages: list, phrases: list) -> List[Tuple[str, int, str]]:
    """
    Search messages for matching phrases and return evidence tuples.
    
    Only searches customer messages because we want to know what the
    CUSTOMER experienced, not what the agent said about it.
    
    Returns: List of (matched_phrase, message_index, role) tuples
    """
    evidence = []
    for idx, msg in enumerate(messages):
        msg_lower = msg["text"].lower()
        for phrase in phrases:
            if phrase.lower() in msg_lower:
                evidence.append((phrase, idx, msg["role"]))
    return evidence


def classify_situation(conversation: dict) -> SituationResult:
    """
    Classify the customer's situation based on conversation content.
    
    Logic:
      1. Scan customer messages for product loss phrases → evidence
      2. Scan customer messages for substandard service phrases → evidence
      3. If both match, pick the one with more evidence (stronger signal)
      4. If neither matches, classify as "other"
      5. Assign confidence based on evidence strength
    
    Args:
        conversation: A conversation dict with 'conversation_id' and 'messages'
    
    Returns:
        SituationResult with classification, confidence, and evidence
    """
    conv_id = conversation.get("conversation_id", "unknown")
    messages = conversation.get("messages", [])

    logger.info(f"Classifying situation for {conv_id}")

    # --- Cache check ---
    cache_key = _hash_conversation(conversation)
    if CACHE_ENABLED and cache_key in _cache:
        logger.debug(f"Cache HIT for situation classification {conv_id}")
        return _cache[cache_key]

    # --- Find evidence for each category ---
    product_loss_evidence = _find_evidence(messages, PRODUCT_LOSS_PHRASES)
    substandard_evidence = _find_evidence(messages, SUBSTANDARD_SERVICE_PHRASES)

    # Build evidence objects
    pl_evidence_objs = [
        SituationEvidence(phrase=phrase, message_index=idx, role=role)
        for phrase, idx, role in product_loss_evidence
    ]
    ss_evidence_objs = [
        SituationEvidence(phrase=phrase, message_index=idx, role=role)
        for phrase, idx, role in substandard_evidence
    ]

    # --- Determine classification ---
    has_product_loss = len(product_loss_evidence) > 0
    has_substandard = len(substandard_evidence) > 0

    if has_product_loss and has_substandard:
        # Both signals present — pick the stronger one
        if len(product_loss_evidence) >= len(substandard_evidence):
            classification = "product_loss"
            all_evidence = pl_evidence_objs + ss_evidence_objs
            notes = "Both product loss and substandard service signals detected; product loss is stronger."
        else:
            classification = "substandard_service"
            all_evidence = ss_evidence_objs + pl_evidence_objs
            notes = "Both product loss and substandard service signals detected; substandard service is stronger."
    elif has_product_loss:
        classification = "product_loss"
        all_evidence = pl_evidence_objs
        notes = "Customer experienced product/service loss (e.g. non-delivery, charged after cancellation)."
    elif has_substandard:
        classification = "substandard_service"
        all_evidence = ss_evidence_objs
        notes = "Customer received substandard service (e.g. broken features, slow performance)."
    else:
        classification = "other"
        all_evidence = []
        notes = "No product loss or substandard service signals. Likely ability-to-pay or general hardship."

    # --- Assign confidence ---
    total_evidence = len(product_loss_evidence) + len(substandard_evidence)
    if total_evidence == 0:
        # "Other" is a default fallback — not super confident about it
        confidence = "medium"
    elif total_evidence >= 3:
        confidence = "high"
    elif total_evidence >= 1:
        confidence = "medium" if (has_product_loss and has_substandard) else "high"
    else:
        confidence = "low"

    result = SituationResult(
        conversation_id=conv_id,
        classification=classification,
        has_product_loss=has_product_loss,
        has_substandard_service=has_substandard,
        situation_other=not (has_product_loss or has_substandard),
        confidence=confidence,
        evidence=all_evidence,
        notes=notes,
    )

    # --- Cache the result ---
    if CACHE_ENABLED:
        _cache[cache_key] = result

    logger.info(f"{conv_id}: classified as '{classification}' (confidence: {confidence})")
    return result


def classify_all_conversations(conversations: list) -> List[SituationResult]:
    """
    Classify situations for a batch of conversations.
    
    Returns a list of SituationResult objects, one per conversation.
    """
    logger.info(f"Starting situation classification on {len(conversations)} conversations")
    results = []
    for conv in conversations:
        result = classify_situation(conv)
        results.append(result)

    # Log summary
    counts = {}
    for r in results:
        counts[r.classification] = counts.get(r.classification, 0) + 1
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    logger.info(f"Situation classification complete: {summary}")

    return results
