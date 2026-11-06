# File previews with a Python agent

AskLess v0.3 connects a bounded file-export workflow to a real LLM host over MCP stdio. It previews all eight combinations of format, delimiter and column names, saves the evidence, and lets the user choose actual file contents. Choosing JSON eliminates the two CSV-specific questions. Choosing CSV retains the choices that still change the file.

## Start the workbench

Install Python 3.12+, uv, Node.js 24.15+ (or 22.22.2+) and pnpm 12. From the repository root:

```bash
./run.sh
```

Open `http://127.0.0.1:8765/decisions`. The web form runs locally without a model. It accepts a flat JSON array or a UTF-8 JSON file, then presents two real files for the next relevant choice. The original contact workflow remains at `/`.

## Start the reference agent

Configure `ALIYUN_API_KEY` (or `DASHSCOPE_API_KEY`) through your secure shell environment. Optional `ALIYUN_BASE_URL` and `ASKLESS_MODEL` follow the [provider configuration](../README.md#connect-a-real-llm). AskLess reads process environment variables; it does not source shell files.

In a second terminal, from the same repository root:

```bash
uv run --extra agent python -m askless.agent \
  --input examples/records.json \
  --task "Prepare a file export and let me compare the formats."
```

The agent asks the model for a structured action, validates its tool name and arguments, then invokes `preview_export` through an actual MCP subprocess. It prints the session URL and exits with code 2 while awaiting a choice. Open that URL and choose JSON or follow the CSV decisions.

Copy the printed resume command, or use:

```bash
uv run --extra agent python -m askless.agent --resume YOUR_SESSION_ID
```

The second process loads the saved session, obtains the collection action from the model and calls `collect_export`. It rechecks the source input, reexecutes the selected policy and verifies the exact output. A new `artifacts/export-*` directory contains the file and `evidence.json`. Use `--output NEW_DIRECTORY` to select another new directory. Existing output directories are rejected.

For one process to wait for your choice, pass `--wait 120`. Waiting is limited to 120 seconds; an unfinished session can always be resumed later. Exit codes: **0** delivered, **2** waiting, **1** failed or stale.

### Custom storage and port

The web service and agent must use the same data directory:

```bash
# Terminal 1
./run.sh --port 8766 --data-dir ./local-decisions

# Terminal 2
uv run --extra agent python -m askless.agent \
  --input examples/records.json \
  --data-dir ./local-decisions --web-url http://127.0.0.1:8766
```

Reuse `--data-dir` and `--web-url` when resuming. Running `run.sh` synchronizes the base dependencies; use `uv run --extra agent` for agent commands so the optional MCP dependency is present.

## Connect another MCP host

Install the optional extra with `uv sync --extra agent --frozen`. Configure an MCP stdio entry in your host, replacing each `/ABSOLUTE/...` value with an actual path. Host configuration keys vary; this is the common `mcpServers` shape:

```json
{
  "mcpServers": {
    "askless": {
      "command": "/ABSOLUTE/askless/.venv/bin/python",
      "args": [
        "-m", "askless.mcp_server",
        "--input", "/ABSOLUTE/records.json",
        "--data-dir", "/ABSOLUTE/askless/.askless",
        "--web-url", "http://127.0.0.1:8765"
      ]
    }
  }
}
```

Start the web workbench separately against that data directory. The MCP server is bound to the one source file supplied at launch. It needs no model credentials. The reference host passes only a minimal stdio environment to its child; provider credentials stay in the host process.

| Tool | Arguments | Result |
| --- | --- | --- |
| `preview_export` | `title`, unique `request_id` | Session ID, status, revision, local workbench URL and pending choice keys |
| `inspect_session` | `session_id` | Current metadata for a session owned by this bound input |
| `collect_export` | `session_id`, current `revision` | Verified artifact metadata, hash and local download URL |

The host opens the workbench URL for the user, waits or polls `inspect_session`, and collects only after `chosen`. MCP tools expose metadata and local URLs. The browser and local evidence file contain the input and output rows. User answers enter through the token-protected local HTTP interface.

The included reference host follows two fixed stages and validates the model's action against the expected tool and arguments. The registered exporter determines execution semantics. General task planning, generated-code execution and native coding-agent hooks remain separate integration work.

## Input and output contract

- UTF-8 JSON: 1–100 objects with identical keys, 1–20 columns, at most 32 KiB. Values are strings, finite numbers, booleans or null. Keys are nonempty and at most 64 UTF-8 bytes. File parsing rejects duplicate JSON keys.
- JSON preserves primitive values, sorts object keys and uses two-space indentation. CSV sorts columns, uses CRLF, and treats null as an empty cell. CSV values are textual; spreadsheet-formula prefixes are neutralized, including headers.
- `file-export/v1` declares `format={json,csv}`, `separator={comma,semicolon}`, `header={include,omit}`. All eight combinations are explored locally. Each result includes the actual text, byte length, filename, MIME type, columns and row count.
- Evidence uses exact canonical JSON equality. Decisions are recalculated on the remaining complete policy space after each answer. For JSON, delimiter and header become irrelevant. A one-column CSV may also make the delimiter irrelevant when quoting does not change the bytes.

## Persistence and failure handling

State is saved separately in `decisions.sqlite3`: `ready → chosen → completed`, with `stale` and `failed` terminal states. The service keeps at most 50 sessions, two unfinished sessions and 8 MiB per saved session. This limit is independent of the contact database; each store's logical data ceiling is 400 MiB, plus SQLite overhead and reusable free pages.

Creation and answers have idempotency keys. Reusing a key with different content is rejected. A new preview in the UI starts a fresh request; a failed transport retry retains its original ID. Answers and completion check the current revision inside an SQLite transaction. Repeated collection of a completed session returns its stored result. Repeating a created reference-host request reuses its validated session, and a saved collection action is reused after a restart.

Reference-host model stages are serialized per data directory using a separate SQLite transaction lock. A concurrent caller receives an explicit busy error before making a model request. The lock is released when the process exits, including a crash; workbench answers use a different database and remain available during model calls.

Before accepting a new answer or completing a source-backed session, the service reads the file and checks its canonical input hash. Changed or unreadable input makes the session `stale`; generate a new preview. A missing branch, invalid scope or hash mismatch is rejected. A failing preview preserves accepted branch evidence without producing automatic choices. Completion failure preserves the session and blocks artifact download.

Each stage permits one logical model call, with at most one provider retry and 45-second HTTP timeouts. Usage records successfully decoded responses. Task text, tool schemas, aggregate row/column counts and confirmed choices go to the configured provider. Raw file rows stay in the local exporter. Provider billing remains the source for failed-request usage.

## HTTP integration

The local API is under `/api/decisions`. Its writes reuse the same-origin and `X-AskLess-Token` checks; get a fresh token from `/api/config` after a service restart.

| Method and path | Body or behavior |
| --- | --- |
| `POST /api/decisions` | `{title, input_text, request_id, max_branches: 8}`; raw JSON text preserves integer values and rejects duplicate keys. Existing callers may provide `inputs` instead. Supply exactly one input field. |
| `GET /api/decisions` | Compact history |
| `GET /api/decisions/{id}` | Current choices, witness trials, events and usage |
| `POST /api/decisions/{id}/answer` | `{key, value, revision, request_id}`; one pending choice |
| `POST /api/decisions/{id}/complete` | `{revision}`; verifies the selected policy |
| `GET /api/decisions/{id}/artifact` | Completed file; unfinished sessions return 409 |
| `GET /api/decisions/{id}/evidence` | Local JSON evidence with input and outputs |
| `DELETE /api/decisions/{id}` | Deletes the local session |

HTTP input has no filesystem-path field. Paths are supplied by the local MCP launcher. For custom Python functions and incremental decisions, see the [SDK guide](python-sdk.md#conditional-decisions).
