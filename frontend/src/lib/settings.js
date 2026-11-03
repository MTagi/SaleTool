/** Prepare Settings data to send to the backend. */

/** The backend interprets this string as "keep the saved key unchanged." */
export const MASKED_SECRET = "__SALETOOL_UNCHANGED__";

/** Fields containing API keys, which need the sentinel handling above. */
const SECTIONS_WITH_SECRET = ["data_source", "llm", "search"];

/**
 * These two flags are UI-only. The backend does not accept them, and Pydantic
 * will reject them if sent.
 *
 * `api_key_set`: the backend indicates a key is saved (it never returns the key).
 * `api_key_dirty`: the user entered a new key during this session.
 */
const UI_ONLY_FIELDS = ["api_key_set", "api_key_dirty"];

/**
 * Convert on-screen Settings into a payload for `PUT /api/settings`.
 *
 * Send an API key only when the user entered a new one. Otherwise send the
 * sentinel so the backend preserves the saved value. Without this, every Save
 * would overwrite the real key with the masked string displayed in the UI.
 */
export function toSavePayload(settings) {
  const payload = { ...settings };

  for (const name of SECTIONS_WITH_SECRET) {
    const section = { ...settings[name] };
    section.api_key = section.api_key_dirty ? section.api_key : MASKED_SECRET;
    for (const field of UI_ONLY_FIELDS) delete section[field];
    payload[name] = section;
  }

  return payload;
}
