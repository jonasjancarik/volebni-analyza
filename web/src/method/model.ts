import type { FlowInputs } from "../api";

/**
 * The voter-flow estimate of src/election_comparison.py, repeated in the
 * browser so that the page explaining the method can show it step by step.
 */

export type Matrix = number[][];

export interface Model {
  /** Share of each source group among registered voters, per precinct (0–1) */
  x: Matrix;
  /** Share of each target group among registered voters, per precinct (0–1) */
  y: Matrix;
  weights: number[];
  sourceVoters: Matrix;
  /** Precincts of every precinct type */
  members: number[][];
  typeOf: number[];
}

export interface Snapshot {
  iteration: number;
  /** One transition matrix per precinct type */
  matrices: Matrix[];
  /** The city-wide matrix */
  matrix: Matrix;
  /** Percent of the differences between precincts that the matrices reproduce */
  explained: number;
}

export function buildModel(inputs: FlowInputs): Model {
  const precincts = inputs.precincts;
  const x = precincts.map((precinct) => precinct.previous.map((value) => value / 100));
  const y = precincts.map((precinct) => precinct.current.map((value) => value / 100));
  const types = Math.max(...precincts.map((precinct) => precinct.type)) + 1;
  const members: number[][] = Array.from({ length: types }, () => []);
  precincts.forEach((precinct, index) => members[precinct.type].push(index));
  return {
    x,
    y,
    weights: precincts.map((precinct) => precinct.registered),
    sourceVoters: precincts.map((precinct, index) => x[index].map((share) => share * precinct.registeredPrevious)),
    members,
    typeOf: precincts.map((precinct) => precinct.type),
  };
}

/** The closest row that is a valid split: nothing below zero, adding up to one. */
function projectToSimplex(row: number[]): number[] {
  const sorted = [...row].sort((a, b) => b - a);
  let cumulative = 0;
  let theta = 0;
  for (let i = 0; i < sorted.length; i++) {
    cumulative += sorted[i];
    const candidate = (cumulative - 1) / (i + 1);
    if (sorted[i] - candidate > 0) theta = candidate;
  }
  return row.map((value) => Math.max(value - theta, 0));
}

function largestEigenvalue(gram: Matrix): number {
  let vector = gram.map(() => 1);
  let value = 0;
  for (let round = 0; round < 200; round++) {
    const next = gram.map((row) => row.reduce((sum, cell, i) => sum + cell * vector[i], 0));
    value = Math.sqrt(next.reduce((sum, cell) => sum + cell * cell, 0));
    if (value === 0) return 0;
    vector = next.map((cell) => cell / value);
  }
  return value;
}

/** One precinct type's fit, advanced one step at a time. */
function createFit(model: Model, precincts: number[], start?: Matrix) {
  const sources = model.x[0].length;
  const targets = model.y[0].length;
  const total = precincts.reduce((sum, index) => sum + model.weights[index], 0);
  const gram: Matrix = Array.from({ length: sources }, () => new Array(sources).fill(0));
  const cross: Matrix = Array.from({ length: sources }, () => new Array(targets).fill(0));
  for (const index of precincts) {
    const weight = model.weights[index] / total;
    const xi = model.x[index];
    const yi = model.y[index];
    for (let r = 0; r < sources; r++) {
      const scaled = xi[r] * weight;
      for (let q = 0; q < sources; q++) gram[r][q] += scaled * xi[q];
      for (let c = 0; c < targets; c++) cross[r][c] += scaled * yi[c];
    }
  }
  // Slightly below 1/λ, because the eigenvalue is found only approximately
  const step = 1 / Math.max(largestEigenvalue(gram) * 1.001, 1e-12);

  let estimate: Matrix = start
    ? start.map((row) => [...row])
    : Array.from({ length: sources }, () => new Array(targets).fill(1 / targets));
  let momentum = estimate.map((row) => [...row]);
  let t = 1;

  return {
    get estimate() {
      return estimate;
    },
    /** Returns the largest change of any cell */
    step(): number {
      const updated = momentum.map((_, r) => {
        const moved = new Array<number>(targets);
        for (let c = 0; c < targets; c++) {
          let gradient = -cross[r][c];
          for (let q = 0; q < sources; q++) gradient += gram[r][q] * momentum[q][c];
          moved[c] = momentum[r][c] - step * gradient;
        }
        return projectToSimplex(moved);
      });
      let uphill = 0;
      let change = 0;
      for (let r = 0; r < sources; r++) {
        for (let c = 0; c < targets; c++) {
          const delta = updated[r][c] - estimate[r][c];
          uphill += (momentum[r][c] - updated[r][c]) * delta;
          change = Math.max(change, Math.abs(delta));
        }
      }
      if (uphill > 0) t = 1;
      const tNext = (1 + Math.sqrt(1 + 4 * t * t)) / 2;
      const pull = (t - 1) / tNext;
      momentum = updated.map((row, r) => row.map((value, c) => value + pull * (value - estimate[r][c])));
      estimate = updated;
      t = tNext;
      return change;
    },
  };
}

