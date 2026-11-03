import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import ConfirmDialog from "../components/ConfirmDialog";
import { useToast } from "../context/ToastContext";
import { formatCriteria, formatDate } from "../lib/format";

export default function History() {
  const [runs, setRuns] = useState(null);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const { show } = useToast();

  useEffect(() => {
    api
      .listRuns()
      .then(setRuns)
      .catch((err) => setError(err.message || "Couldn't load search history."));
  }, []);

  async function handleDelete() {
    if (!pendingDelete) return;
    setDeletingId(pendingDelete.id);
    setError(null);
    try {
      await api.deleteRun(pendingDelete.id);
      setRuns((prev) => prev.filter((item) => item.id !== pendingDelete.id));
      show(`Deleted the search from ${formatDate(pendingDelete.created_at)}.`);
    } catch (err) {
      show(err.message || "Couldn't delete this search.", { tone: "error" });
    } finally {
      setDeletingId(null);
      setPendingDelete(null);
    }
  }

  return (
    <main className="container">
      <div className="page-head">
        <div>
          <h1>Search history</h1>
          <p className="lede">
            Open a search to revisit its companies, saved enrichment, rankings and message drafts.
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
                    <td className="nowrap">
                      <Link to={`/history/${run.id}`}>Open full history</Link>{" "}
                      <button
                        className="link-button danger"
                        disabled={deletingId === run.id}
                        onClick={() => setPendingDelete(run)}
                      >
                        {deletingId === run.id ? "Deleting…" : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete this search?"
        body={`This deletes the search from ${pendingDelete ? formatDate(pendingDelete.created_at) : ""} and its saved enrichment, rankings and message drafts. This cannot be undone.`}
        busy={deletingId !== null}
        onClose={() => setPendingDelete(null)}
        onConfirm={handleDelete}
        confirmLabel="Delete search"
      />
    </main>
  );
}
