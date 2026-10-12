import type { FlowInputs, Flows } from "../api";
import type { Wording } from "./wording";

export interface StepProps {
  inputs: FlowInputs;
  flows: Flows;
  /** Index of the followed group in inputs.sources and inputs.targets */
  source: number;
  target: number;
  previousYear: string;
  currentYear: string;
  colorOf: (name: string) => string;
  words: Wording;
}

interface Props {
  number: number;
  title: string;
  children: React.ReactNode;
}

export function Step({ number, title, children }: Props) {
  return (
    <section className="card method-step">
      <div className="method-step-head">
        <span className="method-number num" aria-hidden>
          {number}
        </span>
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}
