# AI Usage Log (Candidate — fill this out)

Use this template to report how you used AI for the assessment. Keep cost minimal; we care about reasoning and design.

---

## Models and tools used

| Model / tool | Purpose (e.g. code gen, prompts, analysis) |
|--------------|----------------------------------------------|
| Claude 3.5 Sonnet (via Gemini Code Assist) | Architecture planning, code generation, prompt design |
| GPT-4o-mini (prompt design only) | Designed prompts for compliance check and situation classifier (NOT executed — $0 cost) |

---

## Workflows / skills

- Used AI assistant to scaffold the project structure and generate initial compliance checker logic; reviewed and edited all code by hand.
- Designed LLM prompts (`prompts/compliance_check.md`, `prompts/situation_classifier.md`) using prompt engineering best practices — few-shot examples, structured JSON output, zero temperature.
- Ground truth labels in `data/ground_truth.json` were hand-labeled by reviewing each conversation.

---

## Token usage and cost (approximate)

| Model | Input tokens (approx) | Output tokens (approx) | Est. cost ($) |
|-------|------------------------|-------------------------|---------------|
| Claude 3.5 Sonnet | ~80k | ~40k | ~0.60 |
| GPT-4o-mini | 0 (prompts designed but not executed) | 0 | 0.00 |
| **Total** | ~80k | ~40k | **~0.60** |

*Estimate includes architecture planning, code generation, debugging (e.g. fixing word-boundary matching for short keywords), and iterative refinement. All generated code was reviewed, understood, and edited by hand.*

---

## Scaling to production — commentary

### Cost Management
- **Tiered model selection**: Rule-based engine handles 80-90% of conversations at $0 cost. Only ambiguous cases escalate to LLM (Tier 2). This keeps production cost at ~$0.04-0.08/day for 1,000 conversations.
- **Model choice**: Use GPT-4o-mini ($0.15/1M input tokens) instead of GPT-4o ($2.50/1M) for routine checks. Reserve larger models for appeals or complex disputes.

### Caching
- **Content-based caching**: Hash conversation text → cached compliance result. Same conversation = same result instantly. In production, use Redis with TTL (e.g. 24h) for cross-worker caching.
- **Cache hit rate**: In collections, follow-up conversations are common. Expected 30-60% cache hit rate, cutting LLM costs proportionally.

### Rate Limits & Reliability
- **Rate limiting**: Implement client-side rate limiting (e.g. 100 RPM buffer below provider limits). Use exponential backoff with jitter on 429 responses.
- **Fallback strategy**: If LLM is unavailable, fall back to rule-based only. The system is designed to work without any LLM — degraded accuracy, but zero downtime.
- **Circuit breaker**: If LLM error rate exceeds 5%, disable Tier 2 and alert ops team.

### Monitoring
- **Structured logging**: Every compliance check logs conversation_id, rules checked, violations found, latency, and cache hit/miss. Ship to centralized logging (ELK/Datadog).
- **Alerting**: Alert on spike in violation rates (possible systemic issue) or drop in violation rates (possible rule regression).
