import { Link, useParams, useSearchParams } from "react-router-dom";

interface Props {
  precinct: string;
  /** Shorter wording for places with little room, such as table rows */
  short?: boolean;
}

/**
 * Opens the map of the council being viewed with this precinct picked. In a
 * new tab, so that the table or explanation the reader came from stays open.
 */
export function MapLink({ precinct, short }: Props) {
  const { electionId, code } = useParams();
  const [params] = useSearchParams();
  const query = new URLSearchParams({ okrsek: precinct });
  // The followed list travels along, as it does between tabs
  const focus = params.get("k");
  if (focus) query.set("k", focus);
  return (
    <Link
      className="map-link"
      to={`/${electionId}/${code}/mapa?${query}`}
      target="_blank"
      rel="noreferrer"
      title={`Otevře mapu s okrskem ${precinct} v nové kartě`}
      onClick={(event) => event.stopPropagation()}
    >
      {short ? "Mapa" : "Zobrazit na mapě"}
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
        <path d="M3 1h6v6M9 1L1 9" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </Link>
  );
}
