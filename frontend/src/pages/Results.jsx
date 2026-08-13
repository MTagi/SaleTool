import { Link, Navigate, useLocation } from "react-router-dom";
import ResultsView from "../components/ResultsView";
import { useEnrichJob } from "../hooks/useEnrichJob";

export default function Results() {
  const location = useLocation();
  const data = location.state;

  // Hooks must run unconditionally, so this is called even when there is no
  // state to show; passing null simply makes it a no-op.
  const { job: enrichJob } = useEnrichJob(data?.enrichJobId ?? null);

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
          <Link to="/enrichment">Enrichment</Link>
        </div>
      </div>
      <ResultsView
        companies={data.companies}
        totalCompanies={data.total_companies}
        totalContacts={data.total_contacts}
        runId={data.run_id}
        autoEnrichJob={enrichJob}
      />
    </main>
  );
}
