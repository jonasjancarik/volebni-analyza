import { useEffect, useRef, useState } from "react";

interface Props {
  /** What the closed control shows */
  button: React.ReactNode;
  /** The choices; call `close` after one that should close the list */
  children: (close: () => void) => React.ReactNode;
  /** Side of the control the list lines up with */
  align?: "left" | "right";
  /** Name of the list of choices, for screen readers */
  label: string;
}

/** A select whose choices can hold more than text: swatches, colour scales, checkboxes. */
export function Dropdown({ button, children, align = "left", label }: Props) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <div className="dropdown" ref={root}>
      <button
        type="button"
        className="select block dropdown-button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {button}
      </button>
      {open && (
        <div className={`dropdown-panel ${align}`} role="listbox" aria-label={label}>
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}
