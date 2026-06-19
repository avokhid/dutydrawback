import { useState } from "react";
import { processEntry } from "./api";
import UploadForm from "./components/UploadForm";
import EntryViewer from "./components/EntryViewer";
import FindingsPanel from "./components/FindingsPanel";
import type { MockMode, ProcessResponse } from "./types";
import "./extraction.css";

export default function ExtractionApp() {
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(
    file: File,
    claimDate: string,
    mockMode: MockMode,
  ) {
    setLoading(true);
    setError(null);
    try {
      const data = await processEntry(file, claimDate, mockMode);
      setResult(data);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  const allFindings = result
    ? [...result.validation.gates, ...result.validation.warnings]
    : [];

  return (
    <div className="extraction-app">
      <header>
        <h1>Drawback Reviewer</h1>
        <p>CBP 7501 extraction and validation</p>
      </header>

      <main>
        <UploadForm onSubmit={handleSubmit} loading={loading} />

        {error && <div className="error-banner">{error}</div>}

        {result && (
          <>
            <div
              className={`status-banner ${
                result.validation.ok ? "status-pass" : "status-review"
              }`}
            >
              {result.validation.ok && allFindings.length === 0
                ? "Auto-pass — no findings"
                : result.validation.ok
                  ? "Pass with warnings"
                  : "Routed to review — gate findings require human review"}
            </div>

            <div className="results-grid">
              <EntryViewer entry={result.entry} findings={allFindings} />
              <FindingsPanel
                gates={result.validation.gates}
                warnings={result.validation.warnings}
              />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
