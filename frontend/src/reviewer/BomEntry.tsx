import { useEffect, useState } from "react";
import { estimateManufacturing, fetchImportLines } from "./api";
import { C, mono, sans } from "./theme";
import type { ImportLine, ManufacturingEstimate } from "./types";

// Manufacturing drawback needs production data no uploaded document holds: which
// imported inputs went into the exported article, in what quantities, at what
// yield. So this is structured DATA ENTRY, not a calculation — the user supplies
// the numbers, the engine builds designations from exactly what's entered. We do
// not estimate or adjust the BOM.

interface Row {
  id: number;
  entryKey: string;
  quantity_per_unit: string;
  yield_factor: string;
}

let _rowId = 1;
const newRow = (): Row => ({ id: _rowId++, entryKey: "", quantity_per_unit: "", yield_factor: "1" });

const lbl: React.CSSProperties = {
  display: "block", fontFamily: sans, fontSize: 12.5, fontWeight: 500, color: C.inkSoft, marginBottom: 6,
};
const inp: React.CSSProperties = {
  width: "100%", boxSizing: "border-box", height: 38, padding: "0 12px",
  fontFamily: sans, fontSize: 13.5, color: C.ink,
  background: C.panel2, border: `1px solid ${C.line}`, borderRadius: 7,
};

