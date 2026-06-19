import type { Entry7501, Finding } from "../types";

interface Props {
  entry: Entry7501;
  findings: Finding[];
}

function isHeaderHighlighted(findings: Finding[], field: string): boolean {
  return findings.some((f) => f.field === field);
}

function isLineHighlighted(
  findings: Finding[],
  field: string,
  lineNumber: number,
): boolean {
  return findings.some(
    (f) => f.field === field && f.line_number === lineNumber,
  );
}

function headerClass(findings: Finding[], field: string): string {
  if (!isHeaderHighlighted(findings, field)) return "";
  const matching = findings.filter((f) => f.field === field);
  const hasGate = matching.some((f) => f.severity === "gate");
  return hasGate ? "highlight-gate" : "highlight-warn";
}

function lineCellClass(
  findings: Finding[],
  field: string,
  lineNumber: number,
): string {
  if (!isLineHighlighted(findings, field, lineNumber)) return "";
  const matching = findings.filter(
    (f) => f.field === field && f.line_number === lineNumber,
  );
  const hasGate = matching.some((f) => f.severity === "gate");
  return hasGate ? "highlight-gate" : "highlight-warn";
}

const LINE_FIELDS = [
  "line_number",
  "hts_code",
  "description",
  "quantity",
  "unit_of_measure",
  "unit_price",
  "entered_value",
  "duty_paid",
  "mpf_paid",
  "hmf_paid",
] as const;

export default function EntryViewer({ entry, findings }: Props) {
  const totalDtf = entry.line_items.reduce((sum, li) => {
    return (
      sum +
      parseFloat(li.duty_paid) +
      parseFloat(li.mpf_paid) +
      parseFloat(li.hmf_paid)
    );
  }, 0);

  return (
    <section className="entry-viewer">
      <h2>Extracted Entry</h2>

      <div className="header-grid">
        <div className={headerClass(findings, "entry_number")}>
          <span className="label">Entry #</span>
          <span>{entry.entry_number}</span>
        </div>
        <div className={headerClass(findings, "entry_date")}>
          <span className="label">Entry date</span>
          <span>{entry.entry_date}</span>
        </div>
        <div className={headerClass(findings, "importer_of_record")}>
          <span className="label">Importer</span>
          <span>{entry.importer_of_record}</span>
        </div>
        <div className={headerClass(findings, "port_of_entry")}>
          <span className="label">Port</span>
          <span>{entry.port_of_entry ?? "—"}</span>
        </div>
        <div className={headerClass(findings, "total_entered_value")}>
          <span className="label">Total entered value</span>
          <span>${entry.total_entered_value}</span>
        </div>
        <div className={headerClass(findings, "total_duty")}>
          <span className="label">Total duty</span>
          <span>${entry.total_duty}</span>
        </div>
        <div className={headerClass(findings, "total_mpf")}>
          <span className="label">Total MPF</span>
          <span>${entry.total_mpf}</span>
        </div>
        <div className={headerClass(findings, "total_hmf")}>
          <span className="label">Total HMF</span>
          <span>${entry.total_hmf}</span>
        </div>
      </div>

      <p className="drawback-pool">
        Total duties/taxes/fees available for drawback:{" "}
        <strong>${totalDtf.toFixed(2)}</strong>
      </p>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Line</th>
              <th>HTS</th>
              <th>Description</th>
              <th>Qty</th>
              <th>UOM</th>
              <th>Unit price</th>
              <th>Entered value</th>
              <th>Duty</th>
              <th>MPF</th>
              <th>HMF</th>
            </tr>
          </thead>
          <tbody>
            {entry.line_items.map((li) => (
              <tr key={li.line_number}>
                {LINE_FIELDS.map((field) => (
                  <td
                    key={field}
                    className={lineCellClass(findings, field, li.line_number)}
                  >
                    {String(li[field as keyof typeof li])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
