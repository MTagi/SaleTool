import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAppStatus } from "../context/StatusContext";
import { useSelection } from "../hooks/useSelection";

/**
 * Shown until the first search exists.
 *
 * Make required connections visible before the first search.
 */
function GettingStarted({ status }) {
  if (!status || status.counts.runs > 0) return null;

  const items = [
    {
      done: status.data_source_configured,
      text: "Connect Apollo",
      why: "find companies and contacts",
      to: "/settings",
    },
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
      <p className="getting-started-title">Set up your workspace</p>
      <p className="muted small">Connect your data source to start searching. Complete the other steps when you're ready to rank and write.</p>
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

// The backend sends 11 seniority levels as one flat list. Splitting them here is
// a presentation choice: the top group is what "senior contacts" means in practice
// and is preselected, so the row of eleven equal checkboxes stops implying that
// interns and founders are the same kind of choice. Any level the backend adds
// that is not listed here simply won't render — keep this in sync with
// saletool/models.py::SENIORITY_LEVELS.
const SENIORITY_GROUPS = [
  {
    name: "Decision makers",
    levels: ["owner", "founder", "c_suite", "partner", "vp", "head", "director"],
  },
  { name: "Everyone else", levels: ["manager", "senior", "entry", "intern"] },
];

/** Display names for the data providers the backend offers. */
const DATA_PROVIDER_LABELS = {
  apollo: "Apollo.io",
};

/**
 * What is missing for the selected provider compared with the saved Settings?
 *
 * Check the dropdown selection rather than the saved provider: report an
 * unconfigured source immediately instead of waiting for Search to return 400.
 *
 * Settings stores only **one** data source. A selection that differs from the
 * saved provider therefore has no key; that is the penultimate branch.
 *
 * Return an array so providers can add requirements later (endpoint URL, account
 * ID, etc.) without changing the display code.
 */
function whatProviderIsMissing(provider, providersNeedingKey, status) {
  if (!status || !provider) return [];                     // No status yet; cannot decide.
  if (!providersNeedingKey.includes(provider)) return [];  // This provider needs no key.
  if (provider !== status.data_source_provider) return ["an API key"];
  return status.data_source_configured ? [] : ["an API key"];
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
  const [enabledFields, setEnabledFields] = useState(null);
  const seniority = useSelection();
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [autoEnrich, setAutoEnrich] = useState(false);
  const [step, setStep] = useState(0);

  // The seniority list is a backend convention (saletool/seniority.py), so it
  // comes from the backend rather than being kept in sync by hand.
  // `setSeniority` is stable, while `seniority` changes after every selection.
  const setSeniority = seniority.replace;
  useEffect(() => {
    api
      .getSearchOptions()
      .then((data) => {
        setLevels(data.seniority_levels);
        setSeniority(data.default_senior_levels);
        setProviders(data.data_providers || []);
        setProvidersNeedingKey(data.data_providers_requiring_key || []);
        setEnabledFields(data.enabled_search_fields || null);
      })
      .catch((err) => setError(err.message || "Couldn't load the seniority options."));
  }, [setSeniority]);

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

  const selectedProvider = fields.data_provider || status?.data_source_provider || "";
  const selectedProviderLabel = DATA_PROVIDER_LABELS[selectedProvider] || selectedProvider;
  const missingForProvider = whatProviderIsMissing(selectedProvider, providersNeedingKey, status);
  const ready = Boolean(status) && enabledFields !== null && missingForProvider.length === 0;

  const maxCompanies = Math.max(1, parseInt(fields.max_companies, 10) || 1);
  const maxContacts = Math.max(1, parseInt(fields.max_contacts_per_company, 10) || 1);
  const showField = (field) => !enabledFields || enabledFields.includes(field);

  function update(name, value) {
    setFields((f) => ({ ...f, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    const sections = [...e.currentTarget.querySelectorAll("section.card2")];
    for (const [index, section] of sections.entries()) {
      if (step < 2 && index !== step) continue;
      const invalid = [...section.querySelectorAll("input, select")].find(input => !input.checkValidity());
      if (invalid) {
        setStep(index);
        requestAnimationFrame(() => invalid.reportValidity());
        return;
      }
    }
    if (step < 2) { setStep(step + 1); return; }
    if (!ready) return;
    setError(null);
    setSubmitting(true);

    try {
      const formData = new FormData();
      const fieldGroups = {
        industries: "industries",
        keywords: "keywords",
        locations: "locations",
        company_size_min: "company_size",
        company_size_max: "company_size",
        target_titles: "target_titles",
      };
      Object.entries(fields).forEach(([key, value]) => {
        if (key in fieldGroups && (!showField(fieldGroups[key]) || !value.trim())) return;
        formData.append(key, value);
      });
      if (showField("seniority_levels")) {
        formData.append("seniority_filter_present", "true");
        seniority.toList().forEach((level) => formData.append("seniority_levels", level));
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
          const { job_id } = await api.startEnrich(targets, data.run_id);
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
      <div className="page-head">
        <div>
          <p className="eyebrow">Your sales workspace</p>
          <h1>New search</h1>
          <p className="lede">Define your ideal company, find the right people and build a shortlist worth reaching out to.</p>
        </div>
        <Link to="/history" className="button-link">View search history →</Link>
      </div>
      {error && <p className="error">{error}</p>}

      <GettingStarted status={status} />

      <div className="auto-enrich-bar">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={autoEnrich}
            onChange={(e) => setAutoEnrich(e.target.checked)}
          />
          <span><strong>Auto-enrich</strong> — read company websites for contact details and leadership after each search.</span>
        </label>
        <Link to="/settings" className="small">
          Configure
        </Link>
      </div>

      <nav className="search-steps" aria-label="Search steps">
        {["Companies", "Contacts", "Review"].map((label, index) => <button type="button" key={label} aria-current={step === index ? "step" : undefined} onClick={() => setStep(index)}><span>{index + 1}</span>{label}</button>)}
      </nav>
      <div className="cols">
        <form id="search-form" noValidate onSubmit={handleSubmit}>
          <section className="card2" hidden={step !== 0}>
            <header><h2>Company criteria</h2></header>
            <div className="cb">
              <div className="g2">
                {showField("industries") && (
                  <label>
                    Industries (comma-separated)
                    <input
                      type="text"
                      placeholder="Software, Fintech"
                      value={fields.industries}
                      onChange={(e) => update("industries", e.target.value)}
                    />
                    <span className="muted small-note">
                      Matched against the company description, not Apollo&apos;s own taxonomy.
                    </span>
                  </label>
                )}
                {showField("locations") && (
                  <label>
                    Locations
                    <input
                      type="text"
                      placeholder="Vietnam, Singapore"
                      value={fields.locations}
                      onChange={(e) => update("locations", e.target.value)}
                    />
                  </label>
                )}
              </div>
              {showField("keywords") && (
                <label>
                  Keywords
                  <input
                    type="text"
                    placeholder="payments, lending"
                    value={fields.keywords}
                    onChange={(e) => update("keywords", e.target.value)}
                  />
                </label>
              )}
              {showField("company_size") && (
                <div className="g2">
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
              )}
              {showField("company_size") && (
                <p className="muted small-note">Leave both empty for any size.</p>
              )}
              {!["industries", "locations", "keywords", "company_size"].some(showField) && (
                <p className="muted small-note">No company filters selected. <Link to="/settings">Choose fields in Settings</Link>.</p>
              )}
            </div>
          </section>

          <section className="card2" hidden={step !== 1}>
            <header><h2>Contacts to find</h2></header>
            <div className="cb">
              {showField("target_titles") && (
                <label>
                  Specific job titles (comma-separated)
                  <input
                    type="text"
                    placeholder="CEO, Head of Sales"
                    value={fields.target_titles}
                    onChange={(e) => update("target_titles", e.target.value)}
                  />
                  <span className="muted small-note">When an AI model is configured, titles are expanded into equivalent abbreviations and full forms. If unavailable, your original titles are used.</span>
                </label>
              )}

              {showField("seniority_levels") && (
                <>
                  <span className="field-label">Seniority levels</span>
                  {SENIORITY_GROUPS.map((group) => {
                    const inGroup = levels.filter((l) => group.levels.includes(l));
                    if (inGroup.length === 0) return null;
                    return (
                      <div key={group.name}>
                        <div className="pill-group-label">{group.name}</div>
                        <div className="pills">
                          {inGroup.map((level) => (
                            <button
                              key={level}
                              type="button"
                              className="pill"
                              aria-pressed={seniority.has(level)}
                              onClick={() => seniority.toggle(level)}
                            >
                              {level}
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </>
              )}

              {!showField("target_titles") && !showField("seniority_levels") && (
                <p className="muted small-note">No contact filters selected. <Link to="/settings">Choose fields in Settings</Link>.</p>
              )}

              <div className="g2 spaced">
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
                  <span className="muted small-note">
                    Apollo measured 1-2 per company at ~7.8% reply rate; 10 or more drops to ~3.8%.
                  </span>
                </label>
              </div>
            </div>
          </section>

          <section className="card2" hidden={step !== 2}>
            <header><h2>Review data source</h2></header>
            <div className="cb">
              <div className="g2">
                <div>
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
                      The API key lives in Settings, so it is stored encrypted and entered once
                      instead of on every search.
                    </p>
                  )}
                </div>

                <div>
                  <span className="field-label">Options</span>
                  <label className="checkbox spaced-sm">
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
                    A separate paid call, made only for people Apollo says have an email. Untick it
                    to skip the email lookup. Company search may still use Apollo credits.
                  </p>
                </div>
              </div>
            </div>
          </section>
          <div className="wizard-actions">
            {step > 0 && <button type="button" className="secondary" onClick={() => setStep(step - 1)}>Back</button>}
            {step < 2 && <button type="submit" className="primary">Continue &rarr;</button>}
          </div>
        </form>

        <div className="rail">
          <section className="card2">
            <header><h2>Search criteria</h2></header>
            <div className="cb">
              <dl className="search-summary">
                <dt>Industry</dt><dd>{showField("industries") ? fields.industries || "Any industry" : "Not used"}</dd>
                <dt>Location</dt><dd>{showField("locations") ? fields.locations || "Any location" : "Not used"}</dd>
                <dt>Job titles</dt><dd>{showField("target_titles") ? fields.target_titles || "Any title" : "Not used"}</dd>
              </dl>
              <div className="rail-big">
                {maxCompanies}
                <span>companies max</span>
              </div>
              <p className="muted small-note">
                up to {maxCompanies * maxContacts} contacts
              </p>
              <div className="rail-row">
                <span className="k">Company search</span>
                <span>Apollo credits may apply</span>
              </div>
              <div className="rail-row">
                <span className="k">Email lookup</span>
                <span>{fields.apollo_reveal_emails === "true" ? "on — paid" : "off"}</span>
              </div>
              <div className="rail-row">
                <span className="k">Website reading</span>
                <span>{autoEnrich ? "on — after the search" : "off"}</span>
              </div>
              <button
                type="submit"
                form="search-form"
                className="primary"
                disabled={submitting || !ready || step !== 2}
              >
                {submitting ? "Searching…" : "Find companies"}
              </button>
              {!ready && (
                <p className="muted small-note">
                  {enabledFields === null
                    ? "Waiting for search options."
                    : "Disabled until the data source has a key."}
                </p>
              )}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
