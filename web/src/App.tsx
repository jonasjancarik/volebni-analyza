import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { AnalysesPage, AnalysisPage } from "./analyses";
import { useElections } from "./api";
import { Loading, Problem } from "./components/State";
import { TopBar } from "./components/TopBar";
import { CouncilPage } from "./Council";
import { Home } from "./Home";
import { useIsDark } from "./theme";

function ElectionGate({ children }: { children: (electionId: string) => React.ReactNode }) {
  const { electionId = "" } = useParams();
  const elections = useElections();
  if (elections.isPending) return <Loading />;
  if (elections.error) return <Problem error={elections.error} />;
  const election = elections.data.find((item) => item.id === electionId);
  if (!election || !election.hasData) {
    const fallback = elections.data.find((item) => item.hasData);
    if (!fallback) {
      return (
        <Problem
          title="Zatím tu nejsou žádné výsledky"
          text="Výsledky voleb je potřeba nejdřív stáhnout. Postup je v souboru README."
        />
      );
    }
    return <Navigate to={`/${fallback.id}`} replace />;
  }
  return <>{children(election.id)}</>;
}

export function App() {
  // Remounting on a theme change lets maps and charts pick up the new colours
  const dark = useIsDark();
  return (
    <>
      <Routes>
        <Route path="/:electionId?/*" element={<TopBar />} />
      </Routes>
      <main key={String(dark)}>
        <Routes>
          <Route path="/" element={<ElectionGate>{() => null}</ElectionGate>} />
          <Route path="/analyzy" element={<AnalysesPage />} />
          <Route path="/analyzy/:slug" element={<AnalysisPage />} />
          <Route path="/:electionId" element={<ElectionGate>{(id) => <Home electionId={id} />}</ElectionGate>} />
          <Route
            path="/:electionId/:code/:tab?"
            element={<ElectionGate>{(id) => <CouncilPage electionId={id} />}</ElectionGate>}
          />
        </Routes>
      </main>
      <footer className="page footer">
        <span>Zdroj dat: Český statistický úřad, volby.cz</span>
        <span>Adresu stránky můžete komukoli poslat, otevře se mu stejný pohled.</span>
      </footer>
    </>
  );
}
