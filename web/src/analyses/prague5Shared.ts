import { type Area, type DistrictAnalysis, together } from "./districtShared";

export * from "./districtShared";

export interface BlocScenario {
  key: string;
  /** Seats by list key; "joint" is a shared list */
  seats: Record<string, number>;
  blocs: Record<string, number>;
  votes: number | null;
  voters: number | null;
}

export interface Prague5Analysis extends DistrictAnalysis {
  scenarios: BlocScenario[];
  /** Precincts in fifths by the Pirates' share in the previous election, from the weakest */
  fifths: Area[];
  counts: DistrictAnalysis["counts"] & {
    /** Precincts in which Praha 5 Sobě, the Pirates and SEN had more votes than the other bloc */
    coalitionAhead: Record<"then" | "now", number>;
  };
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

/** Percent of votes of a bloc on the ballot for the council of Praha 5 */
export const blocShare = (area: Area, bloc: string, previous = false) =>
  together(area, BLOCS.find((item) => item.key === bloc)!.lists, previous);

/** ODS, TOP 09 and KDU-ČSL together, whichever lists they ran on; in 2022 the Greens ran with KDU-ČSL */
export const right = (area: Area, previous = false) =>
  previous ? together(area, ["odsTop", "kduZeleni"], true) : together(area, ["ods", "top"]);
