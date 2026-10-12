import { fmtInt, fmtPct, fmtPp } from "../format";
import { label } from "./blocks";
import { kindColor } from "./centreShared";
import { change, type DistrictAnalysis, KIND_NAMES, localOverCity, type Precinct, winner } from "./districtShared";
import { type MapLayer, PrecinctMap } from "./PrecinctMap";

interface Props {
  data: DistrictAnalysis;
  colorOf: (key: string) => string;
  /** Lists whose share the map offers */
  shares: string[];
  /** Colour of each group of neighbourhoods */
  groupColors: Record<string, string>;
  /** Comparisons only this district has */
  more?: MapLayer<Precinct>[];
}

/** The precincts of a city district coloured by a list's share, by who leads or by how the two ballots differ. */
export default function DistrictMap({ data, colorOf, shares, groupColors, more = [] }: Props) {
  const { years } = data;
  const groupName = new Map(data.groups.map((group) => [group.key, group.name]));

  const shareLayers: MapLayer<Precinct>[] = [
    ...shares.map((key) => ({
      key,
      label: label(key),
      legend: `${label(key)}, % hlasů do zastupitelstva městské části`,
      value: (precinct: Precinct) => precinct.local[key],
    })),
    {
      key: "turnout",
      label: "Účast",
      legend: "Účast, % zapsaných voličů",
      value: (precinct) => precinct.turnout.now,
    },
  ];

  const comparisons: MapLayer<Precinct>[] = [
    {
      key: "winner",
      label: "Vítěz okrsku",
      legend: "Kandidátka s nejvíce hlasy",
      kind: (precinct) => ({ name: label(winner(precinct)), color: colorOf(winner(precinct)) }),
    },
    ...more,
    {
      key: "pirati-change",
      label: `Piráti proti roku ${years.previous}`,
      legend: `Piráti, změna od roku ${years.previous} v bodech`,
      scale: "change",
      value: (precinct) => change(precinct, "pirati"),
    },
    {
      key: "pirati-ballots",
      label: "Piráti na dvou lístcích",
      legend: "Piráti do zastupitelstva městské části proti pražskému; rozdíl v bodech",
      scale: "change",
      value: (precinct) => localOverCity(precinct, "pirati"),
    },
    {
      key: "group",
      label: "Čtvrti",
      legend: "Čtvrti, jak je dělí tabulka níže",
      kind: (precinct) =>
        precinct.group
          ? { name: groupName.get(precinct.group) ?? precinct.group, color: groupColors[precinct.group] }
          : null,
    },
    // One kind of housing everywhere would be a map of a single colour
    ...(data.kinds.length > 1
      ? [
          {
            key: "kind",
            label: "Zástavba",
            legend: "Převažující zástavba",
            kind: (precinct: Precinct) =>
              precinct.kind ? { name: KIND_NAMES[precinct.kind], color: kindColor(precinct.kind) } : null,
          },
        ]
      : []),
  ];

  return (
    <PrecinctMap
      election={data.council.election}
      code={data.council.code}
      rows={data.precincts}
      initial="winner"
      layers={[
        { title: "Podíl hlasů", items: shareLayers },
        { title: "Srovnání", items: comparisons },
      ]}
      tooltip={(precinct) => (
        <>
          <div className="t-sub">
            Okrsek {precinct.id}
            {precinct.part && ` · ${precinct.part}`}
          </div>
          <div className="t-title">
            {label(winner(precinct))} {fmtPct(precinct.local[winner(precinct)] ?? 0)}
          </div>
          <div>
            Piráti {fmtPct(precinct.local.pirati ?? 0)}, proti roku {years.previous} {fmtPp(change(precinct, "pirati"))}
          </div>
          <div className="t-sub">
            {fmtInt(precinct.registered)} zapsaných voličů, účast {fmtPct(precinct.turnout.now ?? 0, 0)}
          </div>
        </>
      )}
    />
  );
}
