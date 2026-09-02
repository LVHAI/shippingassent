# LLM Intent Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a LangGraph-compatible intent parsing node backed by DashScope qwen3.7-max, with deterministic weight/cargo normalization and safe fallback behavior.

**Architecture:** `agent/intent_parser.py` isolates the DashScope provider and JSON/weight parsing. `agent/nodes.py` adapts the parser to `ShippingState`, normalizes cargo with Task 04, and calculates missing rate parameters. `agent/state.py` provides the extensible TypedDict contract used by later workflow nodes.

**Tech Stack:** Python, TypedDict, DashScope SDK, qwen3.7-max, pytest, unittest.mock.

**Spec:** `docs/superpowers/specs/2026-09-02-llm-intent-extraction-design.md`

## Global Constraints

- LLM: 通义千问 `qwen3.7-max`.
- API key: `DASHSCOPE_API_KEY`.
- Weight unit in state: KG.
- Cargo normalization must use `normalize_cargo_type()`.
- LLM failure fallback: `intent_type="chitchat"`.
- Tests must not call the real LLM or consume API quota.
- Development branch: `feature/develop`; do not modify `main`.

---

### Task 1: Define the extensible shipping state

**Files:**
- Create: `agent/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: no prior implementation.
- Produces: `ShippingState` TypedDict with `user_input`, `intent_type`, `country`, `weight`, `cargo_type`, `missing_params`.

- [ ] **Step 1: Write the failing test**

```python
from typing import get_type_hints

from agent.state import ShippingState


