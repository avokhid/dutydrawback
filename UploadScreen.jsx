import React, { useState, useRef, useCallback } from "react";

// ─────────────────────────────────────────────────────────────────────────
// Duty Drawback — Document Upload (the front door)
//
// Where a customer drops in their 7501s and export records. Stages files with
// type/size validation, shows per-file extraction status, and hands off to the
// activity feed to run the estimate.
//
// This is the moment real, messy customer documents first hit api_extract.py —
// which is also the #1 untested assumption in the whole system. So this screen
// IS the real-document test harness: building it and validating live extraction
// are the same step.
//
// Wire for real:
//   - POST each file to an upload endpoint backed by api_extract.extract_7501_from_pdf
//   - stream per-file extraction status (reuse the SSE pattern)
//   - on "Run estimate", advance to the ActivityFeed component
// Here, extraction is simulated with the same status shapes the backend emits,
// so the flow is clickable without a backend or API key.
// ─────────────────────────────────────────────────────────────────────────

const C = {
  bg: "#10110F", panel: "#181A17", panel2: "#1F221D", line: "#2C302A",
  lineSoft: "#23261F", ink: "#EDEFE9", inkSoft: "#A7AC9E", inkFaint: "#6E7567",
  ok: "#7FB069", okBg: "#1A2417", busy: "#6BA8C9", warn: "#D8A24A", err: "#C16E5A",
  accent: "#6BA8C9", accentBg: "#13202722",
};
const mono = "'JetBrains Mono','SF Mono',ui-monospace,monospace";
const sans = "'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif";

const ACCEPTED = [".pdf", ".xlsx", ".xls", ".csv"];
const MAX_MB = 25;

function classify(name) {
  const n = name.toLowerCase();
  if (n.includes("7501") || n.includes("entry") || n.includes("import")) return "import";
  if (n.includes("bol") || n.includes("export") || n.includes("aes")) return "export";
  return "unknown";
}

function fmtSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

// Demo file seeds so the screen is meaningful without a real picker.
const DEMO_FILES = [
  { name: "entry_summary_7501.pdf", size: 248000 },
  { name: "export_bol_77.pdf", size: 131000 },
  { name: "broker_report_q1.xlsx", size: 54000 },
];

