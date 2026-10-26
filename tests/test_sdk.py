from collections.abc import Callable
from typing import cast

import pytest
from pydantic import JsonValue

from askless.sdk import AgentQuestion, Decision, ExplorationError, explore


def test_custom_workflow_checks_interactions_and_all_three_options() -> None:
    decisions = (
        Decision("format", "Which format?", ("plain", "rich", "compact")),
        Decision("publish", "Include the payload?", ("no", "yes")),
        Decision("spacing", "Which spacing?", ("one", "two")),
    )

    def preview(data: JsonValue, policy: dict[str, str]) -> JsonValue:
        return {"payload": policy["format"] if policy["publish"] == "yes" else "hidden"}

    result = explore(adapter="test/v1", inputs={"task": 1}, decisions=decisions, preview=preview)
    assert len(result.trials) == 12
    assert [group.decision.key for group in result.pending] == ["format", "publish"]
    assert result.decisions[0].comparisons_checked == 8
    assert len(result.decisions[0].witnesses) == 2
    assert result.decisions[2].selected == "one"
    resolved = result.resolve({"format": "compact", "publish": "yes"}, inputs={"task": 1})
    assert resolved.output == {"payload": "compact"}
    assert resolved.policy == {"format": "compact", "publish": "yes", "spacing": "one"}


def test_missing_agent_questions_do_not_drop_contracts() -> None:
    decisions = (Decision("mode", "Mode?", ("a", "b")), Decision("style", "Style?", ("x", "y")))
    questions = (AgentQuestion("q1", "agent", "style", "Style?"), AgentQuestion("q2", "reviewer", "style", "Also style?"))
    result = explore(adapter="test/v1", inputs=[], decisions=decisions, preview=lambda data, policy: policy["mode"], questions=questions)
    assert [group.decision.key for group in result.pending] == ["mode"]
    assert result.decisions[0].question_ids == ()
    assert result.decisions[1].question_ids == ("q1", "q2")


def test_each_preview_and_public_result_gets_an_independent_snapshot() -> None:
    original: JsonValue = {"rows": [1, 2]}

    def preview(data: JsonValue, policy: dict[str, str]) -> JsonValue:
        assert isinstance(data, dict)
        rows = data["rows"]
        assert isinstance(rows, list)
        rows.append(3)
        policy["mode"] = "mutated"
        return rows

    result = explore(adapter="test/v1", inputs=original, decisions=(Decision("mode", "Mode?", ("a", "b")),), preview=preview)
    assert original == {"rows": [1, 2]}
    assert [trial.output for trial in result.trials] == [[1, 2, 3], [1, 2, 3]]
    output = result.trials[0].output
    assert isinstance(output, list)
    output.append(9)
    result.trials[0].policy["mode"] = "corrupt"
    assert result.trials[0].output == [1, 2, 3]
    assert result.trials[0].policy == {"mode": "a"}
    assert result.resolve({}, inputs=original).output == [1, 2, 3]


def test_budget_rejection_happens_before_execution() -> None:
    calls = 0

    def preview(data: JsonValue, policy: dict[str, str]) -> JsonValue:
        nonlocal calls
        calls += 1
        return 0

    with pytest.raises(ValueError, match="budget"):
        explore(adapter="test/v1", inputs=[], decisions=(Decision("mode", "Mode?", ("a", "b", "c")),), preview=preview, max_branches=2)
    assert calls == 0


def test_branch_failure_stops_and_sanitizes_callback_exception() -> None:
    def preview(data: JsonValue, policy: dict[str, str]) -> JsonValue:
        if policy["mode"] == "b":
            raise RuntimeError("credential-sentinel")
        return "success"

    with pytest.raises(ExplorationError) as error:
        explore(adapter="test/v1", inputs=[], decisions=(Decision("mode", "Mode?", ("a", "b")),), preview=preview)
    assert error.value.completed_branches == 1
    assert error.value.stage == "preview"
    assert "credential-sentinel" not in str(error.value)


