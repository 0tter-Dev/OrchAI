import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// Project-scoped metrics summary + recent audit history for the Dashboard
// screen (Phase 7.4). Grouping by role+action covers the current metric
// vocabulary (execution.success/failure/duration/tokens/estimated_cost)
// without needing a per-metric fetch.
export function useDashboardData(projectId) {
  const [summaries, setSummaries] = useState([]);
  const [auditRecords, setAuditRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      api.metricsSummary(projectId, ["role", "action"]),
      api.listAudit(projectId, 20),
    ])
      .then(([metricsPayload, auditPayload]) => {
        if (cancelled) return;
        setSummaries(metricsPayload.summaries);
        setAuditRecords(auditPayload.records);
      })
      .catch((err) => {
        if (!cancelled) setError(String(err.message || err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return { summaries, auditRecords, loading, error };
}
