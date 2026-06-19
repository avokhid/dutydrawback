import { useEffect, useRef, useState } from "react";
import { C, mono, sans } from "./theme";

interface StageEvent {
  stage: string;
  status: string;
  summary: string;
  detail?: {
    refund?: string;
    review?: number;
    [k: string]: unknown;
  };
  timestamp?: string;
}

interface SourceDoc {
  id: string;
  kind: string;
  document: string;
}

const STAGE_LABELS: Record<string, string> = {
  validate: "Checking your documents",
  match: "Pairing imports to exports",
  calculate: "Estimating your recovery",
  done: "Done",
  parse: "Reading your files",
};

function statusColor(s: string): string {
  if (s === "complete") return C.pass;
  if (s === "running") return C.accent;
  if (s === "paused") return C.review;
  if (s === "error") return C.reject;
  return C.inkSoft;
}
function statusBg(s: string): string {
  if (s === "complete") return C.passBg;
  if (s === "running") return C.accentBg;
  if (s === "paused") return C.reviewBg;
  return "transparent";
}

export default function ActivityFeed({ drawbackType = "unused_substitution" }: { drawbackType?: string }) {
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<SourceDoc[]>([]);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    fetch("/api/claim/source-documents")
      .then((r) => r.json())
      .then((d) => setDocs(d.documents || []))
      .catch(() => {});
  }, []);

  const pushEvent = (ev: StageEvent) => {
    setEvents((prev) => {
      const next = [...prev];
      const idx = next.findIndex((e) => e.stage === ev.stage && e.stage !== "done");
      if (idx >= 0 && ev.stage !== "done") next[idx] = ev;
      else next.push(ev);
      return next;
    });
  };

  const run = () => {
    if (esRef.current) esRef.current.close();
    setEvents([]);
    setDone(false);
    setError(null);
    setRunning(true);
    const es = new EventSource("/api/claim/run-stream?drawback_type=" + encodeURIComponent(drawbackType));
    esRef.current = es;
    es.onmessage = (msg) => {
      let ev: StageEvent;
      try {
        ev = JSON.parse(msg.data);
      } catch {
        return;
      }
      pushEvent(ev);
      if (ev.stage === "done") {
        es.close();
        esRef.current = null;
        setRunning(false);
        setDone(true);
      }
    };
    es.onerror = () => {
      es.close();
      esRef.current = null;
      setRunning(false);
      setEvents((prev) => {
        if (!prev.some((e) => e.stage === "done")) setError("Stream interrupted before completion.");
        return prev;
      });
    };
  };

  useEffect(
    () => () => {
      if (esRef.current) esRef.current.close();
    },
    [],
  );

  const refundEvent = events.find((e) => e.detail && e.detail.refund);
  const refund = refundEvent?.detail?.refund ?? null;

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "44px 24px 80px", fontFamily: sans }}>
      <div style={{ maxWidth: 680, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: C.accent }} />
          <span style={{ fontFamily: mono, fontSize: 12.5, letterSpacing: 1, color: C.inkSoft, textTransform: "uppercase" }}>
            Drawback · Pipeline Run
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
          <div>
            <h1 style={{ fontFamily: sans, fontSize: 22, fontWeight: 600, color: C.ink, margin: 0 }}>Estimate run</h1>
            <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, marginTop: 3 }}>
              Watch each step as it runs on your documents
            </div>
          </div>
          <button
            type="button"
            onClick={run}
            disabled={running}
            style={{
              fontFamily: sans,
              fontSize: 13.5,
              fontWeight: 500,
              color: running ? C.inkFaint : C.bg,
              background: running ? C.panel2 : C.accent,
              border: "none",
              borderRadius: 8,
              padding: "9px 18px",
              cursor: running ? "default" : "pointer",
            }}
          >
            {running ? "Running…" : done ? "Run again" : "Run pipeline"}
          </button>
        </div>

        {docs.length > 0 && (
          <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 10, padding: "13px 16px", marginBottom: 16 }}>
            <div style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.4 }}>
              Source documents
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {docs.map((d) => (
                <span
                  key={d.id}
                  style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: mono, fontSize: 12.5, color: C.inkSoft, background: C.panel2, border: `1px solid ${C.line}`, borderRadius: 6, padding: "5px 10px" }}
                >
                  <span style={{ color: C.inkFaint }}>▤</span>
                  {d.document}
                </span>
              ))}
            </div>
          </div>
        )}

        <div style={{ border: `1px solid ${C.line}`, borderRadius: 12, overflow: "hidden", background: C.panel }}>
          {events.length === 0 && (
            <div style={{ padding: "40px 20px", textAlign: "center", fontFamily: sans, fontSize: 13.5, color: C.inkFaint }}>
              Press “Run pipeline” to watch the stages execute.
            </div>
          )}
          {events.map((ev, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 13,
                padding: "14px 18px",
                borderTop: i > 0 ? `1px solid ${C.lineSoft}` : "none",
                background: statusBg(ev.status),
              }}
            >
              <div
                className={ev.status === "running" ? "pulsing" : ""}
                style={{ width: 9, height: 9, borderRadius: "50%", marginTop: 5, flexShrink: 0, background: statusColor(ev.status) }}
              />
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                  <span style={{ fontFamily: sans, fontSize: 13.5, fontWeight: 500, color: C.ink }}>
                    {STAGE_LABELS[ev.stage] || ev.stage}
                  </span>
                  <span
                    style={{
                      fontFamily: mono,
                      fontSize: 10.5,
                      letterSpacing: 0.4,
                      textTransform: "uppercase",
                      color: statusColor(ev.status),
                      border: `1px solid ${statusColor(ev.status)}44`,
                      borderRadius: 4,
                      padding: "1px 6px",
                    }}
                  >
                    {ev.status}
                  </span>
                </div>
                <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, marginTop: 4, lineHeight: 1.5 }}>
                  {ev.summary}
                </div>
                {ev.detail && typeof ev.detail.review === "number" && ev.detail.review > 0 && (
                  <div style={{ fontFamily: sans, fontSize: 12, color: C.review, marginTop: 5 }}>
                    {ev.detail.review} pairing(s) need your confirmation
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {error && <div style={{ marginTop: 14, fontFamily: sans, fontSize: 13, color: C.reject }}>{error}</div>}

        {done && refund && (
          <div
            style={{
              marginTop: 16,
              background: C.panel,
              border: `1px solid ${C.line}`,
              borderLeft: `3px solid ${C.pass}`,
              borderRadius: 10,
              padding: "16px 20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div>
              <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft }}>Estimated recovery</div>
              <div style={{ fontFamily: mono, fontSize: 26, fontWeight: 600, color: C.pass, marginTop: 2 }}>
                ${Number(refund).toLocaleString("en-US", { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint, maxWidth: 280, lineHeight: 1.5 }}>
              Estimate, not a filing. Includes review-tier matches as additional potential.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
