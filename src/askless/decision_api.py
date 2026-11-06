"""Same-origin HTTP surface for durable decision sessions."""

from pathlib import Path
from typing import Self, cast

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import Field, JsonValue, model_validator

from askless.decision_sessions import DecisionSessions
from askless.exporter import SAMPLE_RECORDS, parse_records
from askless.models import Model


class CreateDecision(Model):
    title: str = Field(min_length=1, max_length=2000)
    inputs: JsonValue = None
    input_text: str | None = Field(default=None, max_length=32_768)
    request_id: str = Field(min_length=1, max_length=100)
    max_branches: int = Field(default=8, ge=1, le=8, strict=True)

    @model_validator(mode="after")
    def one_input(self) -> Self:
        if ("inputs" in self.model_fields_set) == ("input_text" in self.model_fields_set):
            raise ValueError("提供 inputs 或 input_text 中的一项。")
        if "input_text" in self.model_fields_set and self.input_text is None:
            raise ValueError("input_text 需要 JSON 文本。")
        return self


class DecisionAnswer(Model):
    key: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=80)
    revision: int = Field(ge=0, strict=True)
    request_id: str = Field(min_length=1, max_length=100)


class CompleteDecision(Model):
    revision: int = Field(ge=0, strict=True)


def decision_router(data_dir: Path) -> APIRouter:
    sessions = DecisionSessions(data_dir / "decisions.sqlite3")
    router = APIRouter(prefix="/api/decisions")

    @router.get("/config")
    def configuration() -> dict[str, JsonValue]:
        return {"sample": SAMPLE_RECORDS, "max_input_bytes": 32_768, "max_branches": 8, "max_open_sessions": 2}

    @router.get("")
    def history() -> list[dict[str, JsonValue]]:
        return sessions.list()

    @router.post("", status_code=201)
    def create(body: CreateDecision) -> dict[str, JsonValue]:
        inputs = parse_records(body.input_text.encode("utf-8")) if body.input_text is not None else body.inputs
        run = sessions.create(body.title, inputs, body.request_id, max_branches=body.max_branches)
        return sessions.view(run.id)

    @router.get("/{run_id}")
    def get(run_id: str) -> dict[str, JsonValue]:
        return sessions.view(run_id)

    @router.post("/{run_id}/answer")
    def answer(run_id: str, body: DecisionAnswer) -> dict[str, JsonValue]:
        sessions.answer(run_id, body.key, body.value, body.revision, body.request_id)
        return sessions.view(run_id)

    @router.post("/{run_id}/complete")
    def complete(run_id: str, body: CompleteDecision) -> dict[str, JsonValue]:
        sessions.complete(run_id, body.revision)
        return sessions.view(run_id)

    @router.delete("/{run_id}", status_code=204)
    def delete(run_id: str) -> Response:
        sessions.delete(run_id)
        return Response(status_code=204)

    @router.get("/{run_id}/artifact")
    def artifact(run_id: str) -> Response:
        result = sessions.artifact(run_id)
        return Response(result.text, media_type=result.media_type, headers={"Content-Disposition": f'attachment; filename="{result.name}"'})

    @router.get("/{run_id}/evidence")
    def evidence(run_id: str) -> dict[str, JsonValue]:
        run = sessions.get(run_id)
        return cast(dict[str, JsonValue], run.model_dump(mode="json", exclude={"source_path", "request_hash", "operations"}))

    return router