export default function UploadScreen({ onRun }) {
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [done, setDone] = useState(false);
  const inputRef = useRef(null);
  const timers = useRef([]);

  const addFiles = useCallback((incoming) => {
    const staged = incoming.map((f, i) => {
      const ext = "." + f.name.split(".").pop().toLowerCase();
      const tooBig = f.size > MAX_MB * 1024 * 1024;
      const badType = !ACCEPTED.includes(ext);
      return {
        id: Date.now() + "-" + i,
        name: f.name, size: f.size,
        kind: classify(f.name),
        status: badType ? "rejected" : tooBig ? "rejected" : "staged",
        error: badType ? "Unsupported file type" : tooBig ? `Over ${MAX_MB}MB` : null,
      };
    });
    setFiles((prev) => [...prev, ...staged]);
    setDone(false);
  }, []);

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  };
  const onPick = (e) => addFiles(Array.from(e.target.files));
  const loadDemo = () => addFiles(DEMO_FILES.map((d) => ({ name: d.name, size: d.size })));
  const remove = (id) => setFiles((f) => f.filter((x) => x.id !== id));

  const valid = files.filter((f) => f.status !== "rejected");

  const extract = () => {
    if (!valid.length) return;
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setExtracting(true); setDone(false);
    // simulate per-file extraction; real version streams status from backend
    valid.forEach((f, i) => {
      const t1 = setTimeout(() => setFiles((prev) => prev.map((x) =>
        x.id === f.id ? { ...x, status: "extracting" } : x)), 300 + i * 250);
      const t2 = setTimeout(() => setFiles((prev) => prev.map((x) =>
        x.id === f.id ? { ...x, status: "extracted", lines: f.kind === "unknown" ? 0 : (3 + i) } : x)),
        900 + i * 600);
      timers.current.push(t1, t2);
    });
    const tDone = setTimeout(() => { setExtracting(false); setDone(true); }, 900 + valid.length * 600 + 200);
    timers.current.push(tDone);
  };

  const statusColor = (s) => s === "extracted" ? C.ok : s === "extracting" ? C.busy : s === "rejected" ? C.err : C.inkSoft;
  const statusLabel = (f) =>
    f.status === "staged" ? "Ready" :
    f.status === "extracting" ? "Reading…" :
    f.status === "extracted" ? (f.lines ? `${f.lines} line(s) read` : "No data found") :
    f.error || "Rejected";

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "44px 24px 80px", fontFamily: sans }}>
      <style>{`*{box-sizing:border-box} button:hover:not(:disabled){filter:brightness(1.1)}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}} .pulsing{animation:pulse 1.1s ease-in-out infinite}
        @media (prefers-reduced-motion:reduce){.pulsing{animation:none}}`}</style>

      <div style={{ maxWidth: 680, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: C.accent }} />
          <span style={{ fontFamily: mono, fontSize: 12.5, letterSpacing: 1, color: C.inkSoft, textTransform: "uppercase" }}>
            Drawback · New Estimate
          </span>
        </div>

        <h1 style={{ fontFamily: sans, fontSize: 22, fontWeight: 600, color: C.ink, margin: "0 0 4px" }}>
          Upload your documents
        </h1>
        <p style={{ fontFamily: sans, fontSize: 14, color: C.inkSoft, margin: "0 0 24px", lineHeight: 1.6 }}>
          Add your entry summaries (7501s) and export records. We'll read them, pair
          your shipments, and estimate what you could recover. PDF, Excel, or CSV.
        </p>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current && inputRef.current.click()}
          style={{
            border: `1.5px dashed ${dragging ? C.accent : C.line}`,
            background: dragging ? C.accentBg : C.panel,
            borderRadius: 12, padding: "32px 20px", textAlign: "center", cursor: "pointer",
            transition: "border-color .15s, background .15s", marginBottom: 16,
          }}>
          <div style={{ fontSize: 26, color: C.inkFaint, marginBottom: 8 }}>↑</div>
          <div style={{ fontFamily: sans, fontSize: 14.5, color: C.ink, fontWeight: 500 }}>
            Drop files here or click to browse
          </div>
          <div style={{ fontFamily: sans, fontSize: 12.5, color: C.inkFaint, marginTop: 4 }}>
            {ACCEPTED.join(", ")} · up to {MAX_MB}MB each
          </div>
          <input ref={inputRef} type="file" multiple accept={ACCEPTED.join(",")} onChange={onPick} style={{ display: "none" }} />
        </div>

        {files.length === 0 && (
          <button onClick={loadDemo} style={{
            fontFamily: sans, fontSize: 13, color: C.accent, background: "none",
            border: "none", cursor: "pointer", padding: 0, marginBottom: 8,
          }}>Or load sample documents →</button>
        )}

        {files.length > 0 && (
          <div style={{ border: `1px solid ${C.line}`, borderRadius: 12, overflow: "hidden", background: C.panel, marginBottom: 16 }}>
            {files.map((f, i) => (
              <div key={f.id} style={{
                display: "flex", alignItems: "center", gap: 12, padding: "12px 16px",
                borderTop: i > 0 ? `1px solid ${C.lineSoft}` : "none",
                opacity: f.status === "rejected" ? 0.6 : 1,
              }}>
                <span className={f.status === "extracting" ? "pulsing" : ""} style={{
                  width: 9, height: 9, borderRadius: "50%", background: statusColor(f.status), flexShrink: 0,
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontFamily: mono, fontSize: 13, color: C.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</span>
                    {f.kind !== "unknown" && f.status !== "rejected" && (
                      <span style={{ fontFamily: sans, fontSize: 10.5, color: C.inkFaint, border: `1px solid ${C.line}`, borderRadius: 4, padding: "1px 6px", textTransform: "uppercase", letterSpacing: 0.3 }}>{f.kind}</span>
                    )}
                  </div>
                  <div style={{ fontFamily: sans, fontSize: 12, color: statusColor(f.status), marginTop: 2 }}>
                    {statusLabel(f)} <span style={{ color: C.inkFaint }}>· {fmtSize(f.size)}</span>
                  </div>
                </div>
                {!extracting && f.status !== "extracted" && (
                  <button onClick={() => remove(f.id)} aria-label="Remove file" style={{
                    background: "none", border: "none", color: C.inkFaint, cursor: "pointer", fontSize: 16, padding: 4,
                  }}>×</button>
                )}
              </div>
            ))}
          </div>
        )}

        {files.some((f) => f.kind === "unknown" && f.status !== "rejected") && (
          <div style={{ fontFamily: sans, fontSize: 12.5, color: C.warn, marginBottom: 16, lineHeight: 1.5 }}>
            Some files couldn't be identified as imports or exports — you'll be asked to confirm those after reading.
          </div>
        )}

        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {!done ? (
            <button onClick={extract} disabled={!valid.length || extracting} style={{
              fontFamily: sans, fontSize: 13.5, fontWeight: 500,
              color: (!valid.length || extracting) ? C.inkFaint : C.bg,
              background: (!valid.length || extracting) ? C.panel2 : C.accent,
              border: "none", borderRadius: 8, padding: "10px 18px",
              cursor: (!valid.length || extracting) ? "default" : "pointer",
            }}>{extracting ? "Reading documents…" : `Read ${valid.length || ""} document${valid.length === 1 ? "" : "s"}`}</button>
          ) : (
            <button onClick={() => onRun && onRun(valid)} style={{
              fontFamily: sans, fontSize: 13.5, fontWeight: 500, color: C.bg, background: C.ok,
              border: "none", borderRadius: 8, padding: "10px 18px", cursor: "pointer",
            }}>Run estimate →</button>
          )}
          {done && (
            <span style={{ fontFamily: sans, fontSize: 13, color: C.ok }}>
              {valid.filter((f) => f.kind !== "unknown").length} document(s) read and ready
            </span>
          )}
        </div>

        {done && (
          <p style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint, marginTop: 16, lineHeight: 1.6 }}>
            Next: we pair your imports to exports and estimate recovery. You'll be able to
            review any pairing we're unsure about before it counts.
          </p>
        )}
      </div>
    </div>
  );
}
