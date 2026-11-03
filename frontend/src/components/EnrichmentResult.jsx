import { useId, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function downloadRaw(result) {
  const blob = new Blob([result.raw_markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = (result.company_name.replace(/[^a-z0-9_-]/gi, "_").slice(0, 100) || "company") + "-raw.md";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

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
  const [expanded, setExpanded] = useState(true);
  const queryDialog = useRef(null);
  const card = useRef(null);
  const bodyId = useId();
  const queryTitleId = useId();
  function collapse() {
    setExpanded(false);
    card.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  const socials = Object.entries(result.social_links || {});
  const nothingFound =
    !result.description &&
    !result.emails?.length &&
    !result.phones?.length &&
    !result.addresses?.length &&
    !result.executives?.length &&
    socials.length === 0;

  return (
    <div className="company-card" ref={card}>
      <dialog className="research-dialog" ref={queryDialog} aria-labelledby={queryTitleId}>
        <header>
          <div><h2 id={queryTitleId}>Research queries</h2><p>{result.company_name} ? {result.query_planning_status === "llm" ? "AI planned" : "Default fallback"}</p></div>
          <button type="button" className="settings-close" aria-label="Close research queries" onClick={() => queryDialog.current.close()}>&times;</button>
        </header>
        <ol>{result.search_queries?.map((query, index) => <li key={index}>{query}</li>)}</ol>
      </dialog>
      <div className="company-head">
        <span className="company-name">{result.company_name}</span>
        <span className="company-meta">
          {result.domain}
          {result.pages_fetched > 0 && ` · ${result.pages_fetched} pages read`}
          {result.llm_calls > 0 && ` · ${result.llm_calls} LLM calls`}
        </span>
        <div className="enrich-card-actions">
          {result.search_queries?.length > 0 && <button type="button" className="secondary" onClick={() => queryDialog.current.showModal()}>Research queries ({result.search_queries.length})</button>}
          <button type="button" className="secondary" aria-expanded={expanded} aria-controls={bodyId} onClick={() => expanded ? collapse() : setExpanded(true)}>{expanded ? "Collapse" : "Expand"}</button>
        </div>
      </div>

      <div className="enrich-body" id={bodyId} hidden={!expanded}>
        {result.raw_markdown && <button type="button" className="secondary" onClick={() => downloadRaw(result)}>Download raw data (.md)</button>}
        {result.summary_markdown ? <article className="enrich-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml
            components={{img: () => null, a: ({children, href}) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>}}>
            {result.summary_markdown}
          </ReactMarkdown>
        </article> : result.report_status && <p className="muted small-note">
          {result.report_status === "no_llm" ? "Configure an AI model to generate an English summary." : result.report_status === "no_data" ? "No source data was available for a summary." : "The English summary could not be generated. Raw data is still available when collected."}
        </p>}
        {result.report_error && <p className="error" role="alert">Summary error: {result.report_error}</p>}
        <details open={!result.summary_markdown}><summary>Extracted fields and sources</summary>
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
        </details>
        <button type="button" className="secondary enrich-collapse-bottom" onClick={collapse}>Collapse company</button>
      </div>
    </div>
  );
}
