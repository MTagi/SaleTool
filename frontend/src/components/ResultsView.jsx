import { useState } from "react";
import { Link } from "react-router-dom";
import { api, getToken } from "../api/client";
import { EnrichmentResult } from "./EnrichJobView";
import JobProgress from "./JobProgress";
import { useEnrichJob } from "../hooks/useJob";

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

/** Per-company enrich button; renders the result inline once the job finishes. */
function CompanyEnrichment({ company, autoResult }) {
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);
  const { job } = useEnrichJob(jobId);

  // A result handed down from the page-level auto-enrich run takes precedence.
  const result = autoResult || job?.results?.[0];
  const running = job && (job.status === "pending" || job.status === "running");

  async function start() {
    setError(null);
    setStarting(true);
    try {
      const { job_id } = await api.startEnrich([
        { company_name: company.name, domain: company.domain || null },
      ]);
      setJobId(job_id);
    } catch (err) {
      setError(err.message || "Couldn't start enrichment.");
    } finally {
      setStarting(false);
    }
  }

  if (result) {
    return <EnrichmentResult result={result} />;
  }

  return (
    <div className="enrich-inline">
      {!jobId && (
        <button className="secondary" onClick={start} disabled={starting}>
          {starting ? "Starting…" : "Enrich"}
        </button>
      )}
      {running && <JobProgress job={job} />}
      {error && <p className="error">{error}</p>}
    </div>
  );
}

export default function ResultsView({
  companies,
  totalCompanies,
  totalContacts,
  runId,
  autoEnrichJob,
}) {
  const [downloadError, setDownloadError] = useState(null);

  async function handleDownload(fmt) {
    setDownloadError(null);
    try {
      await downloadFile(fmt, runId);
    } catch (err) {
      setDownloadError(err.message);
    }
  }

  // Index auto-enrich results by company name so each card can pick up its own.
  const autoResults = {};
  for (const result of autoEnrichJob?.results || []) {
    autoResults[result.company_name] = result;
  }

  return (
    <>
      <div className="actions">
        <button className="link-button" onClick={() => handleDownload("csv")}>
          Download CSV
        </button>
        <button className="link-button" onClick={() => handleDownload("json")}>
          Download JSON
        </button>
      </div>
      {downloadError && <p className="error">{downloadError}</p>}
      <p className="muted">
        {totalCompanies} companies · {totalContacts} contacts
      </p>

      {autoEnrichJob && <JobProgress job={autoEnrichJob} />}

      {companies.length > 0 && runId && (
        <div className="next-step">
          <span>Next: score these against your services to decide who to contact first.</span>
          <Link className="button-link" to={`/matching?run=${runId}`}>
            Rank them →
          </Link>
        </div>
      )}

      {companies.length === 0 && (
        <div className="empty-state">
          <p>No companies matched your criteria.</p>
          <p className="muted small">
            Try fewer filters, a wider location, or a larger company-size range.
          </p>
        </div>
      )}

      {companies.map((r, i) => (
        <div className="company-card" key={r.company.linkedin_url || r.company.name || i}>
          <div className="company-head">
            <span className="company-name">{r.company.name}</span>
            <span className="company-meta">
              {[r.company.industry, r.company.location].filter(Boolean).join(" · ")}
              {r.company.employee_count ? ` · ${r.company.employee_count} employees` : ""}
              {r.company.linkedin_url && (
                <>
                  {" · "}
                  <a href={r.company.linkedin_url} target="_blank" rel="noopener noreferrer">
                    linkedin ↗
                  </a>
                </>
              )}
            </span>
          </div>

          {r.contacts.length === 0 && <p className="muted small">No senior contacts found.</p>}

          {r.contacts.map((c, j) => (
            <div className="contact-row" key={c.linkedin_url || c.full_name || j}>
              <span className="contact-name">{c.full_name}</span>
              <span className="contact-title">{c.title || "—"}</span>
              <span className="tier-chip">{c.seniority || "?"}</span>
              {c.linkedin_url && (
                <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer">
                  linkedin ↗
                </a>
              )}
              {c.email && <span className="contact-email">{c.email}</span>}
            </div>
          ))}

          {isMissingInfo(r.company, r.contacts) && (
            <CompanyEnrichment company={r.company} autoResult={autoResults[r.company.name]} />
          )}
        </div>
      ))}
    </>
  );
}
