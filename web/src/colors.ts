/** Categorical slots in their validated order; a ninth list is never a new hue. */
export const SERIES = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
  "var(--series-7)",
  "var(--series-8)",
];
export const REST = "var(--series-rest)";
export const NON_VOTER = "var(--series-nonvoter)";

/** Light → dark, one hue */
export const SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
/** Loss → no change → gain */
export const DIVERGING = ["#a82a2a", "#e34948", "#f2a9a3", "#e9e8e3", "#86b6ef", "#2a78d6", "#184f95"];
export const NO_DATA = "#d8d7d0";

/**
 * Colour of every list, by its rank in the current election. The colour
 * belongs to the list, so it stays the same in every chart and tab.
 * `extra` are names that only appear elsewhere (lists of the previous
 * election); they take the slots that are left.
 */
export function listColors(names: string[], extra: string[] = []): Map<string, string> {
  const colors = new Map<string, string>();
  for (const name of [...names, ...extra]) {
    if (colors.has(name)) continue;
    colors.set(name, colors.size < SERIES.length ? SERIES[colors.size] : REST);
  }
  return colors;
}

/** Resolves a `var(--x)` colour to its current value (maps and canvases need hex). */
export function resolveColor(color: string): string {
  const match = /^var\((--[\w-]+)\)$/.exec(color);
  if (!match) return color;
  return getComputedStyle(document.documentElement).getPropertyValue(match[1]).trim() || "#888";
}

export interface Scale {
  colors: string[];
  /** Upper edges of all bins but the last */
  edges: number[];
  color: (value: number) => string;
}

function niceStep(span: number, bins: number): number {
  const raw = span / bins;
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  const candidates = [1, 2, 2.5, 5, 10].map((m) => m * power);
  return candidates.find((step) => step >= raw) ?? raw;
}

function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return 0;
  const position = (sorted.length - 1) * q;
  const base = Math.floor(position);
  const next = sorted[Math.min(base + 1, sorted.length - 1)];
  return sorted[base] + (next - sorted[base]) * (position - base);
}

function fromEdges(colors: string[], edges: number[]): Scale {
  return {
    colors,
    edges,
    color: (value) => {
      const bin = edges.findIndex((edge) => value < edge);
      return colors[bin === -1 ? colors.length - 1 : bin];
    },
  };
}

/** Equal steps with round edges; the outer bins absorb outliers. */
export function sequentialScale(values: number[]): Scale {
  const sorted = [...values].sort((a, b) => a - b);
  const low = quantile(sorted, 0.03);
  const high = quantile(sorted, 0.97);
  const bins = SEQUENTIAL.length;
  const step = niceStep(Math.max(high - low, 0.5), bins - 2) || 1;
  const start = Math.ceil(low / step) * step;
  const edges = Array.from({ length: bins - 1 }, (_, i) => Number((start + i * step).toFixed(4)));
  return fromEdges(SEQUENTIAL, edges);
}

/** Symmetric around zero, so that equal gains and losses look equally strong. */
export function divergingScale(values: number[]): Scale {
  const sorted = values.map(Math.abs).sort((a, b) => a - b);
  const reach = Math.max(quantile(sorted, 0.95), 0.6);
  const step = niceStep(reach, 3) || 1;
  const half = step / 2;
  const edges = [-2 * step - half, -step - half, -half, half, step + half, 2 * step + half].map((edge) =>
    Number(edge.toFixed(4)),
  );
  return fromEdges(DIVERGING, edges);
}
