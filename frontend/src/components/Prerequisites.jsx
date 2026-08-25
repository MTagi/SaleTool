import { Link } from "react-router-dom";

/**
 * Missing prerequisites for a step, shown before the form rather than after.
 *
 * `checks` is a list of { ok, label, fix: { to, text } }. Anything not ok is
 * listed with a direct link to the page that fixes it — the point is that the
 * user never has to guess which of the eight pages holds the missing piece.
 *
 * Returns null when everything passes, so callers can drop it in unconditionally.
 */
export default function Prerequisites({ checks }) {
  const missing = checks.filter((c) => !c.ok);
  if (missing.length === 0) return null;

  return (
    <div className="prereq" role="status">
      <p className="prereq-title">
        {missing.length === 1 ? "One thing is missing" : `${missing.length} things are missing`}{" "}
        before you can run this step:
      </p>
      <ul>
        {missing.map((check) => (
          <li key={check.label}>
            {check.label}
            {check.fix && (
              <>
                {" — "}
                <Link to={check.fix.to}>{check.fix.text}</Link>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** True when every check passes; use it to disable the submit button. */
export function allMet(checks) {
  return checks.every((c) => c.ok);
}
