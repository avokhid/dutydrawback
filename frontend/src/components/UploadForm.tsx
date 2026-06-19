import { useState } from "react";
import type { MockMode } from "../types";

interface Props {
  onSubmit: (file: File, claimDate: string, mockMode: MockMode) => void;
  loading: boolean;
}

export default function UploadForm({ onSubmit, loading }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [claimDate, setClaimDate] = useState("2025-09-02");
  const [mockMode, setMockMode] = useState<MockMode>("clean");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    onSubmit(file, claimDate, mockMode);
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <h2>Upload CBP 7501</h2>
      <p className="hint">
        Use mock mode for demo data (PDF content is ignored), or live mode to
        extract via Claude when ANTHROPIC_API_KEY is set.
      </p>

      <label>
        PDF file
        <input
          type="file"
          accept=".pdf,application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          required
        />
      </label>

      <label>
        Claim date
        <input
          type="date"
          value={claimDate}
          onChange={(e) => setClaimDate(e.target.value)}
          required
        />
      </label>

      <fieldset>
        <legend>Extraction mode</legend>
        <label>
          <input
            type="radio"
            name="mock_mode"
            value="clean"
            checked={mockMode === "clean"}
            onChange={() => setMockMode("clean")}
          />
          Mock — clean entry (auto-pass)
        </label>
        <label>
          <input
            type="radio"
            name="mock_mode"
            value="corrupt"
            checked={mockMode === "corrupt"}
            onChange={() => setMockMode("corrupt")}
          />
          Mock — corrupted entry (line 1 value misread)
        </label>
        <label>
          <input
            type="radio"
            name="mock_mode"
            value="live"
            checked={mockMode === "live"}
            onChange={() => setMockMode("live")}
          />
          Live — Claude API extraction (requires ANTHROPIC_API_KEY)
        </label>
      </fieldset>

      <button type="submit" disabled={!file || loading}>
        {loading ? "Processing…" : "Extract & Validate"}
      </button>
    </form>
  );
}
