import type { Summary } from "../api";

export interface TargetPrecinct {
  id: string;
  /** Code of the city district */
  area: string;
  /** Kind of building most of its flats are in; null without data on buildings */
  kind: string | null;
  registered: number;
  turnout: number;
  /** Turnout in the parliamentary election */
  turnoutMid: number | null;
  /** The Pirates' parliamentary voters who did not vote this time, as often as anyone else in the precinct */
  stayedHome: number | null;
  /** The Pirates' voters of the previous election who voted STAN, by the estimate for the precinct's type */
  atStan: number | null;
  /** Shares of the vote for the council of the city, now, in the parliamentary election and before */
  pirati: number | null;
  prahaSobe: number | null;
  piratiMid: number | null;
  piratiThen: number | null;
}

/** The list the Pirates ran on for the council of a city district */
export interface PirateList {
  name: string;
  share: number;
  seats: number;
  councilSeats: number;
  missingVotes: number;
  /** Voters it was short of one more seat */
  missingVoters: number;
}

export interface TargetDistrict {
  code: string;
  name: string;
  registered: number;
  stayedHome: number;
  atStan: number;
  /** The Pirates' part of the votes of the Pirates and Praha Sobě, in percent */
  piratiOfCamp: number | null;
  list: PirateList | null;
}

export interface TargetsAnalysis {
  council: { election: string; code: string; name: string };
  years: { current: string; previous: string; parliamentary: string };
  summary: Summary;
  stayedHome: number;
  atStan: number;
  /** The Pirates' parliamentary voters in the city */
  piratiMid: number;
  /** Precincts left out of the count of people who stayed at home: redrawn, or with hardly anyone voting */
  unusual: number;
  /** Types of precincts the voter-flow estimate fits separately */
  precinctTypes: number;
  districts: TargetDistrict[];
  precincts: TargetPrecinct[];
}

/** The Pirates' part of the votes of both lists, in percent */
export function campPart(precinct: TargetPrecinct): number | null {
  const both = (precinct.pirati ?? 0) + (precinct.prahaSobe ?? 0);
  return both > 0 ? ((precinct.pirati ?? 0) / both) * 100 : null;
}

// Darker the closer the next seat was
const SEAT_BANDS: { below: number; name: string; color: string }[] = [
  { below: 100, name: "do 100 voličů", color: "#184f95" },
  { below: 200, name: "100–200 voličů", color: "#3987e5" },
  { below: 400, name: "200–400 voličů", color: "#9ec5f4" },
  { below: Infinity, name: "přes 400 voličů", color: "#cde2fb" },
];
const NO_LIST = { name: "Piráti nekandidovali", color: "#e9e8e3" };

export function seatBand(list: PirateList | null): { name: string; color: string } {
  if (!list) return NO_LIST;
  const band = SEAT_BANDS.find((item) => list.missingVoters < item.below)!;
  return { name: band.name, color: band.color };
}
