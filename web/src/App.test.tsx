import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import App from "./App";
import { Decisions } from "./Decisions";
import type { Run } from "./types";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ request: api }));

function fixture(id: string): Run {
  return {
    id,
    title: `Run ${id}`,
    mode: "offline",
    model: "deterministic",
    created_at: "2026-10-23T00:00:00Z",
    status: "ready",
    revision: 4,
    dataset: {
      scope: id,
      columns: ["email"],
      rows: [{ email: "a@example.com" }],
    },
    agents: [],
    questions: [],
    trials: [],
    events: [],
    receipts: [],
    result: null,
    error: null,
    llm_calls: 0,
    input_tokens: 0,
    output_tokens: 0,
    groups: [
      {
        key: "duplicates",
        status: "pending",
        selected: null,
        question_ids: [],
        agent_ids: [],
        witnesses: [],
        comparisons_checked: 4,
        reason: "different",
        spec: {
          title: "重复记录如何处理？",
          context: "按文件顺序。",
          options: [
            { value: "first", label: "保留首次记录", description: "第一行" },
            { value: "last", label: "保留末次记录", description: "最后一行" },
          ],
        },
      },
    ],
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

let pendingAnswer: ReturnType<typeof deferred<Run>>;
let pendingStart: ReturnType<typeof deferred<Run>>;
let pendingOpen: ReturnType<typeof deferred<Run>> | undefined;

beforeEach(() => {
  pendingAnswer = deferred<Run>();
  pendingStart = deferred<Run>();
  pendingOpen = undefined;
  api
    .mockReset()
    .mockImplementation((path: string, _token?: string, method?: string) => {
      if (path === "/config")
        return Promise.resolve({
          token: "local-test",
          model: "test",
          configured: false,
          sample_csv: "email\na@example.com\n",
          version: "test",
        });
      if (path === "/runs" && method === "POST") return pendingStart.promise;
      if (path.endsWith("/answers")) return pendingAnswer.promise;
      if (path === "/runs")
        return Promise.resolve(
          ["A", "B"].map((id) => ({ ...fixture(id), rows: 1 })),
        );
      if (path === "/runs/B" && pendingOpen) return pendingOpen.promise;
      if (path.startsWith("/runs/"))
        return Promise.resolve(fixture(path.split("/").at(-1)!));
      throw new Error(`Unexpected API request: ${path}`);
    });
});
afterEach(cleanup);

async function openRun(id: string) {
  fireEvent.click(
    await screen.findByRole("button", { name: new RegExp(`Run ${id}.*等待`) }),
  );
  await waitFor(() =>
    expect(
      screen
        .getByRole("button", { name: new RegExp(`Run ${id}.*等待`) })
        .closest(".history-entry")
        ?.classList.contains("current"),
    ).toBe(true),
  );
}

test("a late answer cannot replace a newly opened run or its selection", async () => {
  render(<App />);
  await openRun("A");
  fireEvent.click(screen.getByRole("radio", { name: "保留首次记录" }));
  fireEvent.click(screen.getByRole("button", { name: "确认决定，继续执行" }));
  await openRun("B");
  fireEvent.click(screen.getByRole("radio", { name: "保留末次记录" }));
  const answered = fixture("A");
  answered.status = "applying";
  answered.groups[0].status = "answered";
  answered.groups[0].selected = "first";
  await act(async () => {
    pendingAnswer.resolve(answered);
  });
  expect(
    screen
      .getByRole("radio", { name: "保留末次记录" })
      .getAttribute("aria-checked"),
  ).toBe("true");
  expect(
    screen
      .getByRole("button", { name: /Run B.*等待/ })
      .closest(".history-entry")
      ?.classList.contains("current"),
  ).toBe(true);
});

test("a late create response cannot replace a run opened from history", async () => {
  render(<App />);
  await screen.findByRole("button", { name: /Run B.*等待/ });
  fireEvent.click(screen.getByRole("button", { name: "让 Agent 先试一遍" }));
  await openRun("B");
  await act(async () => {
    pendingStart.resolve(fixture("C"));
  });
  expect(
    screen
      .getByRole("button", { name: /Run B.*等待/ })
      .closest(".history-entry")
      ?.classList.contains("current"),
  ).toBe(true);
});

test("choices from the old run are disabled while another run loads", async () => {
  render(<App />);
  await openRun("A");
  pendingOpen = deferred<Run>();
  fireEvent.click(screen.getByRole("button", { name: /Run B.*等待/ }));
  const oldChoice = screen.getByRole("radio", { name: "保留末次记录" });
  expect((oldChoice as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(oldChoice);
  await act(async () => {
    pendingOpen?.resolve(fixture("B"));
  });
  expect(
    screen
      .getByRole("radio", { name: "保留末次记录" })
      .getAttribute("aria-checked"),
  ).toBe("false");
  expect(
    (
      screen.getByRole("button", {
        name: "确认决定，继续执行",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});

test("answered cards show the persisted choice even with stale local input", () => {
  const run = fixture("A");
  run.status = "completed";
  run.groups[0].status = "answered";
  run.groups[0].selected = "first";
  render(
    <Decisions
      run={run}
      selected={{ duplicates: "last" }}
      disabled={false}
      onSelect={vi.fn()}
    />,
  );
  expect(
    screen
      .getByRole("radio", { name: "保留首次记录" })
      .getAttribute("aria-checked"),
  ).toBe("true");
  expect(
    screen
      .getByRole("radio", { name: "保留末次记录" })
      .getAttribute("aria-checked"),
  ).toBe("false");
});
