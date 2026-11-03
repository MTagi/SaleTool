import { useEffect, useReducer, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import ResultsView from "../components/ResultsView";
import EnrichmentResult from "../components/EnrichmentResult";
import MatchTable from "../components/MatchTable";
import MessageCard from "../components/MessageCard";
import JobProgress from "../components/JobProgress";
import { isJobRunning } from "../hooks/useJob";
import { formatCriteria, formatDate } from "../lib/format";

function SavedJobs({ title, jobs, children }) {
  const [selectedId, setSelectedId] = useState("");
  const selected = jobs.find((job) => job.id === selectedId) || jobs[0];
  return (
    <section className="card2" aria-label={title}>
      <header>
        <h2>
          {title} <span className="muted small">({jobs.length})</span>
        </h2>
      </header>
      <div className="cb">
        {!selected ? (
          <p className="muted">
            No saved {title.toLowerCase()} for this search yet.
          </p>
        ) : (
          <>
            <form onSubmit={(event) => event.preventDefault()}>
              <label>
                Saved run
                <select
                  value={selected.id}
                  onChange={(event) => setSelectedId(event.target.value)}
                >
                  {jobs.map((job, index) => (
                    <option key={job.id} value={job.id}>
                      {index === 0 ? "Latest · " : ""}
                      {formatDate(job.created_at)} · {job.status}
                      {job.channel ? ` · ${job.channel} · ${job.language}` : ""}
                    </option>
                  ))}
                </select>
              </label>
            </form>
            <JobProgress job={selected} label={title} />
            {children(selected)}
            {selected.results.length === 0 && (
              <p className="muted">No results saved in this run yet.</p>
            )}
          </>
        )}
      </div>
    </section>
  );
}

function downloadHistory(history) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(history, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `saletool_history_${history.run.id}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function HistoryContent({ runId }) {
  const [history, setHistory] = useState(null);
  const [error, setError] = useState(null);
  const [revision, refresh] = useReducer((value) => value + 1, 0);

  useEffect(() => {
    let cancelled = false;
    let timer;
    async function load() {
      try {
        const data = await api.getRunHistory(runId);
        if (cancelled) return;
        setHistory(data);
        setError(null);
        if (
          [...data.enrich_jobs, ...data.match_jobs, ...data.message_jobs].some(
            isJobRunning,
          )
        ) {
          timer = setTimeout(load, 2000);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Couldn't load this history.");
      }
    }
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [runId, revision]);

  useEffect(() => {
    const onFocus = () => refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);

  const run = history?.run;

  return (
    <main className="container">
      <div className="page-head">
        <div>
          <h1>Search history details</h1>
          {run && (
            <p className="lede">
              {formatCriteria(run.criteria)} · {formatDate(run.created_at)}
            </p>
          )}
        </div>
        <div className="toolbar">
          <Link to="/history">← History</Link>
          <button className="secondary" onClick={refresh}>
            Refresh
          </button>
          {history && (
            <button
              className="secondary"
              onClick={() => downloadHistory(history)}
            >
              Download full history JSON
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!history && !error && <p className="muted">Loading saved results…</p>}

      {history && (
        <>
          <p className="muted small">
            Saved results are restored automatically. Search CSV/JSON contains
            the original search; full history JSON includes enrichment, rankings
            and drafts.
          </p>
          <ResultsView
            companies={run.results}
            totalCompanies={run.total_companies}
            totalContacts={run.total_contacts}
            runId={run.id}
            savedEnrichments={history.enrichments}
            onEnrichSaved={refresh}
          />
          <SavedJobs title="Enrichment" jobs={history.enrich_jobs}>
            {(job) => (
              <>
                {!job.run_id && (
                  <p className="muted small">
                    Saved separately; matched by company website or name. Only
                    matching companies are shown; progress refers to the
                    original run.
                  </p>
                )}
                {job.results.map((result, index) => (
                  <EnrichmentResult
                    key={`${job.id}-${index}`}
                    result={result}
                  />
                ))}
              </>
            )}
          </SavedJobs>
          <SavedJobs title="Matching" jobs={history.match_jobs}>
            {(job) => (
              <>
                {job.objective && (
                  <p>
                    <strong>Objective:</strong> {job.objective}
                  </p>
                )}
                <p className="muted small">
                  Services at the time:{" "}
                  {job.services.map((service) => service.name).join(", ") ||
                    "—"}
                </p>
                {job.results.length > 0 && (
                  <MatchTable key={job.id} matches={job.results} />
                )}
                {job.status === "completed" && (
                  <Link
                    to={`/messages?run=${encodeURIComponent(runId)}&match=${encodeURIComponent(job.id)}`}
                  >
                    Write messages using this ranking →
                  </Link>
                )}
              </>
            )}
          </SavedJobs>
          <SavedJobs title="Messages" jobs={history.message_jobs}>
            {(job) => (
              <>
                <p className="muted small">
                  {job.channel} · {job.language} · {job.tone} · Saved drafts;
                  nothing is sent.
                </p>
                {job.notices?.map((notice, index) => (
                  <p className="muted small" key={index}>
                    {notice}
                  </p>
                ))}
                {job.results.map((message, index) => (
                  <MessageCard key={`${job.id}-${index}`} message={message} />
                ))}
              </>
            )}
          </SavedJobs>
        </>
      )}
    </main>
  );
}

export default function HistoryDetail() {
  const { runId } = useParams();
  return <HistoryContent key={runId} runId={runId} />;
}
