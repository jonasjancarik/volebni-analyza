import { Link, useParams } from "react-router-dom";
import { useAnalysis } from "../api";
import { Loading, Problem } from "../components/State";
import { Prague2026 } from "./Prague2026";
import { Prague1, type Prague1Analysis } from "./Prague1";
import { Prague5 } from "./Prague5";
import type { Prague5Analysis } from "./prague5Shared";
import type { CentreAnalysis } from "./centreShared";
import { Prague2026Centre } from "./Prague2026Centre";
import { Prague2026Next } from "./Prague2026Next";
import { Prague2026Spolu } from "./Prague2026Spolu";
import type { NextTimeAnalysis, PragueAnalysis, SpoluStanAnalysis } from "./types";

interface AnalysisEntry {
  slug: string;
  /** Election the analysis is about; the home page of that election links to it */
  election: string;
  kicker: string;
  title: string;
  lede: string;
  updated: string;
  /** Draws the article from the figures the API computed for it */
  body: (data: unknown) => React.ReactNode;
}

export const ANALYSES: AnalysisEntry[] = [
  {
    slug: "praha-2026-pirati-praha-sobe",
    election: "kv2026",
    kicker: "Komunální volby 2026 · Praha",
    title: "Piráti a Praha Sobě v pražských volbách",
    lede: "Proč STAN a Spolu získaly v zastupitelstvu většinu a kolik chybělo k tomu, aby potřebovaly třetího partnera.",
    updated: "12. října 2026",
    body: (data) => <Prague2026 data={data as PragueAnalysis} />,
  },
  {
    slug: "praha-2026-volici-spolu-a-stan",
    election: "kv2026",
    kicker: "Komunální volby 2026 · Praha",
    title: "Kde hledat voliče Spolu a STAN",
    lede: "Kteří voliči obou vítězných kandidátek jsou nejméně pevní a ve kterých částech Prahy jich je nejvíc.",
    updated: "12. října 2026",
    body: (data) => <Prague2026Spolu data={data as SpoluStanAnalysis} />,
  },
  {
    slug: "praha-2026-co-by-zmenilo-vysledek",
    election: "kv2026",
    kicker: "Komunální volby 2026 · Praha",
    title: "Co by příště změnilo výsledek",
    lede: "Kolik by přinesla koalice se SEN, vyšší účast a návrat voličů od STAN, každé zvlášť i dohromady.",
    updated: "12. října 2026",
    body: (data) => <Prague2026Next data={data as NextTimeAnalysis} />,
  },
  {
    slug: "praha-2026-centrum-sidliste-predmesti",
    election: "kv2026",
    kicker: "Komunální volby 2026 · Praha",
    title: "Centrum, sídliště a předměstí",
    lede: "Jak se podpora Pirátů a Prahy Sobě mění s dobou cesty do centra a s tím, v čem lidé bydlí.",
    updated: "12. října 2026",
    body: (data) => <Prague2026Centre data={data as CentreAnalysis} />,
  },
  {
    slug: "praha-5-2026-okrsky-a-bloky",
    election: "kv2026",
    kicker: "Komunální volby 2026 · Praha 5",
    title: "Praha 5 po okrscích",
    lede: "Jak se změnilo zastupitelstvo páté městské části, kde Piráti ztráceli a jak titíž voliči hlasovali o radnici a o magistrátu.",
    updated: "12. října 2026",
    body: (data) => <Prague5 data={data as Prague5Analysis} />,
  },
  {
    slug: "praha-1-2026-okrsky",
    election: "kv2026",
    kicker: "Komunální volby 2026 · Praha 1",
    title: "Praha 1 po okrscích",
    lede: "Roztříštěné zastupitelstvo, ve kterém o posledním mandátu rozhodlo třináct voličů, a centrum města, které volí radnici jinak než magistrát.",
    updated: "12. října 2026",
    body: (data) => <Prague1 data={data as Prague1Analysis} />,
  },
];

export function AnalysisCards({ entries }: { entries: AnalysisEntry[] }) {
  return (
    <div className="analysis-grid">
      {entries.map((entry) => (
        <Link key={entry.slug} to={`/analyzy/${entry.slug}`} className="place-card analysis-card">
          <div className="kicker">{entry.kicker}</div>
          <h3>{entry.title}</h3>
          <p>{entry.lede}</p>
          <span className="more-link">Číst analýzu</span>
        </Link>
      ))}
    </div>
  );
}

export function AnalysesPage() {
  return (
    <div className="page article">
      <header className="article-head">
        <h1>Analýzy</h1>
        <p className="lede">Výsledky voleb vyložené v souvislostech, s čísly počítanými ze stejných dat jako zbytek aplikace.</p>
      </header>
      <AnalysisCards entries={ANALYSES} />
    </div>
  );
}

export function AnalysisPage() {
  const { slug = "" } = useParams();
  const entry = ANALYSES.find((item) => item.slug === slug);
  if (!entry) {
    return (
      <div className="page">
        <Problem title="Tuhle analýzu tu nemáme" text="Zkontrolujte adresu, nebo si vyberte ze seznamu analýz." />
      </div>
    );
  }
  return <Article key={entry.slug} entry={entry} />;
}

function Article({ entry }: { entry: AnalysisEntry }) {
  const analysis = useAnalysis<unknown>(entry.slug);
  return (
    <article className="page article">
      <header className="article-head">
        <nav className="crumbs" aria-label="Kde jste">
          <Link to="/analyzy">Analýzy</Link>
          <span aria-hidden>/</span>
          <span>{entry.kicker}</span>
        </nav>
        <h1>{entry.title}</h1>
        <p className="lede">{entry.lede}</p>
        <div className="small muted">Aktualizováno {entry.updated}</div>
      </header>
      {analysis.isPending && <Loading text="Počítám čísla pro analýzu. Poprvé to trvá několik sekund." />}
      {analysis.error && <Problem error={analysis.error} />}
      {analysis.data != null && <div className="article-body">{entry.body(analysis.data)}</div>}
    </article>
  );
}
