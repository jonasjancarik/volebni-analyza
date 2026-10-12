import type { Summary } from "../api";
import type { FollowedList } from "./types";

type When = "then" | "mid" | "now";
/** Percent of votes by list key; a list that was not on the ballot has no number */
type Shares = Record<string, number | null>;

/**
 * How a set of precincts voted on the five ballots its voters saw: for the
 * council of the district and for the council of the city in two elections, and
 * for Parliament between them.
 */
export interface Area {
  precincts: number;
  registered: number;
  ballots: Record<When, number>;
  turnout: Record<When, number | null>;
  local: Shares;
  previousLocal: Shares;
  city: Shares;
  previousCity: Shares;
  parliamentary: Shares;
}

export interface Precinct extends Area {
  id: string;
  /** Neighbourhood, e.g. Košíře */
  part: string | null;
  /** Key of the group of neighbourhoods the tables show */
  group: string | null;
  /** Kind of building most of its flats are in; null without data on buildings */
  kind: string | null;
}

export interface DistrictAnalysis {
  council: { election: string; code: string; name: string };
  city: { election: string; code: string; name: string };
  years: { current: string; previous: string; parliamentary: string };
  summary: Summary;
  previousSummary: Summary;
  lists: FollowedList[];
  previousLists: { key: string; name: string; share: number; seats: number }[];
  /** Percent of votes for lists that won no seat, now and in the previous election */
  withoutSeats: number;
  previousWithoutSeats: number;
  /** Seats and votes of the groups of lists the article follows */
  blocs: { key: string; seats: Record<"then" | "now", number>; share: Record<"then" | "now", number> }[];
  seats: number;
  majority: number;
  votesPerBallot: number;
  lastSeat: { key: string; seat: number };
  nextInLine: { key: string; seat: number; missingVotes: number; missingVoters: number }[];
  district: Area;
  /** Votes in the district in the parliamentary election */
  parliamentaryVotes: Record<string, number>;
  /** The ballot for the council of the city, in the whole city */
  cityWide: Record<"then" | "now", Record<string, number>>;
  groups: (Area & { key: string; name: string })[];
  kinds: (Area & { kind: string })[];
  /** Numbers of precincts */
  counts: {
    fell: Record<string, number>;
    rose: Record<string, number>;
    compared: number;
    /** Precincts in which each list had the most votes */
    winners: Record<"then" | "now", Record<string, number>>;
    /** Precincts in which a list got less for the council of the district than for that of the city */
    lowerLocally: Record<string, number>;
  };
  /** Turnout and the result, without the precincts left out of turnout */
  turnout: {
    compared: number;
    /** Precincts where turnout rose since the previous election */
    rose: number;
    /** Thirds of precincts from the smallest rise of turnout to the largest */
    byRise: Area[];
    /** Thirds of precincts from the lowest turnout to the highest */
    byLevel: Area[];
    /** Correlation across precincts, from -1 to 1 */
    together: { rise: Record<string, number>; level: Record<string, number>; fallAndPirati: number };
  };
  /** Precincts left out of the turnout of the groups */
  unusual: { id: string; registered: number; turnout: number }[];
  precincts: Precinct[];
}

/** Where a district has few precincts of family houses, they are counted with the mixed ones */
export const KIND_NAMES: Record<string, string> = {
  older: "Starší bytové domy",
  panel: "Panelové domy",
  newer: "Novější bytové domy",
  houses: "Rodinné domy",
  mixed: "Rodinné domy a smíšená zástavba",
};

const sum = (shares: Shares, keys: string[]) => keys.reduce((total, key) => total + (shares[key] ?? 0), 0);

/** Percent of votes of several lists together on the ballot for the council of the district */
export const together = (area: Area, keys: string[], previous = false) =>
  sum(previous ? area.previousLocal : area.local, keys);

export const change = (area: Area, key: string) => (area.local[key] ?? 0) - (area.previousLocal[key] ?? 0);

/** How much better a list did for the council of the district than its counterpart for the council of the city */
export const localOverCity = (area: Area, local: string, city: string = local, previous = false) =>
  previous
    ? (area.previousLocal[local] ?? 0) - (area.previousCity[city] ?? 0)
    : (area.local[local] ?? 0) - (area.city[city] ?? 0);

/** The list with the most votes for the council of the district */
export function winner(area: Area, previous = false): string {
  const shares = previous ? area.previousLocal : area.local;
  return Object.keys(shares).reduce((best, key) => ((shares[key] ?? 0) > (shares[best] ?? 0) ? key : best));
}
