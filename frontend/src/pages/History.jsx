import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

function formatCriteria(criteria) {
  const parts = [];
  if (criteria.keywords?.length) parts.push(criteria.keywords.join(", "));
  if (criteria.industries?.length) parts.push(criteria.industries.join(", "));
  if (criteria.locations?.length) parts.push(criteria.locations.join(", "));
  return parts.length ? parts.join(" · ") : "(không có tiêu chí)";
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString("vi-VN");
  } catch {
    return iso;
  }
}

export default function History() {
  const [runs, setRuns] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listRuns()
      .then(setRuns)
      .catch((err) => setError(err.message || "Không tải được lịch sử."));
  }, []);

  return (
    <main className="container">
      <div className="results-header">
        <h1>Lịch sử tìm kiếm</h1>
        <div className="actions">
          <Link to="/">Tìm kiếm mới</Link>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {runs === null && !error && <p className="muted">Đang tải…</p>}
      {runs?.length === 0 && <p className="muted">Chưa có lần tìm kiếm nào.</p>}

      {runs?.map((run) => (
        <Link className="history-row" to={`/history/${run.id}`} key={run.id}>
          <div className="history-row-main">
            <span className="history-criteria">{formatCriteria(run.criteria)}</span>
            <span className="muted small">
              {run.total_companies} công ty · {run.total_contacts} liên hệ · provider: {run.provider}
            </span>
          </div>
          <span className="muted small history-date">{formatDate(run.created_at)}</span>
        </Link>
      ))}
    </main>
  );
}
