# Python workflow integration

AskLess v0.2 runs finite alternatives before asking a person. You supply trusted,
pure preview code and define its complete observable result. The SDK checks all
combinations, retains meaningful choices, and verifies the selected result again.

## Try the included workflow

From a checkout, with Python 3.12+ and uv:

```bash
uv sync --frozen
uv run python -m askless.demo \
  --choose duplicates=last \
  --choose cancelled=exclude
```

Open the printed `report.html` path in a browser. The same directory contains
`report.json` with the input, every branch, comparisons and timings, plus
`result.json` with the final summary. Each run gets a new directory under
`artifacts/`; the runner refuses to overwrite an existing output directory.

The six synthetic rows produce four included orders and a total of **USD 120.00**
with those choices. All amounts have two decimal places, so rounding is
equivalent across all four contexts of the other decisions. The compiler chooses
the first declared option, `per_order`, for this input.

Use your own data:

```bash
uv run python -m askless.demo --input path/to/orders.json
```

On a terminal, the runner prompts for remaining choices. With noninteractive
stdin it writes a pending report and exits **2**; supply `--choose key=value`
for each pending choice and rerun. Success exits **0**; validation or execution
failure exits **1**. Each run explores the input anew; reports are evidence,
not resumable execution sessions.

Input is a UTF-8 JSON array of 1–200 records, at most 512 KiB:

```json
[
  {"order_id": "A100", "amount": "35.00", "status": "paid"},
  {"order_id": "A100", "amount": "42.00", "status": "paid"},
  {"order_id": "A101", "amount": "12.50", "status": "cancelled"}
]
```

IDs contain 1–64 ASCII letters, digits, underscores or hyphens. Amounts are
nonnegative decimal **strings**, with at most nine integer and four fractional
digits. Status is `paid` or `cancelled`. Extra fields and duplicate JSON keys
are rejected. All amounts are interpreted as USD; the adapter performs no
currency conversion.

| Contract | Options | Execution meaning |
| --- | --- | --- |
| `duplicates` | `first`, `last` | Keep the first/last occurrence of an exact order ID in input order. |
| `cancelled` | `exclude`, `include` | Filter cancellations **after** duplicate selection. |
| `rounding` | `per_order`, `at_total` | Decimal `ROUND_HALF_UP` to cents on each included amount, or only on their sum. |

The observable result includes the total, currency, count, included records,
excluded cancellations and discarded duplicates, all with source row numbers.
Record differences remain visible even if totals happen to match.

## Wrap your own function

The public imports are `Decision`, `AgentQuestion`, `explore`, `Exploration`,
`Resolution` and `ExplorationError` from `askless`.

```python
from pydantic import JsonValue

from askless import Decision, explore


def preview(data: JsonValue, policy: dict[str, str]) -> JsonValue:
    assert isinstance(data, list)
    names = [str(value) for value in data]
    if policy["case"] == "lower":
        names = [name.lower() for name in names]
    return {"names": sorted(names) if policy["sort"] == "yes" else names}


data: JsonValue = ["Ada", "Lin"]
run = explore(
    adapter="name-export/v1",
    inputs=data,
    decisions=(
        Decision("case", "Lowercase the exported names?", ("preserve", "lower")),
        Decision("sort", "Sort the names?", ("no", "yes")),
    ),
    preview=preview,
)

# The list is already sorted. Only case remains for the person to choose.
assert [group.decision.key for group in run.pending] == ["case"]
result = run.resolve({"case": "lower"}, inputs=data)
assert result.output == {"names": ["ada", "lin"]}
```

Integrate the call at the point where your agent would ask for a finite choice.
Render `run.pending`, collect exactly those answers, then call `run.resolve`.
The SDK works synchronously inside any Python application. Applications with
async event loops can move trusted CPU previews to their normal worker facility.

`run.trials` contains each policy, output, output hash and duration. Each compiled
decision includes its matched `question_ids`, comparison count and a pair of
branch IDs witnessing a difference. Inputs, outputs and policies are returned
as independent copies. `run.inputs` returns the original snapshot.

`resolve` accepts **exactly** the pending keys and legal option values. It checks
that the supplied input matches the snapshot, reconstructs the full policy,
reruns the original preview callback, and compares exact output bytes against
the explored branch. A changed result raises `ExplorationError` at `replay`.

