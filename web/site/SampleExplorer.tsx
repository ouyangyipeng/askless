import { useState } from "react";
import sample from "./sample.json";

export function SampleExplorer() {
  const [duplicates, setDuplicates] = useState<"first" | "last">("first");
  const [invalid, setInvalid] = useState<"quarantine" | "block">("quarantine");
  const trial = sample.trials.find(
    (entry) =>
      entry.policy.duplicates === duplicates &&
      entry.policy.invalid === invalid &&
      entry.policy.email_case === "preserve",
  );
  if (!trial)
    throw new Error("The published sample is missing a policy branch.");

  return (
    <div className="sample-explorer">
      <div className="sample-controls">
        <div className="sample-label">
          <b>9 QUESTIONS</b>
          <span aria-hidden="true">→</span>2 DECISIONS
        </div>
        <fieldset>
          <legend>Which duplicate should survive?</legend>
          <span className="choice-note">
            First and last refer to the order in the CSV.
          </span>
          <div className="choice-pair">
            <button
              aria-pressed={duplicates === "first"}
              onClick={() => setDuplicates("first")}
            >
              Keep first row
            </button>
            <button
              aria-pressed={duplicates === "last"}
              onClick={() => setDuplicates("last")}
            >
              Keep last row
            </button>
          </div>
        </fieldset>
        <fieldset>
          <legend>What happens to invalid emails?</legend>
          <span className="choice-note">
            Both options retain the two invalid rows for review.
          </span>
          <div className="choice-pair">
            <button
              aria-pressed={invalid === "quarantine"}
              onClick={() => setInvalid("quarantine")}
            >
              Quarantine & continue
            </button>
            <button
              aria-pressed={invalid === "block"}
              onClick={() => setInvalid("block")}
            >
              Block entire batch
            </button>
          </div>
        </fieldset>
        <div className="equivalent-note">
          <span aria-hidden="true">✓</span>
          <div>
            <strong>Email case? Already resolved.</strong>
            <small>All four paired comparisons match on this input.</small>
          </div>
        </div>
      </div>
      <div
        className="sample-result"
        role="region"
        aria-label="Sample output"
        aria-live="polite"
        aria-atomic="true"
      >
        <div className="result-header">
          <span className="sample-label">OBSERVED OUTPUT</span>
          <span
            className={trial.blocked ? "result-badge blocked" : "result-badge"}
          >
            {trial.blocked ? "BATCH BLOCKED" : "READY TO EXPORT"}
          </span>
        </div>
        <div className="result-count">
          <strong>{trial.rows.length}</strong>
          <span>
            contacts to export · {trial.quarantined.length} quarantined
          </span>
        </div>
        {trial.blocked ? (
          <div className="blocked-result">
            <strong>The whole batch waits.</strong>
            <p>
              Two emails need a fix. No contacts are exported under this policy.
              Switch to quarantine to keep the valid rows moving.
            </p>
          </div>
        ) : (
          <table className="sample-table">
            <thead>
              <tr>
                <th scope="col">NAME</th>
                <th scope="col">EMAIL</th>
              </tr>
            </thead>
            <tbody>
              {trial.rows.map((row) => (
                <tr
                  key={row.email}
                  className={
                    duplicates === "last" &&
                    ["ada@example.com", "lin@example.com"].includes(row.email)
                      ? "changed"
                      : undefined
                  }
                >
                  <td>{row.name}</td>
                  <td>{row.email}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="result-foot" title={trial.output_hash}>
          SHA-256 · {trial.output_hash.slice(0, 28)}…
        </p>
      </div>
    </div>
  );
}
