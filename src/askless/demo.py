"""Run an order-data agent and export a complete local decision report."""

import argparse
import asyncio
import sys
import time
import uuid
from pathlib import Path
from typing import Literal

from askless.llm import Completion, LLMClient, ProviderError, Settings
from askless.order_agent import propose_order_questions
from askless.orders import ORDER_ADAPTER, ORDER_DECISIONS, load_orders, preview_orders
from askless.reporting import build_report, write_report
from askless.sdk import AgentQuestion, Exploration, ExplorationError, explore


def _answers(values: list[str]) -> dict[str, str]:
    answers: dict[str, str] = {}
    contracts = {decision.key: decision for decision in ORDER_DECISIONS}
    for value in values:
        key, separator, option = value.partition("=")
        if not separator or key not in contracts or option not in contracts[key].options:
            raise ValueError("Use --choose key=value with a declared order policy option.")
        if key in answers:
            raise ValueError("Each --choose decision may appear only once.")
        answers[key] = option
    return answers


def _collect(experiment: Exploration, answers: dict[str, str]) -> bool:
    pending = {group.decision.key for group in experiment.pending}
    if not set(answers).issubset(pending):
        raise ValueError("Only pending decisions need --choose answers; equivalent decisions are already resolved.")
    for group in experiment.pending:
        decision = group.decision
        print(f"  {decision.key}: {decision.prompt} [{', '.join(decision.options)}]")
        if decision.key in answers or not sys.stdin.isatty():
            continue
        value = input("  Your choice: ").strip()
        if value not in decision.options:
            raise ValueError("Choose one of the displayed options.")
        answers[decision.key] = value
    return set(answers) == pending


def run(args: argparse.Namespace) -> int:
    if args.output.exists():
        raise ValueError("Output directory already exists. Choose a new directory to preserve earlier evidence.")
    answers = _answers(args.choose)
    data = load_orders(args.input)
    mode: Literal["contract_replay", "live_questions"] = "live_questions" if args.live else "contract_replay"
    completion: Completion | None = None
    summary = "Order workflow. One declared question per contract; eight actual local executions."
    questions = tuple(AgentQuestion(f"orders-{d.key}", "order-agent", d.key, d.prompt) for d in ORDER_DECISIONS)
    if args.live:
        questions, completion, summary = asyncio.run(propose_order_questions(LLMClient(Settings.from_env()), data))
    experiment = explore(adapter=ORDER_ADAPTER, inputs=data, decisions=ORDER_DECISIONS, preview=preview_orders, questions=questions)
    print(f"AskLess / {mode}: {len(experiment.decisions)} declared choices -> {len(experiment.pending)} human decisions; {len(experiment.trials)} previews.")
    complete = _collect(experiment, answers)
    resolution = experiment.resolve(answers, inputs=data) if complete else None
    baseline, baseline_ms = None, 0.0
    if resolution:
        started = time.perf_counter()
        baseline = preview_orders(data, resolution.policy)
        baseline_ms = (time.perf_counter() - started) * 1000
    report = build_report(experiment, mode=mode, summary=summary, completion=completion, resolution=resolution, baseline=baseline, baseline_ms=baseline_ms)
    write_report(report, args.output)
    print(f"Report: {(args.output / 'report.html').resolve()}")
    if not complete:
        print("Awaiting decisions. Rerun with --choose key=value for every pending choice and a new --output directory.")
        return 2
    print(f"Verified: baseline and replay outputs match. Result: {(args.output / 'result.json').resolve()}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Try AskLess on a real, local order-summary workflow.")
    parser.add_argument("--input", type=Path, default=Path("examples/orders.json"), help="UTF-8 JSON orders (default: examples/orders.json in the checkout)")
    parser.add_argument("--choose", action="append", default=[], metavar="KEY=VALUE", help="Answer one pending decision; repeat for each choice")
    parser.add_argument("--live", action="store_true", help="Ask a real LLM to propose relevant questions using aggregate data only")
    parser.add_argument("--output", type=Path, default=Path("artifacts") / ("orders-" + uuid.uuid4().hex[:8]), help="A new directory for HTML/JSON evidence")
    args = parser.parse_args()
    try:
        return run(args)
    except (ValueError, OSError, ExplorationError, ProviderError, EOFError) as error:
        print(f"AskLess stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
