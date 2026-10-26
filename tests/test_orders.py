import asyncio
import json
from decimal import Inexact, localcontext
from pathlib import Path

import httpx
import pytest
from pydantic import JsonValue

from askless.llm import LLMClient, ProviderError, Settings
from askless.order_agent import propose_order_questions
from askless.orders import ORDER_DECISIONS, load_orders, order_profile, preview_orders
from askless.sdk import explore

ROOT = Path(__file__).resolve().parents[1]


def test_orders_workflow_produces_checked_totals_and_resolves_rounding_only() -> None:
    data = load_orders(ROOT / "examples/orders.json")
    experiment = explore(adapter="orders/v1", inputs=data, decisions=ORDER_DECISIONS, preview=preview_orders)
    assert [group.decision.key for group in experiment.pending] == ["duplicates", "cancelled"]
    result = experiment.resolve({"duplicates": "last", "cancelled": "exclude"}, inputs=data)
    output = result.output
    assert isinstance(output, dict)
    assert output["total"] == "120.00"
    assert output["order_count"] == 4
    assert output["excluded_cancelled"] == [{"source_row": 3, "order_id": "A101", "amount": "12.50", "status": "cancelled"}]
    assert output["discarded_duplicates"] == [{"source_row": 1, "order_id": "A100", "amount": "35.00", "status": "paid"}]
    baseline = preview_orders(data, {"duplicates": "first", "cancelled": "include", "rounding": "per_order"})
    assert isinstance(baseline, dict)
    assert baseline["total"] == "125.50"


def test_rounding_remains_a_real_choice_when_fractional_cents_change_total() -> None:
    data: JsonValue = [{"order_id": "A", "amount": "0.005", "status": "paid"}, {"order_id": "B", "amount": "0.005", "status": "paid"}]
    experiment = explore(adapter="orders/v1", inputs=data, decisions=ORDER_DECISIONS, preview=preview_orders)
    assert [group.decision.key for group in experiment.pending] == ["rounding"]
    output = experiment.resolve({"rounding": "at_total"}, inputs=data).output
    assert isinstance(output, dict)
    assert output["total"] == "0.01"
    other = experiment.resolve({"rounding": "per_order"}, inputs=data).output
    assert isinstance(other, dict)
    assert other["total"] == "0.02"


def test_order_arithmetic_is_independent_of_callers_decimal_context() -> None:
    data: JsonValue = [{"order_id": "A", "amount": "1.0049", "status": "paid"}]
    with localcontext() as context:
        context.prec = 4
        context.traps[Inexact] = True
        assert order_profile(data)["fractional_cent_rows"] == 1
        experiment = explore(adapter="orders/v1", inputs=data, decisions=ORDER_DECISIONS, preview=preview_orders)
        result = experiment.resolve({}, inputs=data).output
        assert isinstance(result, dict)
        assert result["total"] == "1.00"


def test_duplicate_selection_precedes_cancelled_order_filtering() -> None:
    data: JsonValue = [{"order_id": "A", "amount": "5.00", "status": "paid"}, {"order_id": "A", "amount": "8.00", "status": "cancelled"}]
    result = preview_orders(data, {"duplicates": "last", "cancelled": "exclude", "rounding": "at_total"})
    assert isinstance(result, dict)
    assert result["total"] == "0.00"
    assert result["order_count"] == 0


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "1.00001", "1000000000", "1e3"])
def test_invalid_amounts_fail_before_any_successful_summary(amount: str) -> None:
    with pytest.raises(ValueError):
        preview_orders([{"order_id": "A", "amount": amount, "status": "paid"}], {"duplicates": "first", "cancelled": "include", "rounding": "per_order"})


def test_unknown_policy_cannot_silently_fall_back() -> None:
    with pytest.raises(ValueError, match="policy"):
        preview_orders([], {"duplicates": "first", "cancelled": "ignore", "rounding": "at_total"})


def test_input_file_rejects_duplicate_json_keys_and_oversize(tmp_path: Path) -> None:
    path = tmp_path / "orders.json"
    path.write_text('[{"order_id":"A","order_id":"B","amount":"1","status":"paid"}]')
    with pytest.raises(ValueError):
        load_orders(path)
    path.write_text(" " * 524_289)
    with pytest.raises(ValueError, match="512"):
        load_orders(path)


def test_model_can_propose_subset_without_receiving_raw_order_values() -> None:
    def response(request: httpx.Request) -> httpx.Response:
        prompt = json.loads(request.content)["messages"][1]["content"]
        assert "CUSTOMER_SENTINEL" not in prompt
        assert '"rows": 1' in prompt
        data = {"summary": "Check cancellation policy.", "questions": [{"decision_key": "cancelled", "prompt": "Include cancelled orders?"}]}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(data)}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 30}},
        )

    llm = LLMClient(Settings(api_key="test-key"), transport=httpx.MockTransport(response))
    questions, completion, summary = asyncio.run(propose_order_questions(llm, [{"order_id": "CUSTOMER_SENTINEL", "amount": "3.00", "status": "paid"}]))
    assert [question.decision_key for question in questions] == ["cancelled"]
    assert completion.input_tokens == 100
    assert summary == "Check cancellation policy."


@pytest.mark.parametrize("keys", [["invented"], ["cancelled", "cancelled"]])
def test_model_cannot_invent_or_duplicate_contracts(keys: list[str]) -> None:
    draft = {"summary": "Questions", "questions": [{"decision_key": key, "prompt": "Choice?"} for key in keys]}
    response = {"choices": [{"message": {"content": json.dumps(draft)}, "finish_reason": "stop"}]}
    llm = LLMClient(Settings(api_key="test-key"), transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)))
    with pytest.raises(ProviderError):
        asyncio.run(propose_order_questions(llm, [{"order_id": "A", "amount": "3.00", "status": "paid"}]))
