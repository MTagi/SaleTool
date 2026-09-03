/**
 * Ô nhập API key.
 *
 * Backend không bao giờ trả key thật về trình duyệt, nên ô này **luôn rỗng**
 * cho tới khi người dùng gõ. Gõ vào là bật cờ `api_key_dirty`, và đó là tín
 * hiệu duy nhất cho biết lần Save này có key mới hay không
 * (xem `lib/settings.js::toSavePayload`).
 *
 * Trước đây ba mục Settings mỗi mục chép lại đoạn này một lần, và lệch nhau ở
 * chỗ có/không có placeholder — gom về một chỗ để chúng không lệch nữa.
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
