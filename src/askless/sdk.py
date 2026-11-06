"""Bounded, exact-result decision compilation for trusted Python previews."""

import hashlib
import itertools
import json
import math
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from pydantic import JsonValue

Preview = Callable[[JsonValue, dict[str, str]], JsonValue]
MAX_INPUT_BYTES = 524_288
MAX_RESULT_BYTES = 65_536
MAX_TOTAL_BYTES = 4_194_304


def _text(value: str, maximum: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


@dataclass(frozen=True)
class Decision:
    key: str
    prompt: str
    options: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.key):
            raise ValueError("Decision keys must be lowercase identifiers (at most 64 characters).")
        if not _text(self.prompt, 500):
            raise ValueError("Decision prompts need 1–500 characters.")
        if not isinstance(self.options, tuple) or not 2 <= len(self.options) <= 8 or any(not _text(option, 80) for option in self.options):
            raise ValueError("Decisions need a tuple of 2–8 nonempty string options (at most 80 characters each).")
        if len(set(self.options)) != len(self.options):
            raise ValueError("Decision options must be unique.")


@dataclass(frozen=True)
class AgentQuestion:
    id: str
    agent_id: str
    decision_key: str
    prompt: str

    def __post_init__(self) -> None:
        if not all(_text(value, maximum) for value, maximum in ((self.id, 100), (self.agent_id, 40), (self.decision_key, 64), (self.prompt, 500))):
            raise ValueError("Invalid agent question text or identifier.")


class ExplorationError(RuntimeError):
    """Safe failure metadata; callback exception text stays out of reports."""

    def __init__(self, stage: str, branch_id: str, completed_branches: int) -> None:
        self.stage = stage
        self.branch_id = branch_id
        self.completed_branches = completed_branches
        super().__init__(f"{stage} failed at branch {branch_id}; {completed_branches} previews completed. No decision result was returned.")


def _check_json(value: object, depth: int = 0) -> None:
    if depth > 64:
        raise ValueError("JSON nesting exceeds 64 levels.")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for child in value:
            _check_json(child, depth + 1)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for child in value.values():
            _check_json(child, depth + 1)
        return
    raise ValueError("Expected finite JSON values with string object keys.")


