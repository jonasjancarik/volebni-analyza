import { fmtInt, fmtPct, fmtPp } from "../format";
import { label } from "./blocks";
import { kindColor } from "./centreShared";
import { type MapLayer, PrecinctMap } from "./PrecinctMap";
import {
  blocShare,
  change,
  GROUP_COLORS,
  KIND_NAMES,
  localOverCity,
  type Prague5Analysis,
  type Precinct,
  winner,
} from "./prague5Shared";

const SHARES = ["praha5Sobe", "ods", "stan", "sen", "ano", "pirati"];

interface Props {
  data: Prague5Analysis;
  colorOf: (key: string) => string;
}

/** The precincts of Praha 5 coloured by a list's share, by who leads or by how the two ballots differ. */
export default function Prague5Map({ data, colorOf }: Props) {
  const { years } = data;
  const groupName = new Map(data.groups.map((group) => [group.key, group.name]));

  const shares: MapLayer<Precinct>[] = [
    ...SHARES.map((key) => ({
      key,
      label: label(key),
      legend: `${label(key)}, % hlasů do zastupitelstva Prahy 5`,
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
    {
      key: "blocs",
      label: "Oba tábory",
      legend: "Praha 5 Sobě, Piráti a SEN proti ODS, TOP 09, STAN a ANO; rozdíl v bodech",
      scale: "change",
      value: (precinct) => blocShare(precinct, "coalition2022") - blocShare(precinct, "townHall"),
    },
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
      legend: "Piráti do zastupitelstva Prahy 5 proti pražskému; rozdíl v bodech",
      scale: "change",
      value: (precinct) => localOverCity(precinct, "pirati"),
    },
    {
      key: "group",
      label: "Čtvrti",
      legend: "Čtvrti, jak je dělí tabulka níže",
      kind: (precinct) =>
        precinct.group
          ? { name: groupName.get(precinct.group) ?? precinct.group, color: GROUP_COLORS[precinct.group] }
          : null,
    },
    ...(data.kinds.length
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
        { title: "Podíl hlasů", items: shares },
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
