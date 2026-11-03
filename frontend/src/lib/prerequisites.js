/**
 * Prerequisites for a step, shared by the banner and submit button.
 *
 * A "check" is `{ ok, label, fix: { to, text } }`. Keep this outside the
 * Prerequisites component so a page can check readiness without importing a
 * component just to call a function.
 */

/** True when all prerequisites pass; used to enable or disable submit. */
export function allMet(checks) {
  return checks.every((check) => check.ok);
}

/** Return unmet prerequisites in the order supplied by the caller. */
export function unmet(checks) {
  return checks.filter((check) => !check.ok);
}
