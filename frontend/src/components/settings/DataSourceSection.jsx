import SettingsSection from "../SettingsSection";
import SecretField from "./SecretField";
import TestButton from "./TestButton";

const PROVIDER_LABELS = {
  apollo: "Apollo.io — company + contact records, official API",
};

const SEARCH_FIELD_LABELS = {
  industries: "Industries",
  keywords: "Keywords",
  locations: "Locations",
  company_size: "Company size",
  target_titles: "Job titles",
  seniority_levels: "Seniority levels",
};

/** Choose where step 1 gets companies and contacts. Search is blocked without a key. */
export default function DataSourceSection({ value, options, onChange, needsSave = false }) {
  const summary = [
    PROVIDER_LABELS[value.provider] || value.provider,
    value.api_key_set ? "key saved" : "no key — search is blocked",
  ].join(" · ");

  return (
    <SettingsSection title="Data source" summary={summary}>
      <p className="muted small-note">
        Where company and contact records come from in step 1. Searching is blocked until this
        provider has a key.
      </p>

      <label>
        Provider
        <select value={value.provider} onChange={(e) => onChange({ provider: e.target.value })}>
          {(options?.data_providers || []).map((provider) => (
            <option key={provider} value={provider}>
              {PROVIDER_LABELS[provider] || provider}
            </option>
          ))}
        </select>
      </label>

      <SecretField value={value} onChange={onChange} />

      <div>
        <span className="field-label">Search fields</span>
        <p className="muted small-note">
          Choose which optional filters appear in New search. Empty fields are omitted from Apollo requests.
        </p>
        {(options?.apollo_search_fields || []).map((field) => (
          <label className="checkbox spaced-sm" key={field}>
            <input
              type="checkbox"
              checked={(value.enabled_search_fields || []).includes(field)}
              onChange={(event) => {
                const selected = value.enabled_search_fields || [];
                onChange({
                  enabled_search_fields: event.target.checked
                    ? [...selected, field]
                    : selected.filter((item) => item !== field),
                });
              }}
            />
            {SEARCH_FIELD_LABELS[field] || field}
          </label>
        ))}
      </div>

      <TestButton key={String(needsSave)} needsSave={needsSave} target="data_source" label="Test data source" />
    </SettingsSection>
  );
}
