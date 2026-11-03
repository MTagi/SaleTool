/** Format a generated message for pasting elsewhere. */

/**
 * Combine the subject and body into one block, ready to paste into an email client.
 * Messages without a subject (LinkedIn, WhatsApp) return only the body.
 */
export function messageToText(message) {
  return message.subject ? `${message.subject}\n\n${message.body}` : message.body;
}

/** Join multiple messages, labeling each one with its recipient. */
export function messagesToText(messages) {
  return messages
    .filter((message) => !message.error)
    .map((message) => `--- ${message.contact_name} (${message.company_name}) ---\n${messageToText(message)}`)
    .join("\n\n");
}
