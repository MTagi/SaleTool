/**
 * Điều kiện cần của một bước, dùng chung giữa banner và nút submit.
 *
 * Một "check" là `{ ok, label, fix: { to, text } }`. Tách khỏi component
 * Prerequisites để trang có thể hỏi "đủ điều kiện chưa?" mà không phải import
 * một component chỉ để gọi một hàm.
 */

/** True khi mọi điều kiện đều đạt — dùng để bật/tắt nút submit. */
export function allMet(checks) {
  return checks.every((check) => check.ok);
}

/** Những điều kiện chưa đạt, theo đúng thứ tự caller khai báo. */
export function unmet(checks) {
  return checks.filter((check) => !check.ok);
}
