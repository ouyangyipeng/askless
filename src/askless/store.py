import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from askless.session import Run

ACTIVE_STATUSES = {"planning", "exploring", "applying"}
MAX_RUN_BYTES = 8_388_608


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with closing(self.connect()) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL)")

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    @staticmethod
    def _check_capacity(connection: sqlite3.Connection) -> None:
        count = connection.execute("SELECT COUNT(*) FROM runs WHERE json_extract(data, '$.status') IN ('planning', 'exploring', 'applying')").fetchone()[0]
        if count >= 2:
            raise Conflict("已有两次运行进行中，请等待完成。")

    @staticmethod
    def _serialize(run: Run) -> str:
        payload = run.model_dump_json()
        if len(payload.encode("utf-8")) > MAX_RUN_BYTES:
            raise ValueError("本次运行的证据超过 8 MiB，请缩小输入数据。")
        return payload

    def create(self, run: Run) -> None:
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] >= 50:
                raise ValueError("本地已保存 50 次运行，请先从历史记录删除不需要的运行。")
            self._check_capacity(connection)
            connection.execute("INSERT INTO runs VALUES (?, ?, ?)", (run.id, run.created_at, self._serialize(run)))

    def get(self, run_id: str) -> Run:
        with closing(self.connect()) as connection, connection:
            row = connection.execute("SELECT data FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return Run.model_validate_json(row[0])

    def update(self, run_id: str, change: Callable[[Run], None]) -> Run:
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT data FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            run = Run.model_validate_json(row[0])
            was_active = run.status in ACTIVE_STATUSES
            change(run)
            if not was_active and run.status in ACTIVE_STATUSES:
                self._check_capacity(connection)
            run.revision += 1
            connection.execute("UPDATE runs SET data = ? WHERE id = ?", (self._serialize(run), run_id))
            return run

    def list(self) -> list[dict[str, str | int]]:
        with closing(self.connect()) as connection, connection:
            rows = connection.execute(
                "SELECT id, json_extract(data, '$.title'), json_extract(data, '$.mode'), json_extract(data, '$.status'), "
                "created_at, json_array_length(data, '$.dataset.rows') FROM runs ORDER BY created_at DESC"
            ).fetchall()
        return [dict(zip(["id", "title", "mode", "status", "created_at", "rows"], row, strict=True)) for row in rows]

    def delete(self, run_id: str) -> None:
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT data FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            if Run.model_validate_json(row[0]).status in {"planning", "exploring", "applying"}:
                raise Conflict("运行进行中，完成后可删除。")
            connection.execute("DELETE FROM runs WHERE id = ?", (run_id,))

    def interrupt_inflight(self) -> None:
        for item in self.list():
            if item["status"] in {"planning", "exploring", "applying"}:

                def interrupt(run: Run) -> None:
                    run.status = "interrupted"
                    run.error = "服务在运行结束前停止。已完成的证据保留，请新建运行。"

                self.update(str(item["id"]), interrupt)
