import { useCallback, useRef, useState } from "react";
import { C, mono, sans } from "./theme";

interface StagedFile {
  id: string;
  name: string;
  size: number;
  kind: "import" | "export" | "unknown";
  status: "staged" | "extracting" | "extracted" | "rejected";
  error?: string | null;
  lines?: number;
}

const ACCEPTED = [".pdf", ".xlsx", ".xls", ".csv", ".jpg", ".jpeg", ".png"];
const MAX_MB = 25;

function classify(name: string): StagedFile["kind"] {
  const n = name.toLowerCase();
  if (n.includes("7501") || n.includes("entry") || n.includes("import")) return "import";
  if (n.includes("bol") || n.includes("export") || n.includes("aes")) return "export";
  return "unknown";
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

const DEMO_FILES = [
  { name: "entry_summary_7501.pdf", size: 248000 },
  { name: "export_bol_77.pdf", size: 131000 },
  { name: "broker_report_q1.xlsx", size: 54000 },
];

export default function UploadScreen({ onRun }: { onRun?: (files: StagedFile[]) => void }) {
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [done, setDone] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const addFiles = useCallback((incoming: { name: string; size: number }[]) => {
    const staged: StagedFile[] = incoming.map((f, i) => {
      const ext = "." + (f.name.split(".").pop() || "").toLowerCase();
      const tooBig = f.size > MAX_MB * 1024 * 1024;
      const badType = !ACCEPTED.includes(ext);
      return {
        id: Date.now() + "-" + i,
        name: f.name,
        size: f.size,
        kind: classify(f.name),
        status: badType || tooBig ? "rejected" : "staged",
        error: badType ? "Unsupported file type" : tooBig ? `Over ${MAX_MB}MB` : null,
      };
    });
    setFiles((prev) => [...prev, ...staged]);
    setDone(false);
  }, []);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  };
  const onPick = (e: React.ChangeEvent<HTMLInputElement>) =>
    addFiles(Array.from(e.target.files ?? []));
  const loadDemo = () => addFiles(DEMO_FILES);
  const remove = (id: string) => setFiles((f) => f.filter((x) => x.id !== id));

  const valid = files.filter((f) => f.status !== "rejected");

  const extract = () => {
    if (!valid.length) return;
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setExtracting(true);
    setDone(false);
    valid.forEach((f, i) => {
      const t1 = setTimeout(
        () => setFiles((prev) => prev.map((x) => (x.id === f.id ? { ...x, status: "extracting" } : x))),
        300 + i * 250,
      );
      const t2 = setTimeout(
        () =>
          setFiles((prev) =>
            prev.map((x) =>
              x.id === f.id ? { ...x, status: "extracted", lines: f.kind === "unknown" ? 0 : 3 + i } : x,
            ),
          ),
        900 + i * 600,
      );
      timers.current.push(t1, t2);
    });
    const tDone = setTimeout(() => {
      setExtracting(false);
      setDone(true);
    }, 900 + valid.length * 600 + 200);
    timers.current.push(tDone);
  };

  const statusColor = (s: StagedFile["status"]) =>
    s === "extracted" ? C.pass : s === "extracting" ? C.accent : s === "rejected" ? C.reject : C.inkSoft;
  const statusLabel = (f: StagedFile) =>
    f.status === "staged"
      ? "Ready"
      : f.status === "extracting"
        ? "Reading…"
        : f.status === "extracted"
          ? f.lines
            ? `${f.lines} line(s) read`
            : "No data found"
          : f.error || "Rejected";

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "44px 24px 80px", fontFamily: sans }}>
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
          Add your entry summaries (7501s) and export records. We'll read them, pair your shipments, and
          estimate what you could recover. PDF, Excel, CSV, or a photo/scan of the form (JPG, PNG).
        </p>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          style={{
            border: `1.5px dashed ${dragging ? C.accent : C.line}`,
            background: dragging ? C.accentBg : C.panel,
            borderRadius: 12,
            padding: "32px 20px",
            textAlign: "center",
            cursor: "pointer",
            transition: "border-color .15s, background .15s",
            marginBottom: 16,
          }}
        >
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
          <button
            type="button"
            onClick={loadDemo}
            style={{ fontFamily: sans, fontSize: 13, color: C.accent, background: "none", border: "none", cursor: "pointer", padding: 0, marginBottom: 8 }}
          >
            Or load sample documents →
          </button>
        )}

        {files.length > 0 && (
          <div style={{ border: `1px solid ${C.line}`, borderRadius: 12, overflow: "hidden", background: C.panel, marginBottom: 16 }}>
            {files.map((f, i) => (
              <div
                key={f.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "12px 16px",
                  borderTop: i > 0 ? `1px solid ${C.lineSoft}` : "none",
                  opacity: f.status === "rejected" ? 0.6 : 1,
                }}
              >
                <span
                  className={f.status === "extracting" ? "pulsing" : ""}
                  style={{ width: 9, height: 9, borderRadius: "50%", background: statusColor(f.status), flexShrink: 0 }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontFamily: mono, fontSize: 13, color: C.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {f.name}
                    </span>
                    {f.kind !== "unknown" && f.status !== "rejected" && (
                      <span style={{ fontFamily: sans, fontSize: 10.5, color: C.inkFaint, border: `1px solid ${C.line}`, borderRadius: 4, padding: "1px 6px", textTransform: "uppercase", letterSpacing: 0.3 }}>
                        {f.kind}
                      </span>
                    )}
                  </div>
                  <div style={{ fontFamily: sans, fontSize: 12, color: statusColor(f.status), marginTop: 2 }}>
                    {statusLabel(f)} <span style={{ color: C.inkFaint }}>· {fmtSize(f.size)}</span>
                  </div>
                </div>
                {!extracting && f.status !== "extracted" && (
                  <button
                    type="button"
                    onClick={() => remove(f.id)}
                    aria-label="Remove file"
                    style={{ background: "none", border: "none", color: C.inkFaint, cursor: "pointer", fontSize: 16, padding: 4 }}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {files.some((f) => f.kind === "unknown" && f.status !== "rejected") && (
          <div style={{ fontFamily: sans, fontSize: 12.5, color: C.review, marginBottom: 16, lineHeight: 1.5 }}>
            Some files couldn't be identified as imports or exports — you'll be asked to confirm those after reading.
          </div>
        )}

        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {!done ? (
            <button
              type="button"
              onClick={extract}
              disabled={!valid.length || extracting}
              style={{
                fontFamily: sans,
                fontSize: 13.5,
                fontWeight: 500,
                color: !valid.length || extracting ? C.inkFaint : C.bg,
                background: !valid.length || extracting ? C.panel2 : C.accent,
                border: "none",
                borderRadius: 8,
                padding: "10px 18px",
                cursor: !valid.length || extracting ? "default" : "pointer",
              }}
            >
              {extracting ? "Reading documents…" : `Read ${valid.length || ""} document${valid.length === 1 ? "" : "s"}`}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => onRun?.(valid)}
              style={{ fontFamily: sans, fontSize: 13.5, fontWeight: 500, color: C.bg, background: C.pass, border: "none", borderRadius: 8, padding: "10px 18px", cursor: "pointer" }}
            >
              Run estimate →
            </button>
          )}
          {done && (
            <span style={{ fontFamily: sans, fontSize: 13, color: C.pass }}>
              {valid.filter((f) => f.kind !== "unknown").length} document(s) read and ready
            </span>
          )}
        </div>

        {done && (
          <p style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint, marginTop: 16, lineHeight: 1.6 }}>
            Next: we pair your imports to exports and estimate recovery. You'll be able to review any pairing
            we're unsure about before it counts.
          </p>
        )}
      </div>
    </div>
  );
}
