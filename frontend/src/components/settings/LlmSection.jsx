import SettingsSection from "../SettingsSection";
import CheckboxField from "./CheckboxField";
import NumberField from "./NumberField";
import SecretField from "./SecretField";
import TestButton from "./TestButton";

// Suggestions for the Model field, not a closed list. The field remains editable
// because OpenRouter adds models frequently and a hardcoded list would quickly age.
const MODEL_SUGGESTIONS = [
  "google/gemini-3.1-flash-lite",
  "google/gemini-2.5-flash-lite",
  "google/gemini-2.5-flash",
  "openai/gpt-5-mini",
];

/** Model used for enrichment, matching, and messaging. */
export default function LlmSection({ value, options, onChange, needsSave = false }) {
  const summary = [value.model || value.provider, value.api_key_set ? "key saved" : "no key"].join(
    " · ",
  );

  return (
    <SettingsSection title="Language model" summary={summary}>
      <p className="muted small-note">
        Used to pull out details that plain parsing can&apos;t — mainly descriptions and leadership
        names.
      </p>

      <CheckboxField checked={value.enabled} onChange={(on) => onChange({ enabled: on })}>
        Enable LLM extraction
      </CheckboxField>

      <label>
        Provider
        <select value={value.provider} onChange={(e) => onChange({ provider: e.target.value })}>
          {(options?.llm_providers || []).map((provider) => (
            <option key={provider} value={provider}>
              {provider}
            </option>
          ))}
        </select>
      </label>

      <label>
        API base URL
        <input
          type="text"
          value={value.base_url}
          onChange={(e) => onChange({ base_url: e.target.value })}
        />
      </label>

      <SecretField value={value} onChange={onChange} placeholder="sk-or-v1-…" />

      <label>
        Model
        <input
          type="text"
          list="model-suggestions"
          value={value.model}
          onChange={(e) => onChange({ model: e.target.value })}
        />
      </label>
      <datalist id="model-suggestions">
        {MODEL_SUGGESTIONS.map((model) => (
          <option key={model} value={model} />
        ))}
      </datalist>
      <p className="muted small-note">
        Pick a model that supports structured outputs. Extraction from cleaned text is an easy task —
        a small, cheap model is enough.
      </p>

      <div className="row">
        <NumberField
          label="Temperature"
          value={value.temperature}
          onChange={(n) => onChange({ temperature: n })}
          min={0}
          max={2}
          step="0.1"
          integer={false}
        />
        <NumberField
          label="Max output tokens"
          value={value.max_output_tokens}
          onChange={(n) => onChange({ max_output_tokens: n })}
          min={1}
        />
      </div>

      <TestButton key={String(needsSave)} needsSave={needsSave} target="llm" label="Test LLM connection" />
      <NumberField
        label="Model context window (tokens)"
        value={value.context_window_tokens ?? 32768}
        onChange={(n) => onChange({ context_window_tokens: n })}
        min={2048}
      />
      <p className="muted small-note">
        Set this to your model's supported context window. Requests reserve output tokens and
        a safety margin, using a conservative UTF-8 byte estimate for input size.
      </p>
    </SettingsSection>
  );
}
