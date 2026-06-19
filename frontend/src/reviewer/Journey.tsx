import { Fragment, useState } from "react";
import { C, mono, sans } from "./theme";

const STEPS = ["Upload", "Read", "Confirm", "Type", "Estimate", "Review"];

function typeLabel(id: string): string {
  return (
    {
      unused_substitution: "unused, substitution",
      unused_direct_identification: "unused, direct ID",
      rejected: "rejected merchandise",
      manufacturing: "manufacturing",
    }[id] || id
  );
}

function Stepper({ current }: { current: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 28, flexWrap: "wrap" }}>
      {STEPS.map((s, i) => (
        <Fragment key={s}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                fontFamily: mono,
                fontSize: 11,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: i < current ? C.pass : i === current ? C.accent : C.panel2,
                color: i <= current ? C.bg : C.inkFaint,
                border: i > current ? `1px solid ${C.line}` : "none",
              }}
            >
              {i < current ? "✓" : i + 1}
            </div>
            <span style={{ fontFamily: sans, fontSize: 12.5, color: i === current ? C.ink : C.inkFaint, fontWeight: i === current ? 500 : 400 }}>
              {s}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div style={{ width: 24, height: 1, background: i < current ? C.pass : C.line, margin: "0 10px" }} />
          )}
        </Fragment>
      ))}
    </div>
  );
}

interface FeedRowProps {
  label: string;
  status: "complete" | "running" | "pending";
  summary: string;
  sub?: string;
}

function FeedRow({ label, status, summary, sub }: FeedRowProps) {
  const col = status === "complete" ? C.pass : status === "running" ? C.accent : C.inkSoft;
  return (
    <div style={{ display: "flex", gap: 12, padding: "13px 16px", borderTop: `1px solid ${C.lineSoft}`, background: status === "complete" ? C.passBg : "transparent" }}>
      <div className={status === "running" ? "pulsing" : ""} style={{ width: 9, height: 9, borderRadius: "50%", background: col, marginTop: 5, flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontFamily: sans, fontSize: 13.5, fontWeight: 500, color: C.ink }}>{label}</span>
          <span style={{ fontFamily: mono, fontSize: 10, textTransform: "uppercase", color: col, border: `1px solid ${col}44`, borderRadius: 4, padding: "1px 6px" }}>{status}</span>
        </div>
        <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, marginTop: 3, lineHeight: 1.5 }}>{summary}</div>
        {sub && <div style={{ fontFamily: sans, fontSize: 12, color: C.review, marginTop: 4 }}>{sub}</div>}
      </div>
    </div>
  );
}

function MiniFeed({ title, rows, footer }: { title: string; rows: FeedRowProps[]; footer: React.ReactNode }) {
  return (
    <div style={{ maxWidth: 600 }}>
      <div style={{ fontFamily: sans, fontSize: 16, fontWeight: 600, color: C.ink, marginBottom: 14 }}>{title}</div>
      <div style={{ border: `1px solid ${C.line}`, borderRadius: 12, overflow: "hidden", background: C.panel }}>
        <div style={{ height: 1 }} />
        {rows.map((r, i) => (
          <FeedRow key={i} {...r} />
        ))}
      </div>
      {footer}
    </div>
  );
}

function Btn({ children, onClick, kind = "primary" }: { children: React.ReactNode; onClick: () => void; kind?: "primary" | "go" | "ghost" }) {
  const styles = {
    primary: { color: C.bg, background: C.accent, border: "none" },
    go: { color: C.bg, background: C.pass, border: "none" },
    ghost: { color: C.ink, background: "transparent", border: `1px solid ${C.line}` },
  }[kind];
  return (
    <button type="button" onClick={onClick} style={{ ...styles, fontFamily: sans, fontSize: 13.5, fontWeight: 500, borderRadius: 8, padding: "10px 18px", cursor: "pointer", marginTop: 18, marginRight: 10 }}>
      {children}
    </button>
  );
}

