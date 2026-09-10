import { useEffect, useState } from "react";
import { api } from "../api/client.js";

// The visible surface of ARCHITECTURAL-CONTRACT.md §2.1/§2.2 (Human
// Authority, Suggested by Default): an escalated message never runs
// unattended -- it renders as this card, not an ordinary chat bubble,
// until the user explicitly approves or rejects it. This must never be
// visually demoted to look like an optional or skippable step
// (docs/architecture/DESKTOP-APPLICATION.md).
export default function ApprovalCard({ taskId, contextPaths, content }) {
  const [flow, setFlow] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);
  // Live AI provider output while an approved stage is streaming
  // (Phase 4/ADR-013 follow-up); null when not currently streaming, ""
  // once streaming starts but before the first delta arrives.
  const [streamingOutput, setStreamingOutput] = useState(null);

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  async function refresh() {
    try {
      setFlow(await api.getRequestFlow(taskId));
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  async function handleApprove() {
    setBusy(true);
    setError(null);
    setStreamingOutput("");
    try {
      await api.approveRequestStream(taskId, contextPaths, "Approved from OrchAI Desktop", {
        onDelta: (delta) => {
          if (delta) setStreamingOutput((current) => (current ?? "") + delta);
        },
      });
      await refresh();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
      setStreamingOutput(null);
    }
  }

  async function handleReject() {
    if (!flow?.suggestion?.suggestion_id) return;
    setBusy(true);
    setError(null);
    try {
      await api.rejectSuggestion(flow.suggestion.suggestion_id);
      await refresh();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  const suggestion = flow?.suggestion;
  // SuggestionEngine.suggest_next() now reuses a task's existing PRESENTED
  // suggestion instead of generating a duplicate on every advance/approve
  // call, so at most one PRESENTED suggestion ever exists per task and
  // this field is trustworthy again (see the "Implementation Note" in
  // docs/decisions/ADR-011-CHAT-FIRST-REQUEST-INTERFACE.md).
  const pending = suggestion?.status === "PRESENTED";

  return (
    <div className="approval-card">
      <div className="approval-card-header">Task escalada — aprovação necessária</div>
      <div className="approval-card-content">{content}</div>

      {flow && (
        <>
          <div>
            <span className="badge">estado: {flow.task?.state}</span>
            {suggestion && (
              <span className="badge">
                sugestão: {suggestion.suggested_role} → {suggestion.suggested_action}
              </span>
            )}
            {suggestion && <span className="badge">status: {suggestion.status}</span>}
          </div>

          {suggestion?.rationale && <div className="subtitle">{suggestion.rationale}</div>}

          {pending ? (
            <div className="approval-card-actions">
              <button className="btn" onClick={handleApprove} disabled={busy}>
                Aprovar
              </button>
              <button className="btn secondary" onClick={handleReject} disabled={busy}>
                Rejeitar
              </button>
            </div>
          ) : (
            <div className="subtitle">
              {flow.status === "PENDING_SUGGESTION"
                ? "Aguardando a próxima sugestão…"
                : `Fluxo: ${flow.status}`}
            </div>
          )}

          {streamingOutput !== null && (
            <pre className="approval-card-stream">{streamingOutput || "Executando…"}</pre>
          )}

          <button
            className="btn secondary"
            style={{ marginTop: "0.5rem" }}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? "Ocultar" : "Ver"} fluxo completo
          </button>
          {expanded && <pre className="approval-card-flow">{JSON.stringify(flow, null, 2)}</pre>}
        </>
      )}

      {error && <div className="error">{error}</div>}
    </div>
  );
}
