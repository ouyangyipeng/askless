<p align="center">
  <a href="https://ouyangyipeng.github.io/askless/"><img src="docs/images/cover.svg" alt="AskLess — More agency. Fewer interruptions. Run the alternatives. Ask only what matters." width="100%" /></a>
</p>

<p align="center">
  <a href="https://ouyangyipeng.github.io/askless/"><strong>Website & interactive example ↗</strong></a>
  &nbsp; · &nbsp;
  <a href="#quickstart">Quickstart</a>
  &nbsp; · &nbsp;
  <a href="docs/architecture.md">Architecture</a>
  &nbsp; · &nbsp;
  <a href="README.zh-CN.md">中文</a>
</p>

<p align="center"><sub>LOCAL-FIRST &nbsp; / &nbsp; MIT LICENSED &nbsp; / &nbsp; EXPERIMENTAL v0.1</sub></p>

<br />

## Your attention deserves a better interface.

Agent teams can produce a lot of questions. Some repeat the same decision. Some lead to exactly the same result. Some really need you.

**AskLess runs the alternatives before asking.** It groups questions by explicit decision contracts, compares real execution results, and presents the choices that change the outcome—with evidence attached.

The first working experiment is a **contact CSV adapter**. Three roles propose questions, one deterministic executor explores every policy combination, and you make the remaining decisions in a local workbench.

| Collect | Explore | Decide |
| :--- | :--- | :--- |
| **9 questions** from three roles | **8 complete policy combinations** | **2 human decisions** in the included sample |
| Shared contracts bring repeated questions together. | Outputs, quarantined rows, and blocking status are compared. | One equivalent choice is resolved for this exact input. |

<sub>These counts come from the included eight-row sample and the fixed three-role, three-contract protocol. Human attention savings and task quality are open evaluation questions.</sub>

<br />

<a href="https://ouyangyipeng.github.io/askless/#explore"><img src="docs/images/workbench.jpg" alt="The actual AskLess local workbench: three roles, eight explored branches, and a queue of two evidence-backed decisions." width="100%" /></a>

<p align="center"><sub>The actual local workbench · Chinese interface in v0.1 · <a href="https://ouyangyipeng.github.io/askless/#explore">Explore the interactive example</a></sub></p>

## Quickstart

