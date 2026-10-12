import { useQuery } from "@tanstack/react-query";
import type { FeatureCollection } from "geojson";

export interface Election {
  id: string;
  name: string;
  type: "municipal" | "parliamentary";
  year: string;
  hasData: boolean;
  previousId: string | null;
  previousYear: string | null;
}

export interface CouncilRef {
  code: string;
  name: string;
  note: string;
  registered: number;
}

export interface Place {
  code: string;
  name: string;
  registered: number;
  turnout: number;
  previousTurnout: number | null;
  winner: { name: string; share: number } | null;
}

export interface Overview {
  kind: "municipal" | "parliamentary";
  councils: number;
  registered: number;
  turnout: number;
  previousTurnout: number | null;
  places: Place[];
  lists: { name: string; votes: number; share: number }[];
}

export interface CandidateList {
  number: string;
  name: string;
  fullName: string;
  votes: number;
  share: number;
  officialShare: number;
  seats: number;
  previous?: { share: number; seats: number } | null;
}

export interface Precinct {
  id: string;
  number: string;
  area: string;
  registered: number;
  ballots: number;
  turnout: number;
  /** Votes in the order of Council.lists */
  votes: number[];
}

export interface Area {
  code: string;
  name: string;
  precincts: number;
}

export interface Summary {
  registered: number;
  ballots: number;
  turnout: number;
  validVotes: number;
  precincts: number;
}

export interface Council {
  code: string;
  name: string;
  kind: string;
  parent: { code: string; name: string } | null;
  seats: number;
  summary: Summary;
  previousSummary: Summary | null;
  lists: CandidateList[];
  precincts: Precinct[];
  areas: Area[];
  hasCandidates: boolean;
  election: { id: string; name: string; type: string; year: string };
  previous: { id: string; year: string } | null;
  minPrecinctsForFlows: number;
}

export interface Estimate {
  value: number;
  low: number;
  high: number;
}

export interface Flows {
  sources: string[];
  targets: string[];
  /** Percent of each source group (rows) that ended in each target group */
  transitions: number[][];
  transitionsLow: number[][];
  transitionsHigh: number[][];
  /** The same flows as percent of all registered voters */
  electorate: number[][];
  /** Percent of each target group (columns) that came from each source group */
  origin: number[][];
  originLow: number[][];
  originHigh: number[][];
  sourceSize: number[];
  targetSize: number[];
  stayedHome: number;
  newlyVoted: Estimate;
  stoppedVoting: Estimate;
  explained: number;
  precinctTypes: number;
  interval: number;
}

export interface ComparedPrecinct {
  id: string;
  registered: number;
  /** [previous, current] */
  turnout: [number, number];
  /** Shares of Comparison.sameLists */
  previous: number[];
  current: number[];
}

export interface Comparison {
  previousYear: string;
  currentYear: string;
  matched: number;
  skipped: number;
  minPrecincts: number;
  rough: boolean;
  nonVoters: string;
  otherLists: string;
  flows: Flows | null;
  sameLists: string[];
  precincts: ComparedPrecinct[];
}

export interface InputPrecinct {
  id: string;
  registered: number;
  registeredPrevious: number;
  /** Precincts of the same type share one transition matrix */
  type: number;
  /** Percent of registered voters in each of FlowInputs.sources */
  previous: number[];
  /** Percent of registered voters in each of FlowInputs.targets */
  current: number[];
}

/** What the voter-flow estimate is computed from */
export interface FlowInputs {
  sources: string[];
  targets: string[];
  precincts: InputPrecinct[];
}

export interface Candidate {
  name: string;
  list: string;
  position: number;
  age: number;
  occupation: string;
  residence: string;
  votes: number;
  share: number;
  elected: boolean;
}

export interface Boundaries extends FeatureCollection {
  missing: number;
  boundariesYear: string;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    let detail = "";
    try {
      detail = (await response.json()).detail ?? "";
    } catch {
      // The body is not JSON; the status alone has to do
    }
    throw new Error(detail || `Data se nepodařilo načíst (chyba ${response.status}).`);
  }
  return response.json();
}

// Results do not change while the page is open; a failed request is reported at once
const forever = { staleTime: Infinity, retry: false } as const;

export const useElections = () =>
  useQuery({ queryKey: ["elections"], queryFn: () => get<Election[]>("/elections"), ...forever });

export const useOverview = (election: string) =>
  useQuery({
    queryKey: ["overview", election],
    queryFn: () => get<Overview>(`/elections/${election}/overview`),
    ...forever,
  });

export const useCouncils = (election: string | undefined) =>
  useQuery({
    queryKey: ["councils", election],
    queryFn: () => get<CouncilRef[]>(`/elections/${election}/councils`),
    enabled: !!election,
    ...forever,
  });

export const useCouncil = (election: string, code: string) =>
  useQuery({
    queryKey: ["council", election, code],
    queryFn: () => get<Council>(`/elections/${election}/councils/${code}`),
    ...forever,
  });

export const useBoundaries = (election: string, code: string, enabled = true) =>
  useQuery({
    queryKey: ["boundaries", election, code],
    queryFn: () => get<Boundaries>(`/elections/${election}/councils/${code}/boundaries`),
    enabled,
    ...forever,
  });

/** Some addresses of each precinct, as flat [lng, lat, …] lists keyed by precinct id */
export interface Addresses {
  points: Record<string, number[]>;
}

export const useAddresses = (election: string, code: string, enabled = true) =>
  useQuery({
    queryKey: ["addresses", election, code],
    queryFn: () => get<Addresses>(`/elections/${election}/councils/${code}/addresses`),
    enabled,
    ...forever,
  });

export const useComparison = (election: string, code: string, area: string | null, enabled = true) =>
  useQuery({
    queryKey: ["comparison", election, code, area],
    queryFn: () =>
      get<Comparison>(
        `/elections/${election}/councils/${code}/comparison${area ? `?area=${encodeURIComponent(area)}` : ""}`,
      ),
    enabled,
    ...forever,
  });

export const useFlowInputs = (election: string, code: string, area: string | null) =>
  useQuery({
    queryKey: ["flow-inputs", election, code, area],
    queryFn: () =>
      get<FlowInputs>(
        `/elections/${election}/councils/${code}/comparison/inputs${area ? `?area=${encodeURIComponent(area)}` : ""}`,
      ),
    ...forever,
  });

export const useCandidates = (election: string, code: string) =>
  useQuery({
    queryKey: ["candidates", election, code],
    queryFn: () => get<Candidate[]>(`/elections/${election}/councils/${code}/candidates`),
    ...forever,
  });

/** Figures of one written analysis; each analysis has its own shape */
export const useAnalysis = <T>(slug: string) =>
  useQuery({ queryKey: ["analysis", slug], queryFn: () => get<T>(`/analyses/${slug}`), ...forever });
