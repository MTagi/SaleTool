/** Định dạng message sinh ra để dán ra ngoài. */

/**
 * Subject và body gộp thành một khối, đúng như khi dán vào mail client.
 * Message không có subject (LinkedIn, WhatsApp) chỉ trả về body.
 */
export function messageToText(message) {
  return message.subject ? `${message.subject}\n\n${message.body}` : message.body;
}

/** Nhiều message nối lại, mỗi cái có tiêu đề để biết của ai. */
export function messagesToText(messages) {
  return messages
    .filter((message) => !message.error)
    .map((message) => `--- ${message.contact_name} (${message.company_name}) ---\n${messageToText(message)}`)
    .join("\n\n");
}
