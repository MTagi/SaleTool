import { useState } from "react";
import { copyText } from "../lib/clipboard";

/** Subject and body as one block, the way it gets pasted into a mail client. */
export function messageToText(message) {
  return message.subject ? `${message.subject}\n\n${message.body}` : message.body;
}

/**
 * One generated message, ready to copy out.
 *
 * Warnings come from the backend, which re-checks the model's output against
 * the real platform limits — a LinkedIn note over 300 characters cannot be sent
 * at all, so it is shown next to the text rather than buried.
 */
export default function MessageCard({ message }) {
  const [copyState, setCopyState] = useState(null); // null | "ok" | "failed"

  async function copy() {
    const ok = await copyText(messageToText(message));
    setCopyState(ok ? "ok" : "failed");
    setTimeout(() => setCopyState(null), 2500);
  }

  if (message.error) {
    return (
      <div className="company-card">
        <div className="company-head">
          <span className="company-name">
            {message.contact_name} <span className="muted small">· {message.company_name}</span>
          </span>
          <span className="company-meta test-fail">not written</span>
        </div>
        <p className="small muted">{message.error}</p>
      </div>
    );
  }

  const blocking = message.warnings?.some((w) => w.includes("cannot be sent"));

  return (
    <div className="company-card">
      <div className="company-head">
        <span className="company-name">
          {message.contact_name}
          {message.contact_title && <span className="contact-title"> · {message.contact_title}</span>}
          <span className="muted small"> · {message.company_name}</span>
        </span>
        <span className="company-meta">
          {message.service_name && <span className="tier-chip">{message.service_name}</span>}{" "}
          <span className="muted small">
            {message.body_words} words · {message.body_chars} chars
          </span>
        </span>
      </div>

      <div className="enrich-body">
        {message.warnings?.length > 0 && (
          <ul className={`message-warnings ${blocking ? "blocking" : ""}`}>
            {message.warnings.map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        )}

        {message.subject && (
          <div className="enrich-detail">
            <span className="enrich-detail-label">Subject</span>
            <span>
              <strong>{message.subject}</strong>{" "}
              <span className="muted small">({message.subject_chars})</span>
            </span>
          </div>
        )}

        <pre className="message-body">{message.body}</pre>

        {message.personalization_used?.length > 0 && (
          <div className="enrich-detail">
            <span className="enrich-detail-label">Based on</span>
            <span className="muted small">{message.personalization_used.join(" · ")}</span>
          </div>
        )}

        <div className="actions">
          <button className="secondary" onClick={copy} type="button">
            {copyState === "ok" ? "Copied" : "Copy"}
          </button>
          {copyState === "failed" && (
            <span className="test-fail small">
              Couldn't copy — select the text above and copy it manually.
            </span>
          )}
          {message.contact_email && (
            <a
              href={`mailto:${message.contact_email}?subject=${encodeURIComponent(
                message.subject || ""
              )}&body=${encodeURIComponent(message.body)}`}
            >
              Open in mail app
            </a>
          )}
          {message.contact_linkedin_url && (
            <a href={message.contact_linkedin_url} target="_blank" rel="noopener noreferrer">
              LinkedIn profile ↗
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
