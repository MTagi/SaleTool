import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import ResultsView from "../components/ResultsView";

export default function HistoryDetail() {
  const { runId } = useParams();
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setRun(null);
    setError(null);
    api
      .getRun(runId)
      .then(setRun)
      .catch((err) => setError(err.message || "Couldn't load this search."));
  }, [runId]);

  return (
    <main className="container">
      <div className="page-head">
        <h1>Result (history)</h1>
        <div className="toolbar">
          <Link to="/history">← History</Link>
          <Link to="/">New search</Link>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {!run && !error && <p className="muted">Loading…</p>}

      {run && (
        <ResultsView
          companies={run.results}
          totalCompanies={run.total_companies}
          totalContacts={run.total_contacts}
          runId={run.id}
        />
      )}
    </main>
  );
}
