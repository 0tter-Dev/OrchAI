// Same-origin backend calls (the frontend is served by the same FastAPI
// process it talks to, under /app/ -- see ADR-017), so plain relative
// API paths are enough; no base URL or CORS configuration is needed.

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  health: () => request("/health"),
  listModules: () => request("/modules"),
  projectReadiness: (projectRoot) =>
    request(`/projects/readiness?project_root=${encodeURIComponent(projectRoot)}`),
  lookupProject: (projectRoot) =>
    request(`/projects/lookup?project_root=${encodeURIComponent(projectRoot)}`),
  registerProject: (projectRoot) =>
    request("/projects", {
      method: "POST",
      body: JSON.stringify({ project_root: projectRoot }),
    }),
  listConversations: (moduleId, projectId) =>
    request(
      `/conversations?module_id=${encodeURIComponent(moduleId)}` +
        (projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""),
    ),
  createConversation: (moduleId, projectId, title = "") =>
    request("/conversations", {
      method: "POST",
      body: JSON.stringify({ module_id: moduleId, project_id: projectId, title }),
    }),
  listMessages: (conversationId) => request(`/conversations/${conversationId}/messages`),
  streamMessage: (conversationId, content, model, handlers) =>
    streamMessage(conversationId, content, model, handlers),
  escalateMessage: (conversationId, content, contextPaths = []) =>
    request(`/conversations/${conversationId}/escalate`, {
      method: "POST",
      body: JSON.stringify({ content, context_paths: contextPaths }),
    }),
  getRequestFlow: (taskId) => request(`/requests/${taskId}/flow`),
  approveRequest: (taskId, contextPaths = [], reason = "Approved from OrchAI Desktop") =>
    request(`/requests/${taskId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason, context_paths: contextPaths }),
    }),
  rejectSuggestion: (suggestionId) =>
    request(`/suggestions/${suggestionId}/reject`, { method: "POST" }),
  listAttachments: (projectId) => request(`/projects/${projectId}/attachments`),
  metricsSummary: (projectId, groupBy = [], since, until) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", projectId);
    if (groupBy.length > 0) params.set("group_by", groupBy.join(","));
    if (since) params.set("since", since);
    if (until) params.set("until", until);
    return request(`/metrics/summary?${params.toString()}`);
  },
  listAudit: (projectId, limit = 20) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", projectId);
    params.set("limit", String(limit));
    return request(`/audit?${params.toString()}`);
  },
};

// POST-based Server-Sent Events (ADR-013, Phase 4): the browser's built-in
// EventSource only supports GET, so a streamed chat reply is consumed by
// reading the response body ourselves and splitting it on the SSE
// "\n\n" event separator. Each event is one `data: <json>\n\n` line, with
// `type` discriminating "user_message" | "delta" | "done" | "error"
// (see interfaces/api/main.py::_serialize_stream_event).
async function streamMessage(conversationId, content, model, { onUserMessage, onDelta, onDone, onError } = {}) {
  const response = await fetch(`/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, model }),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const dataLine = rawEvent.split("\n").find((line) => line.startsWith("data:"));
      if (!dataLine) continue;

      const payload = JSON.parse(dataLine.slice("data:".length).trim());
      if (payload.type === "user_message") onUserMessage?.(payload.message);
      else if (payload.type === "delta") onDelta?.(payload.content);
      else if (payload.type === "done") onDone?.(payload.message);
      else if (payload.type === "error") onError?.(payload.error, payload.message);
    }
  }
}
