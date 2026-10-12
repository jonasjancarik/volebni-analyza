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
