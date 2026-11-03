import { useState } from "react";
import { api } from "../../api/client";

/**
 * Make a real service call to validate the configuration before running a full job.
 *
 * `target` is a section name ("llm", "search", "data_source"); the backend
 * knows which service to call for each one.
 */
export default function TestButton({ target, label, needsSave = false }) {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setResult(null);
    try {
      setResult(await api.testConnection(target));
    } catch (err) {
      setResult({ ok: false, message: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="test-row">
      <button type="button" className="secondary" onClick={run} disabled={busy || needsSave}>
        {busy ? "Testing…" : label}
      </button>
      {needsSave && <span className="muted small-note">Save settings before testing. Tests use the saved configuration.</span>}
      {!needsSave && result && (
        <span className={result.ok ? "test-ok" : "test-fail"}>
          {result.ok ? "✓" : "✕"} {result.message}
          {result.detail ? ` — ${result.detail}` : ""}
        </span>
      )}
    </div>
  );
}
