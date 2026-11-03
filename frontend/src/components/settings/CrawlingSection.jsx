import SettingsSection from "../SettingsSection";
import CheckboxField from "./CheckboxField";
import NumberField from "./NumberField";

/**
 * Crawl limits and etiquette.
 *
 * These settings keep enrichment low-risk: respect robots.txt, wait between
 * requests to the same domain, and provide a real User-Agent. They can be
 * adjusted here, but should not be disabled.
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
        label="Pages reserved for web search"
        value={value.web_search_reserved_pages ?? 4}
        onChange={(n) => onChange({ web_search_reserved_pages: n })}
        min={1}
        max={50}
      />
      <p className="muted small-note">
        Within the total page limit, reserve up to {Math.min(value.web_search_reserved_pages ?? 4, value.max_pages_per_company)} pages
        for external sources and leave {Math.max(0, value.max_pages_per_company - (value.web_search_reserved_pages ?? 4))} for
        the company website. Requires Web search to be enabled. The Web search result limit may
        reduce this reservation. Unused slots are filled with website pages. To skip web search,
        turn it off in Enrichment.
      </p>

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
