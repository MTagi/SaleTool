import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import JobProgress from "../components/JobProgress";
import { CompanyMatchCard } from "../components/MatchJobView";
import { useMatchJob } from "../hooks/useJob";

function formatRun(run) {
  const criteria = [
    run.criteria.keywords?.join(", "),
    run.criteria.industries?.join(", "),
    run.criteria.locations?.join(", "),
  ]
    .filter(Boolean)
    .join(" · ");
  const when = new Date(run.created_at).toLocaleString();
  return `${criteria || "(no criteria)"} — ${run.total_companies} companies — ${when}`;
}

export default function Matching() {
  const [runs, setRuns] = useState(null);
  const [services, setServices] = useState(null);
  const [runId, setRunId] = useState("");
  const [selected, setSelected] = useState([]);
  const [objective, setObjective] = useState("");
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);

  const { job, error: pollError } = useMatchJob(jobId);

  useEffect(() => {
    Promise.all([api.listRuns(), api.listServices()])
      .then(([runList, serviceList]) => {
        setRuns(runList);
        setServices(serviceList);
        // Most people want the search they just ran.
        if (runList.length > 0) setRunId(runList[0].id);
        // Pre-tick every active service: matching against the whole catalog is
        // the common case, narrowing it is the exception.
        setSelected(serviceList.filter((s) => s.active).map((s) => s.id));
      })
      .catch((err) => setError(err.message || "Couldn't load searches and services."));
  }, []);

  const activeServices = useMemo(() => (services || []).filter((s) => s.active), [services]);
  const selectedRun = useMemo(() => (runs || []).find((r) => r.id === runId), [runs, runId]);

  function toggle(serviceId) {
    setSelected((prev) =>
      prev.includes(serviceId) ? prev.filter((id) => id !== serviceId) : [...prev, serviceId]
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!runId) {
      setError("Pick a search run to rank.");
      return;
    }
    if (selected.length === 0) {
      setError("Pick at least one service.");
      return;
    }

    setStarting(true);
    try {
      const { job_id } = await api.startMatch(runId, selected, objective.trim());
      setJobId(job_id);
    } catch (err) {
      setError(err.message || "Couldn't start matching.");
    } finally {
      setStarting(false);
    }
  }

  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <main className="container">
      <div className="results-header">
        <h1>Match services to companies</h1>
        <div className="actions">
          <Link to="/catalog">Service catalog</Link>
          <Link to="/history">History</Link>
        </div>
      </div>

      <p className="muted">
        Scores every company from a past search against the services you pick, then ranks them. Each
        company costs one LLM call, and companies you have already enriched are scored on much more
        information.
      </p>

      {error && <p className="error">{error}</p>}
      {pollError && <p className="error">{pollError}</p>}

      {services?.length === 0 && (
        <p className="muted">
          Your catalog is empty. <Link to="/catalog">Add a service</Link> before matching.
        </p>
      )}

      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Companies to rank</legend>
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
          {selectedRun && (
            <p className="muted small-note">
              {selectedRun.total_companies} companies will be scored ·{" "}
              <Link to={`/history/${selectedRun.id}`}>view this run</Link>
            </p>
          )}
        </fieldset>

        <fieldset>
          <legend>Services to map ({selected.length} selected)</legend>
          {services === null && <p className="muted">Loading…</p>}
          {activeServices.length === 0 && services !== null && (
            <p className="muted small">No active services in the catalog.</p>
          )}
          <div className="checkbox-grid">
            {activeServices.map((service) => (
              <label className="checkbox" key={service.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(service.id)}
                  onChange={() => toggle(service.id)}
                />
                {service.name}
              </label>
            ))}
          </div>
          {activeServices.length > 1 && (
            <div className="actions" style={{ marginTop: 10 }}>
              <button
                type="button"
                className="link-button"
                onClick={() => setSelected(activeServices.map((s) => s.id))}
              >
                Select all
              </button>
              <button type="button" className="link-button" onClick={() => setSelected([])}>
                Clear
              </button>
            </div>
          )}
        </fieldset>

        <fieldset>
          <legend>Ranking preference (optional)</legend>
          <label>
            What should push a company up the list?
            <input
              type="text"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="Prefer companies expanding in northern Vietnam that can decide quickly"
            />
          </label>
        </fieldset>

        <button type="submit" className="primary" disabled={starting || running}>
          {starting ? "Starting…" : running ? "Ranking…" : "Rank companies"}
        </button>
      </form>

      {job && (
        <section className="enrich-results">
          <JobProgress job={job} label="Ranking" />
          {job.results?.map((match) => (
            <CompanyMatchCard key={`${match.company_name}-${match.rank}`} match={match} />
          ))}
        </section>
      )}
    </main>
  );
}
