# v0.3 validation record — 2026-11-06

The conditional file workflow completed through a real Aliyun model, an MCP stdio subprocess, the browser workbench and a fresh Python host process. The selected JSON artifact matched its preview on final replay.

## Environment and method

macOS arm64, Python 3.12.13, MCP Python SDK 2.3.0, Node.js 24.22.1, pnpm 12.4.2. The live run used `qwen3.8-flash`, the included three-row `examples/records.json`, one browser choice and a newly started process for collection. Credentials came from the local process environment. The model received the task, tool schemas and aggregate metadata.

The reference host uses two fixed stages with validated structured model actions. Its final file is produced by the trusted exporter. A native open-ended agent baseline, task-planning quality and user attention time remain unmeasured.

## Live result

| Measurement | Observed value |
| --- | --- |
| Input | 3 rows × 3 columns |
| Complete previews | 8 |
| Manual choices | 1: JSON |
| Automatically resolved after that choice | 2: delimiter and column names |
| Final replay | 1, exact observable output match |
| Delivered file | JSON, 211 bytes |
| Model requests | 2, one per stage, no retries |
| Input tokens | 1,529 |
| Output tokens | 224 |
| Total tokens | 1,753 |
| Preview-stage model elapsed time | 2.03 s |
| Collection-stage model elapsed time | 1.92 s |
| SQLite file after this one session | 24 KiB |

Elapsed values measure each model request and structured-action validation in this run. They exclude browser choice time and process launch. Human choice time was not recorded. Tokens are from successful provider responses; no price estimate was applied.

## Twenty deterministic export scenarios

Ten inputs each ran the JSON and CSV paths: ASCII, Unicode, quoting, newlines, formula prefixes, nulls, booleans, numbers, 100 rows and one column. The baseline asks every initially relevant SDK choice before execution. The incremental path answers format first, then each remaining relevant choice.

| Result across 20 tasks | All choices upfront | Incremental choices |
| --- | ---: | ---: |
| Explicit choices requested | 58 | 39 |
| Outputs equal to direct execution with the same final policy | 20/20 | 20/20 |

The reduction is **19 of 58 choices (32.8%)** in this balanced JSON/CSV fixture set. Every JSON path needs one choice. Nine CSV paths retain all three choices; the single-column case retains two. This records API decision counts; no human completion-time measurement was made.

Both decision paths use eight previews. Incremental answering reuses that evidence. Final verification adds one replay; direct execution of an already selected policy takes one call.

Four additional fault scenarios checked partial preview failure, an insufficient branch budget, changed source input and incomplete persisted evidence. Each stopped without delivering an unverified file. Additional local checks covered concurrent answers, duplicate request IDs, revision conflicts, scope/hash tampering, API token checks and model actions outside the registered stage.

The independent review found three regressions, each reproduced before its fix: browser rounding of integers above JavaScript's safe range, reuse of a creation key after explicit new-preview intent, and duplicate model calls during repeated start or concurrent resume. Regression checks now preserve the raw `9007199254740993` value, reject duplicate JSON fields, create a fresh session for a new action, and allow only one model call during concurrent collection. The reference-host lock also permits human answers while held and is released after its owning process exits.

## Browser and compatibility checks

The final implementation passed **117 Python checks** (31 existing repository checks, 46 retained local SDK checks and 40 local v0.3 checks) and **15 frontend checks**. Ruff, formatting, isort, ty, TypeScript and both workbench/website builds passed. Source and wheel archives were inspected with the dedicated local-test directories excluded.

- The live host exited while awaiting a choice, then a new process restored the session and collected the verified JSON file.
- A separate browser-created session completed CSV → semicolon → omit column names, producing the expected 33-byte file from the two-row workbench sample with zero model calls.
- Desktop, 390 px and 320 px layouts were inspected. The mobile session completed through the same API and no page-level horizontal overflow was observed.
- The final browser/API integration preserved the integer `9007199254740993` through preview, selection and verified JSON delivery after a service restart.
- Existing contact tests and prior local SDK checks were retained. New tests and their dedicated fixtures are local-only under the contributor's repository policy.

The public website replays executor-generated evidence. Its JSON and four CSV endings are verified when `scripts/export_decision_sample.py` generates the sample. The live local workbench executes supplied data separately.
