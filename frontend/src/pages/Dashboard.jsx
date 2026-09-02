import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAppStatus } from "../context/StatusContext";

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

/** Display names for the data providers the backend offers. */
const DATA_PROVIDER_LABELS = {
  apollo: "Apollo.io",
};

const initialFields = {
  industries: "",
  keywords: "",
  locations: "",
  company_size_min: "",
  company_size_max: "",
  target_titles: "",
  max_companies: "20",
  max_contacts_per_company: "5",
  data_provider: "",
  apollo_reveal_emails: "true",
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { status, refresh: refreshStatus } = useAppStatus();
  const [fields, setFields] = useState(initialFields);
  const [levels, setLevels] = useState([]);
  const [providers, setProviders] = useState([]);
  const [providersNeedingKey, setProvidersNeedingKey] = useState([]);
  const [seniority, setSeniority] = useState(new Set());
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
        setProviders(data.data_providers || []);
        setProvidersNeedingKey(data.data_providers_requiring_key || []);
      })
      .catch((err) => setError(err.message || "Couldn't load the seniority options."));
  }, []);

  // Seed the toggle from the saved default, but let the user override it per search.
  useEffect(() => {
    if (status) setAutoEnrich(Boolean(status.auto_enrich_on_search));
  }, [status]);

  // The data source is configured in Settings; the form only mirrors it. Seeding
  // from status keeps the dropdown honest when a second provider is added later.
  useEffect(() => {
    if (status?.data_source_provider) {
      setFields((f) => (f.data_provider ? f : { ...f, data_provider: status.data_source_provider }));
    }
  }, [status]);

  // What the *selected* provider still needs, judged against what Settings holds.
  // Keyed off the dropdown rather than the saved provider so picking a source
  // nobody has configured yet says so immediately, instead of after submitting.
  //
  // Settings stores one data source, so a selection that differs from the saved
  // provider has no key by definition — that is the second condition below.
  const selectedProvider = fields.data_provider || status?.data_source_provider || "";
  const selectedProviderLabel = DATA_PROVIDER_LABELS[selectedProvider] || selectedProvider;
  const missingForProvider =
    status && selectedProvider && providersNeedingKey.includes(selectedProvider)
      ? selectedProvider === status.data_source_provider && status.data_source_configured
        ? []
        : ["an API key"]
      : [];
  const ready = status ? missingForProvider.length === 0 : false;

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
            <select
              value={fields.data_provider}
              onChange={(e) => update("data_provider", e.target.value)}
            >
              {providers.map((p) => (
                <option key={p} value={p}>
                  {DATA_PROVIDER_LABELS[p] || p}
                </option>
              ))}
            </select>
          </label>

          {missingForProvider.length > 0 ? (
            <p className="field-missing" role="status">
              <strong>{selectedProviderLabel}</strong> is missing{" "}
              {missingForProvider.join(", ")} — <Link to="/settings">add it in Settings</Link>.
            </p>
          ) : (
            <p className="muted small-note">
              The API key for this provider lives in Settings, so it is stored encrypted and
              entered once instead of on every search.
            </p>
          )}

          <label className="checkbox">
            <input
              type="checkbox"
              checked={fields.apollo_reveal_emails === "true"}
              onChange={(e) => update("apollo_reveal_emails", e.target.checked ? "true" : "false")}
            />
            Look up email addresses — <strong>uses Apollo credits</strong>
          </label>
          <p className="muted small-note">
            Apollo's search never returns emails; revealing them is a separate paid call. Only
            people Apollo says have an email are looked up. Untick this to see how many companies
            and people match your criteria without spending anything.
          </p>
        </fieldset>

        <button type="submit" className="primary" disabled={submitting || !ready}>
          {submitting ? "Searching…" : "Search"}
        </button>
      </form>
    </main>
  );
}
