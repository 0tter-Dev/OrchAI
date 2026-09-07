import { useEffect, useRef } from "react";
import Chart from "chart.js/auto";
import { useDashboardData } from "../hooks/useDashboardData.js";

// Cross-cutting observability screen (Phase 7.4) -- scoped to the
// currently selected project, not a Module (ADR-015's Module concept is
// for AI-workflow experiences like Forge/Studio, not this). Reached from
// a button on ModuleSelect, not from the module switcher.
export default function Dashboard({ project, onBack }) {
  const { summaries, auditRecords, loading, error } = useDashboardData(project.id);
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || summaries.length === 0) return undefined;
    const chart = new Chart(canvasRef.current, {
      type: "bar",
      data: buildExecutionChartData(summaries),
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: "#e6e6e6" } } },
        scales: {
          x: { ticks: { color: "#9aa1ad" }, grid: { color: "#262b36" } },
          y: {
            ticks: { color: "#9aa1ad", precision: 0 },
            grid: { color: "#262b36" },
            beginAtZero: true,
          },
        },
      },
    });
    return () => chart.destroy();
  }, [summaries]);

  return (
    <div className="screen">
      <div className="header">
        <div>
          <h1>Dashboard</h1>
          <div className="subtitle">{project.name}</div>
        </div>
        <button className="btn secondary" onClick={onBack}>
          ← Módulos
        </button>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && <div className="empty">Carregando…</div>}

      {!loading && (
        <>
          <div className="card" style={{ cursor: "default" }}>
            <div className="card-title">Execuções por role/ação</div>
            {summaries.length === 0 ? (
              <div className="empty">Nenhuma métrica registrada ainda.</div>
            ) : (
              <canvas ref={canvasRef} height="140" />
            )}
          </div>

          <div>
            <div className="subtitle" style={{ marginBottom: "0.6rem" }}>
              Resumo de métricas
            </div>
            {summaries.length === 0 ? (
              <div className="empty">Nenhuma métrica registrada ainda.</div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Dimensões</th>
                    <th>Contagem</th>
                    <th>Soma</th>
                    <th>Média</th>
                  </tr>
                </thead>
                <tbody>
                  {summaries.map((summary, index) => (
                    <tr key={index}>
                      <td>{summary.name}</td>
                      <td>{formatDimensions(summary.dimensions)}</td>
                      <td>{summary.count}</td>
                      <td>{summary.sum}</td>
                      <td>{summary.avg.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div>
            <div className="subtitle" style={{ marginBottom: "0.6rem" }}>
              Auditoria recente
            </div>
            {auditRecords.length === 0 ? (
              <div className="empty">Nenhum registro de auditoria ainda.</div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Quando</th>
                    <th>Ator</th>
                    <th>Operação</th>
                    <th>Resultado</th>
                  </tr>
                </thead>
                <tbody>
                  {auditRecords.map((record) => (
                    <tr key={record.audit_id}>
                      <td>{new Date(record.occurred_at).toLocaleString()}</td>
                      <td>{record.actor}</td>
                      <td>{record.operation}</td>
                      <td>{record.outcome}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function formatDimensions(dimensions) {
  const entries = Object.entries(dimensions);
  if (entries.length === 0) return "—";
  return entries.map(([key, value]) => `${key}=${value}`).join(", ");
}

function buildExecutionChartData(summaries) {
  // execution.success/execution.failure are both emitted on every
  // completion (1.0/0.0 depending on outcome, see MetricsEventHandler) --
  // `sum` is the actual count of that outcome, `count` is just "how many
  // executions landed in this bucket" regardless of which way they went.
  const successByKey = new Map();
  const failureByKey = new Map();
  for (const summary of summaries) {
    const key = `${summary.dimensions.role || "?"}:${summary.dimensions.action || "?"}`;
    if (summary.name === "execution.success") successByKey.set(key, summary.sum);
    if (summary.name === "execution.failure") failureByKey.set(key, summary.sum);
  }
  const labels = Array.from(new Set([...successByKey.keys(), ...failureByKey.keys()]));
  return {
    labels,
    datasets: [
      {
        label: "Sucesso",
        data: labels.map((key) => successByKey.get(key) || 0),
        backgroundColor: "#4ade80",
      },
      {
        label: "Falha",
        data: labels.map((key) => failureByKey.get(key) || 0),
        backgroundColor: "#f87171",
      },
    ],
  };
}
