import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAppStatus } from "../context/StatusContext";
import { PROVIDERS } from "../constants";

/**
 * Shown until the first search exists.
 *
 * Search itself needs no setup, so this is guidance rather than a blocker —
 * it just means nobody has to discover the LLM key requirement two pages later.
 */
function GettingStarted({ status }) {
  if (!status || status.counts.runs > 0) return null;

  const items = [
    {
      done: status.llm_configured,
      text: "Add an LLM API key",
      why: "needed for matching and messages",
      to: "/settings",
    },
    {
      done: status.counts.active_services > 0,
      text: "List the services you sell",
      why: "matching scores companies against these",
      to: "/catalog",
    },
    {
      done: status.sender_configured,
      text: "Fill in your sender profile",
      why: "messages need a name and company to come from",
      to: "/settings",
    },
  ];

  if (items.every((i) => i.done)) return null;

  return (
    <div className="getting-started">
      <p className="getting-started-title">First time here? Search works right away.</p>
      <p className="muted small">These take a minute each and unlock the later steps:</p>
      <ul>
        {items.map((item) => (
          <li key={item.text} className={item.done ? "done" : ""}>
            <span aria-hidden="true">{item.done ? "✓" : "○"}</span>{" "}
            {item.done ? item.text : <Link to={item.to}>{item.text}</Link>}{" "}
            <span className="muted small">— {item.why}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

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
  apollo_reveal_emails: "true",
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { status, refresh: refreshStatus } = useAppStatus();
  const [fields, setFields] = useState(initialFields);
  const [levels, setLevels] = useState([]);
  const [seniority, setSeniority] = useState(new Set());
  const [companiesCsv, setCompaniesCsv] = useState(null);
  const [contactsCsv, setContactsCsv] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [autoEnrich, setAutoEnrich] = useState(false);

  // The seniority list is a backend convention (saletool/seniority.py), so it
  // comes from the backend rather than being kept in sync by hand.
  useEffect(() => {
    api
      .getSearchOptions()
      .then((data) => {
        setLevels(data.seniority_levels);
        setSeniority(new Set(data.default_senior_levels));
      })
      .catch((err) => setError(err.message || "Couldn't load the seniority options."));
  }, []);

  // Seed the toggle from the saved default, but let the user override it per search.
  useEffect(() => {
    if (status) setAutoEnrich(Boolean(status.auto_enrich_on_search));
  }, [status]);

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

      // Kick off enrichment before navigating so the results page can poll a job
      // that is already running. A failure here must not lose the search results.
      let enrichJobId = null;
      if (autoEnrich && data.companies?.length) {
        try {
          const targets = data.companies.map((r) => ({
            company_name: r.company.name,
            domain: r.company.domain || null,
          }));
          const { job_id } = await api.startEnrich(targets);
          enrichJobId = job_id;
        } catch (err) {
          console.warn("Auto-enrich could not start:", err.message);
        }
      }

      refreshStatus();
      navigate("/results", { state: { ...data, enrichJobId } });
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

      <GettingStarted status={status} />

      <div className="auto-enrich-bar">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={autoEnrich}
            onChange={(e) => setAutoEnrich(e.target.checked)}
          />
          <strong>Auto-enrich</strong> — after the search, read each company's website for contact
          details and leadership
        </label>
        <Link to="/settings" className="small">
          Configure
        </Link>
      </div>

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
            {levels.map((level) => (
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

              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={fields.apollo_reveal_emails === "true"}
                  onChange={(e) =>
                    update("apollo_reveal_emails", e.target.checked ? "true" : "false")
                  }
                />
                Look up email addresses — <strong>uses Apollo credits</strong>
              </label>
              <p className="muted small-note">
                Apollo's search never returns emails; revealing them is a separate paid call. Only
                people Apollo says have an email are looked up. Untick this to see how many
                companies and people match your criteria without spending anything.
              </p>
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
