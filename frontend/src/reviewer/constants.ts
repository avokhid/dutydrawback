export const REASON_CODES = [
  "Vendor pack configuration differs from default",
  "Conversion factor wrong in source data",
  "Partial shipment / split carton",
  "Re-measured against commercial invoice",
  "Confirmed same item",
  "Other (specify in note)",
] as const;

export const FIELD_OPTIONS = [
  "Quantity / unit of measure",
  "HTS classification",
  "Entered value",
  "Date / eligibility window",
  "Item identity (not the same product)",
] as const;
