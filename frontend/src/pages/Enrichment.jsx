import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import EnrichmentResult from "../components/EnrichmentResult";
import JobProgress from "../components/JobProgress";
import { useEnrichJob } from "../hooks/useJob";
import { formatRun } from "../lib/format";

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
  const [source, setSource] = useState("run");
  const [runs, setRuns] = useState(null);
  const [runId, setRunId] = useState("");
  const [runCompanies, setRunCompanies] = useState(null);
  const [raw, setRaw] = useState("");
  const [extraContext, setExtraContext] = useState("");
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);

  const { job, error: pollError, running } = useEnrichJob(jobId);

  useEffect(() => {
    api
      .listRuns()
      .then((list) => {
        setRuns(list);
        if (list.length > 0) setRunId(list[0].id);
        // Nobody has searched yet, so pasting is the only thing that can work.
        else setSource("paste");
      })
      .catch((err) => setError(err.message || "Couldn't load your searches."));
  }, []);

  // Enriching straight from a run is the real workflow; the paste box exists for
  // lists that came from somewhere else. Loading the run here saves copying
  // names and domains out to a text editor and back.
  useEffect(() => {
    if (!runId) return;
    setRunCompanies(null);
    api
      .getRun(runId)
      .then((run) => setRunCompanies(run.results || []))
      .catch((err) => setError(err.message || "Couldn't load that search run."));
  }, [runId]);

  const pastedTargets = parseTargets(raw);
  const runTargets = (runCompanies || []).map((r) => ({
    company_name: r.company.name,
    domain: r.company.domain || null,
  }));
  const targets = source === "run" ? runTargets : pastedTargets;
  const withoutDomain = targets.filter((t) => !t.domain).length;

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (targets.length === 0) {
      setError(source === "run" ? "That run has no companies." : "Enter at least one company.");
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

  return (
    <main className="container">
      <div className="page-head">
        <div>
          <h1>Read company websites</h1>
          <p className="lede">
            Pulls description, emails, phones, addresses, tax code, socials and leadership from each
            company&apos;s own site. Cheap and exact sources run first; the model is only asked for
            fields nothing else could fill.
          </p>
        </div>
        <div className="toolbar">
          <Link to="/">Search</Link>
          <Link to="/settings">Settings</Link>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {pollError && <p className="error">{pollError}</p>}

      <div className="cols">
        <form id="enrich-form" onSubmit={handleSubmit}>
          <section className="card2">
            <header>
              <h2>Companies</h2>
            </header>
            <div className="cb">
              <span className="field-label">Where the list comes from</span>
              <div className="pills spaced-sm">
                <button
                  type="button"
                  className="pill"
                  aria-pressed={source === "run"}
                  onClick={() => setSource("run")}
                >
                  A search run
                </button>
                <button
                  type="button"
                  className="pill"
                  aria-pressed={source === "paste"}
                  onClick={() => setSource("paste")}
                >
                  A list I paste
                </button>
              </div>

              {source === "run" && (
                <>
                  <label>
                    Search run
                    <select value={runId} onChange={(e) => setRunId(e.target.value)}>
                      {runs === null && <option value="">Loading…</option>}
                      {runs?.length === 0 && <option value="">No searches yet</option>}
                      {runs?.map((run) => (
                        <option key={run.id} value={run.id}>
                          {formatRun(run)}
                        </option>
                      ))}
                    </select>
                  </label>
                  {runCompanies === null && runId && <p className="muted small">Loading companies…</p>}
                  {runCompanies !== null && (
                    <p className="muted small-note">
                      {runCompanies.length} companies in this run
                      {withoutDomain > 0 && ` · ${withoutDomain} without a domain`}
                    </p>
                  )}
                </>
              )}

              {source === "paste" && (
                <label>
                  One company per line — <code>Company Name, domain.com</code>
                  <textarea
                    rows={8}
                    value={raw}
                    onChange={(e) => setRaw(e.target.value)}
                    placeholder={
                      "Acme Fintech, acmefintech.vn\nBeta Payments, betapayments.io\nGamma Corp"
                    }
                  />
                  <span className="muted small-note">
                    The domain is optional, but without it the tool has to guess — and it guesses
                    wrong for common names.
                  </span>
                </label>
              )}

              <label>
                Extra context for search and the model <span className="muted">— optional</span>
                <input
                  type="text"
                  value={extraContext}
                  onChange={(e) => setExtraContext(e.target.value)}
                  placeholder="fintech companies in Ho Chi Minh City"
                />
                <span className="muted small-note">
                  Helps pick the right company when several share a name.
                </span>
              </label>
            </div>
          </section>
        </form>

        <div className="rail">
          <section className="card2">
            <header>
              <h2>Before you run</h2>
            </header>
            <div className="cb">
              <div className="rail-big">
                {targets.length}
                <span>{targets.length === 1 ? "company" : "companies"}</span>
              </div>
              <p className="muted small-note">
                {withoutDomain > 0
                  ? `${withoutDomain} without a domain — those need web search to find anything`
                  : "every company has a domain"}
              </p>
              <div className="rail-row">
                <span className="k">Apollo credits</span>
                <span>0 — none used</span>
              </div>
              <div className="rail-row">
                <span className="k">Model calls</span>
                <span>only for gaps</span>
              </div>
              <button
                type="submit"
                form="enrich-form"
                className="primary"
                disabled={starting || running || targets.length === 0}
              >
                {starting ? "Starting…" : running ? "Running…" : "Read websites"}
              </button>
              <p className="muted small-note">
                Runs in the background, about 10-30s per company. You can leave the page.
              </p>
            </div>
          </section>
        </div>
      </div>

      {job && (
        <section className="after">
          <JobProgress job={job} />
          {job.results?.map((result, i) => (
            <EnrichmentResult key={`${result.company_name}-${i}`} result={result} />
          ))}
        </section>
      )}
    </main>
  );
}
