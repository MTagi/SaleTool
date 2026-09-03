import SettingsSection from "../SettingsSection";

/**
 * Message gửi đi là của ai.
 *
 * Thiếu tên + tên công ty thì bước Messages bị chặn hẳn: một message phải có
 * người gửi, và thà chặn còn hơn để model tự bịa ra một người.
 */
export default function SenderSection({ value, onChange }) {
  const summary = value.full_name
    ? [value.full_name, value.company_name].filter(Boolean).join(" · ")
    : "Not set — required for messages";

  return (
    <SettingsSection title="Sender profile" summary={summary}>
      <p className="muted small-note">
        Who the generated messages come from. Without at least a name and company, message
        generation is blocked — a message needs a sender, and the model must not invent one.
      </p>

      <div className="row">
        <label>
          Your name
          <input
            type="text"
            value={value.full_name}
            onChange={(e) => onChange({ full_name: e.target.value })}
            placeholder="Tran Van A"
          />
        </label>
        <label>
          Your title
          <input
            type="text"
            value={value.title}
            onChange={(e) => onChange({ title: e.target.value })}
            placeholder="Head of Sales"
          />
        </label>
      </div>

      <label>
        Your company
        <input
          type="text"
          value={value.company_name}
          onChange={(e) => onChange({ company_name: e.target.value })}
          placeholder="ABIM"
        />
      </label>

      <label>
        What your company does — one or two sentences
        <textarea
          rows={2}
          value={value.company_description}
          onChange={(e) => onChange({ company_description: e.target.value })}
          placeholder="We build and run ERP and data platforms for mid-size Vietnamese manufacturers."
        />
      </label>

      <div className="row">
        <label>
          Reply-to email
          <input
            type="text"
            value={value.email}
            onChange={(e) => onChange({ email: e.target.value })}
            placeholder="a.tran@abim.vn"
          />
        </label>
        <label>
          Phone
          <input
            type="text"
            value={value.phone}
            onChange={(e) => onChange({ phone: e.target.value })}
            placeholder="+84 90 123 4567"
          />
        </label>
      </div>

      <label>
        Booking link (optional)
        <input
          type="text"
          value={value.calendar_link}
          onChange={(e) => onChange({ calendar_link: e.target.value })}
          placeholder="https://cal.com/a-tran/15min"
        />
      </label>

      <label>
        Sign-off (optional — inserted verbatim)
        <textarea
          rows={2}
          value={value.signature}
          onChange={(e) => onChange({ signature: e.target.value })}
          placeholder={"Tran Van A\nHead of Sales, ABIM"}
        />
      </label>
    </SettingsSection>
  );
}
