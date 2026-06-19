import type {
  BomPayload,
  BulkRow,
  ClaimEstimate,
  ClaimStats,
  CorrectionPayload,
  ImportLine,
  LineExplanation,
  ManufacturingEstimate,
  ReviewItem,
} from "./types";

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API ${resp.status}: ${text}`);
  }
  return resp.json();
}

export async function fetchStats(): Promise<ClaimStats> {
  return json(await fetch("/api/claim/stats"));
}

export async function fetchEstimate(): Promise<ClaimEstimate> {
  return json(await fetch("/api/claim/estimate"));
}

export async function fetchExplanation(line = 0): Promise<LineExplanation> {
  return json(await fetch(`/api/claim/explanation?line=${line}`));
}

export async function fetchImportLines(): Promise<ImportLine[]> {
  const data = await json<{ import_lines: ImportLine[] }>(
    await fetch("/api/claim/import-lines"),
  );
  return data.import_lines;
}

export async function estimateManufacturing(
  body: BomPayload,
): Promise<ManufacturingEstimate> {
  const resp = await fetch("/api/manufacturing/estimate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    const detail =
      typeof data.detail === "string" ? data.detail : data.detail?.error;
    throw new Error(detail || `API ${resp.status}`);
  }
  return resp.json();
}

export async function fetchBulkMatches(): Promise<BulkRow[]> {
  return json(await fetch("/api/matches?tier=auto_pass"));
}

export async function fetchReviewMatches(): Promise<ReviewItem[]> {
  return json(await fetch("/api/matches?tier=review"));
}

export async function approveBulk(ids: string[]): Promise<ClaimStats> {
  const data = await json<{ stats: ClaimStats }>(
    await fetch("/api/matches/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    }),
  );
  return data.stats;
}

export async function sendToReview(ids: string[]): Promise<ClaimStats> {
  const data = await json<{ stats: ClaimStats }>(
    await fetch("/api/matches/send-to-review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    }),
  );
  return data.stats;
}

export async function approveOne(id: string): Promise<ClaimStats> {
  const data = await json<{ stats: ClaimStats }>(
    await fetch(`/api/matches/${encodeURIComponent(id)}/approve`, {
      method: "POST",
    }),
  );
  return data.stats;
}

export async function rejectOne(id: string): Promise<ClaimStats> {
  const data = await json<{ stats: ClaimStats }>(
    await fetch(`/api/matches/${encodeURIComponent(id)}/reject`, {
      method: "POST",
    }),
  );
  return data.stats;
}

export async function saveCorrection(
  body: CorrectionPayload,
): Promise<{ impact: number; stats: ClaimStats }> {
  return json(
    await fetch("/api/corrections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}
