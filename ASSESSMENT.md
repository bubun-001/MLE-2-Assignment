# Assessment: Compliance for Customer Communication

## Context

Our **collections** team’s goal is to **engage the customer** — leading to the customer paying, us staying **fully compliant**, and earning the **highest service ratings** from the customer. Many situations involve **substandard service** or **actual product/service losses**; we need to handle these fairly and in line with regulations and internal policy.

## Your mission

Build a **tool to streamline the collection process** that:

1. **Checks if agents are breaking compliance rules** — e.g. forbidden language, pressure tactics, misrepresentation — with traceability (which rule fired, severity).
2. **Surfaces whether the customer has actual product/service losses** vs **substandard service** vs other (e.g. ability-to-pay only), so we can route or prioritize fairly and stay compliant.

Outcome we care about: **customer pays**, **we are fully compliant**, and **we earn high service ratings**.

## Concrete tasks

- **Compliance checks**: Classify or score agent–customer conversations (or message batches) for rule violations. Use the mock conversation data and compliance rules in `data/`; implement checks as rule-based (e.g. regex/keywords) and/or model-based. Ensure you can report *which* rule fired and at what severity.
- **Customer situation classification**: Detect “actual product/service losses” vs “substandard service” vs other. You may mock an API or implement a classifier; either way, document the **data contract** (input/output schema) in `docs/`.

APIs and data can be **mocked** (e.g. read from `data/` or local scripts). Specify the **contracts** you rely on (e.g. input/output schemas for compliance check and situation classifier).

## Deliverables

| Deliverable | Where / what |
|-------------|----------------|
| **Code** | Runnable, with minimal setup (e.g. `README` + `requirements.txt` or `pyproject.toml`). Prefer a single clear path: run from `src/` or run a notebook then export. |
| **Presentation / notes / summary** | Short write-up or slides (format flexible: markdown, Notion, PDF) in `docs/` — approach, design choices, tradeoffs. |
| **Prompts and thinking process** | Prompts used for any LLM-based checks or classifiers in `prompts/` or `docs/prompts/`; include a short note on how you designed them. |
| **AI usage log** | Fill `AI_USAGE.md`: models used, tools/workflows, approximate **token usage** and **cost ($)**. Keep cost **minimal** for this exercise; we care about reasoning and design, not spend. Add a short section on **how you would manage cost and scale in production** (e.g. caching, model choice, batching, guardrails). |

## AI usage expectations

- **Required in `AI_USAGE.md`**:
  - List of **models** and **tools** (e.g. Cursor, Claude, ChatGPT, custom scripts).
  - **Approximate token counts** (input/output) and **estimated cost ($)** for the exercise.
  - **Scaling-to-prod commentary**: how you would manage rate limits, caching, cost controls, and reliability at scale.
- Keep usage **minimal** for the exercise; focus on clear design and traceability.

## Repo requirements

- **Self-contained**: Include everything needed to run and evaluate (code, data references, docs, prompts). If you use external APIs, document how to obtain keys or use mocks.
- **Clear contracts**: Document input/output schemas or API contracts for your compliance checker and situation classifier so an evaluator can see “production-ready” design.

Good luck. We’re excited to see how you balance compliance, customer fairness, and technical quality.
