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
      <div className="page-head">
        <div>
          <h1>Search history</h1>
          <p className="lede">
            Every search is kept with its criteria and results. Enrich, ranking and message runs all
            start from one of these.
          </p>
        </div>
        <div className="toolbar">
          <Link className="button-link" to="/">
            New search
          </Link>
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

      {runs && runs.length > 0 && (
        <section className="card2">
          <div className="tw">
            <table className="tbl">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Criteria</th>
                  <th>Source</th>
                  <th>Companies</th>
                  <th>Contacts</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr className="pick" key={run.id}>
                    <td className="nowrap">
                      <strong>{formatDate(run.created_at)}</strong>
                    </td>
                    <td>{formatCriteria(run.criteria)}</td>
                    <td>
                      <span className="badge">{run.provider}</span>
                    </td>
                    <td className="num">{run.total_companies}</td>
                    <td className="num">{run.total_contacts}</td>
                    <td>
                      <Link to={`/history/${run.id}`}>Open</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
