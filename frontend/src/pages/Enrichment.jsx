import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EnrichProgress, EnrichmentResult } from "../components/EnrichJobView";
import { useEnrichJob } from "../hooks/useEnrichJob";

/**
 * Parses the free-text box into enrichment targets.
 * One company per line: "Company Name, domain.com" (domain optional).
 */
function parseTargets(raw) {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split(",").map((p) => p.trim());
      const looksLikeDomain = (v) => v && /\.[a-z]{2,}$/i.test(v) && !v.includes(" ");

      // A single value that looks like a domain is both the name and the domain.
      if (parts.length === 1) {
        return looksLikeDomain(parts[0])
          ? { company_name: parts[0], domain: parts[0] }
          : { company_name: parts[0] };
      }

      const domain = parts.find(looksLikeDomain);
      const name = parts.find((p) => p !== domain) || parts[0];
      return { company_name: name, domain: domain || null };
    });
}

export default function Enrichment() {
  const [raw, setRaw] = useState("");
  const [extraContext, setExtraContext] = useState("");
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);

  const { job, error: pollError } = useEnrichJob(jobId);
  const targets = parseTargets(raw);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (targets.length === 0) {
      setError("Enter at least one company.");
      return;
    }

    setStarting(true);
    try {
      const withContext = extraContext.trim()
        ? targets.map((t) => ({ ...t, extra_context: extraContext.trim() }))
        : targets;
      const { job_id } = await api.startEnrich(withContext);
      setJobId(job_id);
    } catch (err) {
      setError(err.message || "Couldn't start enrichment.");
    } finally {
      setStarting(false);
    }
  }

  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <main className="container">
      <div className="results-header">
        <h1>Enrichment</h1>
        <div className="actions">
          <Link to="/">Search</Link>
          <Link to="/settings">Settings</Link>
        </div>
      </div>

      <p className="muted">
        Reads each company's own website (and, if enabled in Settings, pages about it elsewhere), then
        pulls out contact details and leadership.
      </p>

      {error && <p className="error">{error}</p>}
      {pollError && <p className="error">{pollError}</p>}

      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Companies</legend>
          <label>
            One per line — <code>Company Name, domain.com</code> (domain optional but strongly
            recommended)
            <textarea
              rows={8}
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
              placeholder={"Acme Fintech, acmefintech.vn\nBeta Payments, betapayments.io\nGamma Corp"}
            />
          </label>

          <label>
            Extra context for search and the model (optional)
            <input
              type="text"
              value={extraContext}
              onChange={(e) => setExtraContext(e.target.value)}
              placeholder="fintech companies in Ho Chi Minh City"
            />
          </label>

          {targets.length > 0 && (
            <p className="muted small">
              {targets.length} compan{targets.length === 1 ? "y" : "ies"} detected
              {targets.filter((t) => !t.domain).length > 0 &&
                ` · ${targets.filter((t) => !t.domain).length} without a domain (needs web search to find anything)`}
            </p>
          )}
        </fieldset>

        <button type="submit" className="primary" disabled={starting || running}>
          {starting ? "Starting…" : running ? "Running…" : "Start enrichment"}
        </button>
      </form>

      {job && (
        <section className="enrich-results">
          <EnrichProgress job={job} />
          {job.results?.map((result, i) => (
            <EnrichmentResult key={`${result.company_name}-${i}`} result={result} />
          ))}
        </section>
      )}
    </main>
  );
}