export default function BomEntry() {
  const [entries, setEntries] = useState<ImportLine[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [articleId, setArticleId] = useState("");
  const [qtyExported, setQtyExported] = useState("");
  const [rows, setRows] = useState<Row[]>([newRow()]);
  const [result, setResult] = useState<ManufacturingEstimate | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchImportLines()
      .then(setEntries)
      .catch((e) => setLoadErr(String(e)));
  }, []);

  const setRow = (id: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const addRow = () => setRows((rs) => [...rs, newRow()]);
  const removeRow = (id: number) =>
    setRows((rs) => (rs.length > 1 ? rs.filter((r) => r.id !== id) : rs));

  const complete =
    !!articleId.trim() && !!qtyExported.trim() &&
    rows.every((r) => r.entryKey && r.quantity_per_unit.trim() && r.yield_factor.trim());

  const submit = async () => {
    setErr(null);
    const components = rows.map((r) => {
      const [entry, line] = r.entryKey.split("|");
      return {
        import_entry_number: entry,
        import_line_number: Number(line),
        quantity_per_unit: r.quantity_per_unit,
        yield_factor: r.yield_factor || "1",
      };
    });
    setBusy(true);
    try {
      const data = await estimateManufacturing({
        article_id: articleId,
        quantity_exported: qtyExported,
        components,
      });
      setResult(data);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "44px 24px 80px", fontFamily: sans }}>
      <div style={{ maxWidth: 700, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 22 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: C.review }} />
          <span style={{ fontFamily: mono, fontSize: 12.5, letterSpacing: 1, color: C.inkSoft, textTransform: "uppercase" }}>
            Drawback · Bill of Materials
          </span>
        </div>

        <h1 style={{ fontFamily: sans, fontSize: 22, fontWeight: 600, color: C.ink, margin: "0 0 4px" }}>
          What went into the exported article?
        </h1>
        <p style={{ fontFamily: sans, fontSize: 14, color: C.inkSoft, margin: "0 0 8px", lineHeight: 1.6 }}>
          Manufacturing drawback needs your production data: which imported inputs were
          consumed making the exported article, and in what quantities. This isn't on your
          import or export documents — only you have it.
        </p>
        <p style={{ fontFamily: sans, fontSize: 12.5, color: C.inkFaint, margin: "0 0 24px", lineHeight: 1.6 }}>
          We use exactly the numbers you enter — we don't estimate or adjust your bill of materials.
        </p>

        <div style={{ display: "flex", gap: 12, marginBottom: 22 }}>
          <div style={{ flex: 2 }}>
            <label style={lbl}>Exported article</label>
            <input value={articleId} onChange={(e) => setArticleId(e.target.value)}
              placeholder="e.g. Finished laptop assembly" style={inp} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Quantity exported</label>
            <input value={qtyExported} onChange={(e) => setQtyExported(e.target.value.replace(/[^0-9.]/g, ""))}
              placeholder="e.g. 500" style={{ ...inp, fontFamily: mono }} />
          </div>
        </div>

        <div style={{ fontFamily: sans, fontSize: 14, fontWeight: 600, color: C.ink, marginBottom: 4 }}>
          Imported inputs consumed
        </div>
        <p style={{ fontFamily: sans, fontSize: 12.5, color: C.inkFaint, margin: "0 0 12px", lineHeight: 1.5 }}>
          For each imported input: how many units go into <i>one</i> finished article, and the
          yield (1 = no loss; 0.95 = 5% waste).
        </p>

        {loadErr && (
          <div style={{ fontFamily: sans, fontSize: 12.5, color: C.reject, marginBottom: 12 }}>
            Couldn't load your import lines: {loadErr}
          </div>
        )}

        <div style={{ border: `1px solid ${C.line}`, borderRadius: 12, overflow: "hidden", background: C.panel }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 120px 90px 36px", gap: 10, padding: "10px 14px", background: C.panel2, fontFamily: sans, fontSize: 11.5, color: C.inkFaint, textTransform: "uppercase", letterSpacing: 0.3 }}>
            <div>Imported input (from your 7501s)</div>
            <div>Units per article</div>
            <div>Yield</div>
            <div />
          </div>
          {rows.map((r) => (
            <div key={r.id} style={{ display: "grid", gridTemplateColumns: "1fr 120px 90px 36px", gap: 10, padding: "11px 14px", alignItems: "center", borderTop: `1px solid ${C.lineSoft}` }}>
              <select value={r.entryKey} onChange={(e) => setRow(r.id, { entryKey: e.target.value })} style={{ ...inp, height: 34 }}>
                <option value="">Select an imported input…</option>
                {entries.map((e) => (
                  <option key={`${e.entry_number}|${e.line_number}`} value={`${e.entry_number}|${e.line_number}`}>
                    {e.label}
                  </option>
                ))}
              </select>
              <input value={r.quantity_per_unit} onChange={(e) => setRow(r.id, { quantity_per_unit: e.target.value.replace(/[^0-9.]/g, "") })}
                placeholder="e.g. 2" style={{ ...inp, height: 34, fontFamily: mono }} />
              <input value={r.yield_factor} onChange={(e) => setRow(r.id, { yield_factor: e.target.value.replace(/[^0-9.]/g, "") })}
                style={{ ...inp, height: 34, fontFamily: mono }} />
              <button type="button" onClick={() => removeRow(r.id)} aria-label="Remove input"
                style={{ background: "none", border: "none", color: C.inkFaint, cursor: "pointer", fontSize: 17 }}>×</button>
            </div>
          ))}
        </div>

        <button type="button" onClick={addRow}
          style={{ background: "none", border: "none", color: C.accent, fontFamily: sans, fontSize: 13, cursor: "pointer", padding: "10px 2px 0" }}>
          + Add another imported input
        </button>

        <div style={{ marginTop: 22 }}>
          <button type="button" onClick={submit} disabled={!complete || busy} style={{
            fontFamily: sans, fontSize: 13.5, fontWeight: 500,
            color: complete && !busy ? C.bg : C.inkFaint, background: complete && !busy ? C.review : C.panel2,
            border: "none", borderRadius: 8, padding: "11px 20px", cursor: complete && !busy ? "pointer" : "default",
          }}>{busy ? "Estimating…" : "Estimate manufacturing recovery →"}</button>
          {!complete && (
            <span style={{ fontFamily: sans, fontSize: 12.5, color: C.inkFaint, marginLeft: 12 }}>
              Fill in the article, quantity, and each input row.
            </span>
          )}
        </div>

        {err && (
          <div style={{ marginTop: 18, border: `1px solid ${C.reject}55`, borderRadius: 10, background: C.rejectBg, padding: "13px 16px", fontFamily: sans, fontSize: 12.5, color: C.reject }}>
            {err}
          </div>
        )}

        {result && (
          <div style={{ marginTop: 22, border: `1px solid ${C.line}`, borderRadius: 12, background: C.panel, padding: "18px 20px" }}>
            <div style={{ fontFamily: sans, fontSize: 13, color: C.inkSoft, marginBottom: 4 }}>Estimated manufacturing recovery</div>
            <div style={{ fontFamily: mono, fontSize: 32, fontWeight: 600, color: C.pass, letterSpacing: -0.5, marginBottom: 14 }}>
              ${Number(result.estimated_recovery).toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
            <div style={{ fontFamily: sans, fontSize: 13, fontWeight: 600, color: C.ink, marginBottom: 8 }}>Input units the engine designated</div>
            {result.designations.map((d, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", fontFamily: mono, fontSize: 13, color: C.inkSoft, padding: "6px 0", borderTop: i > 0 ? `1px solid ${C.lineSoft}` : "none" }}>
                <span>{d.entry_number} · line {d.import_line}</span>
                <span style={{ color: C.ink }}>{d.input_units_needed} units</span>
              </div>
            ))}
            <p style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint, marginTop: 12, lineHeight: 1.55 }}>{result.basis}</p>
            <p style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint, marginTop: 6, lineHeight: 1.55 }}>{result.disclaimer}</p>
          </div>
        )}

        <p style={{ fontFamily: sans, fontSize: 12, color: C.inkFaint, marginTop: 24, lineHeight: 1.6, borderTop: `1px solid ${C.lineSoft}`, paddingTop: 16 }}>
          Recovery is computed from the bill of materials you supply. We don't verify your
          inputs or yields — their accuracy is yours to confirm. Manufacturing drawback edge
          cases (multi-input apportionment, yield treatment) should be reviewed by a licensed
          specialist. Estimate, not a filing.
        </p>
      </div>
    </div>
  );
}
