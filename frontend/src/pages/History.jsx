import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { formatCriteria, formatDate } from "../lib/format";

export default function History() {
  const [runs, setRuns] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listRuns()
      .then(setRuns)
      .catch((err) => setError(err.message || "Couldn't load search history."));
  }, []);

  return (
    <main className="container">
      <div className="results-header">
        <h1>Search history</h1>
        <div className="actions">
          <Link to="/">New search</Link>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {runs === null && !error && <p className="muted">Loading…</p>}
      {runs?.length === 0 && (
        <div className="empty-state">
          <p>No searches yet.</p>
          <Link className="button-link" to="/">
            Run your first search →
          </Link>
        </div>
      )}

      {runs?.map((run) => (
        <Link className="history-row" to={`/history/${run.id}`} key={run.id}>
          <div className="history-row-main">
            <span className="history-criteria">{formatCriteria(run.criteria)}</span>
            <span className="muted small">
              {run.total_companies} companies · {run.total_contacts} contacts · provider: {run.provider}
            </span>
          </div>
          <span className="muted small history-date">{formatDate(run.created_at)}</span>
        </Link>
      ))}
    </main>
  );
}
