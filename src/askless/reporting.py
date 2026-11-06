"""Portable local evidence reports; all external text is escaped in HTML."""

import html
import json
from pathlib import Path
from typing import Literal

from pydantic import JsonValue

from askless.llm import Completion
from askless.sdk import Exploration, Resolution, Trial


class _MissingBaseline:
    pass


_MISSING_BASELINE = _MissingBaseline()


def trial_record(trial: Trial) -> dict[str, JsonValue]:
    return {"id": trial.id, "policy": dict(trial.policy), "output": trial.output, "output_hash": trial.output_hash, "elapsed_ms": trial.elapsed_ms}


def build_report(
    experiment: Exploration,
    *,
    mode: Literal["contract_replay", "live_questions"],
    summary: str,
    completion: Completion | None = None,
    resolution: Resolution | None = None,
    baseline: JsonValue | _MissingBaseline = _MISSING_BASELINE,
    baseline_ms: float = 0,
) -> dict[str, JsonValue]:
    if isinstance(baseline, _MissingBaseline):
        if resolution:
            raise ValueError("An explicit baseline result is required for a completed comparison.")
        baseline = None
    decisions: list[JsonValue] = [
        {
            "key": group.decision.key,
            "prompt": group.decision.prompt,
            "options": list(group.decision.options),
            "status": "answered" if resolution and group.status == "pending" else group.status,
            "selected": resolution.policy[group.decision.key] if resolution else group.selected,
            "question_ids": list(group.question_ids),
            "witnesses": list(group.witnesses),
            "comparisons_checked": group.comparisons_checked,
        }
        for group in experiment.decisions
    ]
    if resolution and (resolution.scope != experiment.scope or not resolution.trial.matches(baseline)):
        raise ValueError("The baseline and replay must match this experiment before reporting completion.")
    comparison: JsonValue = None
    if resolution:
        comparison = {
            "outputs_equal": True,
            "baseline_calls": 1,
            "askless_calls": len(experiment.trials) + 1,
            "extra_calls": len(experiment.trials),
            "baseline_ms": baseline_ms,
            "askless_ms": experiment.elapsed_ms + resolution.trial.elapsed_ms,
            "baseline_output": baseline,
            "method": "Same input and final policy; one direct execution versus complete exploration plus selected-policy replay. Human time is not measured.",
        }
    return {
        "schema_version": 1,
        "adapter": experiment.adapter,
        "scope": experiment.scope,
        "status": "completed" if resolution else "ready",
        "mode": mode,
        "agent_summary": summary,
        "input": experiment.inputs,
        "questions": [{"id": q.id, "agent_id": q.agent_id, "decision_key": q.decision_key, "prompt": q.prompt} for q in experiment.questions],
        "decisions": decisions,
        "trials": [trial_record(trial) for trial in experiment.trials],
        "metrics": {
            "registered_decisions": len(experiment.decisions),
            "agent_questions": len(experiment.questions),
            "human_decisions": len(experiment.pending),
            "auto_resolved": len(experiment.decisions) - len(experiment.pending),
            "preview_calls": len(experiment.trials),
            "replay_calls": int(resolution is not None),
            "exploration_ms": experiment.elapsed_ms,
        },
        "model_usage": {
            "requests": completion.requests if completion else 0,
            "input_tokens": completion.input_tokens if completion else 0,
            "output_tokens": completion.output_tokens if completion else 0,
        },
        "result": trial_record(resolution.trial) if resolution else None,
        "comparison": comparison,
        "measurement": "Contract replay uses one declared question per decision. Live questions are a model-produced subset. All contracts are evaluated in both modes. Counts are decisions, not measured human interruptions.",
    }


def _escaped(value: object) -> str:
    return html.escape(str(value), quote=True)


def _json_block(value: JsonValue) -> str:
    return "<pre>" + _escaped(json.dumps(value, ensure_ascii=False, indent=2)) + "</pre>"


def _object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise TypeError("Report object is malformed.")
    return value


def _objects(value: JsonValue) -> list[dict[str, JsonValue]]:
    if not isinstance(value, list):
        raise TypeError("Report array is malformed.")
    return [_object(item) for item in value]


def _decision_cards(report: dict[str, JsonValue]) -> str:
    trials = {str(trial["id"]): trial for trial in _objects(report["trials"])}
    cards: list[str] = []
    for decision in _objects(report["decisions"]):
        witnesses = decision["witnesses"]
        assert isinstance(witnesses, list)
        evidence = "".join(
            "<details><summary>Witness · " + _escaped(branch) + "</summary>" + _json_block(trials[str(branch)]) + "</details>" for branch in witnesses
        )
        if decision["status"] == "auto":
            evidence = "<p>All compared outcomes match. Selected <strong>" + _escaped(decision["selected"]) + "</strong> for this input.</p>"
        elif decision["status"] == "answered":
            evidence = "<p>Confirmed <strong>" + _escaped(decision["selected"]) + "</strong>. Replay verified.</p>" + evidence
        cards.append(
            '<article><span class="tag">'
            + _escaped(decision["status"])
            + "</span><h3>"
            + _escaped(decision["prompt"])
            + "</h3><p>"
            + _escaped(decision["comparisons_checked"])
            + " comparisons · contract "
            + _escaped(decision["key"])
            + "</p>"
            + evidence
            + "</article>"
        )
    return "".join(cards)


