"""
LLM Compliance Layer — Optional, zero-cost by default.

This module provides LLM-based compliance checking as a TIER 2 escalation.
It is designed to catch nuanced violations that keyword matching misses
(e.g. passive-aggressive tone, implicit threats, gaslighting).

HOW IT WORKS:
  - Only runs if OPENAI_API_KEY (or equivalent) is set in the environment.
  - If no API key → gracefully returns None and the system uses rule-based only.
  - In production, you'd only invoke this for "borderline" conversations 
    (ones the rule-based engine can't confidently classify).

COST:
  - $0 by default (no API key = no API calls).
  - With GPT-4o-mini: ~$0.0003 per conversation (~150 input tokens + 200 output).
  - At 1,000 convs/day: ~$0.30/day.

To enable: export OPENAI_API_KEY="sk-..."
"""

import json
import logging
from typing import Optional, List

from src.models import ComplianceViolation
from src.config import LLM_ENABLED, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

logger = logging.getLogger(__name__)


# The prompt template lives in prompts/compliance_check.md,
# but we embed it here for programmatic use.
COMPLIANCE_PROMPT_TEMPLATE = """You are a compliance auditor for a consumer finance collections team.
Your job is to review agent messages in a customer-agent conversation and detect
violations of FDCPA (Fair Debt Collection Practices Act) and internal compliance rules.

RULES:
{rules_text}

CONVERSATION:
{conversation_text}

TASK:
Analyze ONLY the agent's messages. For each violation found, report:
- rule_id: which rule was violated
- severity: the rule's severity level
- matched_text: the exact text that violates the rule  
- explanation: why this is a violation

If no violations are found, return an empty list.

Respond ONLY with valid JSON in this format:
{{"violations": [{{"rule_id": "R001", "severity": "critical", "matched_text": "...", "explanation": "..."}}]}}
"""


def _format_rules(rules_data: dict) -> str:
    """Format compliance rules as text for the prompt."""
    lines = []
    for rule in rules_data.get("rules", []):
        lines.append(
            f"- {rule['id']} [{rule['severity']}] ({rule['category']}): "
            f"{rule['description']}"
        )
    return "\n".join(lines)


def _format_conversation(conversation: dict) -> str:
    """Format conversation messages as readable text for the prompt."""
    lines = []
    for msg in conversation.get("messages", []):
        role = msg["role"].upper()
        lines.append(f"{role}: {msg['text']}")
    return "\n".join(lines)


def check_compliance_llm(
    conversation: dict,
    rules_data: dict,
) -> Optional[List[ComplianceViolation]]:
    """
    Run LLM-based compliance check on a single conversation.
    
    Returns:
        - List of ComplianceViolation objects if LLM is enabled and succeeds
        - None if LLM is not enabled (no API key) or if the call fails
    
    The caller should fall back to rule-based results when this returns None.
    """
    if not LLM_ENABLED:
        logger.debug("LLM compliance check skipped — no API key configured")
        return None

    conv_id = conversation.get("conversation_id", "unknown")
    logger.info(f"Running LLM compliance check for {conv_id} (model: {LLM_MODEL})")

    # Build the prompt
    prompt = COMPLIANCE_PROMPT_TEMPLATE.format(
        rules_text=_format_rules(rules_data),
        conversation_text=_format_conversation(conversation),
    )

    try:
        # Import openai only when actually needed — keeps it optional
        import openai

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a compliance auditor. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )

        # Parse the LLM response
        content = response.choices[0].message.content.strip()
        result = json.loads(content)
        violations_raw = result.get("violations", [])

        violations = []
        for v in violations_raw:
            violation = ComplianceViolation(
                rule_id=v.get("rule_id", "unknown"),
                category="llm_detected",
                severity=v.get("severity", "medium"),
                description=v.get("explanation", "LLM-detected violation"),
                matched_keyword=v.get("matched_text", ""),
                message_index=-1,  # LLM doesn't always give message index
                message_role="agent",
                message_snippet=v.get("matched_text", "")[:120],
            )
            violations.append(violation)

        logger.info(f"LLM found {len(violations)} violation(s) for {conv_id}")
        return violations

    except ImportError:
        logger.warning(
            "openai package not installed. Install with: pip install openai>=1.0.0"
        )
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        return None
    except Exception as e:
        # Catch-all: never let the LLM layer crash the pipeline
        logger.error(f"LLM compliance check failed for {conv_id}: {e}")
        return None
