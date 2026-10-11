import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { type CouncilRef, useCouncils } from "../api";
import { fmtInt, fold } from "../format";

interface Props {
  electionId: string;
  large?: boolean;
  /** Focus the field with "/" from anywhere on the page */
  shortcut?: boolean;
  autoFocus?: boolean;
  parliamentary?: boolean;
}

interface Indexed extends CouncilRef {
  folded: string;
}

/** Councils whose name starts with the query come first, larger ones before smaller. */
function search(index: Indexed[], query: string, limit = 8): Indexed[] {
  const needle = fold(query.trim());
  if (!needle) return [];
  const starts: Indexed[] = [];
  const wordStarts: Indexed[] = [];
  const contains: Indexed[] = [];
  for (const council of index) {
    const position = council.folded.indexOf(needle);
    if (position === -1) continue;
    if (position === 0) starts.push(council);
    else if (/[\s-]/.test(council.folded[position - 1])) wordStarts.push(council);
    else contains.push(council);
    if (starts.length >= limit) break;
  }
  return [...starts, ...wordStarts, ...contains].slice(0, limit);
}

export function Search({ electionId, large, shortcut, autoFocus, parliamentary }: Props) {
  const councils = useCouncils(electionId);
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  // The API returns councils from the largest, so the first matches are the likely ones
  const index = useMemo<Indexed[]>(
    () => (councils.data ?? []).map((council) => ({ ...council, folded: fold(council.name) })),
    [councils.data],
  );
  const results = useMemo(() => search(index, query), [index, query]);

  useEffect(() => setActive(0), [query]);

  useEffect(() => {
    if (!shortcut) return;
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      const typing = /INPUT|TEXTAREA|SELECT/.test(target.tagName);
      if ((event.key === "/" && !typing) || (event.key === "k" && (event.metaKey || event.ctrlKey))) {
        event.preventDefault();
        input.current?.focus();
        input.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [shortcut]);

  const go = (council: CouncilRef) => {
    setQuery("");
    setOpen(false);
    input.current?.blur();
    navigate(`/${electionId}/${council.code}`);
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((value) => Math.min(value + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((value) => Math.max(value - 1, 0));
    } else if (event.key === "Enter" && results[active]) {
      go(results[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
      input.current?.blur();
    }
  };

  const showResults = open && query.trim().length > 0;
  const placeholder = parliamentary ? "Najít kraj" : "Najít obec, město nebo městskou část";

  return (
    <div className={`search${large ? " large" : ""}`}>
      <label className="search-field">
        <svg width={large ? 20 : 16} height={large ? 20 : 16} viewBox="0 0 16 16" fill="none" aria-hidden>
          <circle cx="7" cy="7" r="4.6" stroke="currentColor" strokeWidth="1.6" />
          <path d="M10.6 10.6L14 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <input
          ref={input}
          value={query}
          autoFocus={autoFocus}
          placeholder={placeholder}
          aria-label={placeholder}
          role="combobox"
          aria-expanded={showResults}
          aria-controls="search-results"
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {shortcut && !query && <span className="kbd">/</span>}
      </label>
      {showResults && (
        <ul className="search-results" id="search-results" role="listbox">
          {results.length === 0 && (
            <li className="search-empty">
              {councils.isPending ? "Načítám seznam…" : `Nic takového jsme nenašli. Zkuste jiný název.`}
            </li>
          )}
          {results.map((council, position) => (
            <li
              key={council.code}
              role="option"
              aria-selected={position === active}
              className="search-result"
              onMouseEnter={() => setActive(position)}
              // mousedown, so that the click lands before the field loses focus
              onMouseDown={(event) => {
                event.preventDefault();
                go(council);
              }}
            >
              <span className="name">{council.name}</span>
              <span className="note">{council.note}</span>
              <span className="size num">{fmtInt(council.registered)} voličů</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
