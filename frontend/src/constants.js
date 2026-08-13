// Phải khớp với saletool/models.py (SENIORITY_LEVELS / DEFAULT_SENIOR_LEVELS)
// ở backend — cập nhật cả hai bên nếu đổi danh sách cấp bậc.
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
  { value: "mock", label: "mock — demo, không cần API key" },
  { value: "apollo", label: "apollo — cần API key Apollo.io" },
  { value: "csv_import", label: "csv_import — tự export CSV (vd: Sales Navigator)" },
];
