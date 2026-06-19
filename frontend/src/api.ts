import type { MockMode, ProcessResponse } from "./types";

export async function processEntry(
  file: File,
  claimDate: string,
  mockMode: MockMode,
): Promise<ProcessResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("claim_date", claimDate);
  form.append("mock_mode", mockMode);

  const resp = await fetch("/api/process", {
    method: "POST",
    body: form,
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API error ${resp.status}: ${text}`);
  }

  return resp.json();
}
