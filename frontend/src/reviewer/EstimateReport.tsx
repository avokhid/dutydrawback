import { useEffect, useState } from "react";
import { fetchEstimate } from "./api";
import { C, mono, sans } from "./theme";
import type { ClaimEstimate, EstimateLine } from "./types";

const money = (s: string | null | undefined) => "$" + (s ?? "0.00");

export default function EstimateReport() {
  const [showLines, setShowLines] = useState(true);
  const [e, setE] = useState<ClaimEstimate | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchEstimate()
      .then(setE)
      .catch((ex: unknown) => setErr(ex instanceof Error ? ex.message : String(ex)));
  }, []);

  if (err)
    return <div style={{ padding: 40, fontFamily: mono, color: C.review }}>Could not load estimate: {err}</div>;
  if (!e)
    return <div style={{ padding: 40, fontFamily: mono, color: C.inkSoft }}>Loading estimate…</div>;

  const confidentLines = e.lines.filter((l) => l.conf === "high");
  const reviewLines = e.lines.filter((l) => l.conf === "review");

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "44px 24px 90px", fontFamily: sans }}>
      <div style={{ maxWidth: 820, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 28 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: C.pass }} />
          <span style={{ fontFamily: mono, fontSize: 12.5, letterSpacing: 1, color: C.inkSoft, textTransform: "uppercase" }}>
            Drawback · Recovery Estimate
          </span>
        </div>

        <div style={{ marginBottom: 6, fontFamily: sans, fontSize: 15, color: C.inkSoft }}>
          {e.firm}
          {e.period ? ` · ${e.period}` : ""}
        </div>
        <h1 style={{ fontFamily: sans, fontSize: 19, fontWeight: 500, color: C.inkSoft, margin: "0 0 14px", letterSpacing: -0.2 }}>
          Estimated duty recovery
        </h1>

        <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
          <span style={{ fontFamily: mono, fontSize: 52, fontWeight: 600, color: C.ink, letterSpacing: -1, lineHeight: 1 }}>
            {money(e.rangeLow)}
          </span>
          <span style={{ fontFamily: sans, fontSize: 22, color: C.inkFaint }}>–</span>
          <span style={{ fontFamily: mono, fontSize: 52, fontWeight: 600, color: C.pass, letterSpacing: -1, lineHeight: 1 }}>
            {money(e.rangeHigh)}
          </span>
        </div>
        <p style={{ fontFamily: sans, fontSize: 14, color: C.inkSoft, margin: "14px 0 28px", lineHeight: 1.6, maxWidth: 620 }}>
          The lower figure is what we'd stand behind today from clearly-matched shipments. The upper
          figure adds recovery from matches that need verification — real, but not yet confirmed. This
          is an estimate, not a filing; final recovery depends on documentation review.
        </p>

        <div style={{ marginBottom: 32 }}>
          <div style={{ display: "flex", height: 12, borderRadius: 6, overflow: "hidden", border: `1px solid ${C.line}` }}>
            <div style={{ width: `${e.confidentPct}%`, background: C.pass }} />
            <div style={{ flex: 1, background: C.review, opacity: 0.55 }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontFamily: sans, fontSize: 12.5 }}>
            <span style={{ color: C.pass }}>■ {money(e.confident)} high-confidence</span>
            <span style={{ color: C.review }}>■ {money(e.potential)} additional potential</span>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 32 }}>
          <Metric label="Entries analyzed" value={e.entriesAnalyzed} />
          <Metric label="Lines matched" value={e.matchedLines} />
          <Metric label="Recovery rate" value="99%" sub="of duties/fees" />
          <Metric label="Drawback basis" value="Unused" sub="substitution" small />
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <h2 style={{ fontFamily: sans, fontSize: 16, fontWeight: 600, color: C.ink, margin: 0 }}>
            Recovery by product category
          </h2>
          <button
            type="button"
            onClick={() => setShowLines((s) => !s)}
            style={{ background: "none", border: "none", color: C.accent, fontFamily: sans, fontSize: 12.5, cursor: "pointer" }}
          >
            {showLines ? "Hide detail" : "Show detail"}
          </button>
        </div>

        {showLines && (
          <div style={{ border: `1px solid ${C.line}`, borderRadius: 10, overflow: "hidden", marginBottom: 8 }}>
            <HeaderRow />
            {confidentLines.map((l, i) => (
              <LineRow key={`h${i}`} l={l} />
            ))}
            {reviewLines.length > 0 && (
              <div style={{ padding: "8px 16px", background: C.reviewBg, fontFamily: sans, fontSize: 11.5, color: C.review, letterSpacing: 0.3, textTransform: "uppercase", borderTop: `1px solid ${C.lineSoft}` }}>
                Additional potential — needs verification
              </div>
            )}
            {reviewLines.map((l, i) => (
              <LineRow key={`r${i}`} l={l} muted />
            ))}
          </div>
        )}

        <p style={{ fontFamily: sans, fontSize: 12.5, color: C.inkFaint, margin: "12px 0 32px", lineHeight: 1.6 }}>
          "Capped" lines reflect the substitution lesser-of rule, where recovery is limited to the
          lower of the imported or exported article's duty. All figures are estimates pending
          documentation review and confirmation by a licensed drawback specialist.
        </p>

        <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderLeft: `3px solid ${C.pass}`, borderRadius: 10, padding: "20px 22px", display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ fontFamily: sans, fontSize: 15, fontWeight: 600, color: C.ink, marginBottom: 4 }}>
              Turn this estimate into a recovered refund
            </div>
            <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, lineHeight: 1.55 }}>
              A specialist reviews your documentation, confirms the matches, and prepares the claim.
              You pay only on what's actually recovered.
            </div>
          </div>
          <button
            type="button"
            style={{ fontFamily: sans, fontSize: 14, fontWeight: 500, color: C.bg, background: C.pass, border: "none", borderRadius: 8, padding: "11px 22px", cursor: "pointer", whiteSpace: "nowrap" }}
          >
            Start a claim review
          </button>
        </div>

        <div style={{ marginTop: 20, fontFamily: sans, fontSize: 11.5, color: C.inkFaint, lineHeight: 1.6 }}>
          {e.disclaimer}
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
  small,
}: {
  label: string;
  value: string | number;
  sub?: string;
  small?: boolean;
}) {
  return (
    <div style={{ background: C.panel2, borderRadius: 9, padding: "13px 14px" }}>
      <div style={{ fontFamily: mono, fontSize: small ? 18 : 22, fontWeight: 600, color: C.ink, lineHeight: 1.1 }}>
        {value}
      </div>
      <div style={{ fontFamily: sans, fontSize: 11.5, color: C.inkSoft, marginTop: 4 }}>
        {label}
        {sub && <span style={{ color: C.inkFaint }}> · {sub}</span>}
      </div>
    </div>
  );
}

