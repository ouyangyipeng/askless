import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "./api";
import type { ExportKey, ExportSession, SessionSummary } from "./decisionTypes";

function sessionUrl(id?: string) {
  window.history.replaceState(
    {},
    "",
    id ? "/decisions?session=" + encodeURIComponent(id) : "/decisions",
  );
}

export function useDecisionSession() {
  const [token, setToken] = useState("");
  const [sample, setSample] = useState("");
  const [history, setHistory] = useState<SessionSummary[]>([]);
  const [run, setRun] = useState<ExportSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const version = useRef(0);
  const current = useRef<string | null>(null);
  const operations = useRef(new Map<string, string>());
  const refresh = useCallback(
    () => request<SessionSummary[]>("/decisions").then(setHistory),
    [],
  );

  const open = useCallback(async (id: string) => {
    const stamp = ++version.current;
    current.current = id;
    setRun(null);
    setBusy(true);
    setError("");
    sessionUrl(id);
    try {
      const next = await request<ExportSession>(
        "/decisions/" + encodeURIComponent(id),
      );
      if (stamp === version.current) setRun(next);
    } catch (e) {
      if (stamp === version.current) setError((e as Error).message);
    } finally {
      if (stamp === version.current) setBusy(false);
    }
  }, []);

  useEffect(() => {
    let stopped = false;
    void Promise.all([
      request<{ token: string }>("/config"),
      request<{ sample: unknown }>("/decisions/config"),
    ])
      .then(async ([config, data]) => {
        if (stopped) return;
        setToken(config.token);
        setSample(JSON.stringify(data.sample, null, 2));
        const id = new URLSearchParams(window.location.search).get("session");
        if (id) await open(id);
        if (!stopped) await refresh();
      })
      .catch((e) => {
        if (!stopped) setError((e as Error).message);
      });
    return () => {
      stopped = true;
    };
  }, [open, refresh]);

  useEffect(() => {
    if (!run || !["ready", "chosen"].includes(run.status) || busy) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const id = run.id;
    const stamp = version.current;
    const poll = async () => {
      try {
        const next = await request<ExportSession>("/decisions/" + id);
        if (stopped || stamp !== version.current) return;
        setRun(next);
        if (["ready", "chosen"].includes(next.status))
          timer = setTimeout(() => void poll(), 1600);
        else await refresh();
      } catch (e) {
        if (!stopped && stamp === version.current) {
          setError((e as Error).message);
          timer = setTimeout(() => void poll(), 3500);
        }
      }
    };
    timer = setTimeout(() => void poll(), 1600);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [run?.id, run?.status, busy, refresh]);

  function reset() {
    version.current++;
    operations.current.clear();
    current.current = null;
    setRun(null);
    setBusy(false);
    setError("");
    sessionUrl();
  }

  async function mutate(path: string, body: object, method = "POST") {
    if (!token || busy) return;
    const stamp = ++version.current;
    setBusy(true);
    setError("");
    try {
      const next = await request<ExportSession | undefined>(
        path,
        token,
        method,
        body,
      );
      if (stamp === version.current) {
        current.current = next?.id ?? null;
        setRun(next ?? null);
        sessionUrl(next?.id);
      }
      await refresh();
    } catch (e) {
      if (stamp === version.current) setError((e as Error).message);
    } finally {
      if (stamp === version.current) setBusy(false);
    }
  }

  function operation(key: string) {
    let id = operations.current.get(key);
    if (!id) {
      id = crypto.randomUUID();
      operations.current.set(key, id);
    }
    return id;
  }

  async function create(title: string, text: string) {
    try {
      if (new TextEncoder().encode(text).length > 32_768)
        throw new Error("输入最大为 32 KiB。");
      await mutate("/decisions", {
        title,
        input_text: text,
        request_id: operation(JSON.stringify([title, text])),
      });
    } catch (e) {
      setError(
        e instanceof SyntaxError
          ? "请输入有效的 JSON 对象数组。"
          : (e as Error).message,
      );
    }
  }

  function answer(key: ExportKey, value: string) {
    if (!run || current.current !== run.id) return;
    return mutate(`/decisions/${run.id}/answer`, {
      key,
      value,
      revision: run.revision,
      request_id: operation(`${run.id}:${run.revision}:${key}:${value}`),
    });
  }

  function complete() {
    if (run)
      return mutate(`/decisions/${run.id}/complete`, {
        revision: run.revision,
      });
  }

  function remove() {
    if (run && window.confirm("删除这个会话及其本地输入、预览和证据？"))
      return mutate(`/decisions/${run.id}`, {}, "DELETE");
  }

  return {
    sample,
    history,
    run,
    busy,
    error,
    ready: Boolean(token),
    setError,
    open,
    reset,
    create,
    answer,
    complete,
    remove,
  };
}
