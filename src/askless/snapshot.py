"""Versioned, validated storage for a complete finite exploration."""

import itertools
from typing import Literal, cast

from pydantic import Field, JsonValue, ValidationError

from askless.models import Model
from askless.sdk import (
    MAX_INPUT_BYTES,
    MAX_RESULT_BYTES,
    MAX_TOTAL_BYTES,
    AgentQuestion,
    Decision,
    Exploration,
    Preview,
    Trial,
    _compile,
    _encode,
    _hash,
    _scope,
    _validate_contracts,
)


class ContractData(Model):
    key: str
    prompt: str
    options: tuple[str, ...]


class QuestionData(Model):
    id: str
    agent_id: str
    decision_key: str
    prompt: str


class TrialData(Model):
    id: str
    policy: dict[str, str]
    output: JsonValue
    output_hash: str
    elapsed_ms: float = Field(ge=0, allow_inf_nan=False)


class Snapshot(Model):
    schema_version: Literal[1] = 1
    adapter: str = Field(min_length=1, max_length=200)
    scope: str
    inputs: JsonValue
    decisions: list[ContractData] = Field(max_length=8)
    questions: list[QuestionData] = Field(max_length=256)
    trials: list[TrialData] = Field(min_length=1, max_length=256)
    elapsed_ms: float = Field(ge=0, allow_inf_nan=False)


def trial_data(trial: Trial) -> TrialData:
    return TrialData(id=trial.id, policy=trial.policy, output=trial.output, output_hash=trial.output_hash, elapsed_ms=trial.elapsed_ms)


def save_exploration(run: Exploration) -> dict[str, JsonValue]:
    snapshot = Snapshot(
        adapter=run.adapter,
        scope=run.scope,
        inputs=run.inputs,
        decisions=[ContractData(key=g.decision.key, prompt=g.decision.prompt, options=g.decision.options) for g in run.decisions],
        questions=[QuestionData(id=q.id, agent_id=q.agent_id, decision_key=q.decision_key, prompt=q.prompt) for q in run.questions],
        trials=[trial_data(trial) for trial in run.trials],
        elapsed_ms=run.elapsed_ms,
    )
    return cast(dict[str, JsonValue], snapshot.model_dump(mode="json"))


def _restore_trials(snapshot: Snapshot, contracts: tuple[Decision, ...]) -> tuple[Trial, ...]:
    keys = tuple(contract.key for contract in contracts)
    expected = set(itertools.product(*(contract.options for contract in contracts)))
    seen: set[tuple[str, ...]] = set()
    trials: list[Trial] = []
    total = 0
    for stored in snapshot.trials:
        if set(stored.policy) != set(keys):
            raise ValueError("Snapshot policy keys differ from contracts.")
        values = tuple(stored.policy[key] for key in keys)
        if values not in expected or values in seen:
            raise ValueError("Snapshot policy space is invalid or repeated.")
        seen.add(values)
        encoded = _encode(stored.output, MAX_RESULT_BYTES)
        branch_id = _hash(_encode({"scope": snapshot.scope, "policy": stored.policy}, MAX_INPUT_BYTES))[:16]
        if stored.output_hash != _hash(encoded) or stored.id != branch_id:
            raise ValueError("Snapshot evidence hash mismatch.")
        total += len(encoded)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Snapshot exceeds the total result budget.")
        trials.append(Trial(branch_id, tuple(zip(keys, values, strict=True)), encoded, stored.elapsed_ms))
    if seen != expected:
        raise ValueError("Snapshot must contain the complete policy space.")
    return tuple(trials)


def restore_exploration(data: JsonValue, preview: Preview) -> Exploration:
    _encode(data, 8_388_608)
    try:
        snapshot = Snapshot.model_validate(data)
    except ValidationError:
        raise ValueError("Exploration snapshot has an invalid schema.") from None
    contracts = tuple(Decision(d.key, d.prompt, d.options) for d in snapshot.decisions)
    questions = tuple(AgentQuestion(q.id, q.agent_id, q.decision_key, q.prompt) for q in snapshot.questions)
    _validate_contracts(contracts, questions, 256)
    inputs = _encode(snapshot.inputs, MAX_INPUT_BYTES)
    if snapshot.scope != _scope(snapshot.adapter, inputs, contracts):
        raise ValueError("Snapshot input or contract scope mismatch.")
    trials = _restore_trials(snapshot, contracts)
    groups = tuple(_compile(contract, trials, questions) for contract in contracts)
    return Exploration(snapshot.adapter, snapshot.scope, groups, questions, trials, snapshot.elapsed_ms, inputs, preview)
