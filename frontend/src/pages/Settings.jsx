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

/**
 * Cấu hình dùng chung cho cả hệ thống.
 *
 * Trang này chỉ còn ba việc: nạp settings, lưu settings, và xếp các mục ra màn
 * hình. Mỗi mục là một component riêng trong `components/settings/` — nó tự
 * dựng dòng tóm tắt của chính nó, nên tóm tắt không bao giờ lệch với các trường
 * nó mô tả, và mỗi mục chỉ chạm được vào lát cắt settings của mình.
 */
export default function Settings() {
  const { status, refresh: refreshStatus } = useAppStatus();
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

  /** Trộn một patch vào đúng một mục. Mỗi section chỉ được đưa hàm của mục nó. */
  function patchSection(name, patch) {
    setSettings((current) => ({ ...current, [name]: { ...current[name], ...patch } }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSaving(true);

    try {
      const saved = await api.saveSettings(toSavePayload(settings));
      setSettings(saved.settings);
      setSuccess("Settings saved.");
      // Thêm LLM key hoặc sender profile là mở khoá các bước sau — dải 5 bước
      // và các banner điều kiện phải biết ngay.
      refreshStatus();
    } catch (err) {
      setError(err.message || "Couldn't save settings.");
    } finally {
      setSaving(false);
    }
  }

  if (!settings) {
    return (
      <main className="container">
        <h1>Settings</h1>
        {error ? <p className="error">{error}</p> : <p className="muted">Loading…</p>}
      </main>
    );
  }

  return (
    <main className="container">
      <h1>Settings</h1>
      <p className="lede">
        Applies to everyone using this instance. API keys are encrypted before they are stored and
        are never sent back to the browser.
      </p>

      {error && <p className="error">{error}</p>}
      {success && <p className="success">{success}</p>}

      <div className="cols">
        <form id="settings-form" onSubmit={handleSubmit}>
          <DataSourceSection
            value={settings.data_source}
            options={options}
            onChange={(patch) => patchSection("data_source", patch)}
          />
          <LlmSection
            value={settings.llm}
            options={options}
            onChange={(patch) => patchSection("llm", patch)}
          />
          <WebSearchSection
            value={settings.search}
            options={options}
            onChange={(patch) => patchSection("search", patch)}
          />
          <SenderSection
            value={settings.sender}
            onChange={(patch) => patchSection("sender", patch)}
          />
          <EnrichmentSourcesSection
            value={settings.enrichment}
            onChange={(patch) => patchSection("enrichment", patch)}
          />
          <CrawlingSection
            value={settings.enrichment}
            onChange={(patch) => patchSection("enrichment", patch)}
          />
        </form>

        <div className="rail">
          <ReadinessPanel settings={settings} status={status} />

          <button type="submit" form="settings-form" className="primary" disabled={saving}>
            {saving ? "Saving…" : "Save settings"}
          </button>

          {settings.updated_at && (
            <p className="muted small-note">
              Last updated {new Date(settings.updated_at).toLocaleString()}
              {settings.updated_by ? ` by ${settings.updated_by}` : ""}.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}

/**
 * Cùng bốn điều kiện mà dải 5 bước ở trên đang kiểm, đọc từ cùng một nguồn
 * (`/api/status` + settings vừa lưu) — nên hai chỗ không bao giờ nói khác nhau.
 */
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
