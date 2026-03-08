# MLE Assessment: Compliance for Customer Communication

A compliance checking tool and customer situation classifier for consumer finance collections teams. Analyzes agent–customer conversations for FDCPA rule violations and classifies customer situations to enable fair routing and prioritization.

## Quick Start

```bash
# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run compliance check + situation classification
python src/run_assessment.py
```

## Usage

```bash
# Basic run — compliance check + situation classification on all conversations
python src/run_assessment.py

# Run with evaluation against ground truth (precision/recall/F1 + confusion matrix)
python src/run_assessment.py --eval

# Export structured JSON results to output/
python src/run_assessment.py --json

# Check a specific conversation
python src/run_assessment.py --conversation conv_003

# Combine flags
python src/run_assessment.py --eval --json

# Enable optional LLM layer (requires API key, $0 by default)
OPENAI_API_KEY="sk-..." python src/run_assessment.py --llm
```


## Result Output


 ## Compliance check Results:




```text
conv_007: ✗ NON-COMPLIANT (score: 42)
  [CRITICAL] R001 (forbidden_language): matched 'sue'
    └─ message[0]: "You need to pay your balance of $2,100 immediately. We're going to sue you and garnish your wages if you don't. Your fam..."

  [CRITICAL] R001 (forbidden_language): matched 'garnish'
    └─ message[0]: "You need to pay your balance of $2,100 immediately. We're going to sue you and garnish your wages if you don't. Your fam..."

  [CRITICAL] R001 (forbidden_language): matched 'wages'
    └─ message[0]: "You need to pay your balance of $2,100 immediately. We're going to sue you and garnish your wages if you don't. Your fam..."

  [CRITICAL] R002 (forbidden_language): matched 'family will find out'
    └─ message[0]: "You need to pay your balance of $2,100 immediately. We're going to sue you and garnish your wages if you don't. Your fam..."

  [MEDIUM] R006 (fair_engagement): matched '(absence of acknowledgment)'
```


  ## Compliance check Results:

conv_007: other (confidence: medium)
    Note: No product loss or substandard service signals. Likely ability-to-pay or general    
    

## Architecture

```
Tier 1: Rule-Based Engine (always runs, $0)
  → Keyword/regex matching against compliance rules
  → Per-message traceability (which rule, which message, what severity)
  → Handles inverted R006 logic (agent SHOULD acknowledge hardship)

Tier 2: LLM Layer (optional, only if API key is set)
  → Catches nuanced violations that keywords miss
  → Graceful fallback to Tier 1 if unavailable

Situation Classifier
  → Heuristic keyword matching with confidence scoring
  → Evidence tracking — traces classification to specific phrases

Evaluation Pipeline
  → Ground truth comparison with Precision/Recall/F1
  → Confusion matrix for situation classification
```

## Repo Structure

| Path | Purpose |
|------|---------|
| `ASSESSMENT.md` | Problem statement and deliverables |
| `AI_USAGE.md` | Models, tools, token/cost, scaling notes |
| `data/conversations.json` | 8 sample agent-customer conversations |
| `data/compliance_rules.json` | 6 FDCPA-aligned compliance rules |
| `data/ground_truth.json` | Hand-labeled ground truth for evaluation |
| `docs/summary.md` | Approach, design choices, tradeoffs, scalability |
| `docs/prompt_design.md` | Prompt engineering rationale |
| `docs/api/` | Data contracts and schemas |
| `prompts/compliance_check.md` | LLM prompt for compliance detection |
| `prompts/situation_classifier.md` | LLM prompt for situation classification |
| `src/run_assessment.py` | Main entrypoint (CLI) |
| `src/compliance_checker.py` | Rule-based compliance engine |
| `src/situation_classifier.py` | Customer situation classifier |
| `src/evaluator.py` | Evaluation pipeline with metrics |
| `src/llm_compliance.py` | Optional LLM compliance layer |
| `src/config.py` | Centralized configuration |
| `src/models.py` | Data models and output schemas |

## Environment Variables (optional)

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | Enable LLM-based compliance checks | Not set (LLM disabled) |
| `LLM_MODEL` | Which model to use for LLM checks | `gpt-4o-mini` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
