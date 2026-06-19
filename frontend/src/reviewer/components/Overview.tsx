import type { ClaimStats } from "../types";
import { C } from "../theme";

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div style={{ fontFamily: "var(--mono)", fontSize: 22, fontWeight: 600, color }}>
        {value}
      </div>
      <div style={{ fontFamily: "var(--sans)", fontSize: 12, color: "var(--ink-soft)" }}>
        {label}
      </div>
    </div>
  );
}

function cardBtn(accent: string) {
  return {
    textAlign: "left" as const,
    cursor: "pointer",
    background: C.panel,
    border: `1px solid ${C.line}`,
    borderLeft: `3px solid ${accent}`,
    borderRadius: 10,
    padding: "22px 22px 20px",
    transition: "background .15s",
  };
}

export default function Overview({
  stats,
  onGoBulk,
  onGoReview,
}: {
  stats: ClaimStats;
  onGoBulk: () => void;
  onGoReview: () => void;
}) {
  const total =
    stats.autoPass + stats.review + stats.approved + stats.rejected;
  const pct = total ? Math.round((stats.approved / total) * 100) : 0;

  return (
    <div style={{ maxWidth: 760, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 4 }}>
        <h1
          style={{
            fontFamily: "var(--sans)",
            fontSize: 26,
            fontWeight: 600,
            margin: 0,
            color: "var(--ink)",
            letterSpacing: -0.3,
          }}
        >
          Claim {stats.claimId}
        </h1>
        <span style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--ink-faint)" }}>
          {stats.claimant}
        </span>
      </div>
      <p
        style={{
          fontFamily: "var(--sans)",
          fontSize: 14,
          color: "var(--ink-soft)",
          margin: "0 0 28px",
          lineHeight: 1.6,
        }}
      >
        {total} proposed matches. The engine cleared the confident
        ones; your attention goes only to what it could not resolve.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 14,
          marginBottom: 28,
        }}
      >
        <button type="button" onClick={onGoBulk} style={cardBtn(C.pass)}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 40, fontWeight: 600, color: C.pass, lineHeight: 1 }}>
            {stats.autoPass}
          </div>
          <div style={{ fontFamily: "var(--sans)", fontSize: 14, color: "var(--ink)", marginTop: 8, fontWeight: 500 }}>
            High confidence — ready to approve
          </div>
          <div style={{ fontFamily: "var(--sans)", fontSize: 12.5, color: "var(--ink-soft)", marginTop: 4 }}>
            Clear the whole batch in one action →
          </div>
        </button>
        <button type="button" onClick={onGoReview} style={cardBtn(C.review)}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 40, fontWeight: 600, color: C.review, lineHeight: 1 }}>
            {stats.review}
          </div>
          <div style={{ fontFamily: "var(--sans)", fontSize: 14, color: "var(--ink)", marginTop: 8, fontWeight: 500 }}>
            Needs your review
          </div>
          <div style={{ fontFamily: "var(--sans)", fontSize: 12.5, color: "var(--ink-soft)", marginTop: 4 }}>
            One uncertain field each — confirm or correct →
          </div>
        </button>
      </div>

      <div
        style={{
          display: "flex",
          gap: 24,
          padding: "16px 20px",
          background: C.panel,
          border: `1px solid ${C.line}`,
          borderRadius: 10,
        }}
      >
        <Stat label="Approved" value={stats.approved} color={C.pass} />
        <Stat label="Rejected" value={stats.rejected} color={C.reject} />
        <Stat label="Remaining" value={stats.autoPass + stats.review} color={C.ink} />
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 22, fontWeight: 600, color: C.accent }}>
            ${stats.refund}
          </div>
          <div style={{ fontFamily: "var(--sans)", fontSize: 12, color: "var(--ink-soft)" }}>
            refund approved · {pct}% complete
          </div>
        </div>
      </div>
    </div>
  );
}