REPORT_STYLE = """
:root{color-scheme:light;--paper:#f5f3ed;--ink:#283d33;--muted:#68736b;--line:#d6d9cd;--accent:#bf4d2a}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,sans-serif}
main{max-width:1120px;padding:48px 28px 80px;margin:auto}header{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:20px}
.brand{font-size:25px;font-weight:750;letter-spacing:-1px}.eyebrow,.tag{font:11px/1.5 ui-monospace,monospace;letter-spacing:1.5px;text-transform:uppercase}
h1,h2{font-family:Georgia,serif;font-weight:400;letter-spacing:-1.5px;line-height:1.08}h1{font-size:clamp(40px,7vw,76px);margin:52px 0 24px}
h1 em{color:var(--accent)}h2{font-size:36px;margin-top:50px}h3{font-size:18px;font-weight:550}p{color:var(--muted);max-width:76ch}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin:32px 0;border-block:1px solid var(--line)}.metric{padding:22px 12px}
.metric b{display:block;font:40px Georgia,serif}.metric span{font-size:12px;color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
article{min-width:0;padding:24px;background:#fffdf7;border:1px solid var(--line);border-radius:8px}.tag{color:var(--accent)}
pre{overflow:auto;padding:18px;background:#eaece3;border-radius:5px;font:12px/1.65 ui-monospace,monospace;tab-size:2;max-height:460px}
details{border-top:1px solid var(--line);padding:14px 0}summary{cursor:pointer;font-size:13px}code{overflow-wrap:anywhere}footer{margin-top:44px;border-top:1px solid var(--line);padding-top:18px;font-size:12px;color:var(--muted)}
@media(max-width:720px){.cards{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}main{padding:24px 18px 50px}h1{margin-top:36px}}
"""


def render_report(report: dict[str, JsonValue]) -> str:
    metrics = _object(report["metrics"])
    numbers = "".join(
        '<div class="metric"><b>' + _escaped(metrics[key]) + "</b><span>" + label + "</span></div>"
        for key, label in (
            ("registered_decisions", "declared choices"),
            ("human_decisions", "need your decision"),
            ("auto_resolved", "equivalent on this input"),
            ("preview_calls", "preview executions"),
        )
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        "<title>AskLess · Decision evidence</title><style>" + REPORT_STYLE + "</style></head><body><main>"
        '<header><span class="brand">askless.</span><span class="eyebrow">LOCAL EVIDENCE / ' + _escaped(report["status"]) + "</span></header>"
        "<h1>Run the alternatives.<br><em>Keep the important calls.</em></h1><p>"
        + _escaped(report["agent_summary"])
        + '</p><div class="metrics">'
        + numbers
        + "</div>"
        '<p class="eyebrow">'
        + _escaped(report["adapter"])
        + " / "
        + _escaped(report["mode"])
        + '</p><section class="cards">'
        + _decision_cards(report)
        + "</section>"
        "<h2>Your chosen result.</h2>"
        + (_json_block(report["result"]) if report["result"] else "<p>Awaiting the remaining decisions. No final output has been produced.</p>")
        + "<h2>The cost of asking less.</h2><p>"
        + _escaped(report["measurement"])
        + "</p>"
        + _json_block(report["comparison"])
        + "<details><summary>Original agent questions &amp; model usage</summary>"
        + _json_block(report["questions"])
        + _json_block(report["model_usage"])
        + "</details>"
        + "<details><summary>Every executed branch</summary>"
        + _json_block(report["trials"])
        + "</details>"
        + "<details><summary>Input snapshot</summary>"
        + _json_block(report["input"])
        + "</details>"
        + "<footer>Input and contract scope: <code>"
        + _escaped(report["scope"])
        + "</code><br>Pure local previews · exact declared outputs · no external report resources</footer></main></body></html>"
    )


def write_report(report: dict[str, JsonValue], directory: Path) -> None:
    rendered = render_report(report)
    directory.mkdir(parents=True, exist_ok=False)
    with (directory / "report.json").open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    with (directory / "report.html").open("x", encoding="utf-8") as target:
        target.write(rendered)
    if report["result"] is not None:
        with (directory / "result.json").open("x", encoding="utf-8") as target:
            target.write(json.dumps(_object(report["result"])["output"], ensure_ascii=False, indent=2) + "\n")
