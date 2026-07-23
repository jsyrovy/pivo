export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function trimString(value: unknown): string {
  if (typeof value !== "string") return "";
  return value.trim();
}

export function parseNumber(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value !== "string") return null;
  const normalized = value.trim().replace(",", ".");
  if (!normalized) return null;
  const n = Number.parseFloat(normalized);
  return Number.isFinite(n) ? n : null;
}
