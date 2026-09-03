import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

const POLL_INTERVAL_MS = 2000;

// Trạng thái backend trả về; chỉ hai giá trị này là "chưa xong".
const ACTIVE_STATUSES = ["pending", "running"];

/** Job còn đang chạy? Dùng chung cho cả vòng poll lẫn nút submit của trang. */
export function isJobRunning(job) {
  return Boolean(job) && ACTIVE_STATUSES.includes(job.status);
}

/**
 * Polls a background job until it reaches a terminal state.
 * Pass a falsy jobId to disable polling entirely.
 *
 * `fetchJob` takes the job id and resolves to the job payload — enrichment and
 * matching jobs share the same status/progress shape, so they share this hook.
 *
 * Trả về `running` sẵn để trang không phải tự so chuỗi trạng thái — ba trang đều
 * cần đúng điều kiện đó để khoá nút submit.
 */
export function useJob(jobId, fetchJob) {
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
        const data = await fetchJob(jobId);
        if (cancelled) return;

        setJob(data);
        if (isJobRunning(data)) {
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
    // fetchJob is a stable module-level api method; re-running on it would
    // restart polling on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  return { job, error, running: isJobRunning(job) };
}

export function useEnrichJob(jobId) {
  return useJob(jobId, api.getEnrichJob);
}

export function useMatchJob(jobId) {
  return useJob(jobId, api.getMatchJob);
}

export function useMessageJob(jobId) {
  return useJob(jobId, api.getMessageJob);
}
