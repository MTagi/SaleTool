/**
 * Frontend-only constants.
 *
 * Anything the backend also knows (seniority levels, message channel limits,
 * search providers for enrichment) is fetched from the API instead — a copy
 * here would be a second place to remember to update.
 */
export const PROVIDERS = [
  { value: "mock", label: "mock — demo, no API key needed" },
  { value: "apollo", label: "apollo — requires an Apollo.io API key" },
  { value: "csv_import", label: "csv_import — import a CSV you exported yourself (e.g. Sales Navigator)" },
];
