import { Link, Navigate, useLocation } from "react-router-dom";
import ResultsView from "../components/ResultsView";

export default function Results() {
  const location = useLocation();
  const data = location.state;

  if (!data) {
    // Người dùng vào thẳng /results (vd: reload trang) mà chưa có kết quả nào.
    return <Navigate to="/" replace />;
  }

  return (
    <main className="container">
      <div className="results-header">
        <h1>Kết quả</h1>
        <div className="actions">
          <Link to="/">Tìm kiếm mới</Link>
          <Link to="/history">Lịch sử</Link>
        </div>
      </div>
      <ResultsView
        companies={data.companies}
        totalCompanies={data.total_companies}
        totalContacts={data.total_contacts}
        runId={data.run_id}
      />
    </main>
  );
}
