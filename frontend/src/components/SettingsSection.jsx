/**
 * A collapsible settings group.
 *
 * The settings page is five long sections in one form; most visits only touch
 * one of them. Collapsing the rest turns a page you have to scan into a list you
 * can read. `<details>` handles the open/close state natively, so this keeps
 * working with keyboard and find-in-page.
 *
 * `summary` is a short status line (e.g. "OpenRouter · key saved") so you can
 * see what a section holds without opening it.
 */
export default function SettingsSection({ title, summary, defaultOpen = false, children }) {
  return (
    <details className="settings-section" open={defaultOpen}>
      <summary>
        <span className="settings-section-title">{title}</span>
        {summary && <span className="settings-section-summary">{summary}</span>}
      </summary>
      <div className="settings-section-body">{children}</div>
    </details>
  );
}
