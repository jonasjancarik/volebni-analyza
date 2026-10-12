import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useSearchParams } from "react-router-dom";

/** Pixel width of an element, so that charts can be drawn at their real size. */
export function useWidth<T extends HTMLElement>(initial = 600) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(initial);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    setWidth(element.clientWidth);
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Turns true once the element has scrolled into view, and stays true. */
export function useSeen<T extends Element>(share = 0.4) {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element || seen) return;
    const observer = new IntersectionObserver(([entry]) => entry.isIntersecting && setSeen(true), {
      threshold: share,
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [seen, share]);
  return [ref, seen] as const;
}

export const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

interface TooltipState {
  x: number;
  y: number;
  content: React.ReactNode;
}

/** A tooltip that follows the pointer and stays inside the window. */
export function useTooltip() {
  const [state, setState] = useState<TooltipState | null>(null);
  const show = useCallback((event: { clientX: number; clientY: number }, content: React.ReactNode) => {
    setState({ x: event.clientX, y: event.clientY, content });
  }, []);
  const hide = useCallback(() => setState(null), []);

  let element: React.ReactNode = null;
  if (state) {
    const right = state.x > window.innerWidth - 320;
    const below = state.y < 120;
    element = createPortal(
      <div
        className="tooltip"
        style={{
          left: right ? undefined : state.x + 14,
          right: right ? window.innerWidth - state.x + 14 : undefined,
          top: below ? state.y + 16 : undefined,
          bottom: below ? undefined : window.innerHeight - state.y + 12,
        }}
      >
        {state.content}
      </div>,
      document.body,
    );
  }
  return { show, hide, element };
}

/** One value kept in the address, so that a copied link opens the same view. */
export function useParam(name: string): [string | null, (value: string | null) => void] {
  const [params, setParams] = useSearchParams();
  const set = useCallback(
    (value: string | null) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          if (value == null || value === "") next.delete(name);
          else next.set(name, value);
          return next;
        },
        { replace: true },
      );
    },
    [name, setParams],
  );
  return [params.get(name), set];
}

/** What describes how a tab looks; the rest of the address belongs to one council */
const VIEW_PARAMS = ["m", "z", "barvy", "odsun", "pohled", "zaklad"];

/**
 * Address of another council that opens it the way the current one is shown:
 * the same tab with the same view. With `sameLists` the picked lists carry
 * over too, which only makes sense where every council has the same lists.
 */
export function useSameView(electionId: string, sameLists = false) {
  const location = useLocation();
  return (code: string) => {
    const tab = location.pathname.split("/").filter(Boolean)[2];
    const current = new URLSearchParams(location.search);
    const query = new URLSearchParams();
    for (const name of sameLists ? ["k", ...VIEW_PARAMS] : VIEW_PARAMS) {
      const value = current.get(name);
      if (value) query.set(name, value);
    }
    const search = query.toString();
    return `/${electionId}/${code}${tab ? `/${tab}` : ""}${search ? `?${search}` : ""}`;
  };
}
