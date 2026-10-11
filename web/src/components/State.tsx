export function Loading({ text = "Načítám…" }: { text?: string }) {
  return (
    <div className="state" role="status">
      <div className="spinner" />
      {text}
    </div>
  );
}

export function Problem({ error, title, text }: { error?: Error | null; title?: string; text?: string }) {
  return (
    <div className="state" role="alert">
      <h2>{title ?? "Tohle se nepovedlo načíst"}</h2>
      <p>{text ?? error?.message ?? "Zkuste stránku načíst znovu."}</p>
    </div>
  );
}
