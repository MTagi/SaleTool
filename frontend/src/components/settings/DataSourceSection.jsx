import SettingsSection from "../SettingsSection";
import SecretField from "./SecretField";
import TestButton from "./TestButton";

const PROVIDER_LABELS = {
  apollo: "Apollo.io — company + contact records, official API",
};

/** Bước 1 lấy công ty và liên hệ từ đâu. Chưa có key thì Search bị chặn. */
export default function DataSourceSection({ value, options, onChange }) {
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

      <TestButton target="data_source" label="Test data source" />
    </SettingsSection>
  );
}
