import { useState } from "react";
import orders from "./orders.json";

export function OrderExplorer() {
  const [duplicates, setDuplicates] = useState<"first" | "last">("last");
  const [cancelled, setCancelled] = useState<"exclude" | "include">("exclude");
  const trial = orders.trials.find(
    (entry) =>
      entry.policy.duplicates === duplicates &&
      entry.policy.cancelled === cancelled &&
      entry.policy.rounding === "per_order",
  );
  if (!trial)
    throw new Error("The published order sample is missing a branch.");
  const output = trial.output;

  return (
    <div className="order-explorer">
      <div className="workflow-caption">
        <span className="eyebrow">ORDER SUMMARY / PYTHON SDK</span>
        <span>6 input rows · 3 declared choices · 8 previews</span>
      </div>
      <div className="sample-explorer">
        <div className="sample-controls">
          <div className="sample-label">
            <b>3 DECLARED CHOICES</b>
            <span aria-hidden="true">→</span>2 HUMAN DECISIONS
          </div>
          <fieldset>
            <legend>One order ID. Two amounts.</legend>
            <span className="choice-note">
              A100 appears as $35.00, then $42.00. Which row wins?
            </span>
            <div className="choice-pair">
              <button
                aria-pressed={duplicates === "first"}
                onClick={() => setDuplicates("first")}
              >
                Keep first order
              </button>
              <button
                aria-pressed={duplicates === "last"}
                onClick={() => setDuplicates("last")}
              >
                Keep last order
              </button>
            </div>
          </fieldset>
          <fieldset>
            <legend>Does a cancelled order count?</legend>
            <span className="choice-note">
              A101 adds $12.50 if you include it.
            </span>
            <div className="choice-pair">
              <button
                aria-pressed={cancelled === "exclude"}
                onClick={() => setCancelled("exclude")}
              >
                Exclude cancelled
              </button>
              <button
                aria-pressed={cancelled === "include"}
                onClick={() => setCancelled("include")}
              >
                Include cancelled
              </button>
            </div>
          </fieldset>
          <div className="equivalent-note">
            <span aria-hidden="true">✓</span>
            <div>
              <strong>Rounding resolves itself here.</strong>
              <small>
                All 4 paired comparisons match. Every amount already has two
                decimal places.
              </small>
            </div>
          </div>
        </div>
        <div
          className="sample-result"
          role="region"
          aria-label="Order summary"
          aria-live="polite"
          aria-atomic="true"
        >
          <div className="result-header">
            <span className="sample-label">OBSERVED TOTAL</span>
            <span className="result-badge">SAVED EXECUTION</span>
          </div>
          <div className="order-total">
            <span>USD</span>
            <strong>{output.total}</strong>
          </div>
          <p className="order-count">
            {output.order_count} orders included ·{" "}
            {output.excluded_cancelled.length} cancelled excluded
          </p>
          <table className="sample-table order-table">
            <thead>
              <tr>
                <th scope="col">ORDER ID</th>
                <th scope="col">STATUS</th>
                <th scope="col">AMOUNT / USD</th>
              </tr>
            </thead>
            <tbody>
              {output.orders.map((order) => (
                <tr
                  key={order.order_id}
                  className={order.order_id === "A100" ? "changed" : undefined}
                >
                  <td>{order.order_id}</td>
                  <td>{order.status}</td>
                  <td>{order.amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="result-foot" title={trial.output_hash}>
            SHA-256 · {trial.output_hash.slice(0, 28)}…
          </p>
        </div>
      </div>
      <div className="workflow-cost">
        <span>THE TRADE-OFF</span>
        <p>
          One direct execution becomes eight previews + one verified replay. Try
          your own data to see which questions survive.
        </p>
      </div>
    </div>
  );
}
