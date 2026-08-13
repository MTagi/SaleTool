import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { DEFAULT_SENIOR_LEVELS, PROVIDERS, SENIORITY_LEVELS } from "../constants";

const initialFields = {
  industries: "",
  keywords: "",
  locations: "",
  company_size_min: "",
  company_size_max: "",
  target_titles: "",
  max_companies: "20",
  max_contacts_per_company: "5",
  provider: "mock",
  apollo_api_key: "",
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [fields, setFields] = useState(initialFields);
  const [seniority, setSeniority] = useState(new Set(DEFAULT_SENIOR_LEVELS));
  const [companiesCsv, setCompaniesCsv] = useState(null);
  const [contactsCsv, setContactsCsv] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function update(name, value) {
    setFields((f) => ({ ...f, [name]: value }));
  }

  function toggleSeniority(level) {
    setSeniority((prev) => {
      const next = new Set(prev);
      if (next.has(level)) next.delete(level);
      else next.add(level);
      return next;
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const formData = new FormData();
      Object.entries(fields).forEach(([key, value]) => formData.append(key, value));
      seniority.forEach((level) => formData.append("seniority_levels", level));
      if (fields.provider === "csv_import") {
        if (!companiesCsv) throw new Error("Provider 'csv_import' requires a companies CSV file.");
        formData.append("companies_csv", companiesCsv);
        if (contactsCsv) formData.append("contacts_csv", contactsCsv);
      }

      const data = await api.search(formData);
      navigate("/results", { state: data });
    } catch (err) {
      setError(err.message || "Search failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="container">
      <h1>Find companies &amp; senior contacts</h1>
      {error && <p className="error">{error}</p>}

      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Company criteria</legend>
          <label>
            Industries (comma-separated)
            <input
              type="text"
              placeholder="Software, Fintech"
              value={fields.industries}
              onChange={(e) => update("industries", e.target.value)}
            />
          </label>
          <label>
            Keywords
            <input
              type="text"
              placeholder="payments, lending"
              value={fields.keywords}
              onChange={(e) => update("keywords", e.target.value)}
            />
          </label>
          <label>
            Locations
            <input
              type="text"
              placeholder="Vietnam, Singapore"
              value={fields.locations}
              onChange={(e) => update("locations", e.target.value)}
            />
          </label>
          <div className="row">
            <label>
              Minimum company size (employees)
              <input
                type="number"
                min="0"
                value={fields.company_size_min}
                onChange={(e) => update("company_size_min", e.target.value)}
              />
            </label>
            <label>
              Maximum company size (employees)
              <input
                type="number"
                min="0"
                value={fields.company_size_max}
                onChange={(e) => update("company_size_max", e.target.value)}
              />
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Contacts to find</legend>
          <label>
            Specific job titles (comma-separated)
            <input
              type="text"
              placeholder="CEO, Head of Sales"
              value={fields.target_titles}
              onChange={(e) => update("target_titles", e.target.value)}
            />
          </label>
          <span className="field-label">Seniority levels</span>
          <div className="checkbox-grid">
            {SENIORITY_LEVELS.map((level) => (
              <label key={level} className="checkbox">
                <input
                  type="checkbox"
                  checked={seniority.has(level)}
                  onChange={() => toggleSeniority(level)}
                />
                {level}
              </label>
            ))}
          </div>
          <div className="row">
            <label>
              Max companies
              <input
                type="number"
                min="1"
                value={fields.max_companies}
                onChange={(e) => update("max_companies", e.target.value)}
              />
            </label>
            <label>
              Max contacts per company
              <input
                type="number"
                min="1"
                value={fields.max_contacts_per_company}
                onChange={(e) => update("max_contacts_per_company", e.target.value)}
              />
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Data source</legend>
          <label>
            Provider
            <select value={fields.provider} onChange={(e) => update("provider", e.target.value)}>
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>

          {fields.provider === "apollo" && (
            <div className="provider-fields">
              <label>
                Apollo API key
                <input
                  type="password"
                  autoComplete="off"
                  value={fields.apollo_api_key}
                  onChange={(e) => update("apollo_api_key", e.target.value)}
                />
              </label>
            </div>
          )}

          {fields.provider === "csv_import" && (
            <div className="provider-fields">
              <p className="muted small-note">
                Search/browse Sales Navigator yourself in your browser, export the results to CSV,
                then upload them here.
              </p>
              <label>
                Companies CSV file
                <input type="file" accept=".csv" onChange={(e) => setCompaniesCsv(e.target.files[0] ?? null)} />
              </label>
              <label>
                Contacts CSV file (optional)
                <input type="file" accept=".csv" onChange={(e) => setContactsCsv(e.target.files[0] ?? null)} />
              </label>
            </div>
          )}
        </fieldset>

        <button type="submit" className="primary" disabled={submitting}>
          {submitting ? "Searching…" : "Search"}
        </button>
      </form>
    </main>
  );
}
