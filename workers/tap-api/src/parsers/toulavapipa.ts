import type { Beer, Source } from "../schema";
import { formatStyle, inferStyleFromDegree } from "../style";

interface ColumnMap {
  name: number;
  style: number;
  brewery: number;
}

const FALLBACK_COLUMNS: ColumnMap = { name: 0, style: 1, brewery: 2 };
const TRAILING_DEGREE = /(^|\s)(\d+(?:[.,]\d+)?)\s*°?\s*$/u;

export function parseCsv(text: string): string[][] {
  const stripped = text.replace(/^\uFEFF/, "");
  const delimiter = detectDelimiter(stripped);

  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < stripped.length; i++) {
    const char = stripped[i];
    if (inQuotes) {
      if (char === '"') {
        if (stripped[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === delimiter) {
      row.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && stripped[i + 1] === "\n") i++;
      row.push(field);
      field = "";
      rows.push(row);
      row = [];
    } else {
      field += char;
    }
  }

  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  return rows;
}

function detectDelimiter(text: string): string {
  const firstLine = text.split(/\r?\n/).find((line) => line.trim() !== "") ?? "";
  let semicolons = 0;
  let commas = 0;
  let inQuotes = false;
  for (const char of firstLine) {
    if (char === '"') inQuotes = !inQuotes;
    else if (!inQuotes && char === ";") semicolons++;
    else if (!inQuotes && char === ",") commas++;
  }
  return semicolons > commas ? ";" : ",";
}

export function parseToulavapipaCsv(raw: string, source: Source): Beer[] {
  const rows = parseCsv(raw);
  if (rows.length === 0) return [];

  let columns = FALLBACK_COLUMNS;
  let dataRows = rows;
  const headerColumns = findColumns(rows[0]);
  if (headerColumns) {
    columns = headerColumns;
    dataRows = rows.slice(1);
  }

  const beers: Beer[] = [];
  for (const row of dataRows) {
    const name = cell(row, columns.name);
    const brewery = cell(row, columns.brewery);
    if (!name || !brewery) continue;

    const { name: cleanName, degreePlato } = extractTrailingDegree(name);
    const style = cell(row, columns.style);
    beers.push({
      name: cleanName,
      brewery,
      style: formatStyle(style || inferStyleFromDegree(degreePlato)),
      abv: null,
      degreePlato,
      source,
      order: beers.length + 1,
      pricing: null,
    });
  }
  return beers;
}

function findColumns(header: string[]): ColumnMap | null {
  const cells = header.map((value) => value.trim().toLocaleLowerCase("cs-CZ"));
  const find = (predicate: (value: string) => boolean) => cells.findIndex(predicate);

  let name = find((value) => value.includes("název") || value.includes("name"));
  // "pivovar" contains "pivo" as a substring -- don't mistake the brewery
  // column for the name column when falling back to the "pivo" keyword.
  if (name === -1) name = find((value) => value.includes("pivo") && !value.includes("pivovar"));
  const style = find((value) => value.includes("styl"));
  const brewery = find((value) => value.includes("pivovar"));
  if (name === -1 || style === -1 || brewery === -1) return null;
  return { name, style, brewery };
}

function cell(row: string[], index: number): string {
  return (row[index] ?? "").trim();
}

function extractTrailingDegree(name: string): { name: string; degreePlato: number | null } {
  const match = name.match(TRAILING_DEGREE);
  if (!match) return { name, degreePlato: null };

  const value = Number.parseFloat(match[2].replace(",", "."));
  if (!Number.isFinite(value) || value < 0 || value > 20) {
    return { name, degreePlato: null };
  }

  const stripped = name.slice(0, match.index).trim();
  if (!stripped) return { name, degreePlato: null };
  return { name: stripped, degreePlato: value };
}
