import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useConfig, useElections } from "../api";
import { Search } from "./Search";

export function TopBar() {
  const { electionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const elections = useElections();
  const config = useConfig();
  const available = (elections.data ?? []).filter((election) => election.hasData);
  const current = available.find((election) => election.id === electionId);
  // The landing page has its own, larger search field
  const onHome = location.pathname.split("/").filter(Boolean).length <= 1;

  return (
    <header className="topbar">
      <div className="page topbar-inner">
        <Link to={current ? `/${current.id}` : "/"} className="brand" aria-label="Volební analýza, úvodní stránka">
          <span className="brand-mark" aria-hidden>
            <svg width="14" height="14" viewBox="0 0 14 14">
              <rect x="1" y="8" width="3" height="5" rx="0.8" fill="#fff" />
              <rect x="5.5" y="4.5" width="3" height="8.5" rx="0.8" fill="#fff" />
              <rect x="10" y="1" width="3" height="12" rx="0.8" fill="#3987e5" />
            </svg>
          </span>
          <span className="brand-name">Volební analýza</span>
        </Link>
        <div className="topbar-search">
          {current && !onHome && (
            <Search electionId={current.id} shortcut parliamentary={current.type === "parliamentary"} />
          )}
        </div>
        <div className="topbar-right">
          {config.data?.legacyUrl && (
            <a className="quiet-link" href={config.data.legacyUrl} target="_blank" rel="noreferrer">
              Původní verze
            </a>
          )}
          {current && (
            <select
              className="select"
              aria-label="Volby"
              value={current.id}
              onChange={(event) => navigate(`/${event.target.value}`)}
            >
              {available.map((election) => (
                <option key={election.id} value={election.id}>
                  {election.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
    </header>
  );
}
