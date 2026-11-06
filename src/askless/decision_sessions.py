"""Transactional, restartable sessions for trusted file-export previews."""

import secrets
import sqlite3
from collections.abc import Callable, Generator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import JsonValue

from askless.decision_models import AgentStep, DecisionEvent, DecisionRun, ExportArtifact
from askless.exporter import EXPORT_ADAPTER, EXPORT_DECISIONS, MAX_EXPORT_INPUT, preview_export, read_records, validate_records
from askless.sdk import AgentQuestion, ExplorationError, _encode, _hash, explore
from askless.snapshot import Snapshot, restore_exploration, save_exploration, trial_data
from askless.store import Conflict


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _identifier(value: str) -> None:
    if not value or len(value) > 100 or any(not (char.isascii() and (char.isalnum() or char in "_-")) for char in value):
        raise ValueError("请求 ID 需要 1–100 个 ASCII 字母、数字、下划线或连字符。")


def _event(run: DecisionRun, label: str, detail: str) -> None:
    run.events.append(DecisionEvent(at=_now(), label=label, detail=detail))


def _current_input(run: DecisionRun) -> JsonValue:
    if run.source_path is None:
        return run.inputs
    try:
        data = read_records(Path(run.source_path))
        if _hash(_encode(data, MAX_EXPORT_INPUT)) == run.input_hash:
            return data
    except (OSError, ValueError):
        pass
    run.status, run.error = "stale", "输入文件已变化或无法读取。请基于当前文件重新预览。"
    _event(run, "输入已过期", run.error)
    return None


