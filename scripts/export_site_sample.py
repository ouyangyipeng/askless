"""Export deterministic sample outcomes for the static website."""

import json
from pathlib import Path

from askless.engine import explore, parse_csv


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    dataset = parse_csv((root / "examples/contacts.csv").read_text())
    sample = {
        "scope": dataset.scope,
        "input_rows": len(dataset.rows),
        "trials": [trial.model_dump(mode="json", exclude={"elapsed_ms"}) for trial in explore(dataset)],
    }
    target = root / "web/site/sample.json"
    target.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
