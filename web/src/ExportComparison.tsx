import { ArrowUpRight, Check, FileJson, FileSpreadsheet } from "lucide-react";
import { exportLabels } from "./decisionTypes";
import type { ExportDecision, ExportKey, ExportTrial } from "./decisionTypes";

export function ExportComparison({
  decision,
  trials,
  busy = false,
  choose,
}: {
  decision: ExportDecision;
  trials: ExportTrial[];
  busy?: boolean;
  choose: (key: ExportKey, value: string) => void;
}) {
  const pair = decision.witnesses
    .map((id) => trials.find((trial) => trial.id === id))
    .filter((trial): trial is ExportTrial => Boolean(trial));
  return (
    <div className="export-comparison">
      {pair.map((trial, index) => {
        const value = trial.policy[decision.key];
        const artifact = trial.output.artifact;
        const Icon =
          trial.policy.format === "json" ? FileJson : FileSpreadsheet;
        return (
          <article className="export-option" key={trial.id}>
            <header>
              <div className="export-option-mark">
                <Icon size={23} />
              </div>
              <div>
                <span className="export-kicker">
                  OPTION {index === 0 ? "A" : "B"}
                </span>
                <h3>{exportLabels[value] ?? value}</h3>
              </div>
              <span className="export-bytes">{artifact.bytes} B</span>
            </header>
            <div className="export-filebar">
              <span>{artifact.name}</span>
              <span>
                <Check size={12} /> 已执行
              </span>
            </div>
            <pre tabIndex={0} aria-label={`${exportLabels[value]} 文件内容`}>
              <code>{artifact.text}</code>
            </pre>
            <div className="export-context">
              {trial.output.rows} 行 · {trial.output.columns.length} 列
              <span>
                {Object.entries(trial.policy)
                  .filter(([key]) => key !== decision.key)
                  .map(([, option]) => exportLabels[option] ?? option)
                  .join(" · ")}
              </span>
            </div>
            <button
              className="export-choose"
              disabled={busy}
              onClick={() => choose(decision.key, value)}
            >
              选择 {exportLabels[value] ?? value}
              <ArrowUpRight size={17} />
            </button>
          </article>
        );
      })}
    </div>
  );
}
