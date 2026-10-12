import type { Summary } from "../api";
import type { FollowedList } from "./types";

type When = "then" | "mid" | "now";
/** Percent of votes by list key; a list that was not on the ballot has no number */
type Shares = Record<string, number | null>;

/**
 * How a set of precincts voted on the five ballots its voters saw: for the
 * council of Praha 5 and for the council of the city in two elections, and
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

export interface BlocScenario {
  key: string;
  /** Seats by list key; "joint" is a shared list */
  seats: Record<string, number>;
  blocs: Record<string, number>;
  votes: number | null;
  voters: number | null;
}

export interface Prague5Analysis {
  council: { election: string; code: string; name: string };
  city: { election: string; code: string; name: string };
  years: { current: string; previous: string; parliamentary: string };
  summary: Summary;
  previousSummary: Summary;
  lists: FollowedList[];
  previousLists: { key: string; name: string; share: number; seats: number }[];
  /** Percent of votes for lists that won no seat */
  withoutSeats: number;
  blocs: { key: string; seats: Record<"then" | "now", number>; share: Record<"then" | "now", number> }[];
  seats: number;
  majority: number;
  votesPerBallot: number;
  lastSeat: { key: string; seat: number };
  nextInLine: { key: string; seat: number; missingVotes: number; missingVoters: number }[];
  scenarios: BlocScenario[];
  district: Area;
  /** Votes in Praha 5 in the parliamentary election */
  parliamentaryVotes: Record<string, number>;
  /** The ballot for the council of the city, in the whole city */
  cityWide: Record<"then" | "now", Record<string, number>>;
  groups: (Area & { key: string; name: string })[];
  kinds: (Area & { kind: string })[];
  /** Precincts in fifths by the Pirates' share in the previous election, from the weakest */
  fifths: Area[];
  /** Numbers of precincts */
  counts: {
    fell: Record<string, number>;
    rose: Record<string, number>;
    compared: number;
    /** Precincts in which each list had the most votes */
    winners: Record<"then" | "now", Record<string, number>>;
    /** Precincts in which Praha 5 Sobě, the Pirates and SEN had more votes than the other bloc */
    coalitionAhead: Record<"then" | "now", number>;
    /** Precincts in which a list got less for the council of Praha 5 than for that of the city */
    lowerLocally: Record<string, number>;
  };
  /** Precincts left out of the turnout of the groups */
  unusual: { id: string; registered: number; turnout: number }[];
  precincts: Precinct[];
}

/** The two camps of the council, in the order the charts show them */
export const BLOCS = [
  { key: "coalition2022", name: "Praha 5 Sobě, Piráti a SEN", lists: ["praha5Sobe", "pirati", "sen"] },
  { key: "townHall", name: "ODS, TOP 09, STAN a ANO", lists: ["ods", "top", "odsTop", "stan", "ano"] },
];

export const GROUP_COLORS: Record<string, string> = {
  smichov: "#a4573c",
  kosire: "#7d9a35",
  jinonice: "#b377a6",
  barrandov: "#62788f",
};

/** In Praha 5 the few precincts of family houses are counted with the mixed ones */
export const KIND_NAMES: Record<string, string> = {
  older: "Starší bytové domy",
  panel: "Panelové domy",
  newer: "Novější bytové domy",
  houses: "Rodinné domy",
  mixed: "Rodinné domy a smíšená zástavba",
};

const sum = (shares: Shares, keys: string[]) => keys.reduce((total, key) => total + (shares[key] ?? 0), 0);

/** Percent of votes of a bloc on the ballot for the council of Praha 5 */
export const blocShare = (area: Area, bloc: string, previous = false) =>
  sum(previous ? area.previousLocal : area.local, BLOCS.find((item) => item.key === bloc)!.lists);

/** ODS, TOP 09 and KDU-ČSL together, whichever lists they ran on; in 2022 the Greens ran with KDU-ČSL */
export const right = (area: Area, previous = false) =>
  previous ? sum(area.previousLocal, ["odsTop", "kduZeleni"]) : sum(area.local, ["ods", "top"]);

export const change = (area: Area, key: string) => (area.local[key] ?? 0) - (area.previousLocal[key] ?? 0);

/** How much better a list did for the council of Praha 5 than its counterpart for the council of the city */
export const localOverCity = (area: Area, local: string, city: string = local, previous = false) =>
  previous
    ? (area.previousLocal[local] ?? 0) - (area.previousCity[city] ?? 0)
    : (area.local[local] ?? 0) - (area.city[city] ?? 0);

/** The list with the most votes for the council of Praha 5 */
export function winner(area: Area, previous = false): string {
  const shares = previous ? area.previousLocal : area.local;
  return Object.keys(shares).reduce((best, key) => ((shares[key] ?? 0) > (shares[best] ?? 0) ? key : best));
}
