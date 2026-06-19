import type { Finding } from "../types";

interface Props {
  gates: Finding[];
  warnings: Finding[];
}

function FindingRow({ finding }: { finding: Finding }) {
  const isGate = finding.severity === "gate";
  return (
    <li className={`finding ${isGate ? "finding-gate" : "finding-warn"}`}>
      <span className={`badge ${isGate ? "badge-gate" : "badge-warn"}`}>
        {finding.severity.toUpperCase()}
      </span>
      <span className="finding-code">{finding.code}</span>
      <p className="finding-message">{finding.message}</p>
      {(finding.line_number != null || finding.field) && (
        <p className="finding-location">
          {finding.line_number != null && `Line ${finding.line_number}`}
          {finding.line_number != null && finding.field && " · "}
          {finding.field && `Field: ${finding.field}`}
        </p>
      )}
      {finding.discrepancy && (
        <p className="finding-discrepancy">
          Discrepancy: {finding.discrepancy}
        </p>
      )}
    </li>
  );
}

export default function FindingsPanel({ gates, warnings }: Props) {
  const all = [...gates, ...warnings];

  if (all.length === 0) {
    return (
      <section className="findings-panel">
        <h2>Validation Findings</h2>
        <p className="no-findings">No findings — all fields auto-pass.</p>
      </section>
    );
  }

  return (
    <section className="findings-panel">
      <h2>Validation Findings</h2>
      <ul className="findings-list">
        {gates.map((f, i) => (
          <FindingRow key={`gate-${f.code}-${i}`} finding={f} />
        ))}
        {warnings.map((f, i) => (
          <FindingRow key={`warn-${f.code}-${i}`} finding={f} />
        ))}
      </ul>
    </section>
  );
}
