import json
from pathlib import Path

from askless.engine import explore, parse_csv


def test_published_sample_matches_real_executor() -> None:
    root = Path(__file__).resolve().parents[1]
    dataset = parse_csv((root / "examples/contacts.csv").read_text())
    saved = json.loads((root / "web/site/sample.json").read_text())
    assert saved["scope"] == dataset.scope
    assert saved["input_rows"] == len(dataset.rows)
    assert saved["trials"] == [trial.model_dump(mode="json", exclude={"elapsed_ms"}) for trial in explore(dataset)]
