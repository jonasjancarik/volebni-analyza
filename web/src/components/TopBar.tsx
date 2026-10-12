import { Link, NavLink, useLocation, useNavigate, useParams } from "react-router-dom";
import { useElections } from "../api";
import { setTheme, type ThemeChoice, useThemeChoice } from "../theme";
import { Search } from "./Search";

const THEMES: { value: ThemeChoice; label: string; icon: React.ReactNode }[] = [
  {
    value: "light",
    label: "Světlý vzhled",
    icon: (
      <>
        <circle cx="8" cy="8" r="3" />
        <path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1" />
      </>
    ),
  },
  {
    value: "system",
    label: "Podle systému",
    icon: (
      <>
        <rect x="1.8" y="2.5" width="12.4" height="8.5" rx="1.2" />
        <path d="M5.5 14h5M8 11v3" />
      </>
    ),
  },
  { value: "dark", label: "Tmavý vzhled", icon: <path d="M13.5 9.6A5.8 5.8 0 0 1 6.4 2.5a5.8 5.8 0 1 0 7.1 7.1z" /> },
];

function ThemeSwitch() {
  const choice = useThemeChoice();
  return (
    <div className="theme-switch" role="group" aria-label="Vzhled stránky">
      {THEMES.map((theme) => (
        <button
          key={theme.value}
          type="button"
          aria-pressed={choice === theme.value}
          aria-label={theme.label}
          title={theme.label}
          onClick={() => setTheme(theme.value)}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            {theme.icon}
          </svg>
        </button>
      ))}
    </div>
  );
}

export function TopBar() {
  const { electionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const elections = useElections();
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
          <NavLink to="/analyzy" className="nav-link">
            Analýzy
          </NavLink>
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
          <ThemeSwitch />
          <a
            className="nav-link github-link"
            href="https://github.com/jonasjancarik/volebni-analyza"
            aria-label="Zdrojový kód na GitHubu"
            title="Zdrojový kód na GitHubu"
          >
            <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
            </svg>
          </a>
        </div>
      </div>
    </header>
  );
}
