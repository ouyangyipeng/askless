import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Download,
  GitBranch,
  History,
  LoaderCircle,
  Plus,
  RefreshCw,
  Terminal,
  Trash2,
  Upload,
} from "lucide-react";
import { ExportComparison } from "./ExportComparison";
import { exportLabels, sessionLabels } from "./decisionTypes";
import type { ExportSession } from "./decisionTypes";
import { useDecisionSession } from "./useDecisionSession";
import "./decision.css";

function InputForm({
  sample,
  busy,
  ready,
  create,
  onError,
}: {
  sample: string;
  busy: boolean;
  ready: boolean;
  create: (title: string, text: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [text, setText] = useState("");
  const [title, setTitle] = useState(
    "把这批记录整理为可交付文件，先让我比较结果。",
  );
  const upload = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setText(sample);
  }, [sample]);
  async function load(file?: File) {
    if (!file) return;
    if (file.size > 32_768) {
      onError("输入最大为 32 KiB。");
      return;
    }
    try {
      setText(
        new TextDecoder("utf-8", { fatal: true }).decode(
          await file.arrayBuffer(),
        ),
      );
    } catch {
      onError("请选择 UTF-8 编码的 JSON 文件。");
    }
  }
  return (
    <div className="export-intake">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void create(title, text);
        }}
      >
        <label className="export-label" htmlFor="export-task">
          01 / 你想完成什么
        </label>
        <textarea
          id="export-task"
          className="export-task"
          value={title}
          maxLength={2000}
          onChange={(event) => setTitle(event.target.value)}
          required
        />
        <div className="export-label-row">
          <label className="export-label" htmlFor="export-input">
            02 / 放入你的数据
          </label>
          <button type="button" onClick={() => upload.current?.click()}>
            <Upload size={13} /> 选择文件
          </button>
        </div>
        <input
          ref={upload}
          type="file"
          accept=".json,application/json"
          hidden
          onChange={(event) => {
            void load(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        <textarea
          id="export-input"
          className="export-input"
          value={text}
          onChange={(event) => setText(event.target.value)}
          spellCheck={false}
          required
        />
        <p className="export-hint">
          扁平 JSON 数组 · 最多 100 行 / 20 列 / 32 KiB
        </p>
        <button
          className="export-primary"
          disabled={busy || !ready || !text.trim() || !title.trim()}
        >
          {busy ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <GitBranch size={17} />
          )}
          准备实际结果
          <ArrowRight size={17} />
        </button>
      </form>
      <aside className="export-intro">
        <span className="export-kicker">A SMALLER DECISION SPACE</span>
        <h2>
          一个选择，
          <br />
          让后续问题消失。
        </h2>
        <p>
          先生成文件，再决定格式。选 JSON 后，分隔符和列名不再影响结果；选 CSV
          后，继续比较那些仍有差异的选项。
        </p>
        <div className="export-diagram">
          <span>8 个策略组合</span>
          <i />
          <strong>
            JSON <Check size={15} />
          </strong>
          <i />
          <span className="export-resolved">
            分隔符 <s>待回答</s>
            <br />
            列名 <s>待回答</s>
          </span>
        </div>
        <div className="export-agent-note">
          <Terminal size={18} />
          <div>
            <strong>也可以从 Python Agent 发起</strong>
            <p>
              Agent 通过 MCP 生成预览；你在这里选择，它从保存的会话继续执行。
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
}

function SessionEvidence({ run }: { run: ExportSession }) {
  const usage = run.agent_steps.reduce(
    (total, step) => ({
      requests: total.requests + step.requests,
      tokens: total.tokens + step.input_tokens + step.output_tokens,
    }),
    { requests: 0, tokens: 0 },
  );
  return (
    <aside className="export-evidence">
      <div className="export-evidence-title">
        <span className="export-kicker">RUN RECEIPT</span>
        <span className="export-dot" /> 保存在本机
      </div>
      <dl>
        <div>
          <dt>真实预览</dt>
          <dd>
            {run.trials.length || run.partial_trials?.length || 0}
            <small> / 8</small>
          </dd>
        </div>
        <div>
          <dt>你已确认</dt>
          <dd>{Object.keys(run.answers).length}</dd>
        </div>
        <div>
          <dt>模型请求</dt>
          <dd>
            {usage.requests}
            <small> 次</small>
          </dd>
        </div>
        <div>
          <dt>模型用量</dt>
          <dd>
            {usage.tokens}
            <small> tokens</small>
          </dd>
        </div>
      </dl>
      {run.agent_steps.length > 0 && (
        <p className="export-model">
          {run.agent_steps[0].model}
          <br />
          原始记录仅在本机预览
        </p>
      )}
      <div className="export-event-list">
        {run.events.map((event, index) => (
          <div className="export-event" key={`${event.at}-${index}`}>
            <span />
            <div>
              <strong>{event.label}</strong>
              <p>{event.detail}</p>
            </div>
          </div>
        ))}
      </div>
      <details className="export-scope">
        <summary>查看证据作用域</summary>
        <code>{run.scope ?? "预览未完成"}</code>
        <p>
          会话 {run.id}
          <br />
          版本 {run.revision} · 完成前重新执行并核对输出
        </p>
      </details>
      <a
        className="export-evidence-link"
        href={`/api/decisions/${run.id}/evidence`}
        target="_blank"
        rel="noreferrer"
      >
        打开完整证据 <ArrowRight size={13} />
      </a>
    </aside>
  );
}

function SessionResult({
  run,
  busy,
  complete,
}: {
  run: ExportSession;
  busy: boolean;
  complete: () => void;
}) {
  const artifact = run.result?.output.artifact;
  const autoCount = run.decisions.filter(
    (decision) => decision.status === "auto",
  ).length;
  return (
    <div
      className={`export-result ${run.status === "completed" ? "finished" : ""}`}
    >
      <CheckCircle2 size={35} strokeWidth={1.4} />
      <span className="export-kicker">
        {run.status === "completed" ? "REPLAY VERIFIED" : "READY TO CONTINUE"}
      </span>
      <h2>{autoCount === 2 ? "两项选择已自动消除" : "所有必要选择已确认"}</h2>
      <p>
        {run.status === "completed"
          ? "选定策略已重新执行，文件与预览逐字节一致。"
          : "你的选择已保存。接下来校验输入，并重新执行选定策略。"}
      </p>
      {run.status === "chosen" &&
        (run.owner === "mcp" ? (
          <div className="export-resume">
            <Terminal size={17} />
            <div>
              <strong>等待 Python Agent 恢复</strong>
              <p>复制 Agent 终端中的恢复命令；使用同一个 --data-dir。</p>
              <code>
                python -m askless.agent --resume {run.id} --data-dir
                &lt;原数据目录&gt;
              </code>
              <p>使用 --wait 启动的 Agent 会自动继续。</p>
            </div>
          </div>
        ) : (
          <button className="export-primary" disabled={busy} onClick={complete}>
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <RefreshCw size={16} />
            )}
            复算并生成文件
            <ArrowRight size={16} />
          </button>
        ))}
      {artifact && (
        <div className="export-delivery">
          <div className="export-filebar">
            <strong>{artifact.name}</strong>
            <span>{artifact.bytes} B</span>
          </div>
          <pre tabIndex={0}>
            <code>{artifact.text}</code>
          </pre>
          <a
            className="export-primary"
            href={`/api/decisions/${run.id}/artifact`}
          >
            <Download size={16} />
            下载已验证文件
            <ArrowRight size={16} />
          </a>
        </div>
      )}
    </div>
  );
}

