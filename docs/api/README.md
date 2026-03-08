# Data contracts and mock APIs

Candidates build against these contracts. Implementations can read from `data/` (no live backend required).

---

## 1. Conversation / message API (mock)

**Source**: `data/conversations.json` (array of conversation objects).

**Schema**: [conversation_schema.json](conversation_schema.json)

**Contract**:
- **Input** (conceptually): `conversation_id` or “all” to load full fixture.
- **Output**: One or more conversations. Each has:
  - `conversation_id` (string)
  - `messages` (array of `{ role, text, timestamp }`); role is `agent` or `customer`
  - Optional: `channel`, `customer_segment`

Use this as the input to your compliance checker and (optionally) situation classifier.

---

## 2. Compliance rules API (mock)

**Source**: `data/compliance_rules.json`.

**Schema**: [compliance_rules_schema.json](compliance_rules_schema.json)

**Contract**:
- **Input** (conceptually): `rule_set_id` or `version` (for this exercise, a single file is enough).
- **Output**: Object with `rule_set_id`, `version`, `rules` (array). Each rule has:
  - `id`, `category`, `description`, `severity`
  - Optional: `keywords`, `regex_hint`

Your compliance check should evaluate agent messages (or full conversation) against these rules and report which rule(s) fired and at what severity.

---

## 3. Customer situation (optional)

**Schema**: [customer_situation_schema.json](customer_situation_schema.json)

**Contract** (output of your classifier or mock):
- **Input**: `conversation_id` (and optionally full conversation text).
- **Output**: Structured fields, e.g.:
  - `has_product_loss` (boolean)
  - `has_substandard_service` (boolean)
  - `situation_other` (boolean) or equivalent
  - `notes` (optional string)

You may implement this as a classifier and document the contract in `docs/`, or mock the response; either way, document the input/output schema you use.
