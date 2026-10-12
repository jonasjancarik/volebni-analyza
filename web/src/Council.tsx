import { lazy, Suspense, useMemo } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { type Council, useCouncil } from "./api";
import { listColors } from "./colors";
import { Dropdown } from "./components/Dropdown";
import { Loading, Problem } from "./components/State";
import { listName, plural } from "./format";
import { useParam, useSameView } from "./hooks";
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
  /** The followed list and the lists picked along with it; the map adds their votes up */
  combo: number[];
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
  const sameView = useSameView(electionId);

  const data = council.data;
  const colorByName = useMemo(() => listColors((data?.lists ?? []).map((list) => list.name)), [data]);

  if (council.isPending) return <Loading text="Načítám výsledky…" />;
  if (council.error) return <Problem error={council.error} />;
  if (!data) return null;

  const colors = data.lists.map((list) => colorByName.get(list.name)!);
  // The address holds the numbers of the picked lists, the followed one first
  const picked = [
    ...new Set(
      (focusParam ?? "")
        .split(".")
        .map((number) => data.lists.findIndex((list) => list.number === number))
        .filter((index) => index !== -1),
    ),
  ];
  const combo = picked.length ? picked : [defaultFocus(data)];
  const focus = combo[0];
  const setCombo = (indices: number[]) => setFocusParam(indices.map((index) => data.lists[index].number).join("."));
  const tabs = TABS.filter((item) => item.show(data));
  const active = tabs.find((item) => item.slug === tab) ?? tabs[0];
  // Only the map can show several lists as one
  const several = active.slug === "mapa";
  const parliamentary = data.election.type === "parliamentary";
  const props: TabProps = { council: data, colors, colorByName, focus, combo };
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
              <Link to={sameView(data.parent.code)}>{data.parent.name}</Link>
            </>
          )}
          <span aria-hidden>/</span>
          <span>{data.kind}</span>
        </nav>
        <div className="council-title">
          <h1>{data.name}</h1>
          {data.lists.length > 1 && (
            <div className={`focus-picker${several && combo.length > 1 ? " wide" : ""}`}>
              <span className="field-label">
                {several
                  ? parliamentary
                    ? "Strany na mapě"
                    : "Kandidátky na mapě"
                  : parliamentary
                    ? "Sledovaná strana"
                    : "Sledovaná kandidátka"}
              </span>
              <Dropdown
                align="right"
                label={parliamentary ? "Výběr strany" : "Výběr kandidátky"}
                button={
                  // Several picked lists share the room, each under a shorter name
                  (several ? combo.slice(0, 3) : [focus])
                    .map((index) => (
                      <span className="dropdown-chip" key={index}>
                        <span className="swatch" style={{ background: colors[index] }} />
                        <span className="dropdown-text">{listName(data.lists[index].name)}</span>
                      </span>
                    ))
                    .concat(
                      several && combo.length > 3
                        ? [
                            <span className="dropdown-more" key="more">
                              + {combo.length - 3} {plural(combo.length - 3, "další", "další", "dalších")}
                            </span>,
                          ]
                        : [],
                    )
                }
              >
                {(close) => (
                  <>
                    {several && (
                      <p className="dropdown-hint">
                        Zaškrtněte víc {parliamentary ? "stran" : "kandidátek"} a mapa ukáže jejich hlasy dohromady.
                        Kliknutím na název vyberete jen tu jednu.
                      </p>
                    )}
                    {data.lists.map((list, index) => (
                      <div key={list.number} className="dropdown-option" role="option" aria-selected={combo.includes(index)}>
                        {several && (
                          <input
                            type="checkbox"
                            aria-label={`Přidat na mapu: ${listName(list.name)}`}
                            checked={combo.includes(index)}
                            // The last list left cannot be unticked; the map always shows something
                            disabled={combo.length === 1 && combo[0] === index}
                            onChange={() =>
                              setCombo(combo.includes(index) ? combo.filter((item) => item !== index) : [...combo, index])
                            }
                          />
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            setCombo([index]);
                            close();
                          }}
                        >
                          <span className="swatch" style={{ background: colors[index] }} />
                          <span className="dropdown-text">{listName(list.name)}</span>
                        </button>
                      </div>
                    ))}
                  </>
                )}
              </Dropdown>
            </div>
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
