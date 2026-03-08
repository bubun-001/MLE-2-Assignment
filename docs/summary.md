# Compliance Assessment — Design Summary

## 1. Approach

### Problem
Build a tool that checks agent-customer conversations for compliance violations and classifies customer situations, with traceability, scalability, and production-readiness in mind.

### Architecture: Two-Tier Compliance + Heuristic Classifier

```
Conversation Input
       │
       ▼
┌─────────────────┐     ┌────────────────────┐
│ Tier 1: Rules   │────▶│ Tier 2: LLM        │
│ (keywords/regex)│     │ (optional, $0 def.) │
│ Always runs     │     │ Edge cases only     │
└────────┬────────┘     └─────────┬──────────┘
         │                        │
         └──────┬─────────────────┘
                ▼
       Merged Violations
                │
       ┌────────▼────────┐
       │ Eval Pipeline    │
       │ (P/R/F1 metrics) │
       └─────────────────┘
```

**Why two tiers?**
- Rule-based is fast, deterministic, and free. It handles the majority of cases.
- LLM catches nuanced violations (tone, implicit threats) that keywords miss.
- Tiered approach keeps cost near $0 while maintaining high recall.

---

## 2. Design Choices

### Per-Message vs Per-Conversation Checking
**Chose: Per-message.** The reference implementation joins all agent text into one blob. We check each message individually so violations are traceable to the exact message where they occurred. This matters for audit trails and agent coaching.

### R006 Inverted Logic
Rules R001–R005 are negative (agent SHOULD NOT say X). R006 is positive (agent SHOULD acknowledge hardship). We detect this by:
1. Scanning customer messages for hardship/complaint signals
2. If found, checking whether the agent used ANY acknowledgment phrases
3. Flagging a violation only when acknowledgment is ABSENT

### Confidence Scoring for Situations
Instead of just a label, we report confidence (high/medium/low) based on the number and specificity of evidence phrases. This helps downstream routing decisions.

### Caching by Content Hash
Conversations are hashed by message content. If the same conversation comes through again (e.g. re-processing after a rule update), we return the cached result instantly. This is a simple in-memory cache that could be swapped for Redis in production.

---

## 3. Tradeoffs

| Decision | Benefit | Cost |
|----------|---------|------|
| Rule-based core | Fast, deterministic, free | Misses nuanced violations |
| Optional LLM | Catches edge cases | Adds latency + cost when enabled |
| Per-message checking | Full traceability | Slightly more computation |
| Ground-truth eval | Know if the system works | Requires manual labeling |
| In-memory cache | Fast, zero deps | Lost on restart |

---

## 4. Scalability

### Hash-Based Caching
- **What**: SHA-256 hash of conversation content → cached result
- **Why**: In collections, the same customer might be checked multiple times. Caching avoids redundant work.
- **Current**: In-memory Python dict with simple eviction
- **Production**: Swap for Redis with TTL to share cache across workers and survive restarts

### Tiered Model Selection
- **What**: Rule-based engine handles 80-90% of conversations. Only ambiguous cases escalate to Tier 2 (LLM).
- **Why**: LLM calls cost money and add latency. Most violations are caught by simple keyword matching. Using LLM for everything is wasteful.
- **Production**: Implement a confidence threshold — if rule-based results are "uncertain" (e.g. partial keyword matches, edge-case language), auto-escalate to LLM.

### Structured Logging
- **What**: Python `logging` module with consistent format: `timestamp | level | module | message`
- **Why**: For debugging, monitoring, and compliance auditing. Every compliance check, cache hit/miss, and violation detection is logged.
- **Production**: Output as JSON logs → ship to ELK/Datadog/CloudWatch. Add structured fields like `conversation_id`, `rule_id`, and `latency_ms` for querying.

---

## 5. Data Contracts

### Compliance Check
- **Input**: Conversation object (see `docs/api/conversation_schema.json`)
- **Output**: ComplianceResult with violations, score, and pass/fail

### Situation Classifier
- **Input**: Conversation object
- **Output**: SituationResult with classification, confidence, and evidence (see `docs/api/customer_situation_schema.json`)

### Evaluation
- **Input**: Ground truth labels (`data/ground_truth.json`) + predicted results
- **Output**: EvalReport with precision/recall/F1 and confusion matrix

---

## 6. What I Would Do With More Time

1. **Regex patterns**: Add `regex_hint` patterns to compliance rules for more flexible matching
2. **Fine-tuned classifier**: Train a small model (e.g. DistilBERT) on labeled conversation data for situation classification
3. **Real-time monitoring dashboard**: Stream compliance results to a dashboard showing violation trends
4. **A/B testing framework**: Compare rule-based vs LLM accuracy on new conversations
5. **Human-in-the-loop**: Route high-severity violations to a human reviewer with the evidence pre-attached