export default function DecisionWorkbench() {
  const state = useDecisionSession();
  const { run, busy } = state;
  const pending = run?.decisions.find(
    (decision) => decision.status === "pending",
  );
  return (
    <div className="decision-shell">
      <nav className="export-nav">
        <a className="brand" href="/decisions">
          <span className="brand-mark">
            <GitBranch size={21} />
          </span>
          askless<span className="beta">0.3</span>
        </a>
        <div>
          <a href="/">
            <ArrowLeft size={13} /> 联系人工坊
          </a>
          <a
            href="https://github.com/ouyangyipeng/askless"
            target="_blank"
            rel="noreferrer"
          >
            GitHub ↗
          </a>
        </div>
      </nav>
      <div className="export-layout">
        <aside className="export-sidebar">
          <button className="export-new" onClick={state.reset}>
            <Plus size={16} />
            新建预览
          </button>
          <div className="export-history-title">
            <History size={13} /> 本地会话
            <span>{state.history.length} / 50</span>
          </div>
          <div className="export-history">
            {state.history.map((item) => (
              <button
                className={run?.id === item.id ? "current" : ""}
                key={item.id}
                onClick={() => void state.open(item.id)}
              >
                <strong>{item.title}</strong>
                <span>
                  <i className={item.status} />
                  {sessionLabels[item.status]}
                  <small>{item.owner === "mcp" ? "AGENT" : "LOCAL"}</small>
                </span>
              </button>
            ))}
            {!state.history.length && (
              <p>
                每次预览、选择和交付，
                <br />
                都会留下一份记录。
              </p>
            )}
          </div>
          <p className="export-local-note">
            LOCAL BY DESIGN
            <br />
            输入与产物保存在本机
            <br />
            最多两个未完成会话
          </p>
        </aside>
        <main className="export-main">
          <header className={"export-heading" + (run ? " has-session" : "")}>
            <span className="export-kicker">
              DECISION STUDIO <span>/ {run?.source_name ?? "FILE EXPORT"}</span>
            </span>
            <h1>
              {run ? (
                run.title
              ) : (
                <>
                  先看结果，
                  <br />
                  再做决定。
                </>
              )}
            </h1>
            {!run && (
              <p>让 Agent 把备选方案做给你看，只回答仍会改变结果的问题。</p>
            )}
            {run && (
              <div className="export-session-status">
                <span className={`export-state ${run.status}`}>
                  {sessionLabels[run.status]}
                </span>
                <span>
                  {run.owner === "mcp"
                    ? "Python Agent · MCP"
                    : "本地预览 · 无需模型"}
                </span>
                <button
                  disabled={busy}
                  onClick={() => void state.open(run.id)}
                  aria-label="刷新会话"
                >
                  <RefreshCw size={14} />
                </button>
                <button
                  disabled={busy}
                  onClick={() => void state.remove()}
                  aria-label="删除当前会话"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            )}
          </header>
          {state.error && (
            <div className="export-error" role="alert">
              {state.error}
            </div>
          )}
          {!run ? (
            <InputForm
              sample={state.sample}
              ready={state.ready}
              busy={busy}
              create={state.create}
              onError={state.setError}
            />
          ) : (
            <>
              <ol className="export-progress" aria-label="决策进度">
                {run.decisions.map((decision, index) => (
                  <li className={decision.status} key={decision.key}>
                    <span>
                      {decision.status === "pending" ? (
                        String(index + 1).padStart(2, "0")
                      ) : (
                        <Check size={12} />
                      )}
                    </span>
                    <strong>{exportLabels[decision.key]}</strong>
                    <small>
                      {decision.status === "auto"
                        ? "结果相同 · 自动消除"
                        : decision.status === "answered"
                          ? exportLabels[decision.selected ?? ""]
                          : "待比较"}
                    </small>
                  </li>
                ))}
              </ol>
              <div className="export-session-body">
                <section className="export-session-content" aria-live="polite">
                  {run.error && (
                    <div className="export-error" role="alert">
                      <strong>{sessionLabels[run.status]}</strong>
                      <p>{run.error}</p>
                      <button onClick={state.reset}>
                        基于当前数据重新预览 <ArrowRight size={14} />
                      </button>
                    </div>
                  )}
                  {run.status === "ready" && pending && (
                    <>
                      <div className="export-question">
                        <div>
                          <span className="export-kicker">
                            ONE CHOICE AT A TIME
                          </span>
                          <h2>{pending.prompt}</h2>
                        </div>
                        <span>剩余 {run.pending.length} 项</span>
                      </div>
                      <ExportComparison
                        decision={pending}
                        trials={run.trials}
                        busy={busy}
                        choose={(key, value) => void state.answer(key, value)}
                      />
                      <p className="export-comparison-note">
                        两份文件来自真实执行。卡片底部列出其余策略；确认后，继续比较仍会改变结果的选择。
                      </p>
                    </>
                  )}
                  {["chosen", "completed"].includes(run.status) && (
                    <SessionResult
                      run={run}
                      busy={busy}
                      complete={() => void state.complete()}
                    />
                  )}
                </section>
                <SessionEvidence run={run} />
              </div>
            </>
          )}
          <footer className="export-footer">
            <span>ASKLESS / DECISIONS, WITH EVIDENCE.</span>
            <span>8 次受控预览 · 最终重新执行校验</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