You need **Python 3.12+**, [uv](https://docs.astral.sh/uv/getting-started/installation/), **Node.js 24.15+** (or 22.22.2+), and **pnpm 12**. Development is verified with Node.js 24.

```bash
git clone https://github.com/ouyangyipeng/askless.git
cd askless
./run.sh
```

Open **[127.0.0.1:8765](http://127.0.0.1:8765)**. The script installs locked dependencies, builds the workbench, and starts one local Python service. Use `Ctrl+C` to stop; use `./run.sh --port 8766` to change the port.

**Start without a key.** Choose **离线演示** (offline demo) in the workbench. It uses fixed role questions and runs all eight branches, decision compilation, policy validation, and CSV export locally.

The sample includes eight synthetic rows. Keeping the last duplicate and quarantining invalid emails yields **four contacts and two quarantined rows**. Expand a decision to compare branch outputs; download the CSV and full JSON evidence bundle after completion.

<details>
<summary><strong>Connect a real LLM</strong></summary>

The backend reads credentials from its process environment. Export your credential through your usual secure shell setup before launching. Supported configuration:

| Variable | Purpose |
| :--- | :--- |
| `ALIYUN_API_KEY` | API credential; falls back to `DASHSCOPE_API_KEY` |
| `ALIYUN_BASE_URL` | HTTPS OpenAI-compatible endpoint; defaults to `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `ASKLESS_MODEL` | Model name; defaults to `qwen3.8-flash`. Choose a model available to your account. |

The provider must support Chat Completions, JSON output, and `enable_thinking: false`. Configuration is read from environment variables; `.env` and shell configuration files are not loaded automatically.

A successful live run typically makes six requests: three question proposals and three policy acknowledgments. Each request allows one retry and 45-second connection/read/write timeouts. Model errors preserve completed evidence and display a failed state. Usage shown in the app covers successfully parsed, recorded stages; consult the provider for billing and failed-request usage.

</details>

## The mechanism

```text
  Data engineer ──────┐
  Quality reviewer ───┼── 9 scoped questions
  Delivery lead ──────┘         │
                                ▼
                     Execute all 8 policies
                                │
                     Compare every interaction
                                │
                  ┌─────────────┴─────────────┐
                  ▼                           ▼
           Different outcomes           Equivalent outcomes
           Ask with evidence            Resolve for this input
                  │
                  ▼
           Your chosen policy
                  │
           3 explicit receipts → Re-execute → Match hashes → Export
```

**Equivalence has a concrete scope.** Every question is tied to the complete input's SHA-256. For each decision, the compiler checks four pairs that cover all combinations of the other two choices. A choice is resolved automatically only when every paired comparison matches—including output rows, quarantined rows, and blocked status.

**A decision travels with its evidence.** The same confirmed policy is sent to all three roles. Each must explicitly acknowledge every field. The shared CSV executor reruns the policy, and output hashes must match before delivery completes.

## What you can run today

| Contract | Options | Meaning |
| :--- | :--- | :--- |
| Duplicate contacts | First / last | Keep the first or last occurrence in **CSV order**. Identity uses trimmed, case-insensitive email. |
| Invalid emails | Quarantine / block | Export valid rows, or block the entire batch. Both retain invalid rows for review. |
| Email case | Preserve / lowercase | Change the export spelling. The included sample is already lowercase, so this choice is equivalent. |

v0.1 uses fixed contracts and one trusted executor shared by all three roles. General coding-agent integrations, generated-code execution, cross-task preference learning, and automatic discovery of higher-level decisions are future work. New adapters need their own contracts, controlled execution, and observable result definitions.

## Local data, bounded resources

- **Local storage:** inputs, branch outputs, decisions, and receipts live in `.askless/runs.sqlite3`. Use `--data-dir` to choose another location.
- **Model input:** your task description, role, aggregate statistics, policy contracts, and confirmed result counts/status. Raw CSV rows stay local. Information entered into the task description goes to the configured provider.
- **Input limits:** UTF-8 CSV up to 256 KiB, 2,000 rows, and 30 columns, with one unique `email` header. Header names are limited to 128 UTF-8 bytes; expanded data to 512 KiB.
- **Storage limits:** up to 8 MiB per saved run, 50 retained runs, and two active runs. The logical run-data ceiling is 400 MiB, plus SQLite overhead and reusable free pages.
- **Recovery:** completed and awaiting-decision runs survive restarts. Active runs are marked interrupted, preserving available evidence. Delete history from the workbench; SQLite usually reuses freed pages.
- **Export:** CSV spreadsheet-formula prefixes are neutralized. JSON evidence retains the parsed input. Email validation checks syntax without DNS or delivery checks.

No Docker, separate database service, or local model download is required. See the [validation record](docs/validation-2026-10-23.md) for measured runs, resource use, and test scope.

## Develop

```bash
uv sync --frozen
uv run pytest -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run isort --check-only src tests scripts
uv run ty check src tests scripts
pnpm --dir web install --frozen-lockfile
pnpm --dir web exec prettier --check src site
pnpm --dir web test
pnpm --dir web build
pnpm --dir web site:build
```

Run `pnpm --dir web dev` alongside the Python server for workbench development. Vite proxies `/api` to port 8765. Run `pnpm --dir web site:dev` for the public website.

| Location | Responsibility |
| :--- | :--- |
| `src/askless/engine.py` | CSV validation, branch execution, comparison, question compilation |
| `src/askless/agents.py` · `llm.py` | Role protocol, model calls, explicit acknowledgments |
| `src/askless/service.py` · `store.py` | Lifecycle, transactions, scope, concurrency, storage limits |
| `src/askless/api.py` | Local same-origin API, export, static workbench |
| `web/src/` | React workbench and regression tests |
| `web/site/` | Website source and interactive example |
| `docs/` | Documentation and built GitHub Pages site |

## Help shape the next experiment

We are interested in small adapters with clear result semantics, realistic agent traces, and evaluations of human attention and task quality. Start with the [contribution guide](CONTRIBUTING.md), [architecture](docs/architecture.md), or a [new issue](https://github.com/ouyangyipeng/askless/issues).

The website's sample is generated from the actual executor and checked against it in tests. [Website maintenance](docs/website.md) explains how to rebuild and publish it.

---

<p align="center"><strong>Ask less. Make the important calls.</strong><br /><sub>Created by <a href="https://github.com/ouyangyipeng">Ouyang Yipeng</a> · <a href="LICENSE">MIT License</a></sub></p>
