import { sankey, sankeyLinkHorizontal, type SankeyLink, type SankeyNode } from "d3-sankey";
import { useMemo, useState } from "react";
import type { Flows } from "../api";
import { fmtPct, fmtRange, listName, truncate } from "../format";
import { useTooltip, useWidth } from "../hooks";

interface Props {
  flows: Flows;
  previousYear: string;
  currentYear: string;
  nonVoters: string;
  colorOf: (group: string) => string;
  showStayedHome: boolean;
  /** Group whose flows stay highlighted, e.g. the one picked in the charts below */
  highlight?: { side: "source" | "target"; name: string } | null;
  onPick: (side: "source" | "target", name: string) => void;
}

interface NodeDatum {
  name: string;
  side: "source" | "target";
  label: string;
}

interface LinkDatum {
  source: number;
  target: number;
  value: number;
  row: number;
  column: number;
}

type Node = SankeyNode<NodeDatum, LinkDatum>;
type Link = SankeyLink<NodeDatum, LinkDatum>;

/** Flows smaller than this share of the electorate would only add noise */
const MIN_FLOW = 0.1;

export function Sankey({ flows, previousYear, currentYear, nonVoters, colorOf, showStayedHome, highlight, onPick }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const tooltip = useTooltip();
  const [hover, setHover] = useState<{ node?: number; link?: number } | null>(null);
  const height = 580;
  const top = 34;

  const graph = useMemo(() => {
    const label = (name: string, side: "source" | "target") => {
      if (name !== nonVoters) return listName(name);
      if (showStayedHome) return side === "source" ? `Nevolili ${previousYear}` : `Nevolili ${currentYear}`;
      // Without those who stayed home twice the node holds only people who changed their mind
      return side === "source" ? `Nevolili ${previousYear}, teď přišli` : `Volili ${previousYear}, teď nepřišli`;
    };
    const nodes: NodeDatum[] = [
      ...flows.sources.map((name) => ({ name, side: "source" as const, label: label(name, "source") })),
      ...flows.targets.map((name) => ({ name, side: "target" as const, label: label(name, "target") })),
    ];
    const links: LinkDatum[] = [];
    flows.electorate.forEach((row, r) =>
      row.forEach((value, c) => {
        const stayedHome = flows.sources[r] === nonVoters && flows.targets[c] === nonVoters;
        if (value < MIN_FLOW || (stayedHome && !showStayedHome)) return;
        links.push({ source: r, target: flows.sources.length + c, value, row: r, column: c });
      }),
    );
    const layout = sankey<NodeDatum, LinkDatum>()
      .nodeWidth(12)
      .nodePadding(13)
      .nodeSort(null)
      .linkSort(null)
      .extent([
        [0, top],
        [Math.max(width, 320), height],
      ]);
    return layout({ nodes: nodes.map((node) => ({ ...node })), links: links.map((link) => ({ ...link })) });
  }, [flows, width, showStayedHome, nonVoters, previousYear, currentYear]);

  const path = sankeyLinkHorizontal<NodeDatum, LinkDatum>();
  const narrow = width < 620;
  const labelLimit = narrow ? 13 : 34;

  const isLit = (link: Link, index: number) => {
    if (hover?.link != null) return hover.link === index;
    if (hover?.node != null) return (link.source as unknown as Node).index === hover.node || (link.target as unknown as Node).index === hover.node;
    if (highlight) {
      const node = (highlight.side === "source" ? link.source : link.target) as unknown as Node;
      return node.side === highlight.side && node.name === highlight.name;
    }
    return true;
  };
  const anyDimmed = hover != null || highlight != null;

  return (
    <div ref={ref}>
      <svg className="chart" width={width} height={height + 4} role="img" aria-label={`Odhad přesunů voličů mezi roky ${previousYear} a ${currentYear}`}>
        <text className="label-strong" x={0} y={14} style={{ fontSize: 14 }}>
          {previousYear}
        </text>
        <text className="label-strong" x={width} y={14} textAnchor="end" style={{ fontSize: 14 }}>
          {currentYear}
        </text>
        <g fill="none">
          {graph.links.map((link, index) => {
            const source = link.source as unknown as Node;
            const target = link.target as unknown as Node;
            const lit = isLit(link, index);
            return (
              <path
                key={`${link.row}-${link.column}`}
                className="sankey-link"
                d={path(link) ?? undefined}
                stroke={colorOf(source.name)}
                strokeWidth={Math.max(1, link.width ?? 1)}
                opacity={anyDimmed ? (lit ? 0.62 : 0.07) : 0.36}
                onMouseMove={(event) => {
                  setHover({ link: index });
                  tooltip.show(
                    event,
                    <>
                      <div className="t-title">
                        {source.label} → {target.label}
                      </div>
                      <div>
                        {fmtPct(flows.transitions[link.row][link.column], 0)} skupiny, odhad{" "}
                        {fmtRange(flows.transitionsLow[link.row][link.column], flows.transitionsHigh[link.row][link.column])}
                      </div>
                      <div className="t-sub">{fmtPct(link.value)} všech zapsaných voličů</div>
                    </>,
                  );
                }}
                onMouseLeave={() => {
                  setHover(null);
                  tooltip.hide();
                }}
              />
            );
          })}
        </g>
        {graph.nodes.map((node) => {
          const x0 = node.x0 ?? 0;
          const x1 = node.x1 ?? 0;
          const y0 = node.y0 ?? 0;
          const y1 = node.y1 ?? 0;
          const left = node.side === "source";
          const sizes = left ? flows.sourceSize : flows.targetSize;
          const names = left ? flows.sources : flows.targets;
          const size = sizes[left ? node.index! : node.index! - flows.sources.length];
          // Lists show their share of those who voted, like the results elsewhere;
          // non-voters can only be a share of everyone on the electoral roll
          const voted = 100 - (sizes[names.indexOf(nonVoters)] ?? 0);
          const isNonVoters = node.name === nonVoters;
          const share = isNonVoters ? `${fmtPct(size, 0)} zapsaných` : fmtPct(voted > 0 ? (size / voted) * 100 : 0, 0);
          const tall = y1 - y0 >= 11;
          const picked = highlight?.side === node.side && highlight.name === node.name;
          return (
            <g
              key={`${node.side}-${node.name}`}
              className="sankey-node"
              onMouseEnter={() => setHover({ node: node.index })}
              onMouseLeave={() => setHover(null)}
              onClick={() => onPick(node.side, node.name)}
            >
              <rect x={x0} y={y0} width={x1 - x0} height={Math.max(1, y1 - y0)} rx={2} fill={colorOf(node.name)} />
              {/* A wider invisible target makes thin nodes easy to hit */}
              <rect x={left ? x0 : x0 - 150} y={y0 - 2} width={162} height={Math.max(14, y1 - y0 + 4)} fill="transparent" />
              {tall && (
                <text
                  className={picked ? "label-strong" : "label"}
                  x={left ? x1 + 8 : x0 - 8}
                  y={(y0 + y1) / 2}
                  dy="0.35em"
                  textAnchor={left ? "start" : "end"}
                  style={{ paintOrder: "stroke", stroke: "var(--surface)", strokeWidth: 3, strokeLinejoin: "round" }}
                >
                  {truncate(node.label, labelLimit)}
                  {!narrow && (!isNonVoters || showStayedHome) ? (
                    <tspan className="muted" style={{ fontWeight: 400 }}>
                      {"  "}
                      {share}
                    </tspan>
                  ) : null}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {tooltip.element}
    </div>
  );
}
