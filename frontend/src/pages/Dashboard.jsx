import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAppStatus } from "../context/StatusContext";
import { useSelection } from "../hooks/useSelection";

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
 * Provider đang chọn còn thiếu gì so với những gì Settings đang giữ?
 *
 * Xét theo lựa chọn trên dropdown chứ không theo provider đã lưu: chọn một
 * nguồn chưa ai cấu hình thì phải báo ngay, chứ không phải đợi bấm Search rồi
 * ăn lỗi 400.
 *
 * Settings chỉ giữ **một** data source. Nên nếu lựa chọn khác với provider đã
 * lưu thì theo định nghĩa là chưa có key — đó là nhánh áp chót.
 *
 * Trả về mảng để sau này provider cần nhiều thứ hơn một cái key (endpoint URL,
 * account id…) thì chỉ việc thêm phần tử, chỗ hiển thị không phải sửa.
 */
function whatProviderIsMissing(provider, providersNeedingKey, status) {
  if (!status || !provider) return [];                     // chưa biết gì thì chưa kết luận
  if (!providersNeedingKey.includes(provider)) return [];  // provider này không cần key
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
  const seniority = useSelection();
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [autoEnrich, setAutoEnrich] = useState(false);

  // The seniority list is a backend convention (saletool/seniority.py), so it
  // comes from the backend rather than being kept in sync by hand.
  // `setSeniority` tách riêng vì nó ổn định, còn `seniority` đổi sau mỗi lần tick.
  const setSeniority = seniority.replace;
  useEffect(() => {
    api
      .getSearchOptions()
      .then((data) => {
        setLevels(data.seniority_levels);
        setSeniority(data.default_senior_levels);
        setProviders(data.data_providers || []);
        setProvidersNeedingKey(data.data_providers_requiring_key || []);
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
  const ready = Boolean(status) && missingForProvider.length === 0;

  const maxCompanies = Math.max(1, parseInt(fields.max_companies, 10) || 1);
  const maxContacts = Math.max(1, parseInt(fields.max_contacts_per_company, 10) || 1);

  function update(name, value) {
    setFields((f) => ({ ...f, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const formData = new FormData();
      Object.entries(fields).forEach(([key, value]) => formData.append(key, value));
      seniority.toList().forEach((level) => formData.append("seniority_levels", level));

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

      <div className="cols">
        <form id="search-form" onSubmit={handleSubmit}>
          <section className="card2">
            <header><h2>Company criteria</h2></header>
            <div className="cb">
              <div className="g2">
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
                <label>
                  Locations
                  <input
                    type="text"
                    placeholder="Vietnam, Singapore"
                    value={fields.locations}
                    onChange={(e) => update("locations", e.target.value)}
                  />
                </label>
              </div>
              <label>
                Keywords
                <input
                  type="text"
                  placeholder="payments, lending"
                  value={fields.keywords}
                  onChange={(e) => update("keywords", e.target.value)}
                />
              </label>
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
              <p className="muted small-note">Leave both empty for any size.</p>
            </div>
          </section>

          <section className="card2">
            <header><h2>Contacts to find</h2></header>
            <div className="cb">
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

          <section className="card2">
            <header><h2>Data source</h2></header>
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
                    to see how many companies and people match without spending anything.
                  </p>
                </div>
              </div>
            </div>
          </section>
        </form>

        <div className="rail">
          <section className="card2">
            <header><h2>Before you run</h2></header>
            <div className="cb">
              <div className="rail-big">
                {maxCompanies}
                <span>companies max</span>
              </div>
              <p className="muted small-note">
                up to {maxCompanies * maxContacts} contacts
              </p>
              <div className="rail-row">
                <span className="k">Company search</span>
                <span>free</span>
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
                disabled={submitting || !ready}
              >
                {submitting ? "Searching…" : "Find companies"}
              </button>
              {!ready && (
                <p className="muted small-note">
                  Disabled until the data source has a key.
                </p>
              )}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
