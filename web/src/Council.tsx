import { lazy, Suspense, useMemo } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { type Council, useCouncil } from "./api";
import { listColors } from "./colors";
import { Loading, Problem } from "./components/State";
import { listName, truncate } from "./format";
import { useParam } from "./hooks";
import { CandidatesTab } from "./tabs/CandidatesTab";
import { DataTab } from "./tabs/DataTab";
import { FlowsTab } from "./tabs/FlowsTab";
import { OverviewTab } from "./tabs/OverviewTab";
import { PrecinctsTab } from "./tabs/PrecinctsTab";

// The map library is large; it loads only when the map is opened
const MapTab = lazy(() => import("./tabs/MapTab").then((module) => ({ default: module.MapTab })));

export interface TabProps {
  council: Council;
  /** Colour of each list, in the order of council.lists */
  colors: string[];
  colorByName: Map<string, string>;
  /** Index of the list the user follows */
  focus: number;
}

interface TabDef {
  slug: string;
  label: string;
  show: (council: Council) => boolean;
}

const TABS: TabDef[] = [
  { slug: "", label: "Přehled", show: () => true },
  { slug: "mapa", label: "Mapa okrsků", show: (council) => council.precincts.length > 1 },
  { slug: "presuny", label: "Přesuny voličů", show: (council) => !!council.previous },
  { slug: "okrsky", label: "Okrsky", show: (council) => council.precincts.length > 1 },
  { slug: "kandidati", label: "Kandidáti", show: (council) => council.hasCandidates },
  { slug: "data", label: "Data ke stažení", show: () => true },
];

function defaultFocus(council: Council): number {
  const pirates = council.lists.findIndex((list) => /pirát/i.test(list.name));
  return pirates === -1 ? 0 : pirates;
}

export function CouncilPage({ electionId }: { electionId: string }) {
  const { code = "", tab = "" } = useParams();
  const location = useLocation();
  const council = useCouncil(electionId, code);
  const [focusParam, setFocusParam] = useParam("k");

  const data = council.data;
  const colorByName = useMemo(() => listColors((data?.lists ?? []).map((list) => list.name)), [data]);

  if (council.isPending) return <Loading text="Načítám výsledky…" />;
  if (council.error) return <Problem error={council.error} />;
  if (!data) return null;

  const colors = data.lists.map((list) => colorByName.get(list.name)!);
  const fromParam = data.lists.findIndex((list) => list.number === focusParam);
  const focus = fromParam === -1 ? defaultFocus(data) : fromParam;
  const tabs = TABS.filter((item) => item.show(data));
  const active = tabs.find((item) => item.slug === tab) ?? tabs[0];
  const props: TabProps = { council: data, colors, colorByName, focus };
  // Only the followed list travels between tabs; the rest belongs to one tab
  const keep = focusParam ? `?k=${focusParam}` : "";

  return (
    <div className="page">
      <header className="council-head">
        <nav className="crumbs" aria-label="Kde jste">
          <Link to={`/${electionId}`}>{data.election.name}</Link>
          {data.parent && (
            <>
              <span aria-hidden>/</span>
              <Link to={`/${electionId}/${data.parent.code}`}>{data.parent.name}</Link>
            </>
          )}
          <span aria-hidden>/</span>
          <span>{data.kind}</span>
        </nav>
        <div className="council-title">
          <h1>{data.name}</h1>
          {data.lists.length > 1 && (
            <label className="focus-picker">
              <span className="field-label">
                {data.election.type === "parliamentary" ? "Sledovaná strana" : "Sledovaná kandidátka"}
              </span>
              <select
                className="select block"
                value={data.lists[focus].number}
                onChange={(event) => setFocusParam(event.target.value)}
              >
                {data.lists.map((list) => (
                  <option key={list.number} value={list.number}>
                    {truncate(listName(list.name), 44)}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <nav className="tabs" aria-label="Pohledy">
          {tabs.map((item) => (
            <Link
              key={item.slug}
              to={`/${electionId}/${code}${item.slug ? `/${item.slug}` : ""}${keep}`}
              className={`tab${item === active ? " active" : ""}`}
              aria-current={item === active ? "page" : undefined}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <div className="tab-body" key={`${location.pathname}`}>
        {active.slug === "" && <OverviewTab {...props} />}
        {active.slug === "mapa" && (
          <Suspense fallback={<Loading text="Načítám mapu…" />}>
            <MapTab {...props} />
          </Suspense>
        )}
        {active.slug === "presuny" && <FlowsTab {...props} />}
        {active.slug === "okrsky" && <PrecinctsTab {...props} />}
        {active.slug === "kandidati" && <CandidatesTab {...props} />}
        {active.slug === "data" && <DataTab {...props} />}
      </div>
    </div>
  );
}
