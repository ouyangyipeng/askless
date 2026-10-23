from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DecisionKey(StrEnum):
    duplicates = "duplicates"
    invalid = "invalid"
    email_case = "email_case"


class Policy(Model):
    duplicates: Literal["first", "last"] = "first"
    invalid: Literal["quarantine", "block"] = "quarantine"
    email_case: Literal["preserve", "lower"] = "preserve"


class Dataset(Model):
    scope: str
    columns: list[str]
    rows: list[dict[str, str]]


class RejectedRow(Model):
    line: int
    reason: str
    row: dict[str, str]


class Evidence(Model):
    id: str
    scope: str
    policy: Policy
    rows: list[dict[str, str]]
    quarantined: list[RejectedRow]
    blocked: bool
    duplicate_count: int
    elapsed_ms: float
    output_hash: str


class Question(Model):
    id: str = Field(min_length=1, max_length=100)
    agent_id: str = Field(min_length=1, max_length=40)
    decision_key: DecisionKey
    scope: str
    prompt: str = Field(min_length=1, max_length=500)


class Option(Model):
    value: str
    label: str
    description: str


class DecisionSpec(Model):
    key: DecisionKey
    title: str
    context: str
    options: list[Option]


class DecisionGroup(Model):
    key: DecisionKey
    spec: DecisionSpec
    scope: str
    question_ids: list[str]
    agent_ids: list[str]
    status: Literal["auto", "pending", "answered"]
    selected: str | None = None
    reason: str
    witnesses: list[str]
    comparisons_checked: int


SPECS: dict[DecisionKey, DecisionSpec] = {
    DecisionKey.duplicates: DecisionSpec(
        key=DecisionKey.duplicates,
        title="重复联系人，保留哪一条？",
        context="按去除首尾空白、忽略大小写后的 email 识别重复。选择会改变保留下来的联系人信息。",
        options=[
            Option(value="first", label="保留首次记录", description="同一 email 保留 CSV 中最先出现的一行。"),
            Option(value="last", label="保留末次记录", description="同一 email 保留 CSV 中最后出现的一行；按文件顺序，不推断更新时间。"),
        ],
    ),
    DecisionKey.invalid: DecisionSpec(
        key=DecisionKey.invalid,
        title="遇到无效邮箱，这批数据怎么处理？",
        context="无效记录始终保留在隔离报告中，供你检查和修复。",
        options=[
            Option(value="quarantine", label="隔离异常，继续导入", description="导出有效记录，并单独保留异常记录。"),
            Option(value="block", label="暂停整批导入", description="任意邮箱无效时整批阻断，修正输入后重新运行。"),
        ],
    ),
    DecisionKey.email_case: DecisionSpec(
        key=DecisionKey.email_case,
        title="导出的邮箱保留大小写吗？",
        context="只影响导出邮箱的显示形式；重复识别始终忽略大小写。",
        options=[
            Option(value="preserve", label="保留原样", description="保留有效邮箱的原始大小写。"),
            Option(value="lower", label="统一小写", description="将导出邮箱转为小写。"),
        ],
    ),
}
