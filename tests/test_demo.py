import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from askless.orders import ORDER_ADAPTER, ORDER_DECISIONS, load_orders, preview_orders
from askless.reporting import build_report, render_report
from askless.sdk import AgentQuestion, Decision, explore

ROOT = Path(__file__).resolve().parents[1]


def test_cli_completes_real_workflow_with_reproducible_report(tmp_path: Path) -> None:
    output = tmp_path / "run"
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "askless.demo",
            "--input",
            str(ROOT / "examples/orders.json"),
            "--choose",
            "duplicates=last",
            "--choose",
            "cancelled=exclude",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    report = json.loads((output / "report.json").read_text())
    assert report["status"] == "completed"
    assert report["metrics"]["registered_decisions"] == 3
    assert report["metrics"]["agent_questions"] == 3
    assert report["metrics"]["human_decisions"] == 2
    assert report["metrics"]["preview_calls"] == 8
    assert report["comparison"]["outputs_equal"] is True
    assert report["comparison"]["baseline_calls"] == 1
    assert report["comparison"]["askless_calls"] == 9
    assert report["model_usage"]["requests"] == 0
    assert report["result"]["output"]["total"] == "120.00"
    assert [(decision["status"], decision["selected"]) for decision in report["decisions"]] == [
        ("answered", "last"),
        ("answered", "exclude"),
        ("auto", "per_order"),
    ]
    assert json.loads((output / "result.json").read_text())["total"] == "120.00"
    assert "120.00" in (output / "report.html").read_text()


def test_cli_without_answers_reports_pending_in_noninteractive_mode(tmp_path: Path) -> None:
    output = tmp_path / "pending"
    run = subprocess.run(
        [sys.executable, "-m", "askless.demo", "--output", str(output)], cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False
    )
    assert run.returncode == 2
    report = json.loads((output / "report.json").read_text())
    assert report["status"] == "ready"
    assert report["result"] is None
    assert "duplicates" in run.stdout and "cancelled" in run.stdout
    assert not (output / "result.json").exists()


def test_cli_preserves_existing_output_and_rejects_duplicate_answers(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "report.json"
    sentinel.write_text("keep this")
    run = subprocess.run([sys.executable, "-m", "askless.demo", "--output", str(output)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert run.returncode == 1
    assert sentinel.read_text() == "keep this"
    duplicate = subprocess.run(
        [sys.executable, "-m", "askless.demo", "--choose", "duplicates=first", "--choose", "duplicates=last", "--output", str(tmp_path / "unused")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert duplicate.returncode == 1
    assert not (tmp_path / "unused").exists()


def test_report_escapes_agent_text_and_includes_witness_outputs() -> None:
    data = load_orders(ROOT / "examples/orders.json")
    attack = '</script><img src=x onerror="alert(1)">'
    experiment = explore(
        adapter=ORDER_ADAPTER,
        inputs=data,
        decisions=ORDER_DECISIONS,
        preview=preview_orders,
        questions=(AgentQuestion("q1", "agent", "duplicates", attack),),
    )
    report = build_report(experiment, mode="contract_replay", summary=attack)
    html = render_report(report)

    class Tags(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.tags: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            self.tags.append(tag)

    tags = Tags()
    tags.feed(html)
    assert "img" not in tags.tags and "script" not in tags.tags
    assert "&lt;img" in html
    assert "35.00" in html and "42.00" in html
    assert "125.50" in html


def test_report_baseline_equality_keeps_json_types_distinct() -> None:
    experiment = explore(adapter="types/v1", inputs=[], decisions=(Decision("mode", "Mode?", ("a", "b")),), preview=lambda data, policy: 1)
    result = experiment.resolve({}, inputs=[])
    with pytest.raises(ValueError, match="baseline"):
        build_report(experiment, mode="contract_replay", summary="Type check", resolution=result, baseline=True)


def test_null_result_requires_an_explicit_baseline_before_claiming_a_comparison() -> None:
    experiment = explore(adapter="null/v1", inputs=[], decisions=(), preview=lambda data, policy: None)
    result = experiment.resolve({}, inputs=[])
    with pytest.raises(ValueError, match="baseline"):
        build_report(experiment, mode="contract_replay", summary="Null result", resolution=result)
    report = build_report(experiment, mode="contract_replay", summary="Null result", resolution=result, baseline=None)
    assert report["status"] == "completed"
