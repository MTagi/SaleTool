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
      .catch((err) => setError(err.message || "Không tải được lần tìm kiếm này."));
  }, [runId]);

  return (
    <main className="container">
      <div className="results-header">
        <h1>Kết quả (lịch sử)</h1>
        <div className="actions">
          <Link to="/history">← Lịch sử</Link>
          <Link to="/">Tìm kiếm mới</Link>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {!run && !error && <p className="muted">Đang tải…</p>}

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
