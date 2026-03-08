# Prompt Design Rationale

## Overview

We designed two prompts: one for **compliance checking** and one for **situation classification**. Both follow the same design principles, optimized for accuracy, cost, and parseability.

---

## Design Principles

### 1. Structured JSON Output
Both prompts require the LLM to respond ONLY with valid JSON. This ensures:
- Programmatic parsing without regex hacks
- Easy merging with rule-based results
- Schema validation against our data contracts

### 2. Zero Temperature
We use `temperature=0.0` for both prompts. Compliance and classification are deterministic tasks — there's no "creative" answer. Given the same conversation, the model should always produce the same result.

### 3. Rules Embedded, Not Fine-Tuned
Compliance rules are passed in the prompt each time, not baked into a fine-tuned model. This means:
- Rules can be updated without retraining
- New rules take effect immediately
- Full transparency — the evaluator can see exactly what rules the model was given

### 4. Few-Shot Examples
Each prompt includes 2-3 examples covering:
- A clear positive case (violations / product_loss)
- A clear negative case (compliant / other)
- An edge case where possible

Few-shot examples ground the model's behavior and dramatically reduce format errors.

### 5. Conservative Bias
The compliance prompt explicitly instructs the model to only flag CLEAR violations. This minimizes false positives, which would waste human reviewer time. Our rule-based layer catches the obvious cases; the LLM layer is for nuanced detection.

---

## Prompt Files

| File | Purpose |
|------|---------|
| `prompts/compliance_check.md` | Compliance violation detection — system prompt, user template, few-shot examples |
| `prompts/situation_classifier.md` | Customer situation classification — category definitions, few-shot examples |

---

## Cost Analysis

| Prompt | Avg Input Tokens | Avg Output Tokens | Cost per Call (GPT-4o-mini) |
|--------|-----------------|-------------------|---------------------------|
| Compliance Check | ~300 | ~150 | ~$0.0003 |
| Situation Classifier | ~200 | ~100 | ~$0.0001 |

At 1,000 conversations/day (all going to LLM):
- Compliance: ~$0.30/day
- Situation: ~$0.10/day
- **Total: ~$0.40/day**

With tiered model selection (only 10-20% escalated to LLM):
- **Total: ~$0.04-0.08/day**
