const NBSP = " ";
const MINUS = "−";

const integer = new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 0 });

function fixed(value: number, decimals: number): string {
  return new Intl.NumberFormat("cs-CZ", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
    .format(Math.abs(value))
    .replace(/^/, value < 0 && Number(value.toFixed(decimals)) !== 0 ? MINUS : "");
}

export const fmtInt = (value: number) => integer.format(value).replace("-", MINUS);

export const fmtNum = (value: number, decimals = 1) => fixed(value, decimals);

export const fmtPct = (value: number, decimals = 1) => `${fixed(value, decimals)}${NBSP}%`;

function sign(value: number, decimals: number): string {
  const rounded = Number(value.toFixed(decimals));
  return rounded > 0 ? "+" : rounded < 0 ? MINUS : "±";
}

/** Difference of two percentages, e.g. "+2,1 p. b." */
export const fmtPp = (value: number, decimals = 1) =>
  `${sign(value, decimals)}${fixed(Math.abs(value), decimals)}${NBSP}p.${NBSP}b.`;

export const fmtSignedInt = (value: number) =>
  `${sign(value, 0)}${integer.format(Math.abs(value))}`;

export const fmtRange = (low: number, high: number) =>
  `${fixed(low, 0)}–${fixed(high, 0)}${NBSP}%`;

/** 918 294 → "918 tis.", 8 283 058 → "8,28 mil." */
export function fmtCompact(value: number): string {
  if (value >= 1e6) return `${fixed(value / 1e6, 2)}${NBSP}mil.`;
  if (value >= 1e4) return `${fixed(value / 1e3, 0)}${NBSP}tis.`;
  return fmtInt(value);
}

/** Lower case without diacritics, for searching */
export const fold = (text: string) =>
  text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();

/**
 * Many lists are registered in capitals ("STAROSTOVÉ A NEZÁVISLÍ"), which is
 * hard to read in a list. Names that are entirely upper case get sentence-like
 * casing; short all-caps words (ANO, ODS, SPD, TOP) are kept as abbreviations.
 */
export function listName(name: string): string {
  const letters = name.replace(/[^\p{L}]/gu, "");
  if (letters.length < 6 || letters !== letters.toUpperCase()) return name;
  return name
    .split(/(\s+|-)/)
    .map((word) => {
      const bare = word.replace(/[^\p{L}]/gu, "");
      if (bare.length <= 3) return word === "A" || word === "S" || word === "PRO" ? word.toLowerCase() : word;
      return word.charAt(0) + word.slice(1).toLowerCase();
    })
    .join("");
}

export const truncate = (text: string, limit: number) =>
  text.length <= limit ? text : `${text.slice(0, limit - 1).trimEnd()}…`;

export function plural(count: number, one: string, few: string, many: string): string {
  if (count === 1) return one;
  if (count >= 2 && count <= 4) return few;
  return many;
}

export function downloadCsv(filename: string, rows: (string | number | null | undefined)[][]) {
  const escape = (cell: string | number | null | undefined) => {
    const text = cell == null ? "" : String(cell);
    return /[";\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  // Semicolons and a BOM open correctly in a Czech Excel
  const csv = "﻿" + rows.map((row) => row.map(escape).join(";")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
