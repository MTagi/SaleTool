import SettingsSection from "../SettingsSection";
import NumberField from "./NumberField";
import SecretField from "./SecretField";
import TestButton from "./TestButton";

// Nhãn nói thẳng tình trạng free tier (tra lại 09/2026), vì đó là thứ quyết
// định chọn cái nào — không phải chất lượng kết quả. Thứ tự dropdown do
// models.py::SEARCH_PROVIDERS quyết định, đã xếp cái đáng chọn lên trước.
const PROVIDER_LABELS = {
  none: "None — read the company's own website only (free)",
  tavily: "Tavily — 1,000 searches/month free, no card needed",
  exa: "Exa — 1,000 searches/month free, no card needed",
  searxng: "SearXNG — self-hosted, free, but engines block it more often now",
  serper: "Serper — 2,500 free once, then paid; scrapes Google SERPs (ToS risk)",
  brave: "Brave — no free tier since Feb 2026; card required, no spending cap",
};

/**
 * Tầng 2 của enrichment: tìm trang *ngoài* website công ty.
 *
 * "none" là mặc định và vẫn chạy được — đọc chính website công ty dùng sitemap,
 * không cần search provider nào cả.
 */
export default function WebSearchSection({ value, options, onChange }) {
  const off = value.provider === "none";
  const needsKey = (options?.search_providers_requiring_key || []).includes(value.provider);

  const summary = off
    ? "Off — company websites only"
    : `${value.provider}${value.api_key_set ? " · key saved" : ""}`;

  return (
    <SettingsSection title="Web search" summary={summary}>
      <p className="muted small-note">
        Only needed to find pages <em>other than</em> the company&apos;s own site. Reading the company
        website itself uses its sitemap and needs no search provider.
      </p>

      <label>
        Provider
        <select value={value.provider} onChange={(e) => onChange({ provider: e.target.value })}>
          {(options?.search_providers || []).map((provider) => (
            <option key={provider} value={provider}>
              {PROVIDER_LABELS[provider] || provider}
            </option>
          ))}
        </select>
      </label>

      {value.provider === "searxng" && (
        <label>
          SearXNG instance URL
          <input
            type="text"
            placeholder="http://localhost:8080"
            value={value.searxng_url || ""}
            onChange={(e) => onChange({ searxng_url: e.target.value })}
          />
        </label>
      )}

      {needsKey && <SecretField value={value} onChange={onChange} placeholder="API key" />}

      {!off && (
        <NumberField
          label="Max results per query"
          value={value.max_results}
          onChange={(n) => onChange({ max_results: n })}
          min={1}
          max={50}
        />
      )}

      {!off && <TestButton target="search" label="Test search connection" />}
    </SettingsSection>
  );
}