def test_shipping_state_exposes_intent_fields():
    fields = get_type_hints(ShippingState)
    assert set(fields) >= {
        "user_input", "intent_type", "country", "weight", "cargo_type", "missing_params"
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: FAIL because `agent.state` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
from typing import TypedDict

class ShippingState(TypedDict, total=False):
    user_input: str
    intent_type: str
    country: str | None
    weight: float | None
    cargo_type: str | None
    missing_params: list[str]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/state.py tests/test_state.py
git commit -m "feat: add shipping state contract"
```

---

### Task 2: Build the provider-isolated intent parser

**Files:**
- Create: `agent/intent_parser.py`
- Test: `tests/test_intent_parser.py`

**Interfaces:**
- Consumes: `DASHSCOPE_API_KEY` and user text.
- Produces: `parse_intent(user_input: str, llm_call: Callable | None = None) -> dict` with canonical keys `intent_type`, `country`, `weight`, `cargo_type`, `missing_params`.

- [ ] **Step 1: Write the failing tests**

```python
from agent.intent_parser import parse_intent


def test_parse_intent_converts_weight_units():
    result = parse_intent(
        "寄500g到美国",
        llm_call=lambda _: '{"intent_type":"rate_query","country":"美国","weight":"500g","cargo_type":"普货"}',
    )
    assert result["weight"] == 0.5


def test_parse_intent_converts_jin_to_kg():
    result = parse_intent(
        "寄2斤到美国",
        llm_call=lambda _: '{"intent_type":"rate_query","country":"美国","weight":"2斤","cargo_type":"普货"}',
    )
    assert result["weight"] == 1.0


def test_parse_intent_keeps_kg():
    result = parse_intent(
        "美国5kg普货多少钱",
        llm_call=lambda _: '{"intent_type":"rate_query","country":"美国","weight":"5kg","cargo_type":"普货"}',
    )
    assert result["weight"] == 5.0


def test_parse_intent_rejects_malformed_json_as_safe_fallback():
    result = parse_intent("hello", llm_call=lambda _: "not-json")
    assert result == {
        "intent_type": "chitchat",
        "country": None,
        "weight": None,
        "cargo_type": None,
        "missing_params": [],
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_intent_parser.py -v`
Expected: FAIL because `agent.intent_parser` does not exist.

- [ ] **Step 3: Write minimal implementation**

Use `dashscope.Generation.call(model="qwen3.7-max", messages=[...], result_format="message")` when no injected callable is provided. The prompt must require JSON with the five canonical keys and include these few-shot examples: `美国5kg普货多少钱`, `寄到巴西要多少钱`, `赔偿标准是什么`, `你好`. Extract the provider response text, parse JSON, convert string weights using `g/克 -> /1000`, `斤 -> *0.5`, and `kg -> unchanged`, and return the safe fallback on missing API key, provider exception, malformed JSON, or non-dict output.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_intent_parser.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/intent_parser.py tests/test_intent_parser.py
git commit -m "feat: add dashscope intent parser"
```

---

### Task 3: Add the LangGraph intent node and cargo normalization

**Files:**
- Create: `agent/nodes.py`
- Test: `tests/test_nodes.py`

**Interfaces:**
- Consumes: `ShippingState`; `parse_intent()` from Task 2; `normalize_cargo_type()` from Task 04.
- Produces: `parse_intent_node(state: ShippingState) -> dict`.

- [ ] **Step 1: Write the failing tests**

```python
import agent.nodes as nodes


def test_parse_intent_node_normalizes_cargo_and_returns_state_update(monkeypatch):
    monkeypatch.setattr(nodes, "parse_intent", lambda text: {
        "intent_type": "rate_query",
        "country": "美国",
        "weight": 5.0,
        "cargo_type": "衣服",
        "missing_params": [],
    })
    result = nodes.parse_intent_node({"user_input": "美国5kg衣服多少钱"})
    assert result == {
        "intent_type": "rate_query",
        "country": "美国",
        "weight": 5.0,
        "cargo_type": "P服装",
        "missing_params": [],
    }


def test_parse_intent_node_marks_missing_rate_parameters(monkeypatch):
    monkeypatch.setattr(nodes, "parse_intent", lambda text: {
        "intent_type": "rate_query",
        "country": "巴西",
        "weight": None,
        "cargo_type": None,
        "missing_params": [],
    })
    result = nodes.parse_intent_node({"user_input": "寄到巴西要多少钱"})
    assert result["missing_params"] == ["weight", "cargo_type"]


def test_parse_intent_node_preserves_empty_missing_params_for_rule_query(monkeypatch):
    monkeypatch.setattr(nodes, "parse_intent", lambda text: {
        "intent_type": "rule_query",
        "country": None,
        "weight": None,
        "cargo_type": None,
        "missing_params": [],
    })
    result = nodes.parse_intent_node({"user_input": "赔偿标准是什么"})
    assert result["missing_params"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_nodes.py -v`
Expected: FAIL because `agent.nodes` does not exist.

- [ ] **Step 3: Write minimal implementation**

`parse_intent_node` should read `state["user_input"]`, call `parse_intent`, normalize a non-empty cargo type via `normalize_cargo_type`, and for `rate_query`/`mixed` calculate missing fields in stable order `country`, `weight`, `cargo_type`. For `rule_query` and `chitchat`, `missing_params` must be `[]`. Return only the state fields changed by this node.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_nodes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/nodes.py tests/test_nodes.py
git commit -m "feat: add intent parsing node"
```

---

### Task 4: Full regression verification and Task 05 documentation update

**Files:**
- Modify: `docs/tasks/05-llm-intent-extract.md`

- [ ] **Step 1: Run the complete test suite**

Run: `pytest -q`
Expected: all tests pass with exit code 0.

- [ ] **Step 2: Run the CLI smoke check without a real API call**

Run: `python -c "from agent.intent_parser import parse_intent; print(parse_intent('你好', llm_call=lambda _: '{\\\"intent_type\\\":\\\"chitchat\\\",\\\"country\\\":null,\\\"weight\\\":null,\\\"cargo_type\\\":null}'))"`
Expected: a parsed `chitchat` result with null country/weight/cargo and an empty missing list.

- [ ] **Step 3: Mark Task 05 acceptance criteria complete**

Update each checklist item in `docs/tasks/05-llm-intent-extract.md` to `[x]`, and add a short implementation note naming `agent/state.py`, `agent/intent_parser.py`, and `agent/nodes.py`.

- [ ] **Step 4: Commit documentation**

```bash
git add docs/tasks/05-llm-intent-extract.md
git commit -m "docs: mark Task 05 complete"
```
