import SettingsSection from "../SettingsSection";
import CheckboxField from "./CheckboxField";
import NumberField from "./NumberField";
import SecretField from "./SecretField";
import TestButton from "./TestButton";

// Gợi ý cho ô Model. Không phải danh sách đóng — ô vẫn gõ tự do được, vì
// OpenRouter thêm model liên tục và hardcode danh sách thì tháng sau đã cũ.
const MODEL_SUGGESTIONS = [
  "google/gemini-2.0-flash-001",
  "google/gemini-2.5-flash",
  "meta-llama/llama-3.3-70b-instruct",
  "qwen/qwen-2.5-72b-instruct",
  "openai/gpt-4o-mini",
];

/** Model dùng cho enrichment, matching và messaging. */
export default function LlmSection({ value, options, onChange }) {
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

      <TestButton target="llm" label="Test LLM connection" />
    </SettingsSection>
  );
}
