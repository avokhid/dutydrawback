import { useEffect, useState } from "react";
import { C, mono, sans } from "./theme";

interface DrawbackTypeOption {
  id: string;
  label: string;
  statute: string;
  description: string;
  requires: string[];
  simplest?: boolean;
  estimable?: boolean;
}

const FALLBACK_TYPES: DrawbackTypeOption[] = [
  {
    id: "unused_substitution",
    label: "Unused merchandise — substitution",
    statute: "19 U.S.C. 1313(j)(2)",
    simplest: true,
    estimable: true,
    description:
      "Imported goods exported or destroyed unused; matched to commercially interchangeable substitutes by HTS.",
    requires: [],
  },
  {
    id: "unused_direct_identification",
    label: "Unused merchandise — direct identification",
    statute: "19 U.S.C. 1313(j)(1)",
    estimable: true,
    description: "The actual imported goods are exported or destroyed unused.",
    requires: [],
  },
  {
    id: "rejected",
    label: "Rejected merchandise",
    statute: "19 U.S.C. 1313(c)",
    estimable: false,
    description: "Defective, non-conforming, or unauthorized goods returned, exported, or destroyed.",
    requires: ["rejection_reason"],
  },
  {
    id: "manufacturing",
    label: "Manufacturing drawback",
    statute: "19 U.S.C. 1313(a)/(b)",
    estimable: false,
    description:
      "Imported materials consumed making an exported article. Requires a bill of materials linking inputs to outputs.",
    requires: ["bill_of_materials"],
  },
];

const REJECTION_REASONS = [
  "Defective / did not meet specifications",
  "Not conforming to sample or specification",
  "Shipped without consent of consignee",
  "Determined to be defective after import",
];

export interface DrawbackChoice {
  drawback_type: string;
  rejection_reason?: string;
  needs_bom?: boolean;
}

export default function DrawbackTypeStep({ onContinue }: { onContinue?: (choice: DrawbackChoice) => void }) {
  const [types, setTypes] = useState<DrawbackTypeOption[]>(FALLBACK_TYPES);
  const [selected, setSelected] = useState("unused_substitution");
  const [reason, setReason] = useState(REJECTION_REASONS[0]);

  useEffect(() => {
    fetch("/api/drawback-types")
      .then((r) => r.json())
      .then((d) => {
        if (d.types && d.types.length) setTypes(d.types);
      })
      .catch(() => {});
  }, []);

  const sel = types.find((t) => t.id === selected) ?? types[0];
  const needsReason = (sel.requires ?? []).includes("rejection_reason");
  const needsBom = (sel.requires ?? []).includes("bill_of_materials");

  const handleContinue = () => {
    const choice: DrawbackChoice = { drawback_type: selected };
    if (needsReason) choice.rejection_reason = reason;
    if (needsBom) choice.needs_bom = true;
    onContinue?.(choice);
  };

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "44px 24px 80px", fontFamily: sans }}>
      <div style={{ maxWidth: 660, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 22 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: C.accent }} />
          <span style={{ fontFamily: mono, fontSize: 12.5, letterSpacing: 1, color: C.inkSoft, textTransform: "uppercase" }}>
            Drawback · Choose Type
          </span>
        </div>

        <h1 style={{ fontFamily: sans, fontSize: 22, fontWeight: 600, color: C.ink, margin: "0 0 4px" }}>
          What kind of drawback is this?
        </h1>
        <p style={{ fontFamily: sans, fontSize: 14, color: C.inkSoft, margin: "0 0 22px", lineHeight: 1.6 }}>
          The type determines how we match your shipments and what we need from you. If you're not sure, the first
          option covers the most common case.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20 }}>
          {types.map((t) => {
            const active = t.id === selected;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setSelected(t.id)}
                style={{
                  textAlign: "left",
                  cursor: "pointer",
                  borderRadius: 10,
                  padding: "14px 16px",
                  background: active ? C.accentBg : C.panel,
                  border: active ? `1.5px solid ${C.accent}` : `1px solid ${C.line}`,
                  display: "flex",
                  gap: 13,
                  alignItems: "flex-start",
                }}
              >
                <div
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: "50%",
                    flexShrink: 0,
                    marginTop: 1,
                    border: active ? `5px solid ${C.accent}` : `2px solid ${C.inkFaint}`,
                    background: C.bg,
                  }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
                    <span style={{ fontFamily: sans, fontSize: 14.5, fontWeight: 500, color: C.ink }}>{t.label}</span>
                    <span style={{ fontFamily: mono, fontSize: 11, color: C.inkFaint, border: `1px solid ${C.line}`, borderRadius: 4, padding: "1px 6px" }}>
                      {t.statute}
                    </span>
                    {t.simplest && (
                      <span style={{ fontFamily: sans, fontSize: 10.5, color: C.pass, background: C.passBg, borderRadius: 4, padding: "2px 7px" }}>
                        most common
                      </span>
                    )}
                    {t.estimable === false && (
                      <span style={{ fontFamily: sans, fontSize: 10.5, color: C.review, background: C.reviewBg, borderRadius: 4, padding: "2px 7px" }}>
                        needs extra info
                      </span>
                    )}
                  </div>
                  <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, marginTop: 5, lineHeight: 1.5 }}>{t.description}</div>
                </div>
              </button>
            );
          })}
        </div>

        {needsReason && (
          <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 10, padding: "16px 18px", marginBottom: 20 }}>
            <label style={{ display: "block", fontFamily: sans, fontSize: 13, fontWeight: 500, color: C.ink, marginBottom: 8 }}>
              Why were the goods rejected?
            </label>
            <p style={{ fontFamily: sans, fontSize: 12.5, color: C.inkSoft, margin: "0 0 10px", lineHeight: 1.5 }}>
              Rejected-merchandise drawback requires a stated reason — it's part of what makes the claim eligible. We'll
              record it; the estimate itself currently runs on the unused-substitution basis until the rejected-line
              calculation is wired in.
            </p>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              style={{
                width: "100%",
                height: 38,
                padding: "0 12px",
                fontFamily: sans,
                fontSize: 13.5,
                color: C.ink,
                background: C.panel2,
                border: `1px solid ${C.line}`,
                borderRadius: 7,
              }}
            >
              {REJECTION_REASONS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </div>
        )}

        {needsBom && (
          <div style={{ background: C.reviewBg, border: `1px solid ${C.review}44`, borderRadius: 10, padding: "16px 18px", marginBottom: 20, display: "flex", gap: 12 }}>
            <span style={{ color: C.review, fontSize: 17, lineHeight: 1.2 }}>⚠</span>
            <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, lineHeight: 1.55 }}>
              <span style={{ color: C.ink, fontWeight: 500 }}>Manufacturing needs a bill of materials</span> — which
              imported inputs went into each exported article, in what quantities. Continue to the bill-of-materials
              form to enter them; we then compute the estimate on a manufacturing basis from what you provide.
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={handleContinue}
          style={{
            fontFamily: sans,
            fontSize: 13.5,
            fontWeight: 500,
            color: C.bg,
            background: C.pass,
            border: "none",
            borderRadius: 8,
            padding: "11px 20px",
            cursor: "pointer",
          }}
        >
          {needsBom ? "Enter bill of materials →" : "Run estimate →"}
        </button>
      </div>
    </div>
  );
}
