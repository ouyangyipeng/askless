"""Durable state for the file-preview workflow, separate from contact runs."""

from typing import Literal

from pydantic import Field, JsonValue

from askless.models import Model
from askless.snapshot import Snapshot, TrialData


class AgentStep(Model):
    id: str = Field(min_length=1, max_length=100)
    tool: Literal["preview_export", "collect_export"]
    model: str = Field(min_length=1, max_length=200)
    summary: str = Field(max_length=600)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    requests: int = Field(ge=1, le=2)
    elapsed_ms: float = Field(default=0, ge=0, allow_inf_nan=False)


class DecisionEvent(Model):
    at: str
    label: str
    detail: str


class DecisionRun(Model):
    schema_version: Literal[1] = 1
    id: str
    request_id: str
    request_hash: str
    title: str
    created_at: str
    revision: int = 0
    status: Literal["ready", "chosen", "completed", "stale", "failed"] = "ready"
    owner: Literal["workbench", "mcp"] = "workbench"
    source_path: str | None = None
    inputs: JsonValue
    input_hash: str
    snapshot: Snapshot | None = None
    answers: dict[str, str] = Field(default_factory=dict)
    operations: dict[str, str] = Field(default_factory=dict)
    events: list[DecisionEvent] = Field(default_factory=list)
    agent_steps: list[AgentStep] = Field(default_factory=list, max_length=2)
    partial_trials: list[TrialData] = Field(default_factory=list)
    result: TrialData | None = None
    error: str | None = None


class ExportArtifact(Model):
    name: Literal["records.json", "records.csv"]
    media_type: Literal["application/json", "text/csv"]
    text: str
    bytes: int = Field(ge=0)
