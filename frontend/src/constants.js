// Must match saletool/models.py (SENIORITY_LEVELS / DEFAULT_SENIOR_LEVELS)
// on the backend — update both sides if the list of levels changes.
export const SENIORITY_LEVELS = [
  "owner",
  "founder",
  "c_suite",
  "partner",
  "vp",
  "head",
  "director",
  "manager",
  "senior",
  "entry",
  "intern",
];

export const DEFAULT_SENIOR_LEVELS = ["owner", "founder", "c_suite", "partner", "vp", "head", "director"];

export const PROVIDERS = [
  { value: "mock", label: "mock — demo, no API key needed" },
  { value: "apollo", label: "apollo — requires an Apollo.io API key" },
  { value: "csv_import", label: "csv_import — import a CSV you exported yourself (e.g. Sales Navigator)" },
];
