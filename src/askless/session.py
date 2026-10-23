from typing import Literal

from pydantic import Field

from askless.models import Dataset, DecisionGroup, Evidence, Model, Policy, Question


class AgentState(Model):
    id: str
    name: str
    role: str
    status: str = "waiting"
    summary: str = ""


class Event(Model):
    at: str
    label: str
    detail: str


class Receipt(Model):
    agent_id: str
    summary: str
    policy: Policy
    output_hash: str
    consumed_question_ids: list[str]


class Run(Model):
    id: str
    title: str
    mode: Literal["live", "offline"]
    model: str
    created_at: str
    status: str = "planning"
    revision: int = 0
    dataset: Dataset
    agents: list[AgentState]
    questions: list[Question] = Field(default_factory=list)
    trials: list[Evidence] = Field(default_factory=list)
    groups: list[DecisionGroup] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    receipts: list[Receipt] = Field(default_factory=list)
    result: Evidence | None = None
    error: str | None = None
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


def new_agents() -> list[AgentState]:
    return [
        AgentState(id="data", name="数据工程师", role="记录一致性与数据处理"),
        AgentState(id="quality", name="质量审核员", role="异常输入与验收标准"),
        AgentState(id="delivery", name="交付负责人", role="导出结果与用户取舍"),
    ]
