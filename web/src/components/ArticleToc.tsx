import { type RefObject, useEffect, useState } from "react";

interface Heading {
  id: string;
  text: string;
}

// The chapters of an article and its closing notes on method
const HEADINGS = ".article-body h2, .article-body .method-notes > h3";
// A heading counts as reached once it is this close below the top bar
const REACHED = 110;
// Fewer chapters than this need no table of contents
const FEWEST = 3;

/** "Jak těsně to spolu souvisí" → "jak-tesne-to-spolu-souvisi" */
function slug(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

const smooth = () => (window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");

/** The article's chapters beside it on a wide screen, behind a button in the corner on a narrow one.
 * It reads the headings from the rendered article, so every analysis gets one without listing them. */
export function ArticleToc({ root, ready }: { root: RefObject<HTMLElement | null>; ready: boolean }) {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  // Give every heading an address and collect them
  useEffect(() => {
    if (!ready || !root.current) return;
    const used = new Set<string>();
    const found = [...root.current.querySelectorAll<HTMLElement>(HEADINGS)].map((element) => {
      const text = element.textContent?.trim() ?? "";
      let id = element.id || slug(text) || "kapitola";
      for (let index = 2; used.has(id); index++) id = `${slug(text)}-${index}`;
      used.add(id);
      element.id = id;
      return { id, text };
    });
    setHeadings(found);

    // A link to a chapter opens the article there once its figures are in. Maps
    // and charts above it still grow for a moment, so it stays aligned with the
    // chapter until the layout settles or the reader moves on their own.
    const target = decodeURIComponent(window.location.hash.slice(1));
    const element = target && found.some((heading) => heading.id === target) ? document.getElementById(target) : null;
    if (!element) return;
    const article = root.current;
    const started = performance.now();
    let height = -1;
    let changed = started;
    // A timer rather than a ResizeObserver, which stays silent in a background tab
    const follow = window.setInterval(() => {
      const now = performance.now();
      if (article.offsetHeight !== height) {
        height = article.offsetHeight;
        changed = now;
        element.scrollIntoView({ block: "start", behavior: "instant" });
      }
      if (now - changed > 2500 || now - started > 10000) stop();
    }, 100);
    const stop = () => {
      window.clearInterval(follow);
      window.removeEventListener("wheel", stop);
      window.removeEventListener("touchstart", stop);
      window.removeEventListener("keydown", stop);
    };
    window.addEventListener("wheel", stop, { passive: true });
    window.addEventListener("touchstart", stop, { passive: true });
    window.addEventListener("keydown", stop);
    element.scrollIntoView({ block: "start", behavior: "instant" });
    return stop;
  }, [ready, root]);

  // The chapter being read: the last heading above the reading line
  useEffect(() => {
    if (headings.length < FEWEST) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      let current: string | null = null;
      for (const heading of headings) {
        const element = document.getElementById(heading.id);
        if (element && element.getBoundingClientRect().top <= REACHED) current = heading.id;
      }
      setActive(current);
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [headings]);

  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open]);

  if (headings.length < FEWEST) return null;

  const go = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: smooth(), block: "start" });
    history.replaceState(history.state, "", `#${id}`);
    setOpen(false);
  };
  const toTop = () => {
    window.scrollTo({ top: 0, behavior: smooth() });
    history.replaceState(history.state, "", window.location.pathname + window.location.search);
    setOpen(false);
  };
  const current = headings.find((heading) => heading.id === active);
  const position = current ? headings.indexOf(current) + 1 : 0;

  const list = (
    <ol className="toc-list">
      {headings.map((heading) => (
        <li key={heading.id}>
          <a
            href={`#${heading.id}`}
            aria-current={heading.id === active ? "location" : undefined}
            onClick={(event) => {
              event.preventDefault();
              go(heading.id);
            }}
          >
            {heading.text}
          </a>
        </li>
      ))}
    </ol>
  );

  return (
    <>
      <nav className="toc toc-side" aria-label="Obsah článku">
        <div className="toc-title">Obsah</div>
        {list}
        <button className="toc-top text-button" onClick={toTop}>
          ↑ Na začátek
        </button>
      </nav>

      <div className={`toc-float${open ? " open" : ""}`}>
        {open && <div className="toc-scrim" onClick={() => setOpen(false)} aria-hidden />}
        {open && (
          <nav className="toc toc-panel" aria-label="Obsah článku">
            <div className="toc-title">Obsah</div>
            {list}
            <button className="toc-top text-button" onClick={toTop}>
              ↑ Na začátek
            </button>
          </nav>
        )}
        <button className="toc-button" aria-expanded={open} onClick={() => setOpen(!open)}>
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
            <path d="M2 4h12M2 8h12M2 12h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
          <span className="toc-button-text">{current ? current.text : "Obsah"}</span>
          {current && (
            <span className="toc-count">
              {position}/{headings.length}
            </span>
          )}
        </button>
      </div>
    </>
  );
}