const cells4 = {
  display: "grid",
  gridTemplateColumns: "1fr 130px 130px 70px",
  columnGap: 12,
  alignItems: "center",
} as const;

function HeaderRow() {
  return (
    <div style={{ ...cells4, padding: "10px 16px", background: C.panel2, fontFamily: sans, fontSize: 11.5, color: C.inkFaint, fontWeight: 500, textTransform: "uppercase", letterSpacing: 0.3 }}>
      <div>HTS / category</div>
      <div style={{ textAlign: "right" }}>Duties paid</div>
      <div style={{ textAlign: "right" }}>Est. recovery</div>
      <div style={{ textAlign: "right" }} />
    </div>
  );
}

function LineRow({ l, muted }: { l: EstimateLine; muted?: boolean }) {
  return (
    <div style={{ ...cells4, padding: "12px 16px", borderTop: `1px solid ${C.lineSoft}`, opacity: muted ? 0.7 : 1 }}>
      <div>
        <span style={{ fontFamily: mono, fontSize: 12.5, color: C.ink }}>{l.hts}</span>
        <div style={{ fontFamily: sans, fontSize: 12.5, color: C.inkSoft, marginTop: 2 }}>{l.desc}</div>
      </div>
      <div style={{ textAlign: "right", fontFamily: mono, fontSize: 13, color: C.inkSoft }}>{money(l.duties)}</div>
      <div style={{ textAlign: "right", fontFamily: mono, fontSize: 13, fontWeight: 600, color: muted ? C.review : C.pass }}>
        {money(l.refund)}
      </div>
      <div style={{ textAlign: "right" }}>
        {l.capped && (
          <span style={{ fontFamily: sans, fontSize: 10.5, color: C.inkFaint, border: `1px solid ${C.line}`, borderRadius: 4, padding: "2px 6px" }}>
            capped
          </span>
        )}
      </div>
    </div>
  );
}
