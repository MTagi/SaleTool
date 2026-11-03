import { useEffect, useState } from "react";
import { api } from "../api/client";
import CrawlingSection from "../components/settings/CrawlingSection";
import DataSourceSection from "../components/settings/DataSourceSection";
import EnrichmentSourcesSection from "../components/settings/EnrichmentSourcesSection";
import LlmSection from "../components/settings/LlmSection";
import SenderSection from "../components/settings/SenderSection";
import WebSearchSection from "../components/settings/WebSearchSection";
import { useAppStatus } from "../context/StatusContext";
import { toSavePayload } from "../lib/settings";

const TABS = [
  { id: "general", label: "General", icon: "M4 7h16M4 17h16M8 4v6M16 14v6", keywords: "readiness overview configuration" },
  { id: "data", label: "Data source", icon: "M4 4h16v16H4zM4 9h16M9 9v11", keywords: "apollo api provider key" },
  { id: "llm", label: "AI model", icon: "M12 3l3 6 6 3-6 3-3 6-3-6-6-3 6-3z", keywords: "llm openai model key endpoint" },
  { id: "search", label: "Web search", icon: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14M15 15l6 6", keywords: "search provider tavily brave key" },
  { id: "sender", label: "Sender profile", icon: "M16 7a4 4 0 1 0-8 0 4 4 0 0 0 8 0M4 21v-2a8 8 0 0 1 16 0v2", keywords: "name company email phone signature messages" },
  { id: "enrichment", label: "Enrichment", icon: "M12 3l9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5", keywords: "sources social linkedin" },
  { id: "crawling", label: "Crawling", icon: "M3 4h18v16H3zM3 9h18M7 6h1M11 6h1M7 13h10M7 16h6", keywords: "website pages timeout" },
];

export default function Settings({ onClose }) {
  const { status, refresh: refreshStatus } = useAppStatus();
  const [settings, setSettings] = useState(null);
  const [options, setOptions] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const [activeTab, setActiveTab] = useState("general");
  const [query, setQuery] = useState("");
  const tabs = TABS.filter(tab => (tab.label + " " + tab.keywords).toLowerCase().includes(query.trim().toLowerCase()));
  const selected = tabs.find(tab => tab.id === activeTab) || tabs[0];

  useEffect(() => {
    // B?o v? thay ??i ch?a l?u khi chuy?n trang b?ng sidebar ho?c t?i l?i.
    function guardNavigation(event) {
      const target = event.target.closest(".app-sidebar a, .app-sidebar button");
      if (!target || event.defaultPrevented) return;
      if (target.tagName === "A" && (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)) return;
      if (target.getAttribute("href") === "/settings") return;
      if (saving || (dirty && !window.confirm("You have unsaved changes. Discard them and leave Settings?"))) {
        event.preventDefault();
        event.stopPropagation();
      }
    }
    function guardUnload(event) {
      if (!dirty && !saving) return;
      event.preventDefault();
      event.returnValue = "";
    }
    document.addEventListener("click", guardNavigation, true);
    window.addEventListener("beforeunload", guardUnload);
    return () => {
      document.removeEventListener("click", guardNavigation, true);
      window.removeEventListener("beforeunload", guardUnload);
    };
  }, [dirty, saving]);

  useEffect(() => {
    let cancelled = false;
    api.getSettings().then(data => {
      if (!cancelled) { setSettings(data.settings); setOptions(data.options); }
    }).catch(err => { if (!cancelled) setError(err.message || "Couldn't load settings."); });
    return () => { cancelled = true; };
  }, []);

  function close() {
    if (saving) return;
    if (dirty) setConfirmClose(true);
    else onClose();
  }

  function patchSection(name, patch) {
    setSettings(current => ({ ...current, [name]: { ...current[name], ...patch } }));
    setDirty(true);
    setSuccess(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (saving || !settings) return;
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      const saved = await api.saveSettings(toSavePayload(settings));
      setSettings(saved.settings);
      setDirty(false);
      setConfirmClose(false);
      setSuccess("Settings saved.");
      refreshStatus();
    } catch (err) {
      setError(err.message || "Couldn't save settings.");
    } finally { setSaving(false); }
  }

  function navigateTabs(event, index) {
    let next;
    if (["ArrowDown", "ArrowRight"].includes(event.key)) next = (index + 1) % tabs.length;
    if (["ArrowUp", "ArrowLeft"].includes(event.key)) next = (index + tabs.length - 1) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    if (next === undefined) return;
    event.preventDefault();
    setActiveTab(tabs[next].id);
    document.getElementById("settings-tab-" + tabs[next].id)?.focus();
  }

  const sections = settings ? {
    data: <DataSourceSection needsSave={dirty} value={settings.data_source} options={options} onChange={p => patchSection("data_source", p)} />,
    llm: <LlmSection needsSave={dirty} value={settings.llm} options={options} onChange={p => patchSection("llm", p)} />,
    search: <WebSearchSection needsSave={dirty} value={settings.search} options={options} onChange={p => patchSection("search", p)} />,
    sender: <SenderSection value={settings.sender} onChange={p => patchSection("sender", p)} />,
    enrichment: <EnrichmentSourcesSection value={settings.enrichment} onChange={p => patchSection("enrichment", p)} />,
    crawling: <CrawlingSection value={settings.enrichment} onChange={p => patchSection("enrichment", p)} />,
  } : {};

  return (
    <section className="settings-dialog settings-page" aria-label="Settings">
      <div className="settings-shell">
        <aside className="settings-sidebar">
          <div className="settings-sidebar-heading">
            <button type="button" className="settings-close" aria-label="Close settings" onClick={close} disabled={saving}>&times;</button>
            <strong>Settings</strong>
          </div>
          <input className="settings-search" type="search" placeholder="Search settings" aria-label="Search settings"
            value={query} onChange={e => setQuery(e.target.value)} />
          <div className="settings-tabs" role="tablist" aria-label="Settings categories">
            {tabs.map((tab, index) => (
              <button key={tab.id} type="button" role="tab" id={"settings-tab-" + tab.id}
                aria-selected={selected?.id === tab.id} aria-controls={"settings-panel-" + tab.id}
                tabIndex={selected?.id === tab.id ? 0 : -1}
                onKeyDown={e => navigateTabs(e, index)} onClick={() => setActiveTab(tab.id)}>
                <span className="settings-tab-icon" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d={tab.icon} /></svg></span>{tab.label}
              </button>
            ))}
          </div>
          <p className="settings-sidebar-note">ABIM Sales Assistant<br />Shared workspace settings</p>
        </aside>
        <div className="settings-content">
          <header className="settings-heading"><h1>{selected?.label || "Search settings"}</h1>
            <p>Configure your workspace and connected services.</p></header>
          <form id="settings-form" className="settings-body" onSubmit={handleSubmit}>
            {error && <p className="error" role="alert">{error}</p>}
            {success && <p className="success" role="status">{success}</p>}
            {!settings && !error && <p className="muted" role="status">Loading settings...</p>}
            {!selected && <p className="muted">No settings found. Try model, sender or search.</p>}
            {selected && settings && <div role="tabpanel" id={"settings-panel-" + selected.id}
              aria-labelledby={"settings-tab-" + selected.id} tabIndex={0}>
              <fieldset disabled={saving} className="settings-fields">
                {selected.id === "general" ? <>
                  <p className="settings-intro">These settings apply to everyone using this instance. API keys are encrypted before storage and never sent back to the browser.</p>
                  <ReadinessPanel settings={settings} status={status} />
                  <p className="muted small-note">Choose a category on the left to manage providers, your sender profile and enrichment options.</p>
                  {settings.updated_at && <p className="muted small-note">Last updated {new Date(settings.updated_at).toLocaleString()}{settings.updated_by ? " by " + settings.updated_by : ""}.</p>}
                </> : sections[selected.id]}
              </fieldset>
            </div>}
          </form>
          <footer className="settings-footer">
            {confirmClose ? <div className="settings-discard" role="alert">
              <span>You have unsaved changes.</span>
              <button type="button" onClick={() => setConfirmClose(false)}>Keep editing</button>
              <button type="button" onClick={onClose}>Discard and close</button>
            </div> : <span className="muted small-note">{dirty ? "Unsaved changes" : "Changes apply to this workspace."}</span>}
            <button type="submit" form="settings-form" className="primary" disabled={saving || !settings || !dirty}>
              {saving ? "Saving..." : "Save settings"}
            </button>
          </footer>
        </div>
      </div>
    </section>
  );
}

function ReadinessPanel({ settings, status }) {
  const items = [
    {
      label: "Provider key",
      why: "Search needs it",
      ok: Boolean(settings.data_source.api_key_set),
    },
    {
      label: "Model key",
      why: "Match and Message need it",
      ok: Boolean(settings.llm.api_key_set),
    },
    {
      label: "Sender profile",
      why: "Message needs a name to sign off with",
      ok: Boolean(status?.sender_configured),
    },
    {
      label: "Catalog",
      why: "Match scores companies against these",
      ok: (status?.counts?.active_services ?? 0) > 0,
      value: status ? `${status.counts.active_services} active` : undefined,
    },
  ];

  return (
    <section className="card2">
      <header>
        <h2>Readiness</h2>
      </header>
      <div className="cb flush">
        {items.map((item) => (
          <div className="readiness-row" key={item.label}>
            <div>
              <strong>{item.label}</strong>
              <div className="sub">{item.why}</div>
            </div>
            <span className={item.ok ? "badge good" : "badge bad"}>
              {item.ok ? item.value || "done" : item.value || "missing"}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
