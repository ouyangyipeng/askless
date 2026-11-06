import { useState } from "react";
import sample from "./exports.json";

type Key = "format" | "separator" | "header";
type Answers = Partial<Record<Key, string>>;
const labels: Record<string, string> = {
  format: "File format",
  separator: "Delimiter",
  header: "Column names",
  json: "JSON",
  csv: "CSV",
  comma: "Comma",
  semicolon: "Semicolon",
  include: "Include names",
  omit: "Omit names",
};

export function ExportExplorer() {
  const [answers, setAnswers] = useState<Answers>({});
  const stage =
    sample.stages.find(
      (item) => JSON.stringify(item.answers) === JSON.stringify(answers),
    ) ?? sample.stages[0];
  const pending = stage.decisions.find(
    (decision) => decision.status === "pending",
  );
  const pair =
    pending?.witnesses.map((id) =>
      sample.trials.find((trial) => trial.id === id)!,
    ) ?? [];
  const selected = stage.result;
  return (
    <div className="file-explorer">
      <div className="file-demo-top">
        <span className="eyebrow">FILE EXPORT / INTERACTIVE REPLAY</span>
        <button onClick={() => setAnswers({})}>Reset ↺</button>
      </div>
      <div className="file-demo-progress">
        {stage.decisions.map((decision) => (
          <div key={decision.key} className={decision.status}>
            <span>{decision.status === "pending" ? "○" : "✓"}</span>
            <strong>{labels[decision.key]}</strong>
            <small>
              {decision.status === "auto"
                ? "Same result · resolved"
                : decision.status === "answered"
                  ? labels[decision.selected ?? ""]
                  : "Your choice"}
            </small>
          </div>
        ))}
      </div>
      <div className="file-demo-heading">
        <h3>
          {pending
            ? labels[pending.key] + ": compare the actual files."
            : "Your choice is ready to deliver."}
        </h3>
        <p>
          {pending
            ? `${stage.decisions.filter((decision) => decision.status === "pending").length} relevant choices remain.`
            : `${Object.keys(answers).length} human ${Object.keys(answers).length === 1 ? "choice" : "choices"}. ${stage.decisions.filter((decision) => decision.status === "auto").length} resolved from matching outputs.`}
        </p>
      </div>
      {pending ? (
        <div className="file-demo-options">
          {pair.map((trial, index) => (
            <article key={trial.id}>
              <header>
                <span>OPTION {index === 0 ? "A" : "B"}</span>
                <strong>{labels[trial.policy[pending.key as Key]]}</strong>
                <small>{trial.output.artifact.bytes} B</small>
              </header>
              <div className="file-demo-filename">
                {trial.output.artifact.name}
              </div>
              <pre tabIndex={0}>{trial.output.artifact.text}</pre>
              <footer>
                <span>
                  {Object.entries(trial.policy)
                    .filter(([key]) => key !== pending.key)
                    .map(([, value]) => labels[value])
                    .join(" · ")}
                </span>
                <button
                  onClick={() =>
                    setAnswers({
                      ...answers,
                      [pending.key]: trial.policy[pending.key as Key],
                    })
                  }
                >
                  Choose {labels[trial.policy[pending.key as Key]]}{" "}
                  <span>↗</span>
                </button>
              </footer>
            </article>
          ))}
        </div>
      ) : (
        <div className="file-demo-result">
          <span>✓ MATCHED ON FINAL REPLAY</span>
          <h4>{selected?.artifact.name}</h4>
          <pre tabIndex={0}>{selected?.artifact.text}</pre>
          <p>
            {answers.format === "json"
              ? "Choosing JSON made the delimiter and column-name choices irrelevant. All remaining previews match."
              : "Every retained choice changed the file. The selected CSV was replayed and matched its preview."}
          </p>
        </div>
      )}
      <p className="file-demo-note">
        Recorded from the Python executor: 8 complete previews, then a verified
        replay for each final choice. This page replays bundled evidence; your
        local workbench runs your own data.
      </p>
    </div>
  );
}
