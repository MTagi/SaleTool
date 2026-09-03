/** Chuẩn bị dữ liệu Settings để gửi lên backend. */

/** Backend hiểu chuỗi này là "giữ nguyên key đang lưu, tôi không đổi". */
export const MASKED_SECRET = "__SALETOOL_UNCHANGED__";

/** Những mục có API key, tức là những mục cần xử lý sentinel ở trên. */
const SECTIONS_WITH_SECRET = ["data_source", "llm", "search"];

/**
 * Chỉ hai cờ này là của riêng UI — backend không nhận, và gửi lên thì
 * Pydantic sẽ từ chối.
 *
 * `api_key_set`: backend nói "đã có key" (nó không bao giờ trả key thật về).
 * `api_key_dirty`: người dùng vừa gõ key mới trong phiên này.
 */
const UI_ONLY_FIELDS = ["api_key_set", "api_key_dirty"];

/**
 * Settings trên màn hình -> payload cho `PUT /api/settings`.
 *
 * Chỉ gửi API key khi người dùng thực sự gõ key mới; còn lại gửi sentinel để
 * backend giữ nguyên cái đang có. Không làm thế thì mỗi lần bấm Save sẽ ghi đè
 * key thật bằng chuỗi mask mà UI đang hiển thị.
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
