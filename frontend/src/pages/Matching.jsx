import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import JobProgress from "../components/JobProgress";
import MatchTable from "../components/MatchTable";
import Prerequisites from "../components/Prerequisites";
import { useAppStatus } from "../context/StatusContext";
import { useMatchJob } from "../hooks/useJob";
import { useSelection } from "../hooks/useSelection";
import { formatRun } from "../lib/format";
import { allMet } from "../lib/prerequisites";

export default function Matching() {
  const [searchParams] = useSearchParams();
  const { status, refresh: refreshStatus } = useAppStatus();
  const [runs, setRuns] = useState(null);
  const [services, setServices] = useState(null);
  const [runId, setRunId] = useState("");
  const chosenServices = useSelection();
  const [objective, setObjective] = useState("");
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);
  const picked = useSelection();

  const { job, error: pollError, running } = useMatchJob(jobId);

  useEffect(() => {
    Promise.all([api.listRuns(), api.listServices()])
      .then(([runList, serviceList]) => {
        setRuns(runList);
        setServices(serviceList);
        // Honour ?run= when arriving from a results page, otherwise default to
        // the most recent search — the one people almost always mean.
        const requested = searchParams.get("run");
        const preselect = runList.find((r) => r.id === requested) || runList[0];
        if (preselect) setRunId(preselect.id);
        // Pre-tick every active service: matching against the whole catalog is
        // the common case, narrowing it is the exception.
        chosenServices.replace(serviceList.filter((s) => s.active).map((s) => s.id));
      })
      .catch((err) => setError(err.message || "Couldn't load searches and services."));
    // searchParams is only read for the initial preselect; re-running on every
    // URL change would fight the user's own dropdown choice.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Once a job finishes, the workflow strip should show this step as done.
  useEffect(() => {
    if (job?.status === "completed") refreshStatus();
  }, [job?.status, refreshStatus]);

  const checks = [
    {
      ok: status ? status.llm_configured : true,
      label: "No LLM API key — matching scores every company with a model",
      fix: { to: "/settings", text: "add one in Settings" },
    },
    {
      ok: status ? status.counts.active_services > 0 : true,
      label: "No active services in your catalog to match against",
      fix: { to: "/catalog", text: "add a service" },
    },
    {
      ok: status ? status.counts.runs > 0 : true,
      label: "No saved searches yet",
      fix: { to: "/", text: "run a search" },
    },
  ];
  const ready = allMet(checks);

  const activeServices = useMemo(() => (services || []).filter((s) => s.active), [services]);
  // Công ty bị lỗi lúc chấm thì không tick được, nên cũng không tính vào "chọn tất cả".
  const scorable = useMemo(
    () => (job?.results || []).filter((m) => !m.error).map((m) => m.company_name),
    [job?.results],
  );
  const selectedRun = useMemo(() => (runs || []).find((r) => r.id === runId), [runs, runId]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!runId) {
      setError("Pick a search run to rank.");
      return;
    }
    if (chosenServices.isEmpty) {
      setError("Pick at least one service.");
      return;
    }

    setStarting(true);
    try {
      const { job_id } = await api.startMatch(runId, chosenServices.toList(), objective.trim());
      setJobId(job_id);
    } catch (err) {
      setError(err.message || "Couldn't start matching.");
    } finally {
      setStarting(false);
    }
  }

  return (
    <main className="container">
      <div className="page-head">
        <div>
          <h1>Rank companies against your services</h1>
          <p className="lede">
            The model scores each company against each service; the totalling and ordering is plain
            code, so the ranking is explainable and stable between runs.
          </p>
        </div>
        <div className="toolbar">
          <Link to="/catalog">Service catalog</Link>
          <Link to="/history">History</Link>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {pollError && <p className="error">{pollError}</p>}

      <Prerequisites checks={checks} />

      <div className="cols">
        <form id="match-form" onSubmit={handleSubmit}>
          <section className="card2">
            <header><h2>What to rank</h2></header>
            <div className="cb">
              <div className="g2">
                <div>
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
                </div>

                <div>
                  <span className="field-label">
                    Services to map ({chosenServices.size} of {activeServices.length})
                  </span>
                  {services === null && <p className="muted small">Loading…</p>}
                  {activeServices.length === 0 && services !== null && (
                    <p className="muted small">No active services in the catalog.</p>
                  )}
                  <div className="pills spaced-sm">
                    {activeServices.map((service) => (
                      <button
                        key={service.id}
                        type="button"
                        className="pill"
                        aria-pressed={chosenServices.has(service.id)}
                        onClick={() => chosenServices.toggle(service.id)}
                      >
                        {service.name}
                      </button>
                    ))}
                  </div>
                  {activeServices.length > 1 && (
                    <div className="toolbar spaced-sm">
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => chosenServices.replace(activeServices.map((s) => s.id))}
                      >
                        Select all
                      </button>
                      <button type="button" className="link-button" onClick={chosenServices.clear}>
                        Clear
                      </button>
                    </div>
                  )}
                  <p className="muted small-note">
                    Only services marked active in the catalog appear here.
                  </p>
                </div>
              </div>

              <label>
                What should push a company up the list? <span className="muted">— optional</span>
                <input
                  type="text"
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  placeholder="Prefer companies expanding in northern Vietnam that can decide quickly"
                />
                <span className="muted small-note">
                  Plain language. Applied on top of the catalog scoring, not instead of it.
                </span>
              </label>
            </div>
          </section>
        </form>

        <div className="rail">
          <section className="card2">
            <header><h2>Before you run</h2></header>
            <div className="cb">
              <div className="rail-big">
                {selectedRun?.total_companies ?? 0}
                <span>companies</span>
              </div>
              <p className="muted small-note">1 model call each · no Apollo credits</p>
              <div className="rail-row">
                <span className="k">Services</span>
                <span>{chosenServices.size} selected</span>
              </div>
              <div className="rail-row">
                <span className="k">Ranking preference</span>
                <span>{objective.trim() ? "set" : "none"}</span>
              </div>
              <button
                type="submit"
                form="match-form"
                className="primary"
                disabled={starting || running || !ready}
              >
                {starting ? "Starting…" : running ? "Ranking…" : "Rank companies"}
              </button>
              {!ready && <p className="muted small-note">Finish the steps above first.</p>}
              <p className="muted small-note">
                Companies you have already enriched are scored on much more information; the rest
                are scored on the search data alone and the model is told to cap its confidence.
              </p>
            </div>
          </section>
        </div>
      </div>

      {job && (
        <section className="after">
          <JobProgress job={job} label="Ranking" />

          {job.results?.length > 0 && (
            <section className="card2">
              <header>
                <h2>Ranked list</h2>
                <span className="hint">
                  {job.results.length} scored · the catalog was snapshotted when this ran
                </span>
              </header>
              {!picked.isEmpty && (
                <div className="selbar">
                  <strong>{picked.size} selected</strong>
                  <Link
                    className="button-link"
                    to={`/messages?run=${job.run_id}&match=${job.id}`}
                  >
                    Write messages →
                  </Link>
                  <button className="link-button" onClick={picked.clear}>
                    Clear
                  </button>
                </div>
              )}
              <MatchTable matches={job.results} selection={picked} selectableKeys={scorable} />
            </section>
          )}

          {job.status === "completed" && job.results?.length > 0 && (
            <div className="nextbar">
              <span>Ranked. The top companies are the ones to contact first.</span>
              <Link className="button-link" to={`/messages?run=${job.run_id}&match=${job.id}`}>
                Write messages →
              </Link>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