The SDK executes previews only. Apply external effects in your application
**after** collecting decisions and checking `Resolution`. Your application owns
concurrency, stale external state checks and authorization for those effects.

## Attach actual agent questions

```python
from askless import AgentQuestion

questions = (
    AgentQuestion("q1", "export-agent", "case", "Should names be lowercase?"),
    AgentQuestion("q2", "review-agent", "case", "Preserve the original casing?"),
)
# Pass questions=questions to explore(...).
```

Questions bind to explicit contract keys. Wording is retained for the report;
it does not change execution semantics. Duplicate IDs and unknown keys are
rejected. Multiple questions for the same key share the compiled decision.
All registered decisions are evaluated, including contracts the model omitted.

To test a real model with the included order agent, use the environment
configuration in the [README](../README.md#connect-a-real-llm), then:

```bash
uv run python -m askless.demo --live \
  --choose duplicates=last \
  --choose cancelled=exclude
```

One model request proposes any subset of the three contracts, including none.
Each request permits one retry. The request includes a fixed task, contract
definitions, and counts of rows, duplicate IDs, cancellations and fractional
cents. Raw IDs and amounts stay local. There is no model call during previews
or resolution. Usage records successful decoded responses and any request
retries counted by the provider client. Provider billing is the reference for
failed-request usage.

## Equality and failure semantics

- Equality is exact canonical JSON: object key order is ignored, list order is
  preserved, and JSON types remain distinct. `1`, `1.0` and `true` have different
  representations. NaN, infinity, non-string object keys, tuples and custom
  objects are rejected. Nesting is limited to 64 levels.
- For each decision, fix every combination of the other choices. Compare each
  alternative to the first option in that context. Every comparison must match
  before choosing the first option automatically. A three-option contract is
  covered in full.
- Scope hashes include the complete JSON input, adapter/version identifier and
  ordered decision definitions. Change the adapter identifier when its semantics
  change. A label is supplied by the caller; it is not a digest of Python code.
- Every preview receives independent input and policy copies. Mutations inside
  one call cannot change later branches or the stored evidence.
- A branch exception, malformed/oversized output or result budget failure stops
  exploration. `ExplorationError` exposes `stage`, `branch_id` and
  `completed_branches` (accepted preview results); arbitrary callback exception
  text is suppressed. A callback that exceeds the aggregate result budget has
  run, but its rejected evidence is excluded from this count.
  A failed run yields no successful `Exploration` or automatic selections.

Your observable JSON must include every outcome relevant to the choice. A total
alone would hide changes to individual orders. This version compares declared
results on one input; it does not establish program equivalence across inputs.

## Execution and resource contract

| Budget | Value |
| --- | --- |
| Decisions | Up to 8; each with 2–8 unique string options |
| Branches | Default 32; configurable `max_branches` from 1 to 256 |
| Input snapshot | 512 KiB of canonical UTF-8 JSON |
| One preview result | 64 KiB of canonical UTF-8 JSON |
| All stored preview results | 4 MiB, plus metadata and the input snapshot |
| Agent questions | Up to 256; bounded identifiers and prompts |

The complete branch count is checked **before** invoking callbacks. No sampling
is used when a task exceeds its budget. There are no SDK disk writes; the demo
writes reports only in its chosen output directory. HTML duplicates some JSON
to display witnesses, so report size can exceed the in-memory result-byte budget.

Preview callbacks are trusted code running in the caller's process. They must be
pure, deterministic and finite. The caller controls wall-clock time, peak memory,
network access and effects such as file writes. The SDK snapshots JSON and bounds
retained results; it supplies no process sandbox or hard callback timeout. Use
external isolation before adapting untrusted or generated code.

## Evaluate the trade-off

The offline demo declares one question per contract. Its comparison reports
three available decisions, two retained decisions, eight previews, one replay
and one baseline execution using the same final policy. Model-produced question
counts are recorded separately in live mode.

Run different data, include cases where all choices matter, and compare output
quality alongside execution cost. The built-in tests include a fractional-cent
case where rounding remains pending. Human time, perceived interruption cost,
and agent task quality need evaluations with actual users and tasks.
