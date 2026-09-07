import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { STREAMING_PLACEHOLDER_ID, useConversationChat } from "../hooks/useConversationChat.js";

// Phase 6 skeleton (docs/architecture/MODULES.md, ADR-015): chat +
// read-only attachment browsing. No message→Task escalation yet --
// Studio's Role/Action vocabulary question (ADR-015 §5) is deliberately
// left open, so there is no "Executar como Task" affordance here the
// way ForgeHome has one.
export default function StudioHome({ project, module, onBack }) {
  const chat = useConversationChat(module.module_id, project.id);
  const [attachments, setAttachments] = useState([]);
  const [attachmentsError, setAttachmentsError] = useState(null);
  const transcriptRef = useRef(null);

  useEffect(() => {
    api
      .listAttachments(project.id)
      .then((payload) => setAttachments(payload.resources))
      .catch((err) => setAttachmentsError(String(err.message || err)));
  }, [project.id]);

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [chat.messages]);

  function handleComposerKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      chat.handleSend();
    }
  }

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
            {chat.messages.map((message) => (
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
            ))}
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

          <div className="chat-composer">
            <textarea
              rows={2}
              placeholder={chat.activeId ? "Digite uma mensagem…" : "Selecione uma conversa"}
              value={chat.draft}
              disabled={!chat.activeId || chat.sending}
              onChange={(event) => chat.setDraft(event.target.value)}
              onKeyDown={handleComposerKeyDown}
            />
            <button
              className="btn"
              onClick={chat.handleSend}
              disabled={!chat.activeId || chat.sending || !chat.draft.trim()}
            >
              Enviar
            </button>
          </div>
        </div>

        <aside className="attachments-panel">
          <div className="subtitle">Anexos do projeto</div>
          {attachmentsError && <div className="error">{attachmentsError}</div>}
          {attachments.length === 0 && !attachmentsError && (
            <div className="empty">Nenhum arquivo encontrado.</div>
          )}
          {attachments.map((resource) => (
            <div key={resource.resource} className="attachment-item">
              <div className="attachment-name">{resource.resource}</div>
              <div>
                <span className="badge">{resource.metadata.media_type}</span>
                <span className="badge">{resource.metadata.bytes} bytes</span>
              </div>
            </div>
          ))}
        </aside>
      </div>
    </div>
  );
}