class DecisionSessions:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS decision_sessions (id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL)"
            )

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    @contextmanager
    def agent_turn(self) -> Generator[None, None, None]:
        # A separate SQLite lock keeps slow model calls from blocking human answers.
        path = self.path.with_name(self.path.stem + ".agent-lock.sqlite3")
        with closing(sqlite3.connect(path, timeout=0)) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as error:
                if error.sqlite_errorcode not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                    raise
                raise Conflict("此数据目录中已有 Agent 正在处理。请等待当前阶段完成后重试。") from None
            try:
                yield
            finally:
                connection.rollback()

    def find_request(self, request_id: str) -> DecisionRun | None:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT data FROM decision_sessions WHERE request_id=?", (request_id,)).fetchone()
        return DecisionRun.model_validate_json(row[0]) if row else None

    @staticmethod
    def _load(connection: sqlite3.Connection, run_id: str) -> DecisionRun:
        row = connection.execute("SELECT data FROM decision_sessions WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return DecisionRun.model_validate_json(row[0])

    @staticmethod
    def _serialize(run: DecisionRun) -> str:
        payload = run.model_dump_json()
        if len(payload.encode("utf-8")) > 8_388_608:
            raise ValueError("会话证据超过 8 MiB。")
        return payload

    @staticmethod
    def _capacity(connection: sqlite3.Connection) -> None:
        if connection.execute("SELECT COUNT(*) FROM decision_sessions").fetchone()[0] >= 50:
            raise Conflict("已保留 50 次预览，请先清理不需要的会话。")
        active = connection.execute("SELECT COUNT(*) FROM decision_sessions WHERE json_extract(data,'$.status') IN ('ready','chosen')").fetchone()[0]
        if active >= 2:
            raise Conflict("最多保留两个未完成会话，请完成或删除现有会话。")

    def create(
        self,
        title: str,
        inputs: JsonValue,
        request_id: str,
        *,
        source_path: Path | None = None,
        owner: Literal["workbench", "mcp"] = "workbench",
        max_branches: int = 8,
    ) -> DecisionRun:
        _identifier(request_id)
        if not title.strip() or len(title) > 2000:
            raise ValueError("任务描述需要 1–2,000 个字符。")
        validate_records(inputs)
        input_hash = _hash(_encode(inputs, MAX_EXPORT_INPUT))
        path = str(source_path.resolve()) if source_path else None
        request_hash = _hash(_encode({"title": title, "input_hash": input_hash, "source_path": path, "owner": owner, "budget": max_branches}, 32_768))
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT id FROM decision_sessions WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                run = self._load(connection, existing[0])
                if run.request_hash != request_hash:
                    raise Conflict("同一请求 ID 已用于不同的预览。")
                return run
            self._capacity(connection)
            run = DecisionRun(
                id=secrets.token_hex(16),
                request_id=request_id,
                request_hash=request_hash,
                title=title.strip(),
                created_at=_now(),
                inputs=inputs,
                input_hash=input_hash,
                source_path=path,
                owner=owner,
            )
            if _current_input(run) is not None:
                self._prepare(run, max_branches)
            connection.execute("INSERT INTO decision_sessions VALUES (?,?,?,?)", (run.id, request_id, run.created_at, self._serialize(run)))
            return run

    @staticmethod
    def _prepare(run: DecisionRun, max_branches: int) -> None:
        try:
            experiment = explore(
                adapter=EXPORT_ADAPTER,
                inputs=run.inputs,
                decisions=EXPORT_DECISIONS,
                preview=preview_export,
                max_branches=max_branches,
                questions=tuple(AgentQuestion(f"export-{d.key}", run.owner, d.key, d.prompt) for d in EXPORT_DECISIONS),
            )
            run.snapshot = Snapshot.model_validate(save_exploration(experiment))
            run.status = "ready" if experiment.pending else "chosen"
            _event(run, "预览已准备好", f"已完成 {len(experiment.trials)} 个策略组合。选择后继续检查剩余问题。")
        except (ExplorationError, ValueError) as error:
            run.status = "failed"
            run.error = str(error)
            if isinstance(error, ExplorationError):
                run.partial_trials = [trial_data(trial) for trial in error.trials]
            _event(run, "预览停止", "预算或执行校验失败；已完成的证据保留。")

    def get(self, run_id: str) -> DecisionRun:
        with closing(self.connect()) as connection:
            return self._load(connection, run_id)

    def _update(self, run_id: str, change: Callable[[DecisionRun], bool], *, bump_revision: bool = True) -> DecisionRun:
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            run = self._load(connection, run_id)
            if change(run):
                run.revision += int(bump_revision)
                connection.execute("UPDATE decision_sessions SET data=? WHERE id=?", (self._serialize(run), run_id))
            return run

    def answer(self, run_id: str, key: str, value: str, revision: int, operation_id: str) -> DecisionRun:
        _identifier(operation_id)
        operation_hash = _hash(_encode({"key": key, "value": value, "revision": revision}, 4096))

        def apply(run: DecisionRun) -> bool:
            if operation_id in run.operations:
                if run.operations[operation_id] != operation_hash:
                    raise Conflict("同一回答请求 ID 已被用于其他内容。")
                return False
            if run.revision != revision or run.status != "ready" or run.snapshot is None:
                raise Conflict("会话状态已变化，请刷新后继续。")
            if _current_input(run) is None:
                return True
            progress = restore_exploration(cast(JsonValue, run.snapshot.model_dump(mode="json")), preview_export).progress(run.answers)
            refined = progress.answer(key, value)
            run.answers = refined.answers
            run.operations[operation_id] = operation_hash
            run.status = "ready" if refined.pending else "chosen"
            eliminated = len(progress.pending) - len(refined.pending) - 1
            _event(run, "选择已确认", f"{key} = {value}。另有 {eliminated} 项选择因结果等价而消除。")
            return True

        return self._update(run_id, apply)

    def complete(self, run_id: str, revision: int) -> DecisionRun:
        def apply(run: DecisionRun) -> bool:
            if run.status == "completed":
                return False
            if run.status != "chosen" or run.revision != revision or run.snapshot is None:
                raise Conflict("请先完成待定选择，再恢复执行。")
            current = _current_input(run)
            if current is None:
                return True
            try:
                progress = restore_exploration(cast(JsonValue, run.snapshot.model_dump(mode="json")), preview_export).progress(run.answers)
                run.result = trial_data(progress.resolve(inputs=current).trial)
                run.status = "completed"
                _event(run, "已复算并验证", "选定策略重新执行，产物与已预览结果完全一致。")
            except (ExplorationError, ValueError):
                run.status, run.error = "failed", "复算结果与预览不一致或证据校验失败，请重新预览。"
                _event(run, "恢复停止", run.error)
            return True

        return self._update(run_id, apply)

    def record_agent_step(self, run_id: str, step: AgentStep) -> DecisionRun:
        def apply(run: DecisionRun) -> bool:
            existing = next((s for s in run.agent_steps if s.id == step.id), None)
            if existing:
                if existing != step:
                    raise Conflict("Agent 步骤 ID 已对应其他记录。")
                return False
            if len(run.agent_steps) >= 2:
                raise Conflict("已记录本次 Agent 的两个阶段。")
            run.agent_steps.append(step)
            _event(run, "真实模型调用", f"{step.tool} · {step.requests} 次请求 · {step.input_tokens + step.output_tokens} tokens")
            return True

        return self._update(run_id, apply, bump_revision=False)

    def list(self) -> list[dict[str, JsonValue]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT id, json_extract(data,'$.title'), json_extract(data,'$.status'), created_at, json_extract(data,'$.owner') FROM decision_sessions ORDER BY created_at DESC"
            ).fetchall()
        return [{"id": row[0], "title": row[1], "status": row[2], "created_at": row[3], "owner": row[4]} for row in rows]

    def delete(self, run_id: str) -> None:
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            self._load(connection, run_id)
            connection.execute("DELETE FROM decision_sessions WHERE id=?", (run_id,))

    def artifact(self, run_id: str) -> ExportArtifact:
        run = self.get(run_id)
        if run.status != "completed" or run.result is None or not isinstance(run.result.output, dict):
            raise Conflict("会话尚无通过复算的产物。")
        artifact = ExportArtifact.model_validate(run.result.output.get("artifact"))
        if artifact.bytes != len(artifact.text.encode("utf-8")):
            raise ValueError("产物字节数校验失败。")
        return artifact

    def view(self, run_id: str) -> dict[str, JsonValue]:
        run = self.get(run_id)
        result = cast(dict[str, JsonValue], run.model_dump(mode="json", exclude={"source_path", "request_hash", "operations", "snapshot"}))
        result["source_name"] = Path(run.source_path).name if run.source_path else "工作台输入"
        result["decisions"], result["pending"], result["trials"] = [], [], []
        result["scope"] = run.snapshot.scope if run.snapshot else None
        if run.snapshot:
            experiment = restore_exploration(cast(JsonValue, run.snapshot.model_dump(mode="json")), preview_export)
            progress = experiment.progress(run.answers)
            result["decisions"] = [
                {
                    "key": g.decision.key,
                    "prompt": g.decision.prompt,
                    "options": list(g.decision.options),
                    "status": g.status,
                    "selected": g.selected,
                    "witnesses": list(g.witnesses),
                    "comparisons_checked": g.comparisons_checked,
                }
                for g in progress.decisions
            ]
            result["pending"] = [g.decision.key for g in progress.pending]
            result["trials"] = [cast(JsonValue, trial.model_dump(mode="json")) for trial in run.snapshot.trials]
        return result
