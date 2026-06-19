export const C = {
  bg: "#10110F",
  panel: "#181A17",
  panel2: "#1F221D",
  line: "#2C302A",
  lineSoft: "#23261F",
  ink: "#EDEFE9",
  inkSoft: "#A7AC9E",
  inkFaint: "#6E7567",
  pass: "#7FB069",
  passBg: "#1A2417",
  review: "#D8A24A",
  reviewBg: "#241E12",
  reject: "#C16E5A",
  rejectBg: "#241813",
  accent: "#6BA8C9",
  accentBg: "#13202733",
} as const;

export const mono =
  "'SF Mono','JetBrains Mono','Fira Code',ui-monospace,monospace";
export const sans =
  "'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif";

export function confColor(c: number): string {
  if (c >= 0.9) return C.pass;
  if (c >= 0.5) return C.review;
  return C.reject;
}
