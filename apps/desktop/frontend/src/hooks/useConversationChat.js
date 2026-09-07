import { useEffect, useState } from "react";
import { api } from "../api/client.js";

export const STREAMING_PLACEHOLDER_ID = "__streaming__";

// Shared conversation/streaming-chat state for any module screen
// (ForgeHome, StudioHome, ...): listing/creating conversations, loading
// a conversation's messages, and sending a message with the assistant's
// reply rendered incrementally as it streams in (Phase 4, ADR-013).
export function useConversationChat(moduleId, projectId) {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    refreshConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (activeId) {
      api.listMessages(activeId).then((payload) => setMessages(payload.messages));
    } else {
      setMessages([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  async function refreshConversations(selectId) {
    const payload = await api.listConversations(moduleId, projectId);
    setConversations(payload.conversations);
    if (selectId) {
      setActiveId(selectId);
    } else if (!activeId && payload.conversations.length > 0) {
      setActiveId(payload.conversations[0].conversation_id);
    }
  }

  async function handleNewConversation() {
    setError(null);
    try {
      const conversation = await api.createConversation(moduleId, projectId);
      await refreshConversations(conversation.conversation_id);
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  async function handleSend() {
    const content = draft.trim();
    if (!content || !activeId || sending) return;

    setSending(true);
    setError(null);
    setDraft("");
    try {
      await api.streamMessage(activeId, content, null, {
        onUserMessage: (message) => {
          setMessages((current) => [...current, message]);
        },
        onDelta: (delta) => {
          setMessages((current) => {
            const hasPlaceholder = current.some((m) => m.message_id === STREAMING_PLACEHOLDER_ID);
            if (!hasPlaceholder) {
              return [
                ...current,
                {
                  message_id: STREAMING_PLACEHOLDER_ID,
                  role: "ASSISTANT",
                  status: "STREAMING",
                  content: delta,
                },
              ];
            }
            return current.map((m) =>
              m.message_id === STREAMING_PLACEHOLDER_ID ? { ...m, content: m.content + delta } : m,
            );
          });
        },
        onDone: (message) => {
          setMessages((current) =>
            current.map((m) => (m.message_id === STREAMING_PLACEHOLDER_ID ? message : m)),
          );
        },
        onError: (streamError, message) => {
          setError(streamError);
          setMessages((current) =>
            current.map((m) =>
              m.message_id === STREAMING_PLACEHOLDER_ID
                ? message || { ...m, status: "FAILED", error: streamError }
                : m,
            ),
          );
        },
      });
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setSending(false);
    }
  }

  return {
    conversations,
    activeId,
    setActiveId,
    messages,
    setMessages,
    draft,
    setDraft,
    sending,
    error,
    setError,
    refreshConversations,
    handleNewConversation,
    handleSend,
  };
}
