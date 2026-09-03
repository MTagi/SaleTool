import { useState } from "react";
import { api } from "../../api/client";

/**
 * Gọi thật tới dịch vụ để kiểm tra cấu hình, trước khi chạy nguyên một job.
 *
 * `target` là tên mục ("llm", "search", "data_source") — backend tự biết phải
 * gọi gì cho từng cái.
 */
export default function TestButton({ target, label }) {
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
      <button type="button" className="secondary" onClick={run} disabled={busy}>
        {busy ? "Testing…" : label}
      </button>
      {result && (
        <span className={result.ok ? "test-ok" : "test-fail"}>
          {result.ok ? "✓" : "✕"} {result.message}
          {result.detail ? ` — ${result.detail}` : ""}
        </span>
      )}
    </div>
  );
}
