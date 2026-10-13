import type { Summary } from "../api";
import { fmtNum, fmtPct } from "../format";
import type { FollowedList, VoterGroup } from "./types";

export type When = "then" | "mid" | "now";

/** Voters of a set of precincts, with where those precincts are and what their people live in */
export type Place = VoterGroup & {
  turnout: Partial<Record<When, number>>;
  /** Minutes to the centre by public transport and kilometres from it, for an average voter */
  minutes: number;
  km: number;
  /** Percent of flats in each kind of building */
  homes: Record<string, number>;
};

export type TimeBand = Place & { from: number; to: number | null };
export type KindGroup = Place & { kind: string };
export type KindAtTime = KindGroup & { from: number; to: number | null };

export interface PrecinctPoint {
  id: string;
  kind: string;
  minutes: number;
  km: number;
  registered: number;
  turnout: number;
  stan: number | null;
  spolu: number | null;
  prahaSobe: number | null;
  ano: number | null;
  pirati: number | null;
  /** The Pirates' share in the parliamentary election */
  piratiMid: number | null;
}

export interface CentreAnalysis {
  council: { election: string; code: string; name: string };
  years: { current: string; previous: string; parliamentary: string };
  summary: Summary;
  lists: FollowedList[];
  city: Place;
  /** Precincts by minutes to the centre, from the nearest */
  times: TimeBand[];
  /** Precincts by the kind of building most of their flats are in */
  kinds: KindGroup[];
  /** The same kinds at a similar travel time, where there are enough precincts */
  kindsByTime: KindAtTime[];
  /** City districts where Praha Sobě's own list for the district council is strong, against the rest */
  localBase: {
    districts: { code: string; name: string; share: number }[];
    strong: VoterGroup;
    rest: VoterGroup;
    /** The bands of travel time; a part with too few precincts is missing */
    times: { from: number; to: number | null; strong: VoterGroup | null; rest: VoterGroup | null }[];
  };
  precincts: PrecinctPoint[];
}

export const KINDS: Record<string, { name: string; color: string }> = {
  older: { name: "Starší bytové domy", color: "#a4573c" },
  panel: { name: "Panelové domy", color: "#62788f" },
  newer: { name: "Novější bytové domy", color: "#b377a6" },
  houses: { name: "Rodinné domy", color: "#7d9a35" },
  mixed: { name: "Smíšená zástavba", color: "#b9b6ab" },
};

export const kindName = (kind: string) => KINDS[kind]?.name ?? kind;
export const kindColor = (kind: string) => KINDS[kind]?.color ?? "#b9b6ab";

/** What the map and the chart of precincts can show */
export interface Metric {
  key: string;
  label: string;
  value: (precinct: PrecinctPoint) => number | null;
  format: (value: number) => string;
}

const both = (precinct: PrecinctPoint) =>
  precinct.prahaSobe != null && precinct.pirati != null ? precinct.prahaSobe + precinct.pirati : null;

export const SHARES: Metric[] = [
  { key: "prahaSobe", label: "Praha Sobě", value: (precinct) => precinct.prahaSobe, format: fmtPct },
  { key: "pirati", label: "Piráti", value: (precinct) => precinct.pirati, format: fmtPct },
  { key: "both", label: "Obě dohromady", value: both, format: fmtPct },
  { key: "stan", label: "STAN", value: (precinct) => precinct.stan, format: fmtPct },
  { key: "spolu", label: "Spolu", value: (precinct) => precinct.spolu, format: fmtPct },
  { key: "ano", label: "ANO", value: (precinct) => precinct.ano, format: fmtPct },
  { key: "turnout", label: "Účast", value: (precinct) => precinct.turnout, format: fmtPct },
];

export const MINUTES: Metric = {
  key: "minutes",
  label: "Doba cesty",
  value: (precinct) => precinct.minutes,
  format: (value) => `${fmtNum(value, 0)} min`,
};

export const bandName = (band: { from: number; to: number | null }) =>
  band.to == null ? `${band.from} a víc` : band.from === 0 ? `do ${band.to}` : `${band.from}–${band.to}`;
