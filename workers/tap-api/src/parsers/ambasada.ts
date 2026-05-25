import type { Beer } from "../schema";
import { ambasadaPricing } from "../pricing";
import { formatStyle } from "../style";

interface PendingRow {
  name?: string;
  priceRaw?: string;
  description?: string;
}

type CellHandler = {
  element: (el: Element) => void;
  text: (t: Text) => void;
};

function captureCell(
  isSkipped: () => boolean,
  onClose: (text: string) => void,
): CellHandler {
  let buffer = "";
  let active = false;
  return {
    element(el) {
      if (isSkipped()) return;
      buffer = "";
      active = true;
      el.onEndTag(() => {
        onClose(buffer.trim());
        active = false;
      });
    },
    text(t) {
      if (active) buffer += t.text;
    },
  };
}

export async function parseAmbasadaHtml(response: Response): Promise<Beer[]> {
  const beers: Beer[] = [];
  let tableEnded = false;
  let pending: PendingRow = {};
  const isSkipped = () => tableEnded;

  const rewriter = new HTMLRewriter()
    .on("table.listek_tab td.listek_tab_nadpis", {
      element() {
        tableEnded = true;
      },
    })
    .on(
      "table.listek_tab td.listek_tab_nazev",
      captureCell(isSkipped, (text) => {
        pending.name = text;
      }),
    )
    .on(
      "table.listek_tab td.listek_tab_cena",
      captureCell(isSkipped, (text) => {
        pending.priceRaw = text;
      }),
    )
    .on(
      "table.listek_tab td.listek_tab_popis",
      captureCell(isSkipped, (text) => {
        if (!pending.name) return;
        pending.description = text;
        const beer = buildBeer(pending, beers.length + 1);
        if (beer) beers.push(beer);
        pending = {};
      }),
    );

  await rewriter.transform(response).text();
  return beers;
}

function buildBeer(row: PendingRow, order: number): Beer | null {
  const rawName = row.name ?? "";
  if (!rawName) return null;

  const degreeMatch = rawName.match(/^(\d+)°\s*/);
  const degreePlato = degreeMatch ? Number.parseInt(degreeMatch[1], 10) : null;
  const name = degreeMatch ? rawName.slice(degreeMatch[0].length).trim() : rawName;

  const { abv, brewery, style } = parseDescription(row.description ?? "");
  const pricing = ambasadaPricing(row.priceRaw ?? null, row.description ?? null);

  return {
    name,
    brewery,
    style: formatStyle(style),
    abv,
    degreePlato,
    source: "ambasada",
    order,
    pricing,
  };
}

const STYLE_KEYWORDS = new Set([
  "stout", "lager", "pilsner", "ipa", "neipa", "dipa", "iipa", "tipa",
  "apa", "nepa", "ale", "porter", "weizen", "wheat", "hefeweizen",
  "saison", "tripel", "dubbel", "quadrupel", "gose", "sour",
  "pale", "india", "imperial", "barleywine",
  "kölsch", "altbier", "helles", "dunkel", "bock", "märzen",
  "rauchbier", "berliner", "lambic", "gueuze",
  "ležák", "světlý", "světlé", "polotmavý", "polotmavé",
  "tmavý", "tmavé", "pšeničné", "pšenice", "výčepní", "kvasnicové",
]);

function startsWithStyleKeyword(part: string): boolean {
  const words = part.toLocaleLowerCase("cs-CZ").split(/\s+/).slice(0, 2);
  return words.some((w) => STYLE_KEYWORDS.has(w));
}

export function parseDescription(raw: string): {
  abv: number | null;
  brewery: string;
  style: string;
} {
  let desc = raw.trim();
  if (!desc) return { abv: null, brewery: "", style: "" };

  let abv: number | null = null;
  const abvMatch = desc.match(/^([\d,.]+)\s*%\s*alc\.\s*/i);
  if (abvMatch) {
    const n = Number.parseFloat(abvMatch[1].replace(",", "."));
    abv = Number.isFinite(n) ? n : null;
    desc = desc.slice(abvMatch[0].length);
  }

  if (desc.startsWith("piv. ")) desc = desc.slice(5);

  const parts = desc.split(",").map((p) => p.trim()).filter((p) => p.length > 0);
  if (parts.length === 0) return { abv, brewery: "", style: "" };

  for (let i = 1; i < parts.length; i++) {
    if (startsWithStyleKeyword(parts[i])) {
      return {
        abv,
        brewery: parts.slice(0, i).join(", "),
        style: parts.slice(i).join(", "),
      };
    }
  }

  const totalLen = desc.length;
  const last = parts[parts.length - 1];

  if (parts.length > 1 && last.length <= 40 && totalLen <= 120) {
    return {
      abv,
      brewery: parts.slice(0, -1).join(", "),
      style: last,
    };
  }
  if (totalLen > 120) {
    return {
      abv,
      brewery: parts.slice(0, 2).join(", "),
      style: "",
    };
  }
  return { abv, brewery: desc, style: "" };
}
