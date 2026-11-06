"""Trusted JSON/CSV export previews with conditional presentation choices."""

import csv
import io
import json
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from askless.sdk import Decision, _encode

EXPORT_ADAPTER = "file-export/v1"
MAX_EXPORT_INPUT = 32_768
EXPORT_DECISIONS = (
    Decision("format", "选择你要交付的文件格式", ("json", "csv")),
    Decision("separator", "CSV 使用哪种分隔符？", ("comma", "semicolon")),
    Decision("header", "CSV 包含列名吗？", ("include", "omit")),
)
SAMPLE_RECORDS: JsonValue = [{"name": "Ada", "team": "Systems", "score": 98}, {"name": "Lin", "team": "Research", "score": 94}]


def validate_records(data: JsonValue) -> list[dict[str, JsonValue]]:
    _encode(data, MAX_EXPORT_INPUT)
    if not isinstance(data, list) or not 1 <= len(data) <= 100 or any(not isinstance(row, dict) for row in data):
        raise ValueError("输入需要是包含 1–100 行的 JSON 对象数组。")
    rows = cast(list[dict[str, JsonValue]], data)
    columns = set(rows[0])
    if not 1 <= len(columns) <= 20 or any(not key.strip() or len(key.encode()) > 64 for key in columns):
        raise ValueError("需要 1–20 个非空列名，每个最多 64 UTF-8 字节。")
    if any(set(row) != columns or any(isinstance(value, (list, dict)) for value in row.values()) for row in rows):
        raise ValueError("每行需要相同的列，单元格只支持字符串、数值、布尔值或 null。")
    return rows


def _unique(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError("JSON 中包含重复字段。")
    return dict(pairs)


def read_records(path: Path) -> JsonValue:
    with path.open("rb") as source:
        raw = source.read(MAX_EXPORT_INPUT + 1)
    return parse_records(raw)


def parse_records(raw: bytes) -> JsonValue:
    if len(raw) > MAX_EXPORT_INPUT:
        raise ValueError("输入文件最大 32 KiB。")
    try:
        data = cast(JsonValue, json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique))
    except (ValueError, UnicodeError):
        raise ValueError("输入必须是 UTF-8 JSON，且字段不可重复。") from None
    validate_records(data)
    return data


def _cell(value: JsonValue) -> str:
    text = value if isinstance(value, str) else "" if value is None else json.dumps(value, ensure_ascii=False)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")) else text


def preview_export(data: JsonValue, policy: dict[str, str]) -> JsonValue:
    if set(policy) != {decision.key for decision in EXPORT_DECISIONS} or any(policy[d.key] not in d.options for d in EXPORT_DECISIONS):
        raise ValueError("导出策略不符合已注册选项。")
    rows = validate_records(data)
    columns = sorted(rows[0])
    if policy["format"] == "json":
        text = json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        mime, name = "application/json", "records.json"
    else:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter="," if policy["separator"] == "comma" else ";")
        if policy["header"] == "include":
            writer.writerow([_cell(column) for column in columns])
        writer.writerows([_cell(row[column]) for column in columns] for row in rows)
        text, mime, name = stream.getvalue(), "text/csv", "records.csv"
    column_values: list[JsonValue] = list(columns)
    return {"rows": len(rows), "columns": column_values, "artifact": {"name": name, "media_type": mime, "text": text, "bytes": len(text.encode("utf-8"))}}