def test_scope_covers_input_adapter_and_contracts_and_rejects_stale_resolution() -> None:
    def run(data: JsonValue, adapter: str = "test/v1", options: tuple[str, ...] = ("a", "b")):
        return explore(adapter=adapter, inputs=data, decisions=(Decision("mode", "Mode?", options),), preview=lambda data, policy: 1)

    first = run({"rows": [1]})
    assert len({first.scope, run({"rows": [2]}).scope, run({"rows": [1]}, "test/v2").scope, run({"rows": [1]}, options=("b", "a")).scope}) == 4
    with pytest.raises(ValueError, match="input"):
        first.resolve({}, inputs={"rows": [2]})


@pytest.mark.parametrize("answers", [{}, {"mode": "c"}, {"mode": "b", "extra": "x"}])
def test_resolution_requires_exactly_the_pending_legal_choices(answers: dict[str, str]) -> None:
    result = explore(adapter="test/v1", inputs=[], decisions=(Decision("mode", "Mode?", ("a", "b")),), preview=lambda data, policy: policy["mode"])
    with pytest.raises(ValueError):
        result.resolve(answers, inputs=[])


def test_changed_output_fails_replay() -> None:
    calls = 0

    def preview(data: JsonValue, policy: dict[str, str]) -> JsonValue:
        nonlocal calls
        calls += 1
        return 0 if calls <= 2 else 1

    result = explore(adapter="test/v1", inputs=[], decisions=(Decision("mode", "Mode?", ("a", "b")),), preview=preview)
    with pytest.raises(ExplorationError) as error:
        result.resolve({}, inputs=[])
    assert error.value.stage == "replay"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {1: "value"}, (1, 2), {"deep": {"bad": {1, 2}}}])
def test_non_json_input_cannot_silently_change_type_or_become_equivalent(bad: object) -> None:
    with pytest.raises(ValueError, match="JSON"):
        explore(adapter="test/v1", inputs=cast(JsonValue, bad), decisions=(), preview=lambda data, policy: None)


@pytest.mark.parametrize("bad", [float("nan"), "x" * 65_536])
def test_invalid_or_oversized_output_never_returns_a_success(bad: JsonValue) -> None:
    with pytest.raises(ExplorationError):
        explore(adapter="test/v1", inputs=[], decisions=(), preview=lambda data, policy: bad)


def test_result_storage_has_a_total_budget() -> None:
    decisions = tuple(Decision(f"d{i}", "Choice?", ("a", "b")) for i in range(7))
    with pytest.raises(ExplorationError) as error:
        explore(adapter="test/v1", inputs=[], decisions=decisions, preview=lambda data, policy: "x" * 40_000, max_branches=128)
    assert error.value.stage == "budget"


@pytest.mark.parametrize(
    "build",
    [
        lambda: Decision("mode", "Mode?", ("a", "a")),
        lambda: Decision("mode", "Mode?", ("a",)),
        lambda: Decision("../mode", "Mode?", ("a", "b")),
        lambda: Decision("mode", "", ("a", "b")),
    ],
)
def test_invalid_contracts_are_rejected(build: Callable[[], Decision]) -> None:
    with pytest.raises(ValueError):
        build()


def test_duplicate_contracts_and_unbound_questions_are_rejected() -> None:
    decision = Decision("mode", "Mode?", ("a", "b"))
    with pytest.raises(ValueError, match="unique"):
        explore(adapter="test/v1", inputs=[], decisions=(decision, decision), preview=lambda data, policy: 0)
    with pytest.raises(ValueError, match="question"):
        explore(
            adapter="test/v1",
            inputs=[],
            decisions=(decision,),
            preview=lambda data, policy: 0,
            questions=(AgentQuestion("q1", "agent", "unknown", "Question?"),),
        )


def test_object_key_order_is_equivalent_but_list_order_is_observable() -> None:
    decision = (Decision("mode", "Mode?", ("a", "b")),)
    same = explore(
        adapter="test/v1", inputs=[], decisions=decision, preview=lambda data, policy: {"a": 1, "b": 2} if policy["mode"] == "a" else {"b": 2, "a": 1}
    )
    changed = explore(adapter="test/v1", inputs=[], decisions=decision, preview=lambda data, policy: [1, 2] if policy["mode"] == "a" else [2, 1])
    assert len(same.pending) == 0
    assert len(changed.pending) == 1
