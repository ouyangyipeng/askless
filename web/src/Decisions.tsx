import {
  ArrowUpRight,
  Check,
  ChevronDown,
  Fingerprint,
  Users,
} from "lucide-react";
import type { Evidence, Group, Key, Run } from "./types";

export function DataTable({
  rows,
  columns,
  limit = 5,
}: {
  rows: Record<string, string>[];
  columns: string[];
  limit?: number;
}) {
  if (!rows.length)
    return <div className="empty-table">本分支没有可导出的记录</div>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, limit).map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c} title={row[c]}>
                  {row[c]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > limit && (
        <div className="table-note">
          展示前 {limit} / {rows.length} 行，完整结果保存在证据包中
        </div>
      )}
    </div>
  );
}

function TrialStats({ trial }: { trial: Evidence }) {
  return (
    <div className="trial-stats">
      <span>
        <b>{trial.rows.length}</b> 导出
      </span>
      <span>
        <b>{trial.quarantined.length}</b> 隔离
      </span>
      <span className={trial.blocked ? "orange-text" : "green-text"}>
        {trial.blocked ? "整批阻断" : "可交付"}
      </span>
    </div>
  );
}

function DecisionCard({
  run,
  group,
  index,
  value,
  disabled,
  onSelect,
}: {
  run: Run;
  group: Group;
  index: number;
  value?: string;
  disabled: boolean;
  onSelect: (key: Key, value: string) => void;
}) {
  const witnesses = group.witnesses
    .map((id) => run.trials.find((t) => t.id === id))
    .filter((x): x is Evidence => !!x);
  const enabled = run.status === "ready" && !disabled;
  return (
    <article className="decision-card">
      <div className="decision-heading">
        <span className="number-tag">{String(index + 1).padStart(2, "0")}</span>
        <span className="eyebrow">
          {group.status === "answered" ? "已确认的决定" : "需要你的决定"}
        </span>
        <span className="source-pill">
          <Users size={13} />
          {group.agent_ids.length} 个角色 · {group.question_ids.length} 个问题
        </span>
      </div>
      <h3>{group.spec.title}</h3>
      <p className="muted card-context">{group.spec.context}</p>
      <div
        className="option-grid"
        role="radiogroup"
        aria-label={group.spec.title}
      >
        {group.spec.options.map((option) => {
          const trial = witnesses.find(
            (t) => t.policy[group.key] === option.value,
          );
          const chosen = value === option.value;
          return (
            <button
              className={"option " + (chosen ? "selected" : "")}
              role="radio"
              aria-checked={chosen}
              aria-label={option.label}
              disabled={!enabled}
              key={option.value}
              onClick={() => onSelect(group.key, option.value)}
            >
              <span className="option-title">
                <span className="radio-dot">
                  {chosen && <Check size={12} />}
                </span>
                {option.label}
              </span>
              <span className="option-description">{option.description}</span>
              {trial && <TrialStats trial={trial} />}
              <span className="option-footer">
                {chosen ? "已选择" : enabled ? "选择此方案" : "执行证据"}
                <ArrowUpRight size={14} />
              </span>
            </button>
          );
        })}
      </div>
      <details className="evidence-details">
        <summary>
          <Fingerprint size={14} />
          查看真实分支结果与原始问题
          <ChevronDown size={14} />
        </summary>
        <p className="muted evidence-note">
          以下两份产物来自仅改变此项选择的一对真实执行。其余策略保持相同；还检查了其他组合，共{" "}
          {group.comparisons_checked} 对。
        </p>
        <div className="comparison-grid">
          {witnesses.map((trial) => (
            <div className="branch" key={trial.id}>
              <div className="branch-heading">
                {
                  group.spec.options.find(
                    (o) => o.value === trial.policy[group.key],
                  )?.label
                }
                <span>{trial.elapsed_ms.toFixed(2)} ms</span>
              </div>
              <DataTable rows={trial.rows} columns={run.dataset.columns} />
              <code>sha256 {trial.output_hash.slice(0, 16)}…</code>
            </div>
          ))}
        </div>
        <div className="source-questions">
          {run.questions
            .filter((q) => group.question_ids.includes(q.id))
            .map((q) => (
              <div key={q.id}>
                <span>{run.agents.find((a) => a.id === q.agent_id)?.name}</span>
                <p>{q.prompt}</p>
              </div>
            ))}
        </div>
      </details>
    </article>
  );
}

export function Decisions({
  run,
  selected,
  disabled,
  onSelect,
}: {
  run: Run;
  selected: Partial<PolicySelection>;
  disabled: boolean;
  onSelect: (key: Key, value: string) => void;
}) {
  const decisions = run.groups.filter((g) => g.status !== "auto");
  return (
    <div className="decisions">
      {decisions.map((g, i) => (
        <DecisionCard
          key={g.key}
          run={run}
          group={g}
          index={i}
          disabled={disabled}
          value={
            g.status === "pending" ? selected[g.key] : (g.selected ?? undefined)
          }
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
type PolicySelection = Record<Key, string>;
