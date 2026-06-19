import { useState } from "react";
import { FIELD_OPTIONS, REASON_CODES } from "../constants";
import type { ReviewItem } from "../types";
import { C } from "../theme";
import { ViewHeader, cbStyle, ghostBtn, inputStyle, primaryBtn } from "./ui";

function Field({
  label,
  children,
  flex,
}: {
  label: string;
  children: React.ReactNode;
  flex?: boolean;
}) {
  return (
    <div style={{ marginBottom: 14, flex: flex ? 1 : undefined }}>
      <label
        style={{
          display: "block",
          fontFamily: "var(--sans)",
          fontSize: 12.5,
          fontWeight: 500,
          color: "var(--ink-soft)",
          marginBottom: 6,
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

export default function CorrectionForm({
  item,
  onSave,
  onCancel,
  impactPreview,
}: {
  item: ReviewItem;
  onSave: (data: {
    field: string;
    corrected: string;
    reason: string;
    note: string;
    asRule: boolean;
  }) => void;
  onCancel: () => void;
  impactPreview?: number;
}) {
  const [field, setField] = useState(FIELD_OPTIONS[0]);
  const [corrected, setCorrected] = useState(item.suggestion.text);
  const [reason, setReason] = useState(REASON_CODES[0]);
  const [note, setNote] = useState("");
  const [asRule, setAsRule] = useState(true);
  const impact = impactPreview ?? 0;

  return (
    <div style={{ maxWidth: 620, margin: "0 auto" }}>
      <ViewHeader
        onBack={onCancel}
        title="Correct match"
        sub={`${item.vendor} ${item.part}`}
        accent={C.review}
        backLabel="Cancel"
      />

      <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 12, padding: "20px 22px" }}>
        <Field label="Field being corrected">
          <select value={field} onChange={(e) => setField(e.target.value)} style={inputStyle}>
            {FIELD_OPTIONS.map((o) => (
              <option key={o}>{o}</option>
            ))}
          </select>
        </Field>

        <div style={{ display: "flex", gap: 12 }}>
          <Field label="System proposed" flex>
            <div
              style={{
                ...inputStyle,
                color: "var(--ink-faint)",
                background: C.bg,
                display: "flex",
                alignItems: "center",
              }}
            >
              {item.suggestion.text}
            </div>
          </Field>
          <Field label="Corrected value" flex>
            <input value={corrected} onChange={(e) => setCorrected(e.target.value)} style={inputStyle} />
          </Field>
        </div>

        <Field label="Reason code">
          <select value={reason} onChange={(e) => setReason(e.target.value)} style={inputStyle}>
            {REASON_CODES.map((o) => (
              <option key={o}>{o}</option>
            ))}
          </select>
        </Field>

        <Field label="Note (optional, for audit)">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            placeholder="e.g. Confirmed against packing list PL-4471."
            style={{ ...inputStyle, resize: "vertical", lineHeight: 1.5, padding: "9px 12px", height: "auto" }}
          />
        </Field>

        <label
          style={{
            display: "flex",
            gap: 11,
            padding: "13px 14px",
            background: C.accentBg,
            borderRadius: 8,
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <input
            type="checkbox"
            checked={asRule}
            onChange={(e) => setAsRule(e.target.checked)}
            style={{ ...cbStyle, accentColor: C.accent, marginTop: 2 }}
          />
          <span style={{ fontFamily: "var(--sans)", fontSize: 13, color: "var(--ink-soft)", lineHeight: 1.55 }}>
            Save as reusable rule — apply <b style={{ color: "var(--ink)", fontWeight: 600 }}>{corrected}</b> to
            future matches from <span style={{ fontFamily: "var(--mono)" }}>{item.vendor}</span> part{" "}
            <span style={{ fontFamily: "var(--mono)" }}>{item.part}</span>.
            {asRule && impact > 0 && (
              <span style={{ display: "block", marginTop: 3, color: C.accent }}>
                May auto-resolve up to {impact} matches in this queue.
              </span>
            )}
          </span>
        </label>

        <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
          <button
            type="button"
            onClick={() => onSave({ field, corrected, reason, note, asRule })}
            style={primaryBtn(C.review)}
          >
            Save correction
          </button>
          <button type="button" onClick={onCancel} style={ghostBtn()}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
