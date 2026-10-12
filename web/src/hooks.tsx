import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router-dom";

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
