import { useState } from "react";

function Detail({ label, value }) {
  if (!value) return null;
  return (
    <div className="enrich-detail">
      <span className="enrich-detail-label">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function LinkList({ label, items, hrefPrefix = "" }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="enrich-detail">
      <span className="enrich-detail-label">{label}</span>
      <span>
        {items.map((item, i) => (
          <span key={item}>
            {i > 0 && ", "}
            {hrefPrefix ? <a href={`${hrefPrefix}${item}`}>{item}</a> : item}
          </span>
        ))}
      </span>
    </div>
  );
}

export default function EnrichmentResult({ result }) {
  const [showSources, setShowSources] = useState(false);

  const socials = Object.entries(result.social_links || {});
  const nothingFound =
    !result.description &&
    !result.emails?.length &&
    !result.phones?.length &&
    !result.addresses?.length &&
    !result.executives?.length &&
    socials.length === 0;

  return (
    <div className="company-card">
      <div className="company-head">
        <span className="company-name">{result.company_name}</span>
        <span className="company-meta">
          {result.domain}
          {result.pages_fetched > 0 && ` · ${result.pages_fetched} pages read`}
          {result.llm_calls > 0 && ` · ${result.llm_calls} LLM calls`}
        </span>
      </div>

      <div className="enrich-body">
        {nothingFound && (
          <p className="muted small">
            Nothing found. The site may block crawlers, render entirely in JavaScript, or the domain may
            be wrong.
          </p>
        )}

        {result.description && <p className="enrich-description">{result.description}</p>}

        <Detail label="Industry" value={result.industry} />
        <Detail label="Founded" value={result.founded_year} />
        <Detail label="Headquarters" value={result.headquarters} />
        <Detail label="Size" value={result.employee_count_text} />
        <Detail label="Tax code" value={result.tax_code} />
        <LinkList label="Email" items={result.emails} hrefPrefix="mailto:" />
        <LinkList label="Phone" items={result.phones} hrefPrefix="tel:" />
        <LinkList label="Address" items={result.addresses} />
        <LinkList label="Tech" items={result.technologies} />

        {socials.length > 0 && (
          <div className="enrich-detail">
            <span className="enrich-detail-label">Social</span>
            <span>
              {socials.map(([key, url], i) => (
                <span key={key}>
                  {i > 0 && ", "}
                  <a href={url} target="_blank" rel="noopener noreferrer">
                    {key}
                  </a>
                </span>
              ))}
            </span>
          </div>
        )}

        {result.executives?.length > 0 && (
          <div className="enrich-execs">
            <span className="enrich-detail-label">Leadership</span>
            {result.executives.map((person, i) => (
              <div className="contact-row" key={`${person.full_name}-${i}`}>
                <span className="contact-name">{person.full_name}</span>
                <span className="contact-title">{person.title || "—"}</span>
                {person.source_url && (
                  <a href={person.source_url} target="_blank" rel="noopener noreferrer">
                    source ↗
                  </a>
                )}
              </div>
            ))}
          </div>
        )}

        {result.sources?.length > 0 && (
          <div className="enrich-sources">
            <button className="link-button" onClick={() => setShowSources((v) => !v)}>
              {showSources ? "Hide" : "Show"} sources ({result.sources.length})
            </button>
            {showSources && (
              <ul className="source-list">
                {result.sources.map((source, i) => (
                  <li key={`${source.url}-${i}`}>
                    <span className={source.ok ? "test-ok" : "test-fail"}>{source.ok ? "✓" : "✕"}</span>{" "}
                    <a href={source.url} target="_blank" rel="noopener noreferrer">
                      {source.url}
                    </a>{" "}
                    <span className="muted small">
                      ({source.fetch_method} · {source.extractor}
                      {source.note ? ` · ${source.note}` : ""})
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
