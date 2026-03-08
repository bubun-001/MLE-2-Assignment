"""
Configuration for the compliance assessment pipeline.

Centralizes all tunable knobs — severity weights, cache settings,
model selection, and logging config. Change these instead of
hard-coding values throughout the codebase.
"""

import os
import logging

# ---------------------------------------------------------------------------
# Paths — relative to the repo root
# ---------------------------------------------------------------------------

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"

# Create output directory if it doesn't exist
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Severity weights — used to compute a compliance score per conversation.
# Higher score = more violations / worse compliance.
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS = {
    "critical": 10,
    "high": 5,
    "medium": 2,
    "low": 1,
}

# ---------------------------------------------------------------------------
# Cache settings
# ---------------------------------------------------------------------------

# Enable or disable in-memory caching of compliance/situation results.
# When enabled, identical conversations (same message content) will
# return cached results instead of re-running the checks.
CACHE_ENABLED = True
CACHE_MAX_SIZE = 10_000  # Max entries before we start evicting (LRU-style)

# ---------------------------------------------------------------------------
# Tiered model selection
#
# The system runs in two tiers:
#   Tier 1: Rule-based (always runs, zero cost)
#   Tier 2: LLM-based (only if API key is set AND tier2 is enabled)
#
# In production, you'd escalate to Tier 2 only for "borderline" cases —
# conversations where the rule-based engine finds no clear violations
# but the overall tone seems concerning.
# ---------------------------------------------------------------------------

LLM_ENABLED = bool(os.environ.get("OPENAI_API_KEY"))
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")  # Cheaper model by default
LLM_TEMPERATURE = 0.0  # Deterministic output for compliance (no creativity needed)
LLM_MAX_TOKENS = 1024

# ---------------------------------------------------------------------------
# Logging — structured, human-readable logs with timestamps
# ---------------------------------------------------------------------------

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging():
    """
    Configure logging for the entire pipeline.
    
    Call this once at startup (from run_assessment.py).
    All modules use `logging.getLogger(__name__)` so they
    automatically pick up this configuration.
    """
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
    # Quiet down noisy libraries if any are imported
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
