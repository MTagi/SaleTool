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

  useEffect(() => {
    let cancelled = false;
    api
      .getStatus()
      .then((data) => !cancelled && setStatus(data))
      .catch(() => !cancelled && setStatus(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return { status, loading, refresh };
}
