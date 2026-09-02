# Task 05 LLM Intent Extraction Design

## Goal
Use DashScope qwen3.7-max to convert shipping-related natural-language queries into a small, validated structured state that downstream LangGraph nodes can consume deterministically.

## Architecture

```text
user_input
   |
   v
parse_intent_node
   |
   +--> DashScope qwen3.7-max --> JSON object
   |                              |
   |                              +--> validate intent/country/weight
   |                              +--> normalize_cargo_type()
   |                              +--> calculate missing_params
   |
   +--> on API/parse failure --> chitchat fallback
   |
   v
ShippingState
```

`agent/intent_parser.py` owns the LLM boundary, prompt, JSON extraction, and weight-unit normalization. `agent/nodes.py` exposes the LangGraph-compatible `parse_intent_node(state) -> dict` interface. `agent/state.py` defines the extensible TypedDict state so later workflow nodes can add rate, rule, and response fields without changing the intent-node contract.

## State Contract

Task 05 establishes these fields:

- `user_input: str`
- `intent_type: str` — `rate_query`, `rule_query`, `mixed`, or `chitchat`
- `country: str | None`
- `weight: float | None` — kilograms
- `cargo_type: str | None` — normalized through `normalize_cargo_type`
- `missing_params: list[str]`

The TypedDict is intentionally extensible. Fields not produced by Task 05 may be added by later tasks.

## Intent Rules

- `rate_query`: user asks for price/rate/available shipping channels and has or may need rate parameters.
- `rule_query`: user asks about restrictions, compensation, size limits, prohibited goods, or other shipping rules.
- `mixed`: both rate and rule information are requested.
- `chitchat`: greeting/casual conversation or a query that cannot be reliably classified.

Missing parameters are required only for rate-oriented requests. Country is considered required for a rate query; weight and cargo type are also required. Rule queries and chitchat do not require these parameters.

## LLM Boundary

- API key: `DASHSCOPE_API_KEY`.
- Model: `qwen3.7-max`.
- Request uses JSON output instructions and few-shot examples.
- No real API calls are made by unit tests; the DashScope call is injected/mocked.
- Malformed JSON, missing API key, SDK exceptions, or invalid model output produce a safe `chitchat` result rather than raising from the node.

## Weight Normalization

The parser accepts numeric weight values with `kg`, `g`/`克`, and `斤`. Conversion is deterministic: grams divide by 1000 and Chinese jin divides by 2 because 1 斤 = 0.5 kg. Bare numeric values returned by the LLM are interpreted as kilograms because the prompt requires the model to normalize units.

## Cargo Normalization

The raw LLM cargo value is passed through `normalize_cargo_type()` from Task 04 before being written to state. This preserves unknown values for a future LLM fallback while guaranteeing the existing high-frequency synonyms become canonical cargo types.

## Error Handling

The node never exposes provider exceptions to the LangGraph workflow. It returns a complete safe fallback:

```python
{
    "intent_type": "chitchat",
    "country": None,
    "weight": None,
    "cargo_type": None,
    "missing_params": [],
}
```

## Testing

Unit tests cover exact examples, all weight-unit conversions, cargo synonym normalization, invalid JSON, provider exceptions, missing API key, and the node's state-to-update contract. Tests use a fake LLM callable and therefore consume no DashScope quota.
