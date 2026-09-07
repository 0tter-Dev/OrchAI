import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { native, onPywebviewReady } from "../api/native.js";

function baseName(path) {
  const normalized = path.replace(/[/\\]+$/, "");
  const parts = normalized.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}

export default function ProjectPicker({ onProjectSelected }) {
  const [recentProjects, setRecentProjects] = useState([]);
  const [nativeReady, setNativeReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    onPywebviewReady(() => {
      setNativeReady(true);
      native.listRecentProjects().then(setRecentProjects).catch(() => {});
    });
  }, []);

  async function connectProject(path) {
    setBusy(true);
    setError(null);
    try {
      const name = baseName(path);
      const lookup = await api.lookupProject(path);
      // `id` is the backend's registered Project UUID, not the filesystem
      // path -- other resources (e.g. conversations) reference a project
      // by this id via a foreign key, never by its path.
      const registered = lookup.found ? lookup.project : await api.registerProject(path);
      const readiness = await api.projectReadiness(path);
      const updatedRecents = await native.addRecentProject(path, name);
      setRecentProjects(updatedRecents);
      onProjectSelected({ id: registered.project_id, path, name, readiness });
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function handleOpenFolder() {
    const path = await native.pickFolder();
    if (path) {
      await connectProject(path);
    }
  }

  return (
    <div className="screen">
      <div className="header">
        <div>
          <h1>OrchAI</h1>
          <div className="subtitle">Escolha uma pasta para iniciar ou continuar um projeto.</div>
        </div>
      </div>

      <button className="btn" onClick={handleOpenFolder} disabled={!nativeReady || busy}>
        {busy ? "Conectando…" : "Abrir Pasta"}
      </button>

      {error && <div className="error">{error}</div>}

      <div>
        <div className="subtitle" style={{ marginBottom: "0.6rem" }}>
          Projetos Recentes
        </div>
        {recentProjects.length === 0 ? (
          <div className="empty">Nenhum projeto recente ainda.</div>
        ) : (
          <div className="card-list">
            {recentProjects.map((entry) => (
              <div key={entry.path} className="card" onClick={() => connectProject(entry.path)}>
                <div className="card-title">{entry.name}</div>
                <div className="card-subtitle">{entry.path}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
