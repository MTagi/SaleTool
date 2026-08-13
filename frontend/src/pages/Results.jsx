import { Link, Navigate, useLocation } from "react-router-dom";
import ResultsView from "../components/ResultsView";

export default function Results() {
  const location = useLocation();
  const data = location.state;

  if (!data) {
    // User landed directly on /results (e.g. page reload) with no result to show.
    return <Navigate to="/" replace />;
  }

  return (
    <main className="container">
      <div className="results-header">
        <h1>Results</h1>
        <div className="actions">
          <Link to="/">New search</Link>
          <Link to="/history">History</Link>
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
