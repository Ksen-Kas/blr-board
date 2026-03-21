import { JOB_STATUSES } from "../constants/statuses";

const ALIAS_TO_CANONICAL: Record<string, string> = {
  "screening req": "Screening Req",
  "screening request": "Screening Req",
  "no response": "No Response",
  rejected: "Closed",
  "hr screen": "Interview",
};

function normalizeStatus(value: string): string {
  return (value || "")
    .trim()
    .replace(/^\[+|\]+$/g, "")
    .replace(/\s+/g, " ")
    .toLowerCase();
}

export function canonicalStatusLabel(value: string): string {
  const normalized = normalizeStatus(value);
  const fromAlias = ALIAS_TO_CANONICAL[normalized];
  if (fromAlias) return fromAlias;

  const fromList = JOB_STATUSES.find((status) => status.toLowerCase() === normalized);
  if (fromList) return fromList;

  return value?.trim() || "";
}

export function canonicalStatusKey(value: string): string {
  return canonicalStatusLabel(value).toLowerCase();
}
