"""
Compliance Checker — Rule-based engine for detecting FDCPA violations.

This is the heart of the compliance tool. It scans each agent message
against the compliance rules in data/compliance_rules.json and reports:
  - WHICH rule was violated
  - WHICH specific message triggered it
  - WHAT keyword matched
  - HOW severe it is

Design notes:
  - Rules R001–R005 are "negative" rules: violation = agent SAID something forbidden.
  - Rule R006 is "positive" (inverted): violation = agent FAILED TO acknowledge 
    customer hardship or product issues when they should have.
  - Results are cached by conversation content hash to avoid redundant work.
"""

import json
import hashlib
import logging
import re
from typing import List, Dict, Any, Optional

from src.models import ComplianceViolation, ComplianceResult, Severity
from src.config import DATA_DIR, CACHE_ENABLED, CACHE_MAX_SIZE, SEVERITY_WEIGHTS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache: conversation content hash → ComplianceResult
# Avoids re-checking the same conversation if it comes through again.
# ---------------------------------------------------------------------------
_cache: Dict[str, ComplianceResult] = {}


def _hash_conversation(conversation: dict) -> str:
    """
    Generate a SHA-256 hash of the conversation messages.
    
    We hash only the message content (not metadata like channel or segment)
    because compliance violations depend solely on what was said.
    """
    content = json.dumps(conversation.get("messages", []), sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Optional[ComplianceResult]:
    """Look up a cached result. Returns None on cache miss."""
    if not CACHE_ENABLED:
        return None
    result = _cache.get(key)
    if result:
        logger.debug(f"Cache HIT for conversation hash {key[:12]}...")
    return result


def _cache_put(key: str, result: ComplianceResult) -> None:
    """Store a result in the cache. Evicts oldest entries if full."""
    if not CACHE_ENABLED:
        return
    # Simple eviction: if we hit max size, clear the oldest half
    if len(_cache) >= CACHE_MAX_SIZE:
        logger.info(f"Cache full ({CACHE_MAX_SIZE} entries), evicting oldest half")
        keys_to_remove = list(_cache.keys())[: CACHE_MAX_SIZE // 2]
        for k in keys_to_remove:
            del _cache[k]
    _cache[key] = result
    logger.debug(f"Cached result for conversation hash {key[:12]}...")


# ---------------------------------------------------------------------------
# Customer hardship detection — used for R006 (inverted rule)
# ---------------------------------------------------------------------------

# Phrases that signal a customer is experiencing hardship or product issues.
# If ANY of these appear in customer messages, we expect the agent to respond
# with acknowledgment (R006 keywords).
CUSTOMER_HARDSHIP_PHRASES = [
    "lost my job", "lost job", "unemployed",
    "sick", "ill", "hospital", "medical",
    "divorce", "separated",
    "can't work", "couldn't work", "unable to work",
    "hardship", "struggling", "difficult time",
    "never arrived", "never got", "never received",
    "charged after", "cancelled", "didn't work",
    "bad service", "slow", "dropping", "not working",
    "no response", "complained",
]


def _customer_mentions_hardship(messages: list) -> bool:
    """Check if the customer has raised any hardship or product/service issue."""
    customer_text = " ".join(
        m["text"] for m in messages if m["role"] == "customer"
    ).lower()
    return any(phrase in customer_text for phrase in CUSTOMER_HARDSHIP_PHRASES)


# Additional acknowledgment phrases beyond what's in R006 keywords.
# These capture common ways agents show empathy that the rule keywords
# might not cover exactly (e.g. "I'm sorry" vs "I'm sorry to hear").
AGENT_ACKNOWLEDGMENT_EXTRAS = [
    "sorry", "apologize", "apologies",
    "understand your", "appreciate your patience",
    "look into", "investigate", "resolve",
    "credit", "waive", "refund",
]


def _agent_acknowledges(messages: list, r006_keywords: list) -> bool:
    """Check if the agent used any acknowledgment phrases from R006 or common variations."""
    agent_text = " ".join(
        m["text"] for m in messages if m["role"] == "agent"
    ).lower()
    # Check official R006 keywords first
    if any(kw.lower() in agent_text for kw in r006_keywords):
        return True
    # Also check common empathy/acknowledgment phrases
    return any(phrase in agent_text for phrase in AGENT_ACKNOWLEDGMENT_EXTRAS)


# ---------------------------------------------------------------------------
# Core compliance checking logic
# ---------------------------------------------------------------------------

def load_compliance_rules() -> dict:
    """Load compliance rules from the JSON file."""
    path = DATA_DIR / "compliance_rules.json"
    if not path.exists():
        raise FileNotFoundError(f"Compliance rules not found at {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data.get('rules', []))} compliance rules (version: {data.get('version', 'unknown')})")
    return data


def check_compliance(conversation: dict, rules_data: dict) -> ComplianceResult:
    """
    Check a single conversation for compliance rule violations.
    
    This is the main function. It:
      1. Checks the cache first (skip work if we've seen this exact conversation)
      2. Scans each agent message against rules R001–R005 (keyword matching)
      3. Handles R006 separately (inverted logic — checks for ABSENCE of acknowledgment)
      4. Computes a weighted compliance score
      5. Caches and returns the result
    
    Args:
        conversation: A conversation dict with 'conversation_id' and 'messages'
        rules_data: The full compliance rules dict from compliance_rules.json
    
    Returns:
        ComplianceResult with all violations, score, and pass/fail verdict
    """
    conv_id = conversation.get("conversation_id", "unknown")
    messages = conversation.get("messages", [])
    rules = rules_data.get("rules", [])

    logger.info(f"Checking compliance for {conv_id} ({len(messages)} messages, {len(rules)} rules)")

    # --- Cache check ---
    cache_key = _hash_conversation(conversation)
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info(f"Returning cached result for {conv_id}")
        return cached

    violations: List[ComplianceViolation] = []
    agent_messages_count = 0

    # --- Check each agent message against negative rules (R001–R005) ---
    for msg_idx, message in enumerate(messages):
        if message["role"] != "agent":
            continue  # We only check agent messages for compliance violations
        agent_messages_count += 1

        msg_text_lower = message["text"].lower()
        msg_snippet = message["text"][:120]  # First 120 chars for context

        for rule in rules:
            # Skip R006 here — we handle it separately below
            if rule["id"] == "R006":
                continue

            keywords = rule.get("keywords") or []
            regex_hint = rule.get("regex_hint")

            # Check keywords — use word-boundary matching for short keywords
            # to avoid false positives (e.g. "sue" matching inside "issue")
            for kw in keywords:
                kw_lower = kw.lower()
                if len(kw_lower.split()) == 1 and len(kw_lower) <= 5:
                    # Short single word — use regex word boundary to avoid
                    # partial matches like "issue" matching "sue"
                    pattern = r'\b' + re.escape(kw_lower) + r'\b'
                    matched = bool(re.search(pattern, msg_text_lower))
                else:
                    # Multi-word phrase — simple substring match is fine
                    matched = kw_lower in msg_text_lower

                if matched:
                    violation = ComplianceViolation(
                        rule_id=rule["id"],
                        category=rule["category"],
                        severity=rule["severity"],
                        description=rule["description"],
                        matched_keyword=kw,
                        message_index=msg_idx,
                        message_role="agent",
                        message_snippet=msg_snippet,
                    )
                    violations.append(violation)
                    logger.warning(
                        f"VIOLATION in {conv_id} msg[{msg_idx}]: "
                        f"{rule['id']} ({rule['severity']}) — matched '{kw}'"
                    )

            # Check regex if provided
            if regex_hint:
                try:
                    if re.search(regex_hint, message["text"], re.IGNORECASE):
                        violation = ComplianceViolation(
                            rule_id=rule["id"],
                            category=rule["category"],
                            severity=rule["severity"],
                            description=rule["description"],
                            matched_keyword=f"regex:{regex_hint}",
                            message_index=msg_idx,
                            message_role="agent",
                            message_snippet=msg_snippet,
                        )
                        violations.append(violation)
                        logger.warning(
                            f"VIOLATION in {conv_id} msg[{msg_idx}]: "
                            f"{rule['id']} ({rule['severity']}) — matched regex"
                        )
                except re.error as e:
                    logger.error(f"Invalid regex '{regex_hint}' in rule {rule['id']}: {e}")

    # --- R006: Check for ABSENCE of acknowledgment when customer raises issues ---
    r006 = next((r for r in rules if r["id"] == "R006"), None)
    if r006:
        customer_raised_issue = _customer_mentions_hardship(messages)
        if customer_raised_issue:
            agent_acknowledged = _agent_acknowledges(messages, r006.get("keywords", []))
            if not agent_acknowledged:
                # Agent didn't acknowledge — this is a violation
                violation = ComplianceViolation(
                    rule_id="R006",
                    category=r006["category"],
                    severity=r006["severity"],
                    description=r006["description"],
                    matched_keyword="(absence of acknowledgment)",
                    message_index=-1,  # Conversation-level, not specific message
                    message_role="agent",
                    message_snippet="Agent failed to acknowledge customer hardship/issues",
                )
                violations.append(violation)
                logger.warning(
                    f"VIOLATION in {conv_id}: R006 — customer raised issues "
                    f"but agent did not acknowledge"
                )
            else:
                logger.debug(f"{conv_id}: R006 OK — agent acknowledged customer issues")

    # --- Compute compliance score ---
    score = sum(SEVERITY_WEIGHTS.get(v.severity, 0) for v in violations)

    result = ComplianceResult(
        conversation_id=conv_id,
        is_compliant=len(violations) == 0,
        violations=violations,
        compliance_score=score,
        checked_rules=len(rules),
        messages_checked=agent_messages_count,
    )

    # --- Cache the result ---
    _cache_put(cache_key, result)

    if result.is_compliant:
        logger.info(f"{conv_id}: COMPLIANT (score: {score})")
    else:
        logger.info(f"{conv_id}: NON-COMPLIANT — {len(violations)} violation(s), score: {score}")

    return result


def check_all_conversations(conversations: list, rules_data: dict) -> List[ComplianceResult]:
    """
    Run compliance checks on a list of conversations.
    
    This is the batch entrypoint — processes all conversations and
    returns a list of results. Useful for running against the full dataset.
    """
    logger.info(f"Starting compliance check on {len(conversations)} conversations")
    results = []
    for conv in conversations:
        result = check_compliance(conv, rules_data)
        results.append(result)

    # Log summary stats
    compliant = sum(1 for r in results if r.is_compliant)
    non_compliant = len(results) - compliant
    total_violations = sum(len(r.violations) for r in results)
    logger.info(
        f"Compliance check complete: {compliant}/{len(results)} compliant, "
        f"{non_compliant} non-compliant, {total_violations} total violations"
    )
    return results
