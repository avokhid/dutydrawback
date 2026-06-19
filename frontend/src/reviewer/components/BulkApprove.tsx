import { useEffect, useState } from "react";
import type { BulkRow } from "../types";
import { C, confColor } from "../theme";
import { Key, ViewHeader, cbStyle, ghostBtn, primaryBtn } from "./ui";

const rowGrid = {
  display: "grid",
  gridTemplateColumns: "28px 1fr 1fr 64px",
  gap: 0,
  columnGap: 12,
};

export default function BulkApprove({
  rows,
  onApprove,
  onSendToReview,
  onBack,
}: {
  rows: BulkRow[];
  onApprove: (ids: string[]) => void;
  onSendToReview: (ids: string[]) => void;
  onBack: () => void;
}) {
  const [checked, setChecked] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(rows.map((r) => [r.id, true])),
  );

  useEffect(() => {
    setChecked(Object.fromEntries(rows.map((r) => [r.id, true])));
  }, [rows]);

  const selCount = Object.values(checked).filter(Boolean).length;
  const allSel = rows.length > 0 && selCount === rows.length;

  const toggleAll = () => {
    const v = !allSel;
    setChecked(Object.fromEntries(rows.map((r) => [r.id, v])));
  };

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Enter" && selCount > 0) {
        e.preventDefault();
        onApprove(rows.filter((r) => checked[r.id]).map((r) => r.id));
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [checked, selCount, rows, onApprove]);

  if (rows.length === 0) {
    return (
      <div style={{ maxWidth: 860, margin: "0 auto" }}>
        <ViewHeader
          onBack={onBack}
          title="High-confidence queue"
          sub="No matches waiting — all cleared or routed to review"
          accent={C.pass}
        />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>
      <ViewHeader
        onBack={onBack}
        title="High-confidence queue"
        sub={`${rows.length} matches at ≥90% confidence`}
        accent={C.pass}
      />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", margin: "0 0 12px" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 9, cursor: "pointer", fontFamily: "var(--sans)", fontSize: 13, color: "var(--ink-soft)" }}>
          <input type="checkbox" checked={allSel} onChange={toggleAll} style={cbStyle} />
          {selCount} of {rows.length} selected
        </label>
        <span style={{ fontFamily: "var(--sans)", fontSize: 12.5, color: "var(--ink-faint)" }}>
          Deselect anything that looks off — it routes to review
        </span>
      </div>

      <div style={{ border: `1px solid ${C.line}`, borderRadius: 10, overflow: "hidden" }}>
        <div style={{ ...rowGrid, background: C.panel2, padding: "10px 14px", fontFamily: "var(--sans)", fontSize: 11.5, color: "var(--ink-faint)", fontWeight: 500, letterSpacing: 0.3, textTransform: "uppercase" }}>
          <div />
          <div>Import line</div>
          <div>Matched export</div>
          <div style={{ textAlign: "right" }}>Conf.</div>
        </div>
        {rows.map((r) => (
          <div
            key={r.id}
            style={{
              ...rowGrid,
              padding: "11px 14px",
              alignItems: "center",
              borderTop: `1px solid ${C.lineSoft}`,
              background: checked[r.id] ? "transparent" : C.bg,
              opacity: checked[r.id] ? 1 : 0.42,
              transition: "opacity .12s",
            }}
          >
            <input
              type="checkbox"
              checked={!!checked[r.id]}
              onChange={() => setChecked((s) => ({ ...s, [r.id]: !s[r.id] }))}
              style={cbStyle}
            />
            <div style={{ fontFamily: "var(--mono)", fontSize: 12.5, color: "var(--ink)" }}>
              {r.imp}
              <div style={{ color: "var(--ink-faint)", fontSize: 11, marginTop: 2 }}>
                {r.impHts} · {r.impQty}
              </div>
            </div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 12.5, color: "var(--ink)" }}>
              {r.exp} <span style={{ color: C.pass }}>✓</span>
              <div style={{ color: "var(--ink-faint)", fontSize: 11, marginTop: 2 }}>
                {r.expHts} · {r.expQty}
              </div>
            </div>
            <div style={{ textAlign: "right", fontFamily: "var(--mono)", fontSize: 13, fontWeight: 600, color: confColor(r.conf) }}>
              {Math.round(r.conf * 100)}%
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 16, alignItems: "center" }}>
        <button
          type="button"
          onClick={() => onApprove(rows.filter((r) => checked[r.id]).map((r) => r.id))}
          disabled={!selCount}
          style={primaryBtn(C.pass, !selCount)}
        >
          Approve selected ({selCount}) <Key>⏎</Key>
        </button>
        <button
          type="button"
          onClick={() => onSendToReview(rows.filter((r) => !checked[r.id]).map((r) => r.id))}
          disabled={selCount === rows.length}
          style={ghostBtn(selCount === rows.length)}
        >
          Send unchecked to review
        </button>
      </div>
    </div>
  );
}
