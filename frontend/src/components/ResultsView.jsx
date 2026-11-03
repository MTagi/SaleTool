import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, getToken } from "../api/client";
import EnrichmentResult from "./EnrichmentResult";
import CompanyDrawerRow from "./CompanyDrawerRow";
import JobProgress from "./JobProgress";
import { useEnrichJob } from "../hooks/useJob";
import { useSelection } from "../hooks/useSelection";

async function downloadFile(fmt, runId) {
  const token = getToken();
  const res = await fetch(`/api/download/${fmt}?run_id=${encodeURIComponent(runId)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Couldn't download the file (${res.status})`);

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `saletool_results.${fmt}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** A company is "thin" when the search provider gave us almost nothing to work with. */
function isMissingInfo(company, contacts) {
  return !company.industry || !company.location || !company.employee_count || contacts.length === 0;
}

/**
 * Did enrichment actually find anything? Mirrors CompanyEnrichment.is_empty() on
 * the backend, which is a method and so never reaches the client.
 */
function foundSomething(result) {
  return Boolean(
    result.description ||
      result.emails?.length ||
      result.phones?.length ||
      result.addresses?.length ||
      result.executives?.length ||
      result.tax_code ||
      Object.keys(result.social_links || {}).length,
  );
}

function sameCompany(company, enrichment) {
  function domain(value) {
    if (!value) return "";
    try {
      return new URL(value.includes("://") ? value : `https://${value}`).hostname.toLowerCase().replace(/^www\./, "");
    } catch { return ""; }
  }
  const left = domain(company.domain);
  const right = domain(enrichment.domain);
  if (left && right) return left === right;
  return company.name.trim().toLowerCase() === enrichment.company_name?.trim().toLowerCase();
}

/**
 * The companies of one search run, as a table.
 *
 * It used to be one large card per company. Twenty of those cannot be compared
 * with each other — you scroll and try to remember. A table lets the eye run
 * down a column, and the detail that used to fill each card moves into the row
 * you expand. Selecting rows is what makes the follow-up steps work on the
 * companies you actually care about instead of always the whole run.
 */
