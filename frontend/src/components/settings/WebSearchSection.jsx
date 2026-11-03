import SettingsSection from "../SettingsSection";
import NumberField from "./NumberField";
import SecretField from "./SecretField";
import TestButton from "./TestButton";

// Labels state the free-tier status (checked 2026-09), since that affects the
// choice more than result quality. The dropdown order comes from
// models.py::SEARCH_PROVIDERS, with the most attractive options first.
const PROVIDER_LABELS = {
  none: "None — read the company's own website only (free)",
  tavily: "Tavily — 1,000 searches/month free, no card needed",
  exa: "Exa — 1,000 searches/month free, no card needed",
  serper: "Serper — 2,500 free once, then paid; scrapes Google SERPs (ToS risk)",
  brave: "Brave — no free tier since Feb 2026; card required, no spending cap",
};

/**
 * Enrichment stage 2: find pages *outside* the company's website.
 *
 * "none" is the default and still works: the company website is read through its
 * sitemap, without requiring a search provider.
 */
export default function WebSearchSection({ value, options, onChange, needsSave = false }) {
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
          {(options?.search_providers || []).filter((provider) => provider !== "codex").map((provider) => (
            <option key={provider} value={provider}>
              {PROVIDER_LABELS[provider] || provider}
            </option>
          ))}
        </select>
      </label>

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

      {!off && <TestButton key={String(needsSave)} needsSave={needsSave} target="search" label="Test search connection" />}
    </SettingsSection>
  );
}
