import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

const POLL_INTERVAL_MS = 2000;

/**
 * Polls an enrichment job until it reaches a terminal state.
 * Pass a falsy jobId to disable polling entirely.
 */
export function useEnrichJob(jobId) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return undefined;
    }

    let cancelled = false;

    async function poll() {
      try {
        const data = await api.getEnrichJob(jobId);
        if (cancelled) return;

        setJob(data);
        if (data.status === "pending" || data.status === "running") {
          timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Couldn't read job status.");
      }
    }

    poll();

    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [jobId]);

  return { job, error };
}
