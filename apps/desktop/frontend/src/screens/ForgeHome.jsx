import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { STREAMING_PLACEHOLDER_ID, useConversationChat } from "../hooks/useConversationChat.js";
import ApprovalCard from "./ApprovalCard.jsx";

export default function ForgeHome({ project, module, onBack }) {
  const chat = useConversationChat(module.module_id, project.id);
  const [contextPathsDraft, setContextPathsDraft] = useState("");
  const [escalating, setEscalating] = useState(false);
  // Context paths used to escalate a message aren't part of the persisted
  // Message (they're an orchestration input, not conversation state), so
  // they're kept client-side, keyed by the linked task, and reused when
  // approving the same task (ADR-011's PLAN stage needs them again).
  const [contextPathsByTask, setContextPathsByTask] = useState({});
  const transcriptRef = useRef(null);

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [chat.messages]);

  function parseContextPaths() {
    return contextPathsDraft
      .split(",")
      .map((path) => path.trim())
      .filter(Boolean);
  }

  async function handleEscalate() {
    const content = chat.draft.trim();
    if (!content || !chat.activeId || escalating) return;

    setEscalating(true);
    chat.setError(null);
    chat.setDraft("");
    const contextPaths = parseContextPaths();
    try {
      const payload = await api.escalateMessage(chat.activeId, content, contextPaths);
      chat.setMessages((current) => [...current, payload.message]);
      if (payload.message.linked_task_id) {
        setContextPathsByTask((current) => ({
          ...current,
          [payload.message.linked_task_id]: contextPaths,
        }));
      }
    } catch (err) {
      chat.setError(String(err.message || err));
    } finally {
      setEscalating(false);
    }
  }

  function handleComposerKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      chat.handleSend();
    }
  }

  const busy = chat.sending || escalating;

  return (
    <div className="screen" style={{ padding: 0 }}>
      <div className="chat-layout">
        <aside className="chat-sidebar">
          <button className="btn secondary" onClick={onBack}>
            ← Módulos
          </button>
          <button className="btn" onClick={chat.handleNewConversation}>
            Nova Conversa
          </button>
          <div className="card-list">
            {chat.conversations.map((conversation) => (
              <div
                key={conversation.conversation_id}
                className={
                  "card" + (conversation.conversation_id === chat.activeId ? " active" : "")
                }
                onClick={() => chat.setActiveId(conversation.conversation_id)}
              >
                <div className="card-title">
                  {conversation.title || "Conversa sem título"}
                </div>
              </div>
            ))}
            {chat.conversations.length === 0 && (
              <div className="empty">Nenhuma conversa ainda.</div>
            )}
          </div>
        </aside>

        <div className="chat-main">
          <div className="chat-header">
            <div>
              <h1>{module.name}</h1>
              <div className="subtitle">{project.name}</div>
            </div>
          </div>

          <div className="chat-transcript" ref={transcriptRef}>
            {!chat.activeId && (
              <div className="empty">Crie uma conversa para começar.</div>
            )}
            {chat.messages.map((message) =>
              message.linked_task_id ? (
                <ApprovalCard
                  key={message.message_id}
                  taskId={message.linked_task_id}
                  contextPaths={contextPathsByTask[message.linked_task_id] || []}
                  content={message.content}
                />
              ) : (
                <div
                  key={message.message_id}
                  className={
                    "message " +
                    (message.role === "USER" ? "user" : "assistant") +
                    (message.status === "FAILED" ? " failed" : "")
                  }
                >
                  {message.status === "FAILED" ? `Erro: ${message.error}` : message.content}
                  {message.role === "ASSISTANT" && message.status === "COMPLETE" && (
                    <div className="message-meta">{message.model_id}</div>
                  )}
                </div>
              ),
            )}
            {chat.sending &&
              !chat.messages.some((m) => m.message_id === STREAMING_PLACEHOLDER_ID) && (
                <div className="message assistant">Pensando…</div>
              )}
          </div>

          {chat.error && (
            <div className="error" style={{ padding: "0 1.5rem" }}>
              {chat.error}
            </div>
          )}

          <div className="chat-composer" style={{ flexDirection: "column", gap: "0.5rem" }}>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <textarea
                rows={2}
                placeholder={chat.activeId ? "Digite uma mensagem…" : "Selecione uma conversa"}
                value={chat.draft}
                disabled={!chat.activeId || busy}
                onChange={(event) => chat.setDraft(event.target.value)}
                onKeyDown={handleComposerKeyDown}
              />
              <button
                className="btn"
                onClick={chat.handleSend}
                disabled={!chat.activeId || busy || !chat.draft.trim()}
              >
                Enviar
              </button>
              <button
                className="btn secondary"
                onClick={handleEscalate}
                disabled={!chat.activeId || busy || !chat.draft.trim()}
                title="Cria uma Task real (PLAN → IMPLEMENT → ...), sujeita a aprovação explícita"
              >
                Executar como Task
              </button>
            </div>
            <input
              type="text"
              placeholder="Contexto para a Task (arquivos, separados por vírgula) — opcional"
              value={contextPathsDraft}
              disabled={!chat.activeId || busy}
              onChange={(event) => setContextPathsDraft(event.target.value)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
