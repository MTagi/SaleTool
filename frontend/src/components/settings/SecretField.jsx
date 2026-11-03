/**
 * API key input.
 *
 * The backend never returns the real key to the browser, so this field is
 * **always empty** until the user types into it. Typing sets `api_key_dirty`, the
 * only signal that this Save includes a new key.
 * (xem `lib/settings.js::toSavePayload`).
 *
 * The three Settings fields previously duplicated this logic and differed in
 * whether they had a placeholder. Keep it in one place to avoid drift.
 */
export default function SecretField({ value, onChange, label = "API key", placeholder }) {
  const saved = Boolean(value.api_key_set);
  const typing = Boolean(value.api_key_dirty);

  return (
    <label>
      {label} {saved && !typing && <em>(saved)</em>}
      <input
        type="password"
        autoComplete="off"
        placeholder={saved && !typing ? value.api_key : placeholder}
        value={typing ? value.api_key : ""}
        onChange={(e) => onChange({ api_key: e.target.value, api_key_dirty: true })}
      />
    </label>
  );
}
