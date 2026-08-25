import { createContext, useContext } from "react";
import { useStatus } from "../hooks/useStatus";

const StatusContext = createContext({ status: null, loading: true, refresh: () => {} });

/**
 * One shared readiness probe for the whole app.
 *
 * The workflow strip and the per-page prerequisite banners both need it; a
 * context keeps that to a single request and, more importantly, a single truth —
 * the strip cannot say "catalog done" while the Matching page says it is empty.
 *
 * Call `refresh()` after anything that changes readiness (saving settings,
 * adding a service, finishing a job) so the strip updates without a reload.
 */
export function StatusProvider({ children }) {
  const value = useStatus();
  return <StatusContext.Provider value={value}>{children}</StatusContext.Provider>;
}

export function useAppStatus() {
  return useContext(StatusContext);
}
