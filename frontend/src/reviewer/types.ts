export interface ClaimStats {
  claimId: string;
  claimant: string;
  autoPass: number;
  review: number;
  approved: number;
  rejected: number;
  totalProposed: number;
  refund: string;
}

export interface BulkRow {
  id: string;
  imp: string;
  impHts: string;
  impQty: string;
  exp: string;
  expHts: string;
  expQty: string;
  conf: number;
}

export interface ReviewField {
  label: string;
  imp: string;
  exp: string;
  ok: boolean;
  note?: string;
}

export interface ReviewItem {
  id: string;
  vendor: string;
  part: string;
  conf: number;
  uncertain: string;
  fields: Record<string, ReviewField>;
  suggestion: { text: string; detail: string };
  proof: { source: string; line: string; highlight: string };
}

export interface CorrectionPayload {
  match_id: string;
  field: string;
  system_value: string;
  corrected: string;
  reason: string;
  note: string;
  asRule: boolean;
}

export interface ToastMsg {
  text: string;
  color: string;
}

export interface EstimateLine {
  hts: string;
  desc: string;
  duties: string;
  refund: string;
  capped: boolean;
  conf: "high" | "review";
}

export interface ClaimEstimate {
  firm: string;
  period: string;
  confident: string;
  potential: string;
  rangeLow: string;
  rangeHigh: string;
  confidentPct: number;
  entriesAnalyzed: number;
  matchedLines: number;
  drawbackType: string;
  lines: EstimateLine[];
  disclaimer: string;
}

export interface ExplanationStep {
  text: string;
  math: string | null;
  basis: string | null;
  tier?: string;
  tier_label?: string;
  certainty?: string;
}

export interface RulingRef {
  ruling_id: string;
  date: string;
  issue: string;
  holding: string;
  hts_codes: string[];
  provisions: string[];
  status: string;
  superseded_by: string | null;
  url: string | null;
  is_sample: boolean;
  disposition: string;
}

export interface AdvisoryBlock {
  adjudications: {
    status: string;
    message: string;
    illustrative_decisions: { citation: string; summary: string; note: string }[];
    has_comprehensive_data: boolean;
  };
  discretion: { status: string; message: string };
}

export interface ImportLine {
  entry_number: string;
  line_number: number;
  hts_code: string;
  description: string;
  label: string;
}

export interface BomComponentPayload {
  import_entry_number: string;
  import_line_number: number;
  quantity_per_unit: string;
  yield_factor: string;
}

export interface BomPayload {
  article_id: string;
  quantity_exported: string;
  components: BomComponentPayload[];
}

export interface ManufacturingEstimate {
  article_id: string;
  quantity_exported: string;
  components: number;
  designations: { entry_number: string; import_line: number; input_units_needed: string }[];
  estimated_recovery: string;
  basis: string;
  disclaimer: string;
}

export interface LineExplanation {
  entry_number?: string;
  import_line: number;
  export_id: string;
  drawback_type: string;
  quantity: string;
  refund: string;
  capped: boolean;
  steps: ExplanationStep[];
  line_index?: number;
  line_count?: number;
  hts_code?: string | null;
  provision?: string | null;
  rulings?: RulingRef[];
  advisory?: AdvisoryBlock;
  transparency?: {
    statute: number;
    ruling: number;
    advisory: number;
    discretion_notice: string;
    scope_statement: string;
  };
}