export default function ResultsView({
  companies,
  totalCompanies,
  totalContacts,
  runId,
  autoEnrichJob,
  savedEnrichments = [],
  onEnrichSaved,
}) {
  const navigate = useNavigate();
  const [downloadError, setDownloadError] = useState(null);
  const [error, setError] = useState(null);
  const [openRow, setOpenRow] = useState(null);
  const [query, setQuery] = useState("");
  const selection = useSelection();
  const [bulkJobId, setBulkJobId] = useState(null);
  const [starting, setStarting] = useState(false);
  const { job: bulkJob } = useEnrichJob(bulkJobId);

  useEffect(() => {
    if (bulkJob) onEnrichSaved?.();
  }, [bulkJob, onEnrichSaved]);

  async function handleDownload(fmt) {
    setDownloadError(null);
    try {
      await downloadFile(fmt, runId);
    } catch (err) {
      setDownloadError(err.message);
    }
  }

  // Enrichment can arrive from three places — the page-level auto-enrich run, a
  // bulk run started here, or a single-company run — so they are merged into one
  // index by company name rather than tracked per row.
  const enriched = [...(bulkJob?.results || []), ...(autoEnrichJob?.results || [])];
  const enrichmentFor = (company, index) => enriched.find(result => sameCompany(company, result)) || savedEnrichments[index];

  async function enrichTargets(targets) {
    setError(null);
    setStarting(true);
    try {
      const { job_id } = await api.startEnrich(targets, runId);
      setBulkJobId(job_id);
    } catch (err) {
      setError(err.message || "Couldn't start enrichment.");
    } finally {
      setStarting(false);
    }
  }

  const companyIds = companies.map((r) => r.company.id);

  function enrichSelected() {
    const picked = companies.filter((r) => selection.has(r.company.id));
    enrichTargets(
      picked.map((r) => ({ company_name: r.company.name, domain: r.company.domain || null })),
    );
  }

  return (
    <>
      <div className="page-head">
        <div>
          <p className="muted small">
            {totalCompanies} companies · {totalContacts} senior contacts
          </p>
        </div>
        <div className="toolbar">
          <button className="secondary" onClick={() => handleDownload("csv")}>
            Download CSV
          </button>
          <button className="secondary" onClick={() => handleDownload("json")}>
            Download JSON
          </button>
        </div>
      </div>

      <div className="result-stats" aria-label="Search summary">
        <div><strong>{totalCompanies}</strong><span>Companies</span></div>
        <div><strong>{totalContacts}</strong><span>Contacts</span></div>
        <div><strong>{companies.filter((r, i) => foundSomething(enrichmentFor(r.company, i) || {})).length}</strong><span>Enriched</span></div>
      </div>
      {downloadError && <p className="error">{downloadError}</p>}
      {error && <p className="error">{error}</p>}

      {autoEnrichJob && <JobProgress job={autoEnrichJob} />}
      {bulkJob && <JobProgress job={bulkJob} />}

      {companies.length === 0 && (
        <div className="empty-state">
          <p>No companies matched your criteria.</p>
          <p className="muted small">
            Try fewer filters, a wider location, or a larger company-size range.
          </p>
        </div>
      )}

      {companies.length > 0 && (
        <section className="card2">
          {!selection.isEmpty && (
            <div className="selbar">
              <strong>{selection.size} selected</strong>
              <button className="secondary" onClick={enrichSelected} disabled={starting}>
                {starting ? "Starting…" : "Read websites"}
              </button>
              <button
                className="secondary"
                onClick={() => navigate(`/matching?run=${encodeURIComponent(runId)}`)}
              >
                Rank against catalog
              </button>
              <button
                className="secondary"
                onClick={() => navigate(`/messages?run=${encodeURIComponent(runId)}`)}
              >
                Write messages
              </button>
              <button className="link-button" onClick={selection.clear}>
                Clear
              </button>
            </div>
          )}

          <div className="results-filters"><input type="search" aria-label="Search companies" placeholder="Search company, industry or domain..." value={query} onChange={e => setQuery(e.target.value)} /><Link className="button-link" to="/">+ New search</Link></div>
          <div className="tw">
            <table className="tbl">
              <thead>
                <tr>
                  <th className="tick">
                    <input
                      type="checkbox"
                      checked={selection.hasAll(companyIds)}
                      onChange={(e) => selection.setAll(e.target.checked, companyIds)}
                      aria-label="Select all companies"
                    />
                  </th>
                  <th>Company</th>
                  <th>Industry</th>
                  <th>Size</th>
                  <th>Senior contacts</th>
                  <th>Enriched</th>
                </tr>
              </thead>
              <tbody>
                {!companies.some(r => `${r.company.name} ${r.company.industry || ""} ${r.company.domain || ""}`.toLowerCase().includes(query.toLowerCase())) && <tr><td colSpan={6} className="muted">No companies match this filter.</td></tr>}
                {companies.map((r, i) => {
                  if (!`${r.company.name} ${r.company.industry || ""} ${r.company.domain || ""}`.toLowerCase().includes(query.toLowerCase())) return null;
                  const name = r.company.name;
                  const key = r.company.id;
                  const result = enrichmentFor(r.company, i);
                  const open = openRow === key;
                  const withEmail = r.contacts.filter((c) => c.email).length;

                  return (
                    <CompanyDrawerRow
                      key={key}
                      open={open}
                      title={name}
                      onEnrich={() => enrichTargets([{ company_name: name, domain: r.company.domain || null }])}
                      enriching={starting}
                      onClose={() => setOpenRow(null)}
                      row={
                        <tr className={open ? "pick company-row open" : "pick company-row"}
                          tabIndex={0}
                          aria-label={`View details for ${name}`}
                          aria-expanded={open}
                          onClick={event => {
                            if (event.target.closest("button, a, input, select, textarea, summary")) return;
                            setOpenRow(key);
                          }}
                          onKeyDown={event => {
                            if (event.target !== event.currentTarget) return;
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setOpenRow(key);
                            }
                          }}>
                          <td>
                            <input
                              type="checkbox"
                              checked={selection.has(key)}
                              onChange={() => selection.toggle(key)}
                              aria-label={`Select ${name}`}
                            />
                          </td>
                          <td>
                            <strong>{name}</strong>

                            <div className="sub">
                              {r.company.domain || "no domain"}
                              {r.company.linkedin_url && (
                                <>
                                  {" · "}
                                  <a
                                    href={r.company.linkedin_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                  >
                                    linkedin ↗
                                  </a>
                                </>
                              )}
                            </div>
                          </td>
                          <td>{r.company.industry || <span className="muted">—</span>}</td>
                          <td className="num">
                            {r.company.employee_count || <span className="muted">—</span>}
                          </td>
                          <td className="num">
                            {r.contacts.length}
                            {withEmail > 0 && <div className="sub">{withEmail} with email</div>}
                          </td>
                          <td>
                            {result ? (
                              <span className={foundSomething(result) ? "badge good" : "badge"}>
                                {foundSomething(result) ? "done" : "nothing found"}
                              </span>
                            ) : isMissingInfo(r.company, r.contacts) ? (
                              <button
                                className="secondary"
                                disabled={starting}
                                onClick={() =>
                                  enrichTargets([
                                    { company_name: name, domain: r.company.domain || null },
                                  ])
                                }
                              >
                                Enrich
                              </button>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                        </tr>
                      }
                      detail={
                        <td colSpan={6}>
                            <details className="company-profile" open>
                              <summary>Apollo company profile</summary>
                              {r.company.description && <p>{r.company.description}</p>}
                              <dl>
                                {[
                                  ["Industry", r.company.industry],
                                  ["Location", r.company.location],
                                  ["Employees", r.company.employee_count],
                                  ["Website", r.company.domain],
                                  ["Founded", r.company.founded_year],
                                  ["Phone", r.company.phone],
                                  ["Address", r.company.address],
                                  ["Annual revenue (Apollo estimate)", r.company.annual_revenue],
                                  ["Total funding", r.company.total_funding],
                                  ["Technologies", r.company.technologies?.join(", ")],
                                  ["Keywords", r.company.keywords?.join(", ")],
                                ].filter(([, value]) => value !== null && value !== undefined && value !== "").map(([label, value]) =>
                                  <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
                                )}
                              </dl>
                              <p className="muted small-note">Source: Apollo search. Only available fields are shown; older searches may not contain these details.</p>
                            </details>
                          <div data-pane="Contacts">
                          {r.contacts.length === 0 && (
                            <p className="muted small">No senior contacts found.</p>
                          )}
                          {r.contacts.length > 0 && (
                            <table className="tbl">
                              <thead>
                                <tr>
                                  <th>Name</th>
                                  <th>Title</th>
                                  <th>Seniority</th>
                                  <th>Email</th>
                                  <th>LinkedIn</th>
                                </tr>
                              </thead>
                              <tbody>
                                {r.contacts.map((c, j) => (
                                  <tr key={c.linkedin_url || c.full_name || j}>
                                    <td>
                                      <strong>{c.full_name}</strong>
                                    </td>
                                    <td>{c.title || "—"}</td>
                                    <td>
                                      <span className="badge">{c.seniority || "?"}</span>
                                    </td>
                                    <td>{c.email || <span className="muted">not revealed</span>}</td>
                                    <td>
                                      {c.linkedin_url ? (
                                        <a
                                          href={c.linkedin_url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                        >
                                          profile ↗
                                        </a>
                                      ) : (
                                        <span className="muted">—</span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                          </div>
                          <div data-pane="Enrichment">{result ? <EnrichmentResult result={result} /> : <p className="muted">No enrichment yet. Read the company website to find more information.</p>}</div>
                        </td>
                      }
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {companies.length > 0 && runId && (
        <div className="nextbar">
          <span>Next: score these against your services to decide who to contact first.</span>
          <Link className="button-link" to={`/matching?run=${runId}`}>
            Rank them →
          </Link>
        </div>
      )}
    </>
  );
}
