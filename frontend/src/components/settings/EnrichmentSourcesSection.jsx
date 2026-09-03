import SettingsSection from "../SettingsSection";
import CheckboxField from "./CheckboxField";

// Đúng thứ tự chạy trong enrichment/pipeline.py: rẻ và chắc chắn trước, LLM
// sau cùng. Thứ tự trên màn hình phải khớp thứ tự thật, vì đó chính là điều
// dòng chú thích bên dưới đang hứa với người dùng.
const SOURCES = [
  {
    key: "use_structured_data",
    label: "Structured data — JSON-LD, meta tags, mailto/tel, regex (free, most accurate)",
  },
  { key: "use_company_website", label: "Company website — sitemap plus a shallow crawl (free)" },
  {
    key: "use_web_search",
    label: "Web search — pages about the company elsewhere (needs a search provider)",
  },
  { key: "use_llm", label: "LLM extraction — only for fields the steps above couldn't fill" },
  {
    key: "use_browser_fallback",
    label: "Browser fallback — render JavaScript-heavy pages (much slower)",
  },
];

/** Bật/tắt từng tầng của enrichment. */
export default function EnrichmentSourcesSection({ value, onChange }) {
  const summary =
    [
      value.use_company_website && "website",
      value.use_web_search && "web search",
      value.use_llm && "LLM",
    ]
      .filter(Boolean)
      .join(" + ") || "all sources off";

  return (
    <SettingsSection title="Enrichment sources" summary={summary}>
      <p className="muted small-note">
        These run in order, cheapest and most reliable first. Anything found early is not overwritten
        later.
      </p>

      {SOURCES.map((source) => (
        <CheckboxField
          key={source.key}
          checked={value[source.key]}
          onChange={(on) => onChange({ [source.key]: on })}
        >
          {source.label}
        </CheckboxField>
      ))}

      <CheckboxField
        checked={value.auto_enrich_on_search}
        onChange={(on) => onChange({ auto_enrich_on_search: on })}
      >
        Auto-enrich — start enrichment automatically after every search
      </CheckboxField>
    </SettingsSection>
  );
}
