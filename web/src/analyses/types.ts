import type { Flows, Summary } from "../api";

/** Flows between lists named by short keys, with the sizes of both electorates */
export interface KeyedFlows extends Flows {
  matched: number;
  registered: number;
  previousRegistered: number;
  /** Numbers of precinct types the ranges cover, when the estimate was repeated for each */
  settings?: number[];
}

export interface FollowedList {
  key: string;
  name: string;
  votes: number;
  share: number;
  seats: number;
  voters: number;
  previousShare: number | null;
  previousSeats: number | null;
  previousVoters: number | null;
}

export interface Scenario {
  key: string;
  /** Seats by list key; "joint" stands for a shared list of Pirates and Praha Sobě */
  seats: Record<string, number>;
  stanSpolu: number;
  votes: number | null;
  voters: number | null;
}

export interface District {
  code: string;
  name: string;
  registered: number;
  turnout: number;
  shares: Record<string, number | null>;
  previousShares: Record<string, number | null>;
}

export interface PrecinctFifth {
  precincts: number;
  shares: Record<string, number>;
  previousShares: Record<string, number>;
}

export interface PragueAnalysis {
  council: { election: string; code: string; name: string };
  years: { current: string; previous: string; parliamentary: string };
  summary: Summary;
  previousSummary: Summary;
  lists: FollowedList[];
  /** Percent of votes for lists that did not reach five percent */
  belowThreshold: number;
  seats: number;
  majority: number;
  votesPerBallot: number;
  lastSeat: string;
  nextInLine: { key: string; seat: number; missingVotes: number; missingVoters: number }[];
  scenarios: Scenario[];
  flows: KeyedFlows;
  /** The same estimate with lists down to 2.5 % kept apart */
  flowsSmallLists: KeyedFlows;
  precincts: {
    compared: number;
    fell: Record<string, number>;
    rose: Record<string, number>;
    piratiAhead: { now: number; then: number };
    precincts: { now: number; then: number };
    winners: { now: Record<string, number>; then: Record<string, number> };
    fifths: PrecinctFifth[];
  };
  districts: District[];
  parliamentary: {
    summary: Summary;
    lists: { key: string; name: string; votes: number; share: number }[];
    flows: KeyedFlows;
  };
}

type When = "then" | "mid" | "now";

/** People who voted in a set of precincts in three elections: the previous municipal one, the parliamentary one between and the current one */
export interface VoterGroup {
  precincts: number;
  registered: number;
  voted: Record<When, number>;
  /** By list key; a list that did not run in an election has no number for it */
  voters: Record<string, Partial<Record<When, number>>>;
}

export interface SpoluStanAnalysis {
  council: { election: string; code: string; name: string };
  years: { current: string; previous: string; parliamentary: string };
  summary: Summary;
  previousSummary: Summary;
  lists: FollowedList[];
  seats: number;
  majority: number;
  votesPerBallot: number;
  scenarios: Scenario[];
  flows: KeyedFlows;
  parliamentary: PragueAnalysis["parliamentary"];
  city: VoterGroup;
  /** Precincts in fifths by the share of its parliamentary voters Spolu kept, from the lowest */
  fifths: VoterGroup[];
  districts: (VoterGroup & { code: string; name: string })[];
  /** The city-wide estimate narrowed to each district large enough for one */
  districtFlows: { code: string; name: string; rough: boolean; flows: KeyedFlows }[];
}

/** Seats of STAN and Spolu together for combinations of two changes */
export interface SeatGridData {
  columns: number[];
  /** One row per share of SEN's voters, one cell per column */
  cells: number[][];
}

export interface NextTimeAnalysis {
  council: { election: string; code: string; name: string };
  years: { current: string; previous: string; parliamentary: string };
  summary: Summary;
  lists: FollowedList[];
  seats: number;
  majority: number;
  votesPerBallot: number;
  actual: Scenario;
  /** Pirates and Praha Sobě on one list, with the votes they have */
  joint: Scenario;
  sen: { votes: number; voters: number; strongholds: { name: string; share: number }[] };
  /** Seats by the percent of SEN's voters that follow it to another list; a step for every change */
  transfers: { recipient: string; steps: (Scenario & { share: number })[] }[];
  /** Fewest voters for the first seat STAN and Spolu lose and for the second; null when out of reach */
  levers: { key: string; first: Scenario | null; second: Scenario | null }[];
  combined: {
    shares: number[];
    new: SeatGridData;
    back: SeatGridData;
    remaining: { share: number; new: Scenario | null; back: Scenario | null }[];
  };
  flows: KeyedFlows;
  flowsSmallLists: KeyedFlows;
  parliamentary: PragueAnalysis["parliamentary"];
}
