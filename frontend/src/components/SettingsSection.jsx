/**
 * One settings group, as a card.
 *
 * These used to be <details> that collapsed, on the reasoning that most visits
 * only touch one section. The wireframe reverses that: with every section open
 * you can see the whole configuration at once, and the Readiness panel beside
 * them is what stops the page from becoming a scroll hunt. `summary` stays — a
 * short status line ("OpenRouter · key saved") next to the title, so a section
 * still says what it holds without reading its fields.
 */
export default function SettingsSection({ title, summary, children }) {
  return (
    <section className="card2">
      <header>
        <h2>{title}</h2>
        {summary && <span className="hint">{summary}</span>}
      </header>
      <div className="cb">{children}</div>
    </section>
  );
}
