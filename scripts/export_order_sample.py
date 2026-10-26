"""Generate the website's order outputs from the installed Python SDK."""

import json
from pathlib import Path

from askless.orders import ORDER_ADAPTER, ORDER_DECISIONS, load_orders, preview_orders
from askless.sdk import explore


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    inputs = load_orders(root / "examples/orders.json")
    experiment = explore(adapter=ORDER_ADAPTER, inputs=inputs, decisions=ORDER_DECISIONS, preview=preview_orders)
    sample = {
        "adapter": experiment.adapter,
        "scope": experiment.scope,
        "input": inputs,
        "decisions": [
            {"key": group.decision.key, "prompt": group.decision.prompt, "status": group.status, "comparisons_checked": group.comparisons_checked}
            for group in experiment.decisions
        ],
        "trials": [{"id": trial.id, "policy": trial.policy, "output": trial.output, "output_hash": trial.output_hash} for trial in experiment.trials],
    }
    (root / "web/site/orders.json").write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
