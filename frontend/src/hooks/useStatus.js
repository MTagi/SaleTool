import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";

/**
 * What is configured and what data exists, in one call.
 *
 * Pages use this to say up front "you need an LLM key first" instead of letting
 * someone fill a whole form and discover it from a 400 on submit.
 *
 * A failure here is never fatal: `status` stays null and callers fall back to
 * showing the form. Blocking the UI because a status probe failed would be a
 * worse bug than the one this prevents.
 */
export function useStatus() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    return api
      .getStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, []);

  // refresh giữ nguyên tham chiếu (useCallback []) nên effect này chỉ chạy
  // một lần — không cần bản sao thứ hai của cùng đoạn fetch.
  useEffect(() => {
    refresh();
  }, [refresh]);

  return { status, loading, refresh };
}
