/** Shared display formatting. */

export function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

/** The criteria of a search run as one line: "fintech · Vietnam". */
export function formatCriteria(criteria) {
  const parts = [
    criteria.keywords?.join(", "),
    criteria.industries?.join(", "),
    criteria.locations?.join(", "),
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "(no criteria)";
}

/**
 * A search run as one dropdown line.
 *
 * `countOf` picks which total matters to the caller — Matching ranks companies,
 * Messages writes to contacts.
 */
export function formatRun(run, countOf = "companies") {
  const total = countOf === "contacts" ? run.total_contacts : run.total_companies;
  return `${formatCriteria(run.criteria)} — ${total} ${countOf} — ${formatDate(run.created_at)}`;
}
