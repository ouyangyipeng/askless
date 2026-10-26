import json
from pathlib import Path

from askless.engine import explore, parse_csv


def test_order_sample_matches_every_sdk_branch() -> None:
    from askless.orders import ORDER_ADAPTER, ORDER_DECISIONS, load_orders, preview_orders
    from askless.sdk import explore as explore_decisions

    root = Path(__file__).resolve().parents[1]
    inputs = load_orders(root / "examples/orders.json")
    result = explore_decisions(adapter=ORDER_ADAPTER, inputs=inputs, decisions=ORDER_DECISIONS, preview=preview_orders)
    saved = json.loads((root / "web/site/orders.json").read_text())
    assert saved["input"] == inputs
    assert saved["scope"] == result.scope
    assert saved["trials"] == [{"id": trial.id, "policy": trial.policy, "output": trial.output, "output_hash": trial.output_hash} for trial in result.trials]
    assert saved["decisions"] == [
        {"key": group.decision.key, "prompt": group.decision.prompt, "status": group.status, "comparisons_checked": group.comparisons_checked}
        for group in result.decisions
    ]


def test_published_sample_matches_real_executor() -> None:
    root = Path(__file__).resolve().parents[1]
    dataset = parse_csv((root / "examples/contacts.csv").read_text())
    saved = json.loads((root / "web/site/sample.json").read_text())
    assert saved["scope"] == dataset.scope
    assert saved["input_rows"] == len(dataset.rows)
    assert saved["trials"] == [trial.model_dump(mode="json", exclude={"elapsed_ms"}) for trial in explore(dataset)]
