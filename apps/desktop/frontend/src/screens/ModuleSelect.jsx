import { useEffect, useState } from "react";
import { api } from "../api/client.js";

export default function ModuleSelect({ project, onModuleSelected, onOpenDashboard, onBack }) {
  const [modules, setModules] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listModules()
      .then((payload) => setModules(payload.modules))
      .catch((err) => setError(String(err.message || err)));
  }, []);

  const readiness = project.readiness;
  const security = readiness?.security_profile;

  return (
    <div className="screen">
      <div className="header">
        <div>
          <h1>{project.name}</h1>
          <div className="subtitle">{project.path}</div>
        </div>
        <div style={{ display: "flex", gap: "0.6rem" }}>
          <button className="btn secondary" onClick={onOpenDashboard}>
            Dashboard
          </button>
          <button className="btn secondary" onClick={onBack}>
            Trocar Pasta
          </button>
        </div>
      </div>

      {readiness && (
        <div>
          <span className="badge">readiness: {readiness.readiness_level}</span>
          <span className={`badge ${readiness.has_git ? "ok" : "warn"}`}>
            git {readiness.has_git ? "ok" : "ausente"}
          </span>
          <span className={`badge ${readiness.has_tests ? "ok" : "warn"}`}>
            tests {readiness.has_tests ? "ok" : "ausente"}
          </span>
          {security && (
            <span className={`badge ${security.allow_cloud_provider_sharing ? "warn" : "ok"}`}>
              cloud sharing {security.allow_cloud_provider_sharing ? "permitido" : "bloqueado"}
            </span>
          )}
        </div>
      )}

      {error && <div className="error">{error}</div>}

      <div>
        <div className="subtitle" style={{ marginBottom: "0.6rem" }}>
          Escolha um módulo
        </div>
        <div className="card-list">
          {modules.map((module) => (
            <div
              key={module.module_id}
              className="card"
              onClick={() => onModuleSelected(module)}
            >
              <div className="card-title">{module.name}</div>
              <div className="card-subtitle">{module.description}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
