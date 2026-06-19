import { useCallback, useEffect, useState } from "react";
import {
  approveBulk,
  approveOne,
  fetchBulkMatches,
  fetchReviewMatches,
  fetchStats,
  rejectOne,
  saveCorrection,
  sendToReview,
} from "./api";
import BulkApprove from "./components/BulkApprove";
import CorrectionForm from "./components/CorrectionForm";
import Overview from "./components/Overview";
import SingleReview from "./components/SingleReview";
import { Toast } from "./components/ui";
import { C } from "./theme";
import type { BulkRow, ClaimStats, ReviewItem, ToastMsg } from "./types";
import "./reviewer.css";

type View = "overview" | "bulk" | "review";

export default function ReviewerApp() {
  const [view, setView] = useState<View>("overview");
  const [stats, setStats] = useState<ClaimStats | null>(null);
  const [bulkRows, setBulkRows] = useState<BulkRow[]>([]);
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [reviewIdx, setReviewIdx] = useState(0);
  const [correcting, setCorrecting] = useState<ReviewItem | null>(null);
  const [toast, setToast] = useState<ToastMsg | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const flash = useCallback((text: string, color: string) => {
    setToast({ text, color });
    setTimeout(() => setToast(null), 2600);
  }, []);

  const refresh = useCallback(async () => {
    const [s, bulk, review] = await Promise.all([
      fetchStats(),
      fetchBulkMatches(),
      fetchReviewMatches(),
    ]);
    setStats(s);
    setBulkRows(bulk);
    setQueue(review);
    if (reviewIdx >= review.length && review.length > 0) {
      setReviewIdx(review.length - 1);
    }
    if (review.length === 0) {
      setCorrecting(null);
    }
  }, [reviewIdx]);

  useEffect(() => {
    refresh()
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [refresh]);

  const handleApproveBulk = async (ids: string[]) => {
    const s = await approveBulk(ids);
    setStats(s);
    await refresh();
    flash(`${ids.length} matches approved and written to the audit trail.`, C.pass);
    setView("overview");
  };

  const handleSendToReview = async (ids: string[]) => {
    const s = await sendToReview(ids);
    setStats(s);
    await refresh();
    flash(`${ids.length} match${ids.length === 1 ? "" : "es"} routed to detailed review.`, C.review);
  };

  const handleApproveOne = async (id: string) => {
    const s = await approveOne(id);
    setStats(s);
    await refresh();
    flash("Match approved. Advancing to next.", C.pass);
    if (queue.length <= 1) setView("overview");
  };

  const handleRejectOne = async (id: string) => {
    const s = await rejectOne(id);
    setStats(s);
    await refresh();
    flash("Match rejected. Import line returned to the unmatched pool.", C.reject);
    if (queue.length <= 1) setView("overview");
  };

  const handleSaveCorrection = async (data: {
    field: string;
    corrected: string;
    reason: string;
    note: string;
    asRule: boolean;
  }) => {
    if (!correcting) return;
    const result = await saveCorrection({
      match_id: correcting.id,
      field: data.field,
      system_value: correcting.suggestion.text,
      corrected: data.corrected,
      reason: data.reason,
      note: data.note,
      asRule: data.asRule,
    });
    setStats(result.stats);
    setCorrecting(null);
    await refresh();
    if (data.asRule && result.impact > 0) {
      flash(`Correction saved · rule created · ${result.impact} matches auto-resolved.`, C.accent);
      setView("overview");
    } else {
      flash("Correction saved to this match and the audit trail.", C.pass);
      if (queue.length <= 1) setView("overview");
    }
  };

  const reviewItem = queue[reviewIdx];

  if (loading) {
    return (
      <div className="reviewer-shell">
        <p style={{ color: "var(--ink-soft)", fontFamily: "var(--sans)" }}>Loading claim…</p>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="reviewer-shell">
        <p style={{ color: C.reject, fontFamily: "var(--sans)" }}>
          {error ?? "Could not load claim data. Is the API running?"}
        </p>
      </div>
    );
  }

  return (
    <div className="reviewer-shell">
      <div className="reviewer-brand">
        <div className="reviewer-brand-dot" />
        <span>Drawback · Match Reviewer</span>
      </div>

      {view === "overview" && (
        <Overview
          stats={stats}
          onGoBulk={() => setView("bulk")}
          onGoReview={() => {
            if (queue.length) {
              setReviewIdx(0);
              setView("review");
            }
          }}
        />
      )}

      {view === "bulk" && (
        <BulkApprove
          rows={bulkRows}
          onApprove={handleApproveBulk}
          onSendToReview={handleSendToReview}
          onBack={() => setView("overview")}
        />
      )}

      {view === "review" && reviewItem && !correcting && (
        <SingleReview
          item={reviewItem}
          index={reviewIdx}
          total={queue.length}
          onApprove={handleApproveOne}
          onReject={handleRejectOne}
          onCorrect={setCorrecting}
          onBack={() => setView("overview")}
          onSkip={() => setReviewIdx((i) => (queue.length ? (i + 1) % queue.length : 0))}
        />
      )}

      {view === "review" && correcting && (
        <CorrectionForm
          item={correcting}
          onSave={handleSaveCorrection}
          onCancel={() => setCorrecting(null)}
        />
      )}

      {view === "review" && !reviewItem && !correcting && (
        <div style={{ maxWidth: 760, margin: "0 auto", color: "var(--ink-soft)" }}>
          <p>Review queue empty.</p>
          <button type="button" onClick={() => setView("overview")} style={{ color: C.accent, background: "none", border: "none", cursor: "pointer" }}>
            ← Back to overview
          </button>
        </div>
      )}

      <Toast msg={toast} />
    </div>
  );
}
