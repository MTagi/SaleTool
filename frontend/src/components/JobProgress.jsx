/**
 * Progress bar for any background job that reports total/completed/failed.
 * Shared by enrichment and service matching.
 */
export default function JobProgress({ job, label = "Enriching" }) {
  if (!job) return null;

  const done = job.status === "completed" || job.status === "failed";
  const processed = job.completed + job.failed;
  const percent = job.total ? Math.round((processed / job.total) * 100) : 0;

  return (
    <div className="job-progress">
      <div className="job-progress-head">
        <span>
          {done ? "Finished" : label} — {processed} of {job.total}
          {job.failed > 0 ? ` (${job.failed} failed)` : ""}
        </span>
        {job.current_target && !done && <span className="muted small">{job.current_target}</span>}
      </div>
      <div className="progress-bar">
        <div className="progress-bar-fill" style={{ width: `${percent}%` }} />
      </div>
      {job.error && <p className="muted small">Last error: {job.error}</p>}
    </div>
  );
}
