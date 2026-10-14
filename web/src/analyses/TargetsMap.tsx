import { fmtInt, fmtPct } from "../format";
import { type MapLayer, PrecinctMap } from "./PrecinctMap";
import { campPart, seatBand, type TargetDistrict, type TargetPrecinct, type TargetsAnalysis } from "./targetsShared";

const people = (value: number | null) => (value == null ? "bez odhadu" : `asi ${fmtInt(Math.round(value))} lidí`);

/** Prague's precincts coloured by where the Pirates' work on the ground could count. */
export default function TargetsMap({ data }: { data: TargetsAnalysis }) {
  const { years } = data;
  const districtOf = new Map(data.districts.map((district) => [district.code, district]));
  const district = (precinct: TargetPrecinct): TargetDistrict | undefined => districtOf.get(precinct.area);
  // The legend lists kinds in the order of the rows: the closest seats first
  const missing = (precinct: TargetPrecinct) => district(precinct)?.list?.missingVoters ?? Infinity;
  const rows = [...data.precincts].sort((a, b) => missing(a) - missing(b));

  const targets: MapLayer<TargetPrecinct>[] = [
    {
      key: "stayedHome",
      label: "Nepřišli k volbám",
      legend: `Voliči Pirátů do Sněmovny ${years.parliamentary}, kteří letos nepřišli (lidé)`,
      value: (precinct) => precinct.stayedHome,
      describe: (precinct) => (
        <>
          Nepřišlo {people(precinct.stayedHome)}
          <div className="t-sub">Piráti do Sněmovny {fmtPct(precinct.piratiMid ?? 0)}</div>
        </>
      ),
    },
    {
      key: "atStan",
      label: "Odešli ke STAN",
      legend: `Voliči Pirátů z roku ${years.previous}, kteří letos volili STAN (lidé)`,
      value: (precinct) => precinct.atStan,
      describe: (precinct) => (
        <>
          Ke STAN odešlo {people(precinct.atStan)}
          <div className="t-sub">
            Piráti do zastupitelstva hl. m. {years.previous} {fmtPct(precinct.piratiThen ?? 0)}, {years.current}{" "}
            {fmtPct(precinct.pirati ?? 0)}
          </div>
        </>
      ),
    },
    {
      key: "seat",
      label: "Další mandát v městské části",
      legend: "Kolik voličů chybělo k dalšímu mandátu",
      kind: (precinct) => seatBand(district(precinct)?.list ?? null),
      describe: (precinct) => {
        const list = district(precinct)?.list;
        if (!list) return "Piráti tu do zastupitelstva městské části nekandidovali";
        return (
          <>
            Chybělo asi {fmtInt(list.missingVoters)} voličů
            <div className="t-sub">
              {list.name}: {fmtPct(list.share)}, {list.seats} z {list.councilSeats} mandátů
            </div>
          </>
        );
      },
    },
  ];

  const context: MapLayer<TargetPrecinct>[] = [
    {
      key: "camp",
      label: "Díl Pirátů",
      legend: "Kolik procent z hlasů Pirátů a Prahy Sobě dostali Piráti",
      value: (precinct) => campPart(precinct),
      describe: (precinct) => (
        <>
          Piráti mají {fmtPct(campPart(precinct) ?? 0, 0)} z hlasů obou
          <div className="t-sub">
            Piráti {fmtPct(precinct.pirati ?? 0)}, Praha Sobě {fmtPct(precinct.prahaSobe ?? 0)}
          </div>
        </>
      ),
    },
    {
      key: "turnout",
      label: "Účast",
      legend: `Účast v roce ${years.current}, % zapsaných voličů`,
      value: (precinct) => precinct.turnout,
      describe: (precinct) => `Účast ${fmtPct(precinct.turnout)}`,
    },
    {
      key: "piratiMid",
      label: "Piráti do Sněmovny",
      legend: `Piráti ve sněmovních volbách ${years.parliamentary}, % hlasů`,
      value: (precinct) => precinct.piratiMid,
      describe: (precinct) => `Piráti do Sněmovny ${fmtPct(precinct.piratiMid ?? 0)}`,
    },
  ];

  return (
    <PrecinctMap
      election={data.council.election}
      code={data.council.code}
      rows={rows}
      initial="stayedHome"
      layers={[
        { title: "Kde hledat", items: targets },
        { title: "Souvislosti", items: context },
      ]}
      tooltip={(precinct, layer) => (
        <>
          <div className="t-sub">
            Okrsek {precinct.id}
            {district(precinct) && ` · ${district(precinct)!.name}`}
          </div>
          <div className="t-title">{layer.describe?.(precinct)}</div>
          <div className="t-sub">
            {fmtInt(precinct.registered)} zapsaných voličů, účast {fmtPct(precinct.turnout, 0)}
            {precinct.turnoutMid != null && ` (do Sněmovny ${fmtPct(precinct.turnoutMid, 0)})`}
          </div>
        </>
      )}
    />
  );
}