export default function Journey({ onBom }: { onBom?: () => void } = {}) {
  const [step, setStep] = useState(0);
  const [typeSel, setTypeSel] = useState("unused_substitution");

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "40px 24px 80px", fontFamily: sans }}>
      <div style={{ maxWidth: 680, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 22 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: C.accent }} />
          <span style={{ fontFamily: mono, fontSize: 12.5, letterSpacing: 1, color: C.inkSoft, textTransform: "uppercase" }}>
            Drawback · Estimate Journey
          </span>
        </div>

        <Stepper current={step} />

        {step === 0 && (
          <div>
            <h1 style={{ fontFamily: sans, fontSize: 22, fontWeight: 600, color: C.ink, margin: "0 0 4px" }}>Upload your documents</h1>
            <p style={{ fontFamily: sans, fontSize: 14, color: C.inkSoft, margin: "0 0 20px", lineHeight: 1.6 }}>
              Add your entry summaries and export records. PDF, Excel, or CSV.
            </p>
            <div style={{ border: `1.5px dashed ${C.line}`, background: C.panel, borderRadius: 12, padding: "30px 20px", textAlign: "center", marginBottom: 16 }}>
              <div style={{ fontSize: 24, color: C.inkFaint, marginBottom: 8 }}>↑</div>
              <div style={{ fontFamily: sans, fontSize: 14.5, color: C.ink, fontWeight: 500 }}>Drop files here or click to browse</div>
              <div style={{ fontFamily: sans, fontSize: 12.5, color: C.inkFaint, marginTop: 4 }}>.pdf, .xlsx, .csv · up to 25MB each</div>
            </div>
            <div style={{ border: `1px solid ${C.line}`, borderRadius: 12, overflow: "hidden", background: C.panel }}>
              {[
                ["entry_summary_7501.pdf", "import"],
                ["export_bol_77.pdf", "export"],
              ].map(([n, k], i) => (
                  <div key={n} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", borderTop: i > 0 ? `1px solid ${C.lineSoft}` : "none" }}>
                    <span style={{ width: 9, height: 9, borderRadius: "50%", background: C.inkSoft }} />
                    <span style={{ fontFamily: mono, fontSize: 13, color: C.ink, flex: 1 }}>{n}</span>
                    <span style={{ fontFamily: sans, fontSize: 10.5, color: C.inkFaint, border: `1px solid ${C.line}`, borderRadius: 4, padding: "1px 6px", textTransform: "uppercase" }}>{k}</span>
                  </div>
                ))}
            </div>
            <Btn onClick={() => setStep(1)}>Read 2 documents</Btn>
          </div>
        )}

        {step === 1 && (
          <MiniFeed
            title="Reading your documents"
            rows={[
              { label: "entry_summary_7501.pdf", status: "complete", summary: "Read 1 import line. Quantities and duties checked." },
              { label: "export_bol_77.pdf", status: "complete", summary: "Read 1 export line. Proof of export found." },
            ]}
            footer={<Btn onClick={() => setStep(2)}>See what we found →</Btn>}
          />
        )}

        {step === 2 && (
          <div style={{ maxWidth: 600 }}>
            <div style={{ fontFamily: sans, fontSize: 16, fontWeight: 600, color: C.ink, marginBottom: 6 }}>What we read</div>
            <p style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, margin: "0 0 16px", lineHeight: 1.6 }}>
              Confirm this looks right before we estimate. Anything we were unsure about is flagged.
            </p>
            <div style={{ border: `1px solid ${C.line}`, borderRadius: 12, overflow: "hidden", background: C.panel }}>
              <div style={{ padding: "13px 16px" }}>
                <div style={{ fontFamily: mono, fontSize: 12.5, color: C.ink }}>entry_summary_7501.pdf</div>
                <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, marginTop: 4 }}>500 laptops · HTS 8471.30.0100 · $124,000 value · $442.40 in fees</div>
              </div>
              <div style={{ padding: "13px 16px", borderTop: `1px solid ${C.lineSoft}` }}>
                <div style={{ fontFamily: mono, fontSize: 12.5, color: C.ink }}>export_bol_77.pdf</div>
                <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, marginTop: 4 }}>60 cartons exported · HTS 8471.30.0100 · 2025-09-02</div>
              </div>
            </div>
            <div style={{ fontFamily: sans, fontSize: 12.5, color: C.pass, marginTop: 12 }}>No problems found — your documents are clean.</div>
            <Btn kind="go" onClick={() => setStep(3)}>Choose drawback type →</Btn>
          </div>
        )}

        {step === 3 && (
          <div style={{ maxWidth: 600 }}>
            <div style={{ fontFamily: sans, fontSize: 16, fontWeight: 600, color: C.ink, marginBottom: 6 }}>What kind of drawback is this?</div>
            <p style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, margin: "0 0 16px", lineHeight: 1.6 }}>
              The type determines how we match your shipments and what we need from you. The first option covers the most common case.
            </p>
            {(
              [
                ["unused_substitution", "Unused — substitution", "1313(j)(2)", "most common", C.pass, C.passBg],
                ["unused_direct_identification", "Unused — direct ID", "1313(j)(1)", null, null, null],
                ["rejected", "Rejected merchandise", "1313(c)", null, null, null],
                ["manufacturing", "Manufacturing", "1313(a)/(b)", "needs extra info", C.review, C.reviewBg],
              ] as [string, string, string, string | null, string | null, string | null][]
            ).map(([id, label, st, tag, tc, tbg]) => (
              <div
                key={id}
                onClick={() => setTypeSel(id)}
                style={{
                  display: "flex",
                  gap: 12,
                  alignItems: "center",
                  cursor: "pointer",
                  marginBottom: 8,
                  borderRadius: 10,
                  padding: "13px 15px",
                  background: typeSel === id ? C.accentBg : C.panel,
                  border: typeSel === id ? `1.5px solid ${C.accent}` : `1px solid ${C.line}`,
                }}
              >
                <div style={{ width: 16, height: 16, borderRadius: "50%", flexShrink: 0, border: typeSel === id ? `5px solid ${C.accent}` : `2px solid ${C.inkFaint}`, background: C.bg }} />
                <span style={{ fontFamily: sans, fontSize: 14, fontWeight: 500, color: C.ink }}>{label}</span>
                <span style={{ fontFamily: mono, fontSize: 11, color: C.inkFaint, border: `1px solid ${C.line}`, borderRadius: 4, padding: "1px 6px" }}>{st}</span>
                {tag && <span style={{ fontFamily: sans, fontSize: 10.5, color: tc as string, background: tbg as string, borderRadius: 4, padding: "2px 7px" }}>{tag}</span>}
              </div>
            ))}
            {typeSel === "rejected" && (
              <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 10, padding: "14px 16px", marginTop: 10 }}>
                <div style={{ fontFamily: sans, fontSize: 13, fontWeight: 500, color: C.ink, marginBottom: 8 }}>Why were the goods rejected?</div>
                <select style={{ width: "100%", height: 36, padding: "0 12px", fontFamily: sans, fontSize: 13, color: C.ink, background: C.panel2, border: `1px solid ${C.line}`, borderRadius: 7 }}>
                  <option>Defective / did not meet specifications</option>
                  <option>Not conforming to sample or specification</option>
                  <option>Shipped without consent of consignee</option>
                </select>
              </div>
            )}
            {typeSel === "manufacturing" && (
              <div style={{ background: C.reviewBg, border: `1px solid ${C.review}44`, borderRadius: 10, padding: "14px 16px", marginTop: 10, fontFamily: sans, fontSize: 13, color: C.inkSoft, lineHeight: 1.55 }}>
                <span style={{ color: C.ink, fontWeight: 500 }}>Manufacturing needs a bill of materials</span> — which imported inputs went into each exported article. Continue to the bill-of-materials form to enter them, and the estimate runs on a manufacturing basis.
              </div>
            )}
            <Btn kind="go" onClick={() => { if (typeSel === "manufacturing") { onBom?.(); } else { setStep(4); } }}>{typeSel === "manufacturing" ? "Enter bill of materials →" : "Run estimate →"}</Btn>
          </div>
        )}

        {step === 4 && (
          <MiniFeed
            title="Estimating your recovery"
            rows={[
              { label: "Checking your documents", status: "complete", summary: "No problems found — your documents are clean." },
              { label: "Pairing imports to exports", status: "complete", summary: "Paired 1 shipment.", sub: "1 pairing needs your confirmation before it counts" },
              { label: "Estimating your recovery", status: "complete", summary: `You could recover about $2,970.00 (${typeLabel(typeSel)}).` },
            ]}
            footer={<Btn onClick={() => setStep(5)}>Review the uncertain pairing →</Btn>}
          />
        )}

        {step === 5 && (
          <div style={{ maxWidth: 620 }}>
            <div style={{ fontFamily: sans, fontSize: 16, fontWeight: 600, color: C.ink, marginBottom: 6 }}>One pairing to confirm</div>
            <p style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, margin: "0 0 16px", lineHeight: 1.6 }}>
              We paired these but want your confirmation on the unit conversion.
            </p>
            <div style={{ border: `1px solid ${C.line}`, borderRadius: 12, overflow: "hidden", background: C.panel }}>
              {(
                [
                  ["HTS", "8471.30.0100", "8471.30.0100", true],
                  ["Description", "WIDGET-A laptop", "Laptop assembly", true],
                  ["Quantity / unit", "500 cartons", "6,000 units", false],
                  ["Value", "$124,000", "$131,400", true],
                ] as [string, string, string, boolean][]
              ).map(([f, imp, exp, ok], i) => (
                <div
                  key={f}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "120px 1fr 1fr",
                    padding: "11px 16px",
                    borderTop: i > 0 ? `1px solid ${C.lineSoft}` : "none",
                    background: ok ? "transparent" : C.reviewBg,
                  }}
                >
                  <span style={{ fontFamily: sans, fontSize: 12.5, color: ok ? C.inkSoft : C.review, fontWeight: ok ? 400 : 500 }}>
                    {f}
                    {!ok && " ⚠"}
                  </span>
                  <span style={{ fontFamily: mono, fontSize: 12.5, color: C.ink }}>{imp}</span>
                  <span style={{ fontFamily: mono, fontSize: 12.5, color: C.ink }}>
                    {exp} {ok && <span style={{ color: C.pass }}>✓</span>}
                  </span>
                </div>
              ))}
            </div>
            <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, marginTop: 12, padding: "11px 14px", background: C.accentBg, borderRadius: 8, lineHeight: 1.5 }}>
              Suggested: 1 carton = 12 units → 500 cartons = 6,000 units. Confirm to count this toward your estimate.
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <Btn kind="go" onClick={() => setStep(0)}>Confirm — counts $2,970</Btn>
              <Btn kind="ghost" onClick={() => setStep(0)}>Start over</Btn>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
