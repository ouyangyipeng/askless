# Python workflow validation — 2026-10-26

Environment: macOS arm64, Python 3.12.13, Node.js 24, pnpm 12.4.2. The v0.2
upgrade adds no runtime dependencies; the existing lock pins are retained.

## Reproduce

```bash
uv sync --frozen
uv run python -m askless.demo \
  --choose duplicates=last --choose cancelled=exclude
```

For real model questions, export provider credentials through your secure shell
configuration and add `--live`. Every invocation writes a fresh report directory;
the terminal prints its location. Credentials and local report files are excluded
from the repository.

## Observed runs

Both recorded final runs used `examples/orders.json`: six synthetic rows, three
contracts and eight policy combinations. Confirmed choices: `duplicates=last`,
`cancelled=exclude`; equivalent rounding selected `per_order`.

| Observation | Offline contract replay | Live model questions |
| --- | ---: | ---: |
| Registered decisions | 3 | 3 |
| Original question trace | 3 declared | 2 model-proposed |
| Retained human decisions | 2 | 2 |
| Automatically resolved choices | 1 | 1 |
| Local preview executions | 8 | 8 |
| Selected-policy replays | 1 | 1 |
| Direct baseline executions | 1 | 1 |
| Model requests | 0 | 1 |
| Input / output tokens | 0 / 0 | 294 / 117 |
| Final order count | 4 | 4 |
| Final USD total | 120.00 | 120.00 |
| Baseline and replay output equality | Exact match | Exact match |

Both final output hashes:

```text
3a0a3b56f98f1e54d93e9b2dc0a5b94c1da4699dc257f6af2623caa95bb8455c
```

In these individual local runs, SDK exploration plus replay took approximately
0.370 ms offline and 0.379 ms live; direct execution took approximately 0.010 ms.
These measurements cover the tiny local data transformation and SDK bookkeeping.
They exclude model latency, user time and report rendering; they are individual
observations rather than a throughput benchmark. The exact durations are retained
in local JSON evidence.

The final live report's three files totalled 49,794 bytes (about 48.6 KiB).
The final built wheel was 31,085 bytes (about 30.4 KiB) at the packaging smoke check.
No model download, container image or new service was introduced.

The live model already limited its proposal to the two meaningful contracts, so
that run retained two of two proposed questions. Offline replay demonstrates
three declared choices becoming two human decisions. Human attention savings
and task quality across natural agent workloads remain to be measured.

## Behavior and integration checks

- 77 Python tests passed after the correctness fixes, including the existing
  contact workflow and its HTTP/persistence tests.
- 8 frontend tests passed, covering both website examples and workbench behavior.
- Ruff, isort, format, ty and TypeScript checks passed; workbench and website
  production builds passed.
- The frozen uv installation completed and installed AskLess 0.2.0. A wheel was
  built, checked for SDK modules and `py.typed`, imported directly, and used for
  a successful exploration and replay.
- All Python snippets in both READMEs and the SDK guide executed successfully.
- The generated website order fixture matches every branch and comparison
  decision produced by the current SDK.
- Desktop browser interaction verified all four order totals: 120.00, 132.50,
  125.50 and 113.00. Browser console errors were empty. 390 px and 320 px layouts
  had no horizontal document overflow.

Tests include multi-option interactions, input/adapter scope changes, mutation
isolation, incomplete budgets, failed previews, strict finite JSON, storage caps,
invalid answers, changed replay output, cancellation/deduplication ordering,
fractional cents, model contract validation and safe report rendering/writes.

## Independent review

A read-only reviewer checked 250 fixed random decision truth tables against an
independent full-context comparison, plus JSON types, model omissions and HTML
injection/overwrite scenarios. No blocking findings remained after these fixes:

- Order arithmetic and profiling now use their own Decimal context, independent
  of an embedding application's precision and traps.
- Baseline comparison uses the same exact JSON semantics as SDK output equality.
- A completed comparison requires an explicit baseline, including for null output.
- Completed reports display answered choices and their confirmed values.

Each fix has a regression observed failing before the change and passing after.

## Execution boundary

The SDK compares declared results on a complete input snapshot. Preview callbacks
are trusted application code. The host application owns callback wall-clock time,
peak memory, external effects and adapter version labels. The CLI/report workflow
is separate from the contact workbench's SQLite history. See
[the SDK contract](python-sdk.md#execution-and-resource-contract).
