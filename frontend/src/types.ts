export interface ExtractionProvenance {
  page: number;
  bbox?: [number, number, number, number] | null;
  confidence?: number | null;
}

export interface LineItem {
  line_number: number;
  hts_code: string;
  description: string;
  quantity: string;
  unit_of_measure: string;
  unit_price: string;
  entered_value: string;
  duty_paid: string;
  mpf_paid: string;
  hmf_paid: string;
  provenance: Record<string, ExtractionProvenance>;
}

export interface Entry7501 {
  entry_number: string;
  entry_date: string;
  importer_of_record: string;
  port_of_entry?: string | null;
  line_items: LineItem[];
  total_entered_value: string;
  total_duty: string;
  total_mpf: string;
  total_hmf: string;
}

export interface Finding {
  code: string;
  severity: "gate" | "warn";
  message: string;
  line_number?: number | null;
  field?: string | null;
  discrepancy?: string | null;
}

export interface ValidationResult {
  ok: boolean;
  gates: Finding[];
  warnings: Finding[];
}

export interface ProcessResponse {
  entry: Entry7501;
  validation: ValidationResult;
}

export type MockMode = "clean" | "corrupt" | "live";
