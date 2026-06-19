import { useState } from "react";
import Journey from "./reviewer/Journey";
import App from "./App";

// ─────────────────────────────────────────────────────────────────────────
// Duty Drawback — Top-level shell with two tabs.
//
// Resolves the "two layouts competing for the front door" confusion: the app
// has two intended surfaces for two audiences, and this shell makes the split
// explicit while letting users move freely between them (a broker may run a
// quick estimate, then switch to the console to work the claim properly).
//
//   Importer estimate  → the guided, linear estimator (Journey): documents in,
//                         watch the steps, get a recovery number.
//   Reviewer console   → the expert back-office hub (App): match queue, bulk
//                         approve, corrections, links to every tool.
//
// Same engine underneath; different depth and audience. Tabs (not a one-time
// fork) so switching is free.
// ─────────────────────────────────────────────────────────────────────────

const C = {
  bg: "#10110F", line: "#2C302A", ink: "#EDEFE9",
  inkSoft: "#A7AC9E", inkFaint: "#6E7567", estimator: "#7FB069", reviewer: "#D8A24A",
};
const mono = "'JetBrains Mono','SF Mono',ui-monospace,monospace";
const sans = "'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif";

const TABS = [
  { id: "estimate", label: "Importer estimate", sub: "Guided · get a recovery number", color: C.estimator },
  { id: "reviewer", label: "Reviewer console", sub: "Expert · work a claim", color: C.reviewer },
];

export default function Shell() {
  const [tab, setTab] = useState("estimate");

  return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: sans }}>
      <div style={{ borderBottom: `1px solid ${C.line}`, position: "sticky", top: 0, background: C.bg, zIndex: 10 }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 24px", display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontFamily: mono, fontSize: 12.5, letterSpacing: 1, color: C.inkSoft, textTransform: "uppercase", marginRight: 24, padding: "18px 0" }}>
            Drawback
          </span>
          {TABS.map((t) => {
            const active = t.id === tab;
            return (
              <button key={t.id} onClick={() => setTab(t.id)} style={{
                background: "none", border: "none", cursor: "pointer",
                padding: "16px 18px", position: "relative",
                borderBottom: active ? `2px solid ${t.color}` : "2px solid transparent",
              }}>
                <div style={{ fontFamily: sans, fontSize: 14, fontWeight: active ? 600 : 500,
                  color: active ? C.ink : C.inkSoft, textAlign: "left" }}>{t.label}</div>
                <div style={{ fontFamily: sans, fontSize: 11.5, color: C.inkFaint, marginTop: 2 }}>{t.sub}</div>
              </button>
            );
          })}
        </div>
      </div>

      <div>
        {tab === "estimate" && <Journey />}
        {tab === "reviewer" && <App />}
      </div>
    </div>
  );
}