/** City-wide matrix: every type counts by how many voters of the source group live in it. */
function aggregate(model: Model, matrices: Matrix[], members: number[][]): Matrix {
  const sources = model.x[0].length;
  const targets = model.y[0].length;
  const flows: Matrix = Array.from({ length: sources }, () => new Array(targets).fill(0));
  const totals = new Array(sources).fill(0);
  members.forEach((precincts, type) => {
    for (let r = 0; r < sources; r++) {
      let voters = 0;
      for (const index of precincts) voters += model.sourceVoters[index][r];
      totals[r] += voters;
      for (let c = 0; c < targets; c++) flows[r][c] += voters * matrices[type][r][c];
    }
  });
  return flows.map((row, r) => row.map((value) => value / (totals[r] || 1)));
}

/** What the matrices predict for one target group in every precinct (0–1). */
export function predictColumn(model: Model, matrices: Matrix[], column: number): number[] {
  return model.x.map((shares, index) => {
    const matrix = matrices[model.typeOf[index]];
    let predicted = 0;
    for (let r = 0; r < shares.length; r++) predicted += shares[r] * matrix[r][column];
    return predicted;
  });
}

function explained(model: Model, matrices: Matrix[]): number {
  const targets = model.y[0].length;
  const total = model.weights.reduce((sum, weight) => sum + weight, 0);
  const mean = new Array(targets).fill(0);
  model.y.forEach((row, index) => row.forEach((value, c) => (mean[c] += (value * model.weights[index]) / total)));
  let residual = 0;
  let spread = 0;
  for (let c = 0; c < targets; c++) {
    const predicted = predictColumn(model, matrices, c);
    model.y.forEach((row, index) => {
      residual += (row[c] - predicted[index]) ** 2 * model.weights[index];
      spread += (row[c] - mean[c]) ** 2 * model.weights[index];
    });
  }
  return spread > 0 ? (1 - residual / spread) * 100 : 0;
}

/**
 * The search for the matrices from an even split to the result. Snapshots
 * thin out as the search slows down, so that they play back at an even pace.
 */
export function trajectory(model: Model, maxIterations = 20000): Snapshot[] {
  const fits = model.members.map((precincts) => createFit(model, precincts));
  const snapshots: Snapshot[] = [];
  const record = (iteration: number) => {
    const matrices = fits.map((fit) => fit.estimate);
    snapshots.push({
      iteration,
      matrices,
      matrix: aggregate(model, matrices, model.members),
      explained: explained(model, matrices),
    });
  };
  record(0);
  let next = 1;
  for (let iteration = 1; iteration <= maxIterations; iteration++) {
    const change = Math.max(...fits.map((fit) => fit.step()));
    const done = change < 1e-9 || iteration === maxIterations;
    if (iteration >= next || done) {
      record(iteration);
      next = Math.max(iteration + 1, Math.round(iteration * 1.13));
    }
    if (done) break;
  }
  return snapshots;
}

/** A small seeded generator, so that the same page always draws the same precincts. */
export function randomSource(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * The city-wide matrix estimated from precincts drawn at random with
 * repetition, within every precinct type so that none of them runs empty.
 */
export function resampledMatrix(model: Model, startingFrom: Matrix[], random: () => number): Matrix {
  const picked = model.members.map((precincts) =>
    precincts.map(() => precincts[Math.floor(random() * precincts.length)]),
  );
  const matrices = picked.map((precincts, type) => {
    const fit = createFit(model, precincts, startingFrom[type]);
    for (let iteration = 0; iteration < 600; iteration++) {
      if (fit.step() < 1e-6) break;
    }
    return fit.estimate;
  });
  return aggregate(model, matrices, picked);
}
