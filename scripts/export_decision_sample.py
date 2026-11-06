"""Generate a complete, replay-verified file-export demo for GitHub Pages."""

import json
from pathlib import Path

from pydantic import JsonValue

from askless.exporter import EXPORT_ADAPTER, EXPORT_DECISIONS, preview_export, read_records
from askless.sdk import DecisionProgress, explore


def stages(progress: DecisionProgress) -> list[dict[str, JsonValue]]:
    result = progress.resolve(inputs=progress.exploration.inputs).output if not progress.pending else None
    current: dict[str, JsonValue] = {
        "answers": dict(progress.answers),
        "decisions": [
            {"key": group.decision.key, "status": group.status, "selected": group.selected, "witnesses": list(group.witnesses)} for group in progress.decisions
        ],
        "result": result,
    }
    descendants: list[dict[str, JsonValue]] = []
    if progress.pending:
        decision = progress.pending[0].decision
        for option in decision.options:
            descendants.extend(stages(progress.answer(decision.key, option)))
    return [current, *descendants]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    data = read_records(root / "examples/records.json")
    exploration = explore(adapter=EXPORT_ADAPTER, inputs=data, decisions=EXPORT_DECISIONS, preview=preview_export)
    sample = {
        "adapter": exploration.adapter,
        "scope": exploration.scope,
        "input": data,
        "trials": [{"id": trial.id, "policy": trial.policy, "output": trial.output, "output_hash": trial.output_hash} for trial in exploration.trials],
        "stages": stages(exploration.progress()),
    }
    (root / "web/site/exports.json").write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
