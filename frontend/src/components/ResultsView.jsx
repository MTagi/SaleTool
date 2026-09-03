import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, getToken } from "../api/client";
import EnrichmentResult from "./EnrichmentResult";
import ExpandableRow from "./ExpandableRow";
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
}) {
  const navigate = useNavigate();
  const [downloadError, setDownloadError] = useState(null);
  const [error, setError] = useState(null);
  const [openRow, setOpenRow] = useState(null);
  const selection = useSelection();
  const [bulkJobId, setBulkJobId] = useState(null);
  const [starting, setStarting] = useState(false);
  const { job: bulkJob } = useEnrichJob(bulkJobId);

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
  const enriched = {};
  for (const result of autoEnrichJob?.results || []) enriched[result.company_name] = result;
  for (const result of bulkJob?.results || []) enriched[result.company_name] = result;

  async function enrichTargets(targets) {
    setError(null);
    setStarting(true);
    try {
      const { job_id } = await api.startEnrich(targets);
      setBulkJobId(job_id);
    } catch (err) {
      setError(err.message || "Couldn't start enrichment.");
    } finally {
      setStarting(false);
    }
  }

  const companyNames = companies.map((r) => r.company.name);

  function enrichSelected() {
    const picked = companies.filter((r) => selection.has(r.company.name));
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

          <div className="tw">
            <table className="tbl">
              <thead>
                <tr>
                  <th className="tick">
                    <input
                      type="checkbox"
                      checked={selection.hasAll(companyNames)}
                      onChange={(e) => selection.setAll(e.target.checked, companyNames)}
                      aria-label="Select all companies"
                    />
                  </th>
                  <th>Company</th>
                  <th>Industry</th>
                  <th>Size</th>
                  <th>Senior contacts</th>
                  <th>Enriched</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {companies.map((r, i) => {
                  const name = r.company.name;
                  const key = r.company.linkedin_url || name || i;
                  const result = enriched[name];
                  const open = openRow === name;
                  const withEmail = r.contacts.filter((c) => c.email).length;

                  return (
                    <ExpandableRow
                      key={key}
                      open={open}
                      row={
                        <tr className={open ? "pick open" : "pick"}>
                          <td>
                            <input
                              type="checkbox"
                              checked={selection.has(name)}
                              onChange={() => selection.toggle(name)}
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
                          <td>
                            <button
                              className="link-button"
                              onClick={() => setOpenRow(open ? null : name)}
                            >
                              {open ? "Hide" : "View"}
                            </button>
                          </td>
                        </tr>
                      }
                      detail={
                        <td colSpan={7}>
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
                          {result && <EnrichmentResult result={result} />}
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
