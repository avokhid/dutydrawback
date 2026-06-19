import { useEffect, useState } from "react";
import type { ReviewItem } from "../types";
import { C, confColor } from "../theme";
import { Key, Pill, ViewHeader, ghostBtn, primaryBtn } from "./ui";

function renderProof(p: ReviewItem["proof"]) {
  if (!p.highlight || !p.line.includes(p.highlight)) {
    return <span>{p.line}</span>;
  }
  const parts = p.line.split(p.highlight);
  return (
    <span>
      {parts[0]}
      <span
        style={{
          background: C.reviewBg,
          color: C.review,
          padding: "1px 5px",
          borderRadius: 3,
          border: `1px solid ${C.review}55`,
        }}
      >
        {p.highlight}
      </span>
      {parts[1]}
    </span>
  );
}

export default function SingleReview({
  item,
  index,
  total,
  onApprove,
  onReject,
  onCorrect,
  onBack,
  onSkip,
}: {
  item: ReviewItem;
  index: number;
  total: number;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onCorrect: (item: ReviewItem) => void;
  onBack: () => void;
  onSkip: () => void;
}) {
  const [showProof, setShowProof] = useState(false);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      const k = e.key.toLowerCase();
      if (k === "a") {
        e.preventDefault();
        onApprove(item.id);
      } else if (k === "e") {
        e.preventDefault();
        onCorrect(item);
      } else if (k === "r") {
        e.preventDefault();
        onReject(item.id);
      } else if (k === "p") {
        e.preventDefault();
        setShowProof((s) => !s);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [item, onApprove, onReject, onCorrect]);

  const rows = Object.entries(item.fields);

  return (
    <div style={{ maxWidth: 760, margin: "0 auto" }}>
      <ViewHeader
        onBack={onBack}
        title="Match review"
        sub={`Item ${index + 1} of ${total} · ${item.vendor} ${item.part}`}
        accent={C.review}
        right={
          <Pill color={confColor(item.conf)} bg={C.reviewBg}>
            {Math.round(item.conf * 100)}% confidence
          </Pill>
        }
      />

      <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 12, overflow: "hidden" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "130px 1fr 1fr",
            background: C.panel2,
            padding: "10px 16px",
            fontFamily: "var(--sans)",
            fontSize: 11.5,
            color: "var(--ink-faint)",
            fontWeight: 500,
            textTransform: "uppercase",
            letterSpacing: 0.3,
          }}
        >
          <div>Field</div>
          <div>↓ Import · 7501</div>
          <div>↓ Export · BOL</div>
        </div>
        {rows.map(([key, f]) => {
          const flagged = key === item.uncertain;
          return (
            <div
              key={key}
              style={{
                display: "grid",
                gridTemplateColumns: "130px 1fr 1fr",
                padding: "12px 16px",
                borderTop: `1px solid ${C.lineSoft}`,
                alignItems: "center",
                background: flagged ? C.reviewBg : "transparent",
              }}
            >
              <div
                style={{
                  fontFamily: "var(--sans)",
                  fontSize: 12.5,
                  color: flagged ? C.review : "var(--ink-soft)",
                  fontWeight: flagged ? 600 : 400,
                }}
              >
                {f.label}
                {flagged && " ⚠"}
              </div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--ink)" }}>{f.imp}</div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--ink)" }}>
                {f.exp}
                {f.ok && !flagged && <span style={{ color: C.pass, marginLeft: 6 }}>✓</span>}
                {f.note && (
                  <span
                    style={{
                      color: f.ok ? C.pass : C.review,
                      fontSize: 11,
                      marginLeft: 6,
                      fontFamily: "var(--sans)",
                    }}
                  >
                    {f.note}
                  </span>
                )}
              </div>
            </div>
          );
        })}

        <div
          style={{
            display: "flex",
            gap: 11,
            padding: "13px 16px",
            background: C.accentBg,
            borderTop: `1px solid ${C.lineSoft}`,
          }}
        >
          <span style={{ color: C.accent, fontSize: 16, lineHeight: 1.2 }}>◆</span>
          <div style={{ fontFamily: "var(--sans)", fontSize: 13, color: "var(--ink-soft)", lineHeight: 1.55 }}>
            <span style={{ color: "var(--ink)", fontWeight: 500 }}>{item.suggestion.text}.</span>{" "}
            {item.suggestion.detail}.
          </div>
        </div>

        <div style={{ borderTop: `1px solid ${C.lineSoft}` }}>
          <button
            type="button"
            onClick={() => setShowProof((s) => !s)}
            style={{
              width: "100%",
              textAlign: "left",
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "11px 16px",
              fontFamily: "var(--sans)",
              fontSize: 12.5,
              color: C.accent,
              display: "flex",
              alignItems: "center",
              gap: 7,
            }}
          >
            <span style={{ fontSize: 11 }}>{showProof ? "▾" : "▸"}</span> Source proof — {item.proof.source}{" "}
            <Key>P</Key>
          </button>
          {showProof && (
            <div
              style={{
                margin: "0 16px 14px",
                padding: "11px 13px",
                background: C.bg,
                border: `1px solid ${C.line}`,
                borderRadius: 7,
                fontFamily: "var(--mono)",
                fontSize: 12,
                color: "var(--ink-soft)",
                lineHeight: 1.7,
              }}
            >
              {renderProof(item.proof)}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" onClick={() => onApprove(item.id)} style={primaryBtn(C.pass)}>
          Approve match <Key>A</Key>
        </button>
        <button type="button" onClick={() => onCorrect(item)} style={ghostBtn()}>
          Correct field <Key>E</Key>
        </button>
        <button type="button" onClick={() => onReject(item.id)} style={ghostBtn()}>
          Reject <Key>R</Key>
        </button>
        <button
          type="button"
          onClick={onSkip}
          style={{ ...ghostBtn(), marginLeft: "auto", borderColor: "transparent", color: "var(--ink-faint)" }}
        >
          Skip for now →
        </button>
      </div>
    </div>
  );
}