def _encode(value: object, limit: int) -> bytes:
    _check_json(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Value cannot be represented as bounded UTF-8 JSON.") from None
    if len(encoded) > limit:
        raise ValueError(f"JSON exceeds the {limit}-byte budget.")
    return encoded


def _decode(value: bytes) -> JsonValue:
    return cast(JsonValue, json.loads(value))


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class Trial:
    id: str
    _policy: tuple[tuple[str, str], ...] = field(repr=False)
    _output: bytes = field(repr=False)
    elapsed_ms: float

    @property
    def policy(self) -> dict[str, str]:
        return dict(self._policy)

    @property
    def output(self) -> JsonValue:
        return _decode(self._output)

    @property
    def output_hash(self) -> str:
        return _hash(self._output)

    def matches(self, output: JsonValue) -> bool:
        return _encode(output, MAX_RESULT_BYTES) == self._output


@dataclass(frozen=True)
class CompiledDecision:
    decision: Decision
    status: Literal["auto", "pending"]
    selected: str | None
    question_ids: tuple[str, ...]
    witnesses: tuple[str, ...]
    comparisons_checked: int


@dataclass(frozen=True)
class Resolution:
    scope: str
    trial: Trial

    @property
    def policy(self) -> dict[str, str]:
        return self.trial.policy

    @property
    def output(self) -> JsonValue:
        return self.trial.output

    @property
    def output_hash(self) -> str:
        return self.trial.output_hash


@dataclass(frozen=True)
class Exploration:
    adapter: str
    scope: str
    decisions: tuple[CompiledDecision, ...]
    questions: tuple[AgentQuestion, ...]
    trials: tuple[Trial, ...]
    elapsed_ms: float
    _input: bytes = field(repr=False)
    _preview: Preview = field(repr=False, compare=False)

    @property
    def inputs(self) -> JsonValue:
        return _decode(self._input)

    @property
    def pending(self) -> tuple[CompiledDecision, ...]:
        return tuple(group for group in self.decisions if group.status == "pending")

    def resolve(self, answers: Mapping[str, str], *, inputs: JsonValue) -> Resolution:
        if _encode(inputs, MAX_INPUT_BYTES) != self._input:
            raise ValueError("The input changed; explore it again before resolving decisions.")
        if set(answers) != {group.decision.key for group in self.pending}:
            raise ValueError("Answers must contain exactly the pending decision keys.")
        policy: dict[str, str] = {}
        for group in self.decisions:
            value = answers[group.decision.key] if group.status == "pending" else group.selected
            if value not in group.decision.options or not isinstance(value, str):
                raise ValueError("Answer is outside the declared options.")
            policy[group.decision.key] = value
        expected = next(trial for trial in self.trials if trial.policy == policy)
        replay = _execute(self._preview, self._input, policy, expected.id, "replay", len(self.trials))
        if replay._output != expected._output:
            raise ExplorationError("replay", expected.id, len(self.trials))
        return Resolution(self.scope, replay)


def _execute(preview: Preview, inputs: bytes, policy: dict[str, str], branch_id: str, stage: str, completed: int) -> Trial:
    started = time.perf_counter()
    try:
        output = _encode(preview(_decode(inputs), dict(policy)), MAX_RESULT_BYTES)
    except Exception:  # noqa: BLE001 -- Preserve safe stage metadata without leaking arbitrary callback text.
        raise ExplorationError(stage, branch_id, completed) from None
    return Trial(branch_id, tuple(policy.items()), output, (time.perf_counter() - started) * 1000)


def _validate_contracts(decisions: tuple[Decision, ...], questions: tuple[AgentQuestion, ...], max_branches: int) -> None:
    if type(max_branches) is not int or not 1 <= max_branches <= 256:
        raise ValueError("Branch budget must be an integer between 1 and 256.")
    if len(decisions) > 8 or any(not isinstance(decision, Decision) for decision in decisions):
        raise ValueError("Provide at most eight Decision objects.")
    keys = {decision.key for decision in decisions}
    if len(keys) != len(decisions):
        raise ValueError("Decision keys must be unique.")
    if len(questions) > 256 or any(not isinstance(question, AgentQuestion) for question in questions):
        raise ValueError("Provide at most 256 agent questions.")
    if len({question.id for question in questions}) != len(questions) or any(question.decision_key not in keys for question in questions):
        raise ValueError("Every question needs a unique ID and a registered decision key.")
    if math.prod(len(decision.options) for decision in decisions) > max_branches:
        raise ValueError("Complete policy space exceeds the branch budget; no previews were executed.")


def _compile(decision: Decision, trials: tuple[Trial, ...], questions: tuple[AgentQuestion, ...]) -> CompiledDecision:
    contexts: dict[tuple[tuple[str, str], ...], list[Trial]] = {}
    for trial in trials:
        context = tuple((key, value) for key, value in trial._policy if key != decision.key)
        contexts.setdefault(context, []).append(trial)
    witnesses: tuple[str, ...] = ()
    checked = 0
    for variants in contexts.values():
        for variant in variants[1:]:
            checked += 1
            if variant._output != variants[0]._output and not witnesses:
                witnesses = (variants[0].id, variant.id)
    return CompiledDecision(
        decision=decision,
        status="pending" if witnesses else "auto",
        selected=None if witnesses else decision.options[0],
        question_ids=tuple(question.id for question in questions if question.decision_key == decision.key),
        witnesses=witnesses,
        comparisons_checked=checked,
    )


def explore(
    *,
    adapter: str,
    inputs: JsonValue,
    decisions: Sequence[Decision],
    preview: Preview,
    questions: Sequence[AgentQuestion] = (),
    max_branches: int = 32,
) -> Exploration:
    """Execute pure previews for every policy; only complete evidence can resolve a choice."""
    started = time.perf_counter()
    contracts, trace = tuple(decisions), tuple(questions)
    _validate_contracts(contracts, trace, max_branches)
    if not _text(adapter, 200) or not callable(preview):
        raise ValueError("An adapter/version identifier and callable preview are required.")
    snapshot = _encode(inputs, MAX_INPUT_BYTES)
    signature = {
        "adapter": adapter,
        "input_hash": _hash(snapshot),
        "decisions": [{"key": d.key, "prompt": d.prompt, "options": list(d.options)} for d in contracts],
    }
    scope = _hash(_encode(signature, MAX_INPUT_BYTES))
    trials: list[Trial] = []
    stored_bytes = 0
    for values in itertools.product(*(decision.options for decision in contracts)):
        policy = dict(zip((decision.key for decision in contracts), values, strict=True))
        branch_id = _hash(_encode({"scope": scope, "policy": policy}, MAX_INPUT_BYTES))[:16]
        trial = _execute(preview, snapshot, policy, branch_id, "preview", len(trials))
        stored_bytes += len(trial._output)
        if stored_bytes > MAX_TOTAL_BYTES:
            raise ExplorationError("budget", branch_id, len(trials))
        trials.append(trial)
    evidence = tuple(trials)
    compiled = tuple(_compile(decision, evidence, trace) for decision in contracts)
    return Exploration(adapter, scope, compiled, trace, evidence, (time.perf_counter() - started) * 1000, snapshot, preview)
