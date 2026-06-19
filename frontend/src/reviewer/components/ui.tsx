import type { ReactNode } from "react";

export function Pill({
  children,
  color,
  bg,
}: {
  children: ReactNode;
  color: string;
  bg: string;
}) {
  return (
    <span
      style={{
        fontFamily: "var(--mono)",
        fontSize: 11,
        letterSpacing: 0.3,
        padding: "3px 8px",
        borderRadius: 5,
        color,
        background: bg,
        whiteSpace: "nowrap",
        border: `1px solid ${color}33`,
      }}
    >
      {children}
    </span>
  );
}

export function Key({ children }: { children: ReactNode }) {
  return (
    <kbd
      style={{
        fontFamily: "var(--mono)",
        fontSize: 10,
        padding: "2px 6px",
        borderRadius: 4,
        background: "var(--panel2)",
        border: "1px solid var(--line)",
        color: "var(--ink-soft)",
        marginLeft: 6,
        lineHeight: 1.4,
      }}
    >
      {children}
    </kbd>
  );
}

export function Toast({ msg }: { msg: { text: string; color: string } | null }) {
  if (!msg) return null;
  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        left: "50%",
        transform: "translateX(-50%)",
        background: "var(--panel2)",
        border: "1px solid var(--line)",
        borderLeft: `3px solid ${msg.color}`,
        borderRadius: 9,
        padding: "11px 18px",
        fontFamily: "var(--sans)",
        fontSize: 13,
        color: "var(--ink)",
        boxShadow: "0 8px 28px rgba(0,0,0,0.4)",
        zIndex: 50,
        maxWidth: 420,
      }}
    >
      {msg.text}
    </div>
  );
}

export function ViewHeader({
  onBack,
  title,
  sub,
  accent,
  right,
  backLabel = "Back",
}: {
  onBack: () => void;
  title: string;
  sub: string;
  accent: string;
  right?: ReactNode;
  backLabel?: string;
}) {
  return (
    <div style={{ marginBottom: 20 }}>
      <button
        type="button"
        onClick={onBack}
        style={{
          background: "none",
          border: "none",
          color: "var(--ink-faint)",
          fontFamily: "var(--sans)",
          fontSize: 12.5,
          cursor: "pointer",
          padding: 0,
          marginBottom: 12,
        }}
      >
        ← {backLabel}
      </button>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span
          style={{ width: 3, height: 26, background: accent, borderRadius: 2 }}
        />
        <h2
          style={{
            fontFamily: "var(--sans)",
            fontSize: 20,
            fontWeight: 600,
            margin: 0,
            color: "var(--ink)",
            letterSpacing: -0.2,
          }}
        >
          {title}
        </h2>
        {right && <div style={{ marginLeft: "auto" }}>{right}</div>}
      </div>
      <div
        style={{
          fontFamily: "var(--sans)",
          fontSize: 13,
          color: "var(--ink-soft)",
          marginLeft: 15,
          marginTop: 3,
        }}
      >
        {sub}
      </div>
    </div>
  );
}

export function primaryBtn(accent: string, disabled?: boolean) {
  return {
    fontFamily: "var(--sans)",
    fontSize: 13.5,
    fontWeight: 500,
    color: "var(--bg)",
    background: accent,
    border: "none",
    borderRadius: 8,
    padding: "9px 16px",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.4 : 1,
    display: "inline-flex" as const,
    alignItems: "center" as const,
  };
}

export function ghostBtn(disabled?: boolean) {
  return {
    fontFamily: "var(--sans)",
    fontSize: 13.5,
    fontWeight: 500,
    color: "var(--ink)",
    background: "transparent",
    border: "1px solid var(--line)",
    borderRadius: 8,
    padding: "9px 16px",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.4 : 1,
    display: "inline-flex" as const,
    alignItems: "center" as const,
  };
}

export const inputStyle = {
  width: "100%",
  boxSizing: "border-box" as const,
  height: 38,
  padding: "0 12px",
  fontFamily: "var(--sans)",
  fontSize: 13.5,
  color: "var(--ink)",
  background: "var(--panel2)",
  border: "1px solid var(--line)",
  borderRadius: 7,
  outline: "none",
};

export const cbStyle = {
  width: 16,
  height: 16,
  accentColor: "var(--pass)",
  cursor: "pointer",
};
