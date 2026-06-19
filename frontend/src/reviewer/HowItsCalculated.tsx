import { useEffect, useState } from "react";
import { fetchExplanation } from "./api";
import { C, mono, sans } from "./theme";
import type { LineExplanation } from "./types";

function tierColor(tier?: string): string {
  if (tier === "statute") return C.pass;
  if (tier === "ruling") return C.accent;
  return C.review;
}

export default function HowItsCalculated() {
  const [data, setData] = useState<LineExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(true);
  const [showLaw, setShowLaw] = useState(true);
  const [showRulings, setShowRulings] = useState(false);

  useEffect(() => {
    fetchExplanation(0)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return <div style={{ padding: 40, fontFamily: mono, color: C.reject }}>{error}</div>;
  }
  if (!data) {
    return <div style={{ padding: 40, fontFamily: mono, color: C.inkSoft }}>Loading the derivation…</div>;
  }

  const scope = data.transparency?.scope_statement;
  const rulings = data.rulings ?? [];
  const adjudication = data.advisory?.adjudications?.message;
  const discretion = data.advisory?.discretion?.message;

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "44px 24px 80px", fontFamily: sans }}>
      <div style={{ maxWidth: 620, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 22 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: C.accent }} />
          <span style={{ fontFamily: mono, fontSize: 12.5, letterSpacing: 1, color: C.inkSoft, textTransform: "uppercase" }}>
            Drawback · Recovery Detail
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 4 }}>
          <span style={{ fontFamily: sans, fontSize: 15, color: C.inkSoft }}>Estimated recovery for this line</span>
          {data.capped && (
            <span style={{ fontFamily: sans, fontSize: 11, color: C.review, border: `1px solid ${C.review}44`, borderRadius: 4, padding: "2px 7px" }}>
              capped
            </span>
          )}
        </div>
        <div style={{ fontFamily: mono, fontSize: 36, fontWeight: 600, color: C.pass, letterSpacing: -0.5, marginBottom: 20 }}>
          ${Number(data.refund).toLocaleString("en-US", { minimumFractionDigits: 2 })}
        </div>

        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: C.panel,
            border: `1px solid ${C.line}`,
            borderRadius: 9,
            padding: "12px 16px",
            width: "100%",
            cursor: "pointer",
            textAlign: "left",
          }}
        >
          <span style={{ fontSize: 12, color: C.accent }}>{open ? "▾" : "▸"}</span>
          <span style={{ fontFamily: sans, fontSize: 14, fontWeight: 500, color: C.ink }}>How it's calculated</span>
          <span style={{ fontFamily: sans, fontSize: 12.5, color: C.inkFaint, marginLeft: "auto" }}>
            {data.steps.filter((s) => s.math).length} steps
          </span>
        </button>

        {open && (
          <div style={{ marginTop: 12, border: `1px solid ${C.line}`, borderRadius: 12, overflow: "hidden", background: C.panel }}>
            {data.steps.map((s, i) => {
              const isFinal = !!s.math && s.math.startsWith("=");
              return (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    gap: 13,
                    padding: "15px 18px",
                    borderTop: i > 0 ? `1px solid ${C.lineSoft}` : "none",
                    background: isFinal ? C.passBg : "transparent",
                  }}
                >
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: "50%",
                      flexShrink: 0,
                      fontFamily: mono,
                      fontSize: 11,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: isFinal ? C.pass : C.panel2,
                      color: isFinal ? C.bg : C.inkSoft,
                      border: isFinal ? "none" : `1px solid ${C.line}`,
                    }}
                  >
                    {isFinal ? "=" : i + 1}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: sans, fontSize: 13.5, color: C.ink, lineHeight: 1.55 }}>{s.text}</div>
                    {s.math && (
                      <div
                        style={{
                          fontFamily: mono,
                          fontSize: 13,
                          color: isFinal ? C.pass : C.inkSoft,
                          marginTop: 6,
                          background: isFinal ? "transparent" : C.bg,
                          borderRadius: 6,
                          padding: isFinal ? 0 : "6px 10px",
                          display: "inline-block",
                          fontWeight: isFinal ? 600 : 400,
                        }}
                      >
                        {s.math}
                      </div>
                    )}
                    {showLaw && s.basis && (
                      <div style={{ marginTop: 7 }}>
                        <div style={{ fontFamily: sans, fontSize: 12, color: C.accent, display: "flex", gap: 6 }}>
                          <span style={{ flexShrink: 0 }}>§</span>
                          <span style={{ lineHeight: 1.5 }}>{s.basis}</span>
                        </div>
                        {s.tier && (
                          <span
                            style={{
                              display: "inline-block",
                              marginTop: 6,
                              fontFamily: sans,
                              fontSize: 10.5,
                              color: tierColor(s.tier),
                              border: `1px solid ${tierColor(s.tier)}44`,
                              borderRadius: 4,
                              padding: "2px 7px",
                            }}
                          >
                            {s.tier_label} · {s.certainty}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {open && (
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 14, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => setShowLaw((l) => !l)}
              style={{ background: "none", border: "none", color: C.accent, fontFamily: sans, fontSize: 13, cursor: "pointer", padding: 0 }}
            >
              {showLaw ? "Hide legal basis" : "Show legal basis for each step"}
            </button>
            <span style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint }}>Every step traces to the statute it comes from.</span>
          </div>
        )}

        <div style={{ marginTop: 20 }}>
          <button
            type="button"
            onClick={() => setShowRulings((r) => !r)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: C.panel,
              border: `1px solid ${C.line}`,
              borderRadius: 9,
              padding: "12px 16px",
              width: "100%",
              cursor: "pointer",
              textAlign: "left",
            }}
          >
            <span style={{ fontSize: 12, color: C.accent }}>{showRulings ? "▾" : "▸"}</span>
            <span style={{ fontFamily: sans, fontSize: 14, fontWeight: 500, color: C.ink }}>Relevant CBP rulings</span>
            <span style={{ fontFamily: sans, fontSize: 11, color: C.accent, background: C.accentBg, borderRadius: 4, padding: "2px 7px", marginLeft: 8 }}>
              Ruling tier
            </span>
            <span style={{ fontFamily: sans, fontSize: 12.5, color: C.inkFaint, marginLeft: "auto" }}>{rulings.length}</span>
          </button>

          {showRulings && (
            <div style={{ marginTop: 10 }}>
              {rulings.length === 0 && (
                <p style={{ fontFamily: sans, fontSize: 12.5, color: C.inkFaint, margin: "2px 2px 0", lineHeight: 1.55 }}>
                  No rulings ingested for this line yet. The ruling tier is populated from CBP CROSS in the deploying environment.
                </p>
              )}
              {rulings.map((r) => (
                <div key={r.ruling_id} style={{ border: `1px solid ${C.line}`, borderRadius: 10, padding: "13px 16px", background: C.panel, marginBottom: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <span style={{ fontFamily: mono, fontSize: 12.5, color: C.accent }}>{r.ruling_id}</span>
                    <span style={{ fontFamily: sans, fontSize: 11.5, color: C.inkFaint }}>{r.date}</span>
                    {r.is_sample && (
                      <span style={{ fontFamily: sans, fontSize: 10.5, color: C.review, border: `1px solid ${C.review}44`, borderRadius: 4, padding: "1px 6px" }}>
                        SAMPLE — replace with live CROSS data
                      </span>
                    )}
                  </div>
                  <div style={{ fontFamily: sans, fontSize: 13, color: C.ink, marginTop: 6, fontWeight: 500 }}>{r.issue}</div>
                  <div style={{ fontFamily: sans, fontSize: 12.5, color: C.inkSoft, marginTop: 4, lineHeight: 1.5 }}>{r.holding}</div>
                  <div style={{ fontFamily: sans, fontSize: 12, color: C.review, marginTop: 8 }}>{r.disposition}</div>
                </div>
              ))}
              <p style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint, margin: "4px 2px 0", lineHeight: 1.55 }}>
                Rulings are relevant references for you to confirm — not determinations, and they don't change the figure above.
              </p>
            </div>
          )}
        </div>

        {(adjudication || discretion) && (
          <div style={{ marginTop: 20, background: C.panel, border: `1px solid ${C.line}`, borderRadius: 10, padding: "15px 17px" }}>
            <div style={{ fontFamily: sans, fontSize: 13, fontWeight: 500, color: C.ink, marginBottom: 8 }}>
              What this estimate cannot tell you
            </div>
            {adjudication && (
              <div style={{ fontFamily: sans, fontSize: 12.5, color: C.inkSoft, lineHeight: 1.6, marginBottom: 10 }}>
                <span style={{ color: C.review }}>Adjudication patterns.</span> {adjudication}
              </div>
            )}
            {discretion && (
              <div style={{ fontFamily: sans, fontSize: 12.5, color: C.inkSoft, lineHeight: 1.6 }}>
                <span style={{ color: C.review }}>CBP discretion.</span> {discretion}
              </div>
            )}
          </div>
        )}

        <div style={{ marginTop: 20, borderTop: `1px solid ${C.lineSoft}`, paddingTop: 16 }}>
          <div style={{ fontFamily: sans, fontSize: 12.5, fontWeight: 500, color: C.inkSoft, marginBottom: 6 }}>
            What this estimate is based on
          </div>
          <p style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint, margin: "0 0 8px", lineHeight: 1.6 }}>
            {scope ??
              "Every step above rests on drawback law as written in statute and regulation. It does not yet incorporate CBP rulings or practice patterns, and it cannot account for case-by-case CBP discretion."}
          </p>
          <p style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint, margin: 0, lineHeight: 1.6 }}>
            This is an estimate showing how the figure is derived, not a filing. A licensed drawback specialist — and
            ultimately CBP — make the final determination.
          </p>
        </div>
      </div>
    </div>
  );
}
