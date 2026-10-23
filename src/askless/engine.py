import csv
import hashlib
import io
import itertools
import json
import time

from email_validator import EmailNotValidError, validate_email

from askless.models import SPECS, Dataset, DecisionGroup, DecisionKey, Evidence, Policy, Question, RejectedRow

MAX_BYTES = 262_144
MAX_ROWS = 2_000
MAX_COLUMN_BYTES = 128
MAX_DATASET_BYTES = 524_288


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def parse_csv(text: str) -> Dataset:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("CSV 最大为 256 KiB。")
    try:
        table = list(csv.reader(io.StringIO(text.lstrip("\ufeff")), strict=True))
    except csv.Error as error:
        raise ValueError("CSV 引号或格式无效。") from error
    if len(table) < 2 or len(table) - 1 > MAX_ROWS:
        raise ValueError("CSV 需包含标题和 1–2,000 行数据。")
    columns = [cell.strip() for cell in table[0]]
    if "email" not in columns or len(columns) != len(set(columns)) or any(not c for c in columns) or len(columns) > 30:
        raise ValueError("CSV 需包含唯一的 email 列，标题不可为空或重复，最多 30 列。")
    if any(len(column.encode("utf-8")) > MAX_COLUMN_BYTES for column in columns):
        raise ValueError("每个列名最多 128 UTF-8 字节。")
    if any(len(row) != len(columns) for row in table[1:]):
        raise ValueError("每行数据的列数必须与标题相同。")
    rows = [dict(zip(columns, row, strict=True)) for row in table[1:]]
    if len(json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False).encode("utf-8")) > MAX_DATASET_BYTES:
        raise ValueError("展开后的数据超过 512 KiB，请缩短列名或分批导入。")
    return Dataset(scope=digest({"columns": columns, "rows": rows}), columns=columns, rows=rows)


def valid_email(email: str) -> bool:
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        return False
    return True


def execute(dataset: Dataset, policy: Policy) -> Evidence:
    started = time.perf_counter()
    selected: dict[str, dict[str, str]] = {}
    rejected: list[RejectedRow] = []
    duplicates = 0
    for line, source in enumerate(dataset.rows, 2):
        row = dict(source)
        email = row["email"].strip()
        if not valid_email(email):
            rejected.append(RejectedRow(line=line, reason="邮箱为空或格式无效", row=row))
            continue
        identity = email.casefold()
        row["email"] = email.lower() if policy.email_case == "lower" else email
        if identity in selected:
            duplicates += 1
            if policy.duplicates == "first":
                continue
        selected[identity] = row
    blocked = policy.invalid == "block" and bool(rejected)
    rows = [] if blocked else list(selected.values())
    observed = {"rows": rows, "quarantined": [r.model_dump() for r in rejected], "blocked": blocked}
    return Evidence(
        id=digest({"scope": dataset.scope, "policy": policy.model_dump()})[:16],
        scope=dataset.scope,
        policy=policy,
        rows=rows,
        quarantined=rejected,
        blocked=blocked,
        duplicate_count=duplicates,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        output_hash=digest(observed),
    )


def policies() -> list[Policy]:
    keys = list(SPECS)
    return [Policy.model_validate(dict(zip(keys, values, strict=True))) for values in itertools.product(*[[o.value for o in SPECS[k].options] for k in keys])]


def explore(dataset: Dataset) -> list[Evidence]:
    return [execute(dataset, policy) for policy in policies()]


def differing_pair(key: DecisionKey, trials: list[Evidence]) -> tuple[list[str], int]:
    buckets: dict[str, list[Evidence]] = {}
    for trial in trials:
        other = trial.policy.model_dump(exclude={key})
        buckets.setdefault(digest(other), []).append(trial)
    witnesses: list[str] = []
    for pair in buckets.values():
        if pair[0].output_hash != pair[1].output_hash and not witnesses:
            witnesses = [pair[0].id, pair[1].id]
    return witnesses, len(buckets)


def compile_questions(questions: list[Question], trials: list[Evidence], scope: str) -> list[DecisionGroup]:
    if any(q.scope != scope for q in questions) or any(t.scope != scope for t in trials):
        raise ValueError("Question/evidence scope mismatch")
    if len({q.id for q in questions}) != len(questions):
        raise ValueError("Question IDs must be unique")
    expected = {digest(p.model_dump()) for p in policies()}
    if len(trials) != len(expected) or {digest(t.policy.model_dump()) for t in trials} != expected:
        raise ValueError("Evidence must cover the complete policy space")
    groups: list[DecisionGroup] = []
    for key, spec in SPECS.items():
        relevant = [q for q in questions if q.decision_key == key]
        if not relevant:
            raise ValueError("Every executable decision requires a question")
        witnesses, checked = differing_pair(key, trials)
        groups.append(
            DecisionGroup(
                key=key,
                spec=spec,
                scope=scope,
                question_ids=[q.id for q in relevant],
                agent_ids=sorted({q.agent_id for q in relevant}),
                status="pending" if witnesses else "auto",
                selected=None if witnesses else spec.options[0].value,
                reason="真实执行产生不同结果，保留给你决定。"
                if witnesses
                else f"覆盖其他策略的 {checked} 种组合，两种选择的输出、隔离记录和阻断状态均相同；仅适用于这批数据。",
                witnesses=witnesses,
                comparisons_checked=checked,
            )
        )
    return groups


def export_csv(rows: list[dict[str, str]], columns: list[str]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)

    def safe(value: str) -> str:
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value

    writer.writerow([safe(c) for c in columns])
    writer.writerows([safe(row.get(c, "")) for c in columns] for row in rows)
    return output.getvalue()


def profile(dataset: Dataset) -> dict[str, int]:
    result = execute(dataset, Policy())
    return {
        "rows": len(dataset.rows),
        "columns": len(dataset.columns),
        "invalid_emails": len(result.quarantined),
        "duplicate_emails": result.duplicate_count,
        "uppercase_emails": sum(r["email"] != r["email"].lower() for r in dataset.rows),
    }
