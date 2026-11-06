import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clock3,
  Database,
  Download,
  FileSpreadsheet,
  FlaskConical,
  GitBranch,
  History as HistoryIcon,
  LoaderCircle,
  Plus,
  Radio,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { request } from "./api";
import { DataTable, Decisions } from "./Decisions";
import { isActive, statusLabel } from "./types";
import type { Config, History, Key, Run } from "./types";

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [history, setHistory] = useState<History[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [title, setTitle] = useState(
    "把这批联系人整理成可以导入的 CSV，先把会改变结果的选择做给我看。",
  );
  const [csv, setCsv] = useState("");
  const [filename, setFilename] = useState("contacts.csv");
  const [mode, setMode] = useState<"live" | "offline">("live");
  const [selected, setSelected] = useState<Partial<Record<Key, string>>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const upload = useRef<HTMLInputElement>(null);
  const currentId = useRef<string | null>(null);
  const viewVersion = useRef(0);
  const refreshHistory = useCallback(
    () => request<History[]>("/runs").then(setHistory),
    [],
  );

  useEffect(() => {
    void request<Config>("/config")
      .then((c) => {
        setConfig(c);
        setCsv(c.sample_csv);
        setMode(c.configured ? "live" : "offline");
        return refreshHistory();
      })
      .catch((e) => setError(String(e.message)));
  }, [refreshHistory]);
  useEffect(() => {
    if (!run || !isActive(run.status)) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const id = run.id;
    async function poll() {
      try {
        const next = await request<Run>("/runs/" + id);
        if (stopped || currentId.current !== id) return;
        setRun(next);
        if (isActive(next.status)) timer = setTimeout(() => void poll(), 900);
        else await refreshHistory();
      } catch (e) {
        if (!stopped) {
          setError((e as Error).message);
          timer = setTimeout(() => void poll(), 2500);
        }
      }
    }
    timer = setTimeout(() => void poll(), 600);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [run?.id, run?.status, refreshHistory]);

  async function start() {
    if (!config || busy) return;
    const version = ++viewVersion.current;
    setBusy(true);
    setError("");
    setSelected({});
    try {
      const next = await request<Run>("/runs", config.token, "POST", {
        title,
        csv_text: csv,
        mode,
      });
      if (viewVersion.current === version) {
        currentId.current = next.id;
        setRun(next);
      }
      await refreshHistory();
    } catch (e) {
      if (viewVersion.current === version) setError((e as Error).message);
    } finally {
      if (viewVersion.current === version) setBusy(false);
    }
  }
  async function choose() {
    if (!config || !run || busy || currentId.current !== run.id) return;
    const version = viewVersion.current;
    const id = run.id;
    setBusy(true);
    setError("");
    try {
      const next = await request<Run>(
        `/runs/${id}/answers`,
        config.token,
        "POST",
        {
          answers: selected,
          revision: run.revision,
        },
      );
      if (viewVersion.current === version && currentId.current === id) {
        setSelected({});
        setRun(next);
      }
      await refreshHistory();
    } catch (e) {
      if (viewVersion.current === version) setError((e as Error).message);
    } finally {
      if (viewVersion.current === version) setBusy(false);
    }
  }
  async function openRun(id: string) {
    const version = ++viewVersion.current;
    setBusy(true);
    setError("");
    setSelected({});
    currentId.current = id;
    try {
      const next = await request<Run>("/runs/" + id);
      if (viewVersion.current === version && currentId.current === id)
        setRun(next);
    } catch (e) {
      if (viewVersion.current === version) {
        currentId.current = run?.id ?? null;
        setError((e as Error).message);
      }
    } finally {
      if (viewVersion.current === version) setBusy(false);
    }
  }
  async function remove(item: History) {
    if (!config || !window.confirm("删除这次运行及其本地数据？")) return;
    try {
      await request(`/runs/${item.id}`, config.token, "DELETE");
      if (currentId.current === item.id) {
        viewVersion.current += 1;
        currentId.current = null;
        setRun(null);
        setBusy(false);
        setSelected({});
      }
      await refreshHistory();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function loadFile(file?: File) {
    if (!file) return;
    if (file.size > 262144) {
      setError("CSV 文件最大为 256 KiB。");
      return;
    }
    const version = viewVersion.current;
    try {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(
        await file.arrayBuffer(),
      );
      if (viewVersion.current !== version) return;
      setCsv(text);
      setFilename(file.name);
      setError("");
    } catch {
      if (viewVersion.current === version)
        setError("文件读取失败，请使用 UTF-8 编码的 CSV。");
    }
  }
  const required =
    run?.groups.filter((g) => g.status === "pending").length ?? 0;
  const humanDecisions =
    run?.groups.filter((g) => g.status !== "auto").length ?? 0;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="AskLess 首页">
          <span className="brand-mark">
            <GitBranch size={21} />
          </span>
          askless<span className="beta">LAB</span>
        </a>
        <div className="sidebar-caption">LESS ASKING. MORE DOING.</div>
        <button
          className={"nav-item " + (!run ? "active" : "")}
          onClick={() => {
            viewVersion.current += 1;
            currentId.current = null;
            setRun(null);
            setSelected({});
            setError("");
            setBusy(false);
          }}
        >
          <Plus size={17} />
          新建试验<span>↗</span>
        </button>
        <div className="sidebar-section">
          <HistoryIcon size={13} />
          本地运行<span>{history.length}</span>
        </div>
        <nav className="history-list" aria-label="运行历史">
          {history.length === 0 ? (
            <p className="empty-history">
              第一份运行记录
              <br />
              会从这里开始。
            </p>
          ) : (
            history.map((item) => (
              <div
                className={
                  "history-entry " + (run?.id === item.id ? "current" : "")
                }
                key={item.id}
              >
                <button onClick={() => void openRun(item.id)}>
                  <span className={"history-dot " + item.status} />
                  <span>
                    <b>{item.title}</b>
                    <small>
                      {statusLabel[item.status]} · {item.rows} 行
                    </small>
                  </span>
                </button>
                {!isActive(item.status) && (
                  <button
                    className="delete-run"
                    aria-label="删除运行"
                    onClick={() => void remove(item)}
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            ))
          )}
        </nav>
        <div className="sidebar-bottom">
          <ShieldCheck size={17} />
          <div>
            <b>在你的电脑上运行</b>
            <span>原始 CSV 与执行产物本地保存</span>
          </div>
          <span className="local-dot" />
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>工作台</span>
            <ChevronRight size={13} />
            <b>{run ? "决策试验" : "新建试验"}</b>
          </div>
          <select
            className="mobile-history"
            aria-label="切换本地运行"
            value={run?.id ?? ""}
            onChange={(e) => void openRun(e.target.value)}
            disabled={history.length === 0}
          >
            <option value="" disabled>
              选择历史运行
            </option>
            {history.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
          <span
            className={"connection " + (config?.configured ? "online" : "")}
          >
            <span />
            {config?.configured ? config.model : "离线演示可用"}
          </span>
        </header>
        <div className="content">
          {error && (
            <div className="error-banner" role="alert">
              {error}
              <button aria-label="关闭提示" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {!run ? (
            <>
              <div className="intro">
                <div className="eyebrow">
                  <span className="tiny-line" />
                  THE DECISION COMPILER
                </div>
                <h1>
                  把时间，
                  <br />
                  <span>留给决定。</span>
                </h1>
                <p>
                  让 Agent 先试过所有选择。
                  <br />
                  只有真正改变结果的问题，才来到你面前。
                </p>
                <div className="intro-notation">
                  <span>3</span> agents <ArrowRight size={18} />
                  <span>8</span> experiments <ArrowRight size={18} />
                  <span>?</span> decisions
                </div>
              </div>
              <div className="setup-grid">
                <section className="setup-card">
                  <div className="section-heading">
                    <div>
                      <span className="eyebrow">01 / 开始一次真实试验</span>
                      <h2>这次，让它们处理什么？</h2>
                    </div>
                    <FileSpreadsheet size={23} />
                  </div>
                  <label className="field-label" htmlFor="brief">
                    任务描述
                  </label>
                  <textarea
                    id="brief"
                    className="brief-input"
                    maxLength={2000}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                  <div className="field-row">
                    <label className="field-label">输入数据</label>
                    <button
                      className="text-button"
                      onClick={() => {
                        if (config) {
                          setCsv(config.sample_csv);
                          setFilename("contacts.csv");
                        }
                      }}
                    >
                      载入示例
                    </button>
                  </div>
                  <button
                    className="file-drop"
                    onClick={() => upload.current?.click()}
                  >
                    <span className="file-icon">
                      <FileSpreadsheet size={22} />
                    </span>
                    <span>
                      <b>{filename}</b>
                      <small>UTF-8 CSV · 需包含 email 列 · 最大 256 KiB</small>
                    </span>
                    <Upload size={18} />
                  </button>
                  <input
                    ref={upload}
                    type="file"
                    accept=".csv,text/csv"
                    hidden
                    onChange={(e) => void loadFile(e.target.files?.[0])}
                  />
                  <details className="csv-editor">
                    <summary>
                      查看或编辑输入 CSV
                      <ChevronRight size={13} />
                    </summary>
                    <textarea
                      aria-label="CSV 数据"
                      spellCheck={false}
                      value={csv}
                      onChange={(e) => setCsv(e.target.value)}
                    />
                  </details>
                  <div className="mode-bar">
                    <span>提问方式</span>
                    <div className="segmented">
                      <button
                        className={mode === "live" ? "chosen" : ""}
                        disabled={!config?.configured}
                        onClick={() => setMode("live")}
                      >
                        <Radio size={12} />
                        真实 LLM
                      </button>
                      <button
                        className={mode === "offline" ? "chosen" : ""}
                        onClick={() => setMode("offline")}
                      >
                        离线演示
                      </button>
                    </div>
                  </div>
                  <p className="privacy-note">
                    {mode === "live"
                      ? "任务描述、聚合统计与策略合同发送至阿里云；原始数据留在本机。"
                      : "离线模式使用固定角色提问，执行与比较仍在本机真实运行。"}
                  </p>
                  <button
                    className="primary start-button"
                    disabled={busy || !config || !title.trim() || !csv.trim()}
                    onClick={() => void start()}
                  >
                    {busy ? (
                      <LoaderCircle className="spin" size={18} />
                    ) : (
                      <FlaskConical size={18} />
                    )}
                    让 Agent 先试一遍
                    <ArrowRight size={18} />
                  </button>
                </section>
                <aside className="how-it-works">
                  <span className="eyebrow">WHAT HAPPENS NEXT</span>
                  <h2>
                    问题到你之前，
                    <br />
                    先经过一轮计算。
                  </h2>
                  <div className="flow-step">
                    <span>01</span>
                    <div>
                      <b>三个角色，独立提问</b>
                      <p>数据、质量、交付，各自提出影响结果的选择。</p>
                    </div>
                  </div>
                  <div className="flow-line" />
                  <div className="flow-step">
                    <span>02</span>
                    <div>
                      <b>实际执行，找出差异</b>
                      <p>完整试跑 8 种策略组合，留下可核对的产物。</p>
                    </div>
                  </div>
                  <div className="flow-line" />
                  <div className="flow-step">
                    <span>03</span>
                    <div>
                      <b>你只决定重要的部分</b>
                      <p>合并同源问题，自动解决结果等价的选择。</p>
                    </div>
                  </div>
                  <div className="scenario-note">
                    <Database size={17} />
                    <p>
                      <b>首个试验场：联系人 CSV</b>
                      <br />
                      重复处理 · 异常隔离 · 邮箱大小写
                      <br />
                      选择适用于本次完整输入数据。
                    </p>
                  </div>
                </aside>
              </div>
            </>
          ) : (
            <>
              <div className="run-heading">
                <div>
                  <span className="eyebrow">
                    EXPERIMENT / {run.id.slice(0, 8)}
                  </span>
                  <h1>
                    {run.groups.length
                      ? "更少追问，更清楚的决定。"
                      : "先让 Agent 把选择跑出来。"}
                  </h1>
                  <p>{run.title}</p>
                </div>
                <span className={"run-status " + run.status}>
                  {isActive(run.status) ? (
                    <LoaderCircle size={14} className="spin" />
                  ) : (
                    <CircleDot size={14} />
                  )}{" "}
                  {statusLabel[run.status]}
                </span>
              </div>
              <div className="run-metadata">
                <span>
                  <FileSpreadsheet size={13} />
                  {run.dataset.rows.length} 行输入
                </span>
                <span>
                  <FingerprintIcon />
                  {run.dataset.scope.slice(0, 12)}
                </span>
                <span className={run.mode === "offline" ? "offline-label" : ""}>
                  {run.mode === "live"
                    ? `${run.model} · 真实调用`
                    : "离线演示 · 固定提问"}
                </span>
                <span>
                  {run.llm_calls} 次 LLM 请求 ·{" "}
                  {(run.input_tokens + run.output_tokens).toLocaleString()}{" "}
                  tokens
                </span>
              </div>
              <div className="agents-grid">
                {run.agents.map((agent, i) => (
                  <article className="agent" key={agent.id}>
                    <div className="agent-top">
                      <span className={"avatar avatar-" + i}>
                        {["D", "Q", "P"][i]}
                      </span>
                      <div>
                        <h3>{agent.name}</h3>
                        <small>{agent.role}</small>
                      </div>
                      {["thinking", "resuming"].includes(agent.status) ? (
                        <LoaderCircle size={15} className="spin" />
                      ) : agent.status === "done" ? (
                        <CheckCircle2 size={16} className="green-text" />
                      ) : (
                        <span className="agent-state">
                          {agent.status === "waiting_decision"
                            ? "待决定"
                            : "准备中"}
                        </span>
                      )}
                    </div>
                    <p>{agent.summary || "正在等待角色分析…"}</p>
                    <div className="agent-count">
                      {
                        run.questions.filter((q) => q.agent_id === agent.id)
                          .length
                      }{" "}
                      个原始问题
                      <span>
                        {agent.status === "done"
                          ? "答案已消费"
                          : "作用域已绑定"}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
              {run.error && (
                <div className="error-banner" role="alert">
                  {run.error}
                </div>
              )}
              {run.groups.length > 0 && (
                <>
                  <div className="compression">
                    <div>
                      <span className="eyebrow">这次试验的结果</span>
                      <div className="compression-equation">
                        <b>{run.questions.length}</b>
                        <span>个问题</span>
                        <ArrowRight size={28} />
                        <b className="orange-text">{humanDecisions}</b>
                        <span>个决定</span>
                      </div>
                    </div>
                    <div className="compression-facts">
                      <span>
                        <Check size={15} />
                        {run.trials.length} 次真实执行
                      </span>
                      <span>
                        <Check size={15} />
                        {
                          run.groups.filter((g) => g.status === "auto").length
                        }{" "}
                        项结果等价
                      </span>
                      <span>
                        <Check size={15} />
                        覆盖策略交互
                      </span>
                    </div>
                  </div>
                  {run.groups
                    .filter((g) => g.status === "auto")
                    .map((g) => (
                      <details className="auto-resolved" key={g.key}>
                        <summary>
                          <CheckCircle2 size={17} />
                          <span>
                            {g.spec.title}
                            <b>已由试验解决</b>
                          </span>
                          <ChevronRight size={15} />
                        </summary>
                        <p>
                          {g.reason} 默认采用“
                          {
                            g.spec.options.find((o) => o.value === g.selected)
                              ?.label
                          }
                          ”。
                        </p>
                      </details>
                    ))}
                  <Decisions
                    run={run}
                    selected={selected}
                    disabled={busy}
                    onSelect={(key, value) => {
                      if (!busy && currentId.current === run.id)
                        setSelected((s) => ({ ...s, [key]: value }));
                    }}
                  />
                </>
              )}
              {run.status === "completed" && run.result && (
                <section className="results">
                  <div className="result-heading">
                    <span className="success-icon">
                      <Check size={23} />
                    </span>
                    <div>
                      <span className="eyebrow">DECISIONS → ACTION</span>
                      <h2>
                        {run.result.blocked
                          ? "整批暂停，等待数据修复。"
                          : `${run.result.rows.length} 条联系人，已准备好。`}
                      </h2>
                      <p>
                        {run.result.quarantined.length}{" "}
                        条异常记录保存在证据包。三个角色已按相同策略重新验证。
                      </p>
                    </div>
                  </div>
                  <div className="receipts">
                    {run.receipts.map((r) => (
                      <div key={r.agent_id}>
                        <CheckCircle2 size={15} />
                        <p>
                          <b>
                            {run.agents.find((a) => a.id === r.agent_id)?.name}
                          </b>
                          {r.summary}
                        </p>
                      </div>
                    ))}
                  </div>
                  <DataTable
                    rows={run.result.rows}
                    columns={run.dataset.columns}
                    limit={10}
                  />
                  <div className="download-row">
                    {!run.result.blocked && (
                      <a
                        className="primary"
                        href={`/api/runs/${run.id}/export`}
                        download
                      >
                        <Download size={16} />
                        下载最终 CSV
                      </a>
                    )}
                    <a
                      className="secondary"
                      href={`/api/runs/${run.id}/evidence`}
                      download
                    >
                      <Download size={16} />
                      下载完整证据包
                    </a>
                  </div>
                </section>
              )}
              <details className="timeline" open={isActive(run.status)}>
                <summary>
                  <Clock3 size={15} />
                  执行轨迹<span>{run.events.length} 个事件</span>
                </summary>
                <div>
                  {run.events.map((e, i) => (
                    <div className="event" key={i}>
                      <time>
                        {new Date(e.at).toLocaleTimeString("zh-CN", {
                          hour12: false,
                        })}
                      </time>
                      <span className="event-dot" />
                      <div>
                        <b>{e.label}</b>
                        <p>{e.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </details>
              {run.status === "ready" && (
                <div className="decision-bar">
                  <div>
                    <span className="selection-count">
                      {Object.keys(selected).length}
                      <small> / {required}</small>
                    </span>
                    <p>
                      {required
                        ? "看过结果，再做选择。"
                        : "所有选择均由真实执行解决。"}
                      <small>确认后答案会传播到三个角色。</small>
                    </p>
                  </div>
                  <button
                    className="primary"
                    disabled={busy || Object.keys(selected).length !== required}
                    onClick={() => void choose()}
                  >
                    {busy ? (
                      <LoaderCircle className="spin" size={16} />
                    ) : (
                      <ArrowRight size={16} />
                    )}
                    确认决定，继续执行
                  </button>
                </div>
              )}
            </>
          )}
          <footer>
            <span>ASKLESS / v{config?.version ?? "0.2.0"}</span>
            <span>
              先看证据，再做决定。
              <Sparkles size={12} />
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}

function FingerprintIcon() {
  return <GitBranch size={13} />;
}
