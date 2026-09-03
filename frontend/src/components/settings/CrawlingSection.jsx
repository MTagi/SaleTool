import SettingsSection from "../SettingsSection";
import CheckboxField from "./CheckboxField";
import NumberField from "./NumberField";

/**
 * Giới hạn và phép lịch sự khi crawl.
 *
 * Đây là thứ giữ cho bước enrichment ở mức rủi ro thấp — tôn trọng robots.txt,
 * chờ giữa hai request cùng domain, khai báo User-Agent thật. Chúng có mặt ở
 * đây để chỉnh, không phải để tắt.
 */
export default function CrawlingSection({ value, onChange }) {
  return (
    <SettingsSection title="Crawling behaviour" summary="Politeness and limits">
      <p className="muted small-note">
        Staying polite is what keeps this step low-risk. Please don&apos;t turn these off.
      </p>

      <div className="row">
        <NumberField
          label="Max pages per company"
          value={value.max_pages_per_company}
          onChange={(n) => onChange({ max_pages_per_company: n })}
          min={1}
          max={50}
        />
        <NumberField
          label="Request timeout (seconds)"
          value={value.request_timeout_seconds}
          onChange={(n) => onChange({ request_timeout_seconds: n })}
          min={1}
          step="1"
          integer={false}
        />
      </div>

      <NumberField
        label="Delay between requests to the same site (seconds)"
        value={value.request_delay_seconds}
        onChange={(n) => onChange({ request_delay_seconds: n })}
        min={0}
        step="0.5"
        integer={false}
      />

      <CheckboxField
        checked={value.respect_robots_txt}
        onChange={(on) => onChange({ respect_robots_txt: on })}
      >
        Respect robots.txt
      </CheckboxField>

      <label>
        User agent
        <input
          type="text"
          value={value.user_agent}
          onChange={(e) => onChange({ user_agent: e.target.value })}
        />
      </label>
    </SettingsSection>
  );
}
