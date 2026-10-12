import { listName, plural } from "../format";

/** Phrases about groups of voters, where non-voters and merged small lists need their own wording. */
export interface Wording {
  short: (name: string) => string;
  /** "v roce 2022 volili kandidátku X" */
  votedPlural: (name: string, year: string) => string;
  /** The same with the verb matching a count: "volil", "volili", "volilo" */
  voted: (count: number, name: string, year: string) => string;
  /** Colour for small marks; the non-voter grey is too faint for dots */
  mark: (name: string) => string;
}

export function wording(nonVoters: string, otherLists: string, colorOf: (name: string) => string): Wording {
  const phrase = (verb: string, name: string, year: string) => {
    if (name === nonVoters) return `v roce ${year} ne${verb}`;
    if (name === otherLists) return `v roce ${year} ${verb} některou z ostatních kandidátek`;
    return `v roce ${year} ${verb} kandidátku ${listName(name)}`;
  };
  return {
    short: (name) => (name === nonVoters ? "Nevoliči" : listName(name)),
    votedPlural: (name, year) => phrase("volili", name, year),
    voted: (count, name, year) => phrase(plural(count, "volil", "volili", "volilo"), name, year),
    mark: (name) => (name === nonVoters || name === otherLists ? "var(--ink-3)" : colorOf(name)),
  };
}

export const people = (count: number) => plural(count, "člověk", "lidé", "lidí");
