import { useEffect, useState } from "react";
import { api } from "../api/client";

// Sentinel the backend understands as "keep the stored key unchanged".
const MASKED_SECRET = "__SALETOOL_UNCHANGED__";

const SEARCH_PROVIDER_LABELS = {
  none: "None — read the company's own website only (free)",
  searxng: "SearXNG — self-hosted, no API key, unlimited (free)",
  brave: "Brave Search API — paid, ~$5 per 1,000 queries",
  tavily: "Tavily — paid, LLM-optimised results",
  serper: "Serper — cheapest, but scrapes Google SERPs (ToS risk)",
};

const MODEL_SUGGESTIONS = [
  "google/gemini-2.0-flash-001",
  "google/gemini-2.5-flash",
  "meta-llama/llama-3.3-70b-instruct",
  "qwen/qwen-2.5-72b-instruct",
  "openai/gpt-4o-mini",
];

function TestButton({ target, label }) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setState(null);
    try {
      const result = await api.testConnection(target);
      setState(result);
    } catch (err) {
      setState({ ok: false, message: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="test-row">
      <button type="button" className="secondary" onClick={run} disabled={busy}>
        {busy ? "Testing…" : label}
      </button>
      {state && (
        <span className={state.ok ? "test-ok" : "test-fail"}>
          {state.ok ? "✓" : "✕"} {state.message}
          {state.detail ? ` — ${state.detail}` : ""}
        </span>
      )}
    </div>
  );
}

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [options, setOptions] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getSettings()
      .then((data) => {
        setSettings(data.settings);
        setOptions(data.options);
      })
      .catch((err) => setError(err.message || "Couldn't load settings."));
  }, []);

  function updateSection(section, key, value) {
    setSettings((s) => ({ ...s, [section]: { ...s[section], [key]: value } }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSaving(true);

    try {
      // Only send a key when the user actually typed a new one; otherwise tell
      // the backend to keep what it already has.
      const payload = {
        ...settings,
        llm: { ...settings.llm, api_key: settings.llm.api_key_dirty ? settings.llm.api_key : MASKED_SECRET },
        search: {
          ...settings.search,
          api_key: settings.search.api_key_dirty ? settings.search.api_key : MASKED_SECRET,
        },
      };
      delete payload.llm.api_key_dirty;
      delete payload.llm.api_key_set;
      delete payload.search.api_key_dirty;
      delete payload.search.api_key_set;

      const saved = await api.saveSettings(payload);
      setSettings(saved.settings);
      setSuccess("Settings saved.");
    } catch (err) {
      setError(err.message || "Couldn't save settings.");
    } finally {
      setSaving(false);
    }
  }

  if (error && !settings) {
    return (
      <main className="container">
        <h1>Settings</h1>
        <p className="error">{error}</p>
      </main>
    );
  }

  if (!settings) {
    return (
      <main className="container">
        <h1>Settings</h1>
        <p className="muted">Loading…</p>
      </main>
    );
  }

  const searchNeedsKey = (options?.search_providers_requiring_key || []).includes(
    settings.search.provider,
  );

  return (
    <main className="container">
      <h1>Settings</h1>
      <p className="muted">
        Applies to everyone using this instance. API keys are encrypted before they are stored and are
        never sent back to the browser.
      </p>

      {error && <p className="error">{error}</p>}
      {success && <p className="success">{success}</p>}

      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Language model</legend>
          <p className="muted small-note">
            Used to pull out details that plain parsing can't — mainly descriptions and leadership names.
          </p>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings.llm.enabled}
              onChange={(e) => updateSection("llm", "enabled", e.target.checked)}
            />
            Enable LLM extraction
          </label>

          <label>
            Provider
            <select
              value={settings.llm.provider}
              onChange={(e) => updateSection("llm", "provider", e.target.value)}
            >
              {(options?.llm_providers || []).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>

          <label>
            API base URL
            <input
              type="text"
              value={settings.llm.base_url}
              onChange={(e) => updateSection("llm", "base_url", e.target.value)}
            />
          </label>

          <label>
            API key {settings.llm.api_key_set && !settings.llm.api_key_dirty && <em>(saved)</em>}
            <input
              type="password"
              autoComplete="off"
              placeholder={settings.llm.api_key_set ? settings.llm.api_key : "sk-or-v1-…"}
              value={settings.llm.api_key_dirty ? settings.llm.api_key : ""}
              onChange={(e) => {
                setSettings((s) => ({
                  ...s,
                  llm: { ...s.llm, api_key: e.target.value, api_key_dirty: true },
                }));
              }}
            />
          </label>

          <label>
            Model
            <input
              type="text"
              list="model-suggestions"
              value={settings.llm.model}
              onChange={(e) => updateSection("llm", "model", e.target.value)}
            />
          </label>
          <datalist id="model-suggestions">
            {MODEL_SUGGESTIONS.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          <p className="muted small-note">
            Pick a model that supports structured outputs. Extraction from cleaned text is an easy task —
            a small, cheap model is enough.
          </p>

          <div className="row">
            <label>
              Temperature
              <input
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={settings.llm.temperature}
                onChange={(e) => updateSection("llm", "temperature", parseFloat(e.target.value) || 0)}
              />
            </label>
            <label>
              Max output tokens
              <input
                type="number"
                min="1"
                value={settings.llm.max_output_tokens}
                onChange={(e) =>
                  updateSection("llm", "max_output_tokens", parseInt(e.target.value, 10) || 1)
                }
              />
            </label>
          </div>

          <TestButton target="llm" label="Test LLM connection" />
        </fieldset>

        <fieldset>
          <legend>Web search</legend>
          <p className="muted small-note">
            Only needed to find pages <em>other than</em> the company's own site. Reading the company
            website itself uses its sitemap and needs no search provider.
          </p>

          <label>
            Provider
            <select
              value={settings.search.provider}
              onChange={(e) => updateSection("search", "provider", e.target.value)}
            >
              {(options?.search_providers || []).map((p) => (
                <option key={p} value={p}>
                  {SEARCH_PROVIDER_LABELS[p] || p}
                </option>
              ))}
            </select>
          </label>

          {settings.search.provider === "searxng" && (
            <label>
              SearXNG instance URL
              <input
                type="text"
                placeholder="http://localhost:8080"
                value={settings.search.searxng_url || ""}
                onChange={(e) => updateSection("search", "searxng_url", e.target.value)}
              />
            </label>
          )}

          {searchNeedsKey && (
            <label>
              API key {settings.search.api_key_set && !settings.search.api_key_dirty && <em>(saved)</em>}
              <input
                type="password"
                autoComplete="off"
                placeholder={settings.search.api_key_set ? settings.search.api_key : "API key"}
                value={settings.search.api_key_dirty ? settings.search.api_key : ""}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    search: { ...s.search, api_key: e.target.value, api_key_dirty: true },
                  }))
                }
              />
            </label>
          )}

          {settings.search.provider !== "none" && (
            <label>
              Max results per query
              <input
                type="number"
                min="1"
                max="50"
                value={settings.search.max_results}
                onChange={(e) =>
                  updateSection("search", "max_results", parseInt(e.target.value, 10) || 1)
                }
              />
            </label>
          )}

          {settings.search.provider !== "none" && (
            <TestButton target="search" label="Test search connection" />
          )}
        </fieldset>

        <fieldset>
          <legend>Sender profile</legend>
          <p className="muted small-note">
            Who the generated messages come from. Without at least a name and company, message
            generation is blocked — a message needs a sender, and the model must not invent one.
          </p>

          <div className="row">
            <label>
              Your name
              <input
                type="text"
                value={settings.sender.full_name}
                onChange={(e) => updateSection("sender", "full_name", e.target.value)}
                placeholder="Tran Van A"
              />
            </label>
            <label>
              Your title
              <input
                type="text"
                value={settings.sender.title}
                onChange={(e) => updateSection("sender", "title", e.target.value)}
                placeholder="Head of Sales"
              />
            </label>
          </div>

          <label>
            Your company
            <input
              type="text"
              value={settings.sender.company_name}
              onChange={(e) => updateSection("sender", "company_name", e.target.value)}
              placeholder="ABIM"
            />
          </label>

          <label>
            What your company does — one or two sentences
            <textarea
              rows={2}
              value={settings.sender.company_description}
              onChange={(e) => updateSection("sender", "company_description", e.target.value)}
              placeholder="We build and run ERP and data platforms for mid-size Vietnamese manufacturers."
            />
          </label>

          <div className="row">
            <label>
              Reply-to email
              <input
                type="text"
                value={settings.sender.email}
                onChange={(e) => updateSection("sender", "email", e.target.value)}
                placeholder="a.tran@abim.vn"
              />
            </label>
            <label>
              Phone
              <input
                type="text"
                value={settings.sender.phone}
                onChange={(e) => updateSection("sender", "phone", e.target.value)}
                placeholder="+84 90 123 4567"
              />
            </label>
          </div>

          <label>
            Booking link (optional)
            <input
              type="text"
              value={settings.sender.calendar_link}
              onChange={(e) => updateSection("sender", "calendar_link", e.target.value)}
              placeholder="https://cal.com/a-tran/15min"
            />
          </label>

          <label>
            Sign-off (optional — inserted verbatim)
            <textarea
              rows={2}
              value={settings.sender.signature}
              onChange={(e) => updateSection("sender", "signature", e.target.value)}
              placeholder={"Tran Van A\nHead of Sales, ABIM"}
            />
          </label>
        </fieldset>

        <fieldset>
          <legend>Enrichment sources</legend>
          <p className="muted small-note">
            These run in order, cheapest and most reliable first. Anything found early is not overwritten
            later.
          </p>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings.enrichment.use_structured_data}
              onChange={(e) => updateSection("enrichment", "use_structured_data", e.target.checked)}
            />
            Structured data — JSON-LD, meta tags, mailto/tel, regex (free, most accurate)
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings.enrichment.use_company_website}
              onChange={(e) => updateSection("enrichment", "use_company_website", e.target.checked)}
            />
            Company website — sitemap plus a shallow crawl (free)
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings.enrichment.use_web_search}
              onChange={(e) => updateSection("enrichment", "use_web_search", e.target.checked)}
            />
            Web search — pages about the company elsewhere (needs a search provider)
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings.enrichment.use_llm}
              onChange={(e) => updateSection("enrichment", "use_llm", e.target.checked)}
            />
            LLM extraction — only for fields the steps above couldn't fill
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings.enrichment.use_browser_fallback}
              onChange={(e) => updateSection("enrichment", "use_browser_fallback", e.target.checked)}
            />
            Browser fallback — render JavaScript-heavy pages (much slower)
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings.enrichment.auto_enrich_on_search}
              onChange={(e) => updateSection("enrichment", "auto_enrich_on_search", e.target.checked)}
            />
            Auto-enrich — start enrichment automatically after every search
          </label>
        </fieldset>

        <fieldset>
          <legend>Crawling behaviour</legend>
          <p className="muted small-note">
            Staying polite is what keeps this step low-risk. Please don't turn these off.
          </p>

          <div className="row">
            <label>
              Max pages per company
              <input
                type="number"
                min="1"
                max="50"
                value={settings.enrichment.max_pages_per_company}
                onChange={(e) =>
                  updateSection(
                    "enrichment",
                    "max_pages_per_company",
                    parseInt(e.target.value, 10) || 1,
                  )
                }
              />
            </label>
            <label>
              Request timeout (seconds)
              <input
                type="number"
                min="1"
                step="1"
                value={settings.enrichment.request_timeout_seconds}
                onChange={(e) =>
                  updateSection(
                    "enrichment",
                    "request_timeout_seconds",
                    parseFloat(e.target.value) || 1,
                  )
                }
              />
            </label>
          </div>

          <label>
            Delay between requests to the same site (seconds)
            <input
              type="number"
              min="0"
              step="0.5"
              value={settings.enrichment.request_delay_seconds}
              onChange={(e) =>
                updateSection("enrichment", "request_delay_seconds", parseFloat(e.target.value) || 0)
              }
            />
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings.enrichment.respect_robots_txt}
              onChange={(e) => updateSection("enrichment", "respect_robots_txt", e.target.checked)}
            />
            Respect robots.txt
          </label>

          <label>
            User agent
            <input
              type="text"
              value={settings.enrichment.user_agent}
              onChange={(e) => updateSection("enrichment", "user_agent", e.target.value)}
            />
          </label>
        </fieldset>

        <button type="submit" className="primary" disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </button>

        {settings.updated_at && (
          <p className="muted small">
            Last updated {new Date(settings.updated_at).toLocaleString()}
            {settings.updated_by ? ` by ${settings.updated_by}` : ""}.
          </p>
        )}
      </form>
    </main>
  );
}
