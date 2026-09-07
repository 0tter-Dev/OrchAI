# ADR-014 --- Conversation and Message Domain Model

## Status

Accepted --- Design only; implementation is follow-up work (OrchAI
Desktop Phase 3, see `docs/architecture/DESKTOP-APPLICATION.md`).

## Context

OrchAI has no notion of a conversation or a message anywhere in the
codebase today --- confirmed by direct inspection of `domain/` and
`application/`, which contain no such concept. The closest existing
thing is the Chat-First Request Interface (ADR-011): `POST /requests`
maps one-to-one onto a `Task`, and `GET /requests/{id}/flow` renders
that Task's full orchestration trace. That model works because a
Request and a Task share the same cardinality and the same lifecycle:
one bounded unit of AI-assisted work, from creation to a terminal
state.

A desktop chat product needs something structurally different: a
`Conversation` is multi-turn and long-lived, most of the messages a
user sends in it are not requests to perform a bounded unit of
work ("what does this function do?", "explain this error", ordinary
back-and-forth) and should not need a `Task`/`Authorization`/
`Execution` behind every single one, and the conversation's own history
must be persisted and retrievable independently of any one Task's
lifecycle. Forcing every message through the `/requests` projection
would require creating a `Task` per message, which distorts the
documented meaning of `Task` in `ARCHITECTURAL-CONTRACT.md` §2.8 ("a
task defines the scope and intent of a unit of work") and would flood
the audit/authorization machinery with entries for messages that never
needed authorization in the first place.

The central risk this ADR must close: `ARCHITECTURAL-CONTRACT.md` §2.2
establishes that "a suggestion is never an implicit authorization" ---
the system must not silently escalate from information/suggestion to
actual execution. A chat interface that classified user intent
automatically ("this message sounds like an implementation request,
let me open a Task for it") would be a *more* aggressive escalation of
authority than the suggestion mechanism the contract already
constrains, since it would decide, on the system's own initiative and
without the deliberate friction of a suggestion-and-approval step, that
a conversational message should become a unit of real orchestrated
work.

## Decision

Introduce `Conversation` and `Message` as a new, independent bounded
context --- `domain/conversations/`, `application/conversations/`,
persisted via `infrastructure/persistence/...conversations` --- rather
than modeling conversation as another projection over `Task`.

1. **Domain shape.**

   ```text
   domain/conversations/entities.py
     Conversation: id (ConversationId), module_id (ModuleId),
                   project_id (ProjectId | None), title,
                   created_at, archived: bool
     Message: id (MessageId), conversation_id, role (USER|ASSISTANT|SYSTEM),
              content, created_at, provider_name, model_id (ModelId | None),
              linked_task_id (TaskId | None),
              linked_execution_id (ExecutionId | None),
              resource_usage (reuses the existing ResourceUsage shape
              from domain/executions/entities.py)
   ```

   `ConversationId`/`MessageId` are added to `domain/identifiers.py`
   following the existing `Identifier` pattern. `Message` does not need
   a state machine of `Task`/`Execution`'s complexity --- its lifecycle
   is the trivial `PENDING → STREAMING → COMPLETE | FAILED`, tracked as
   a plain enum, not a `StateMachine`-governed aggregate.

2. **Message-to-Task escalation is always explicit, never inferred.**
   A message becomes a real `Task` only when the user deliberately
   triggers it --- a dedicated UI action (an "Execute as Task" control
   on the composer) or an explicit slash-command (`/plan`,
   `/implement`, `/review`, ...) that maps directly to a known
   `(role, action)` pair. When that happens, OrchAI calls the existing
   `/requests` machinery (ADR-011) exactly as any other caller would ---
   no new lifecycle, no shortcut around authorization, policy, or
   suggestion evaluation --- and records the resulting `task_id` /
   `execution_id` on the triggering `Message` via `linked_task_id` /
   `linked_execution_id`. There is no automatic intent classifier in
   this design. If automatic classification is proposed later, it must
   itself surface only as a *suggestion* (`PENDING_SUGGESTION`, subject
   to the same explicit-approval boundary as any other suggestion) ---
   never as a direct, silent Task creation --- and that would be its own
   future ADR, not an extension of this one.

3. **New persistence and endpoints.** A new migration,
   `infrastructure/persistence/db/migrations/0009_conversations.sql`,
   follows the existing hand-rolled, dialect-portable raw-SQL convention
   used by `0001`--`0008`. New repositories
   (`application/conversations/ports.py`:
   `ConversationRepository`, `MessageRepository`) get in-memory and
   SQLAlchemy implementations mirroring the existing pattern for
   `Task`/`Execution`. New endpoints in `interfaces/api/main.py`:

   ```text
   POST /conversations                    {module_id, project_id?, title?}
   GET  /conversations?module_id=&project_id=
   GET  /conversations/{id}
   POST /conversations/{id}/messages      send a user message; may stream (ADR-013)
   GET  /conversations/{id}/messages
   ```

   `POST /conversations/{id}/messages` is additive: it does not replace
   `POST /requests`. When a message escalates to a Task (point 2
   above), the conversations application service invokes the same
   internal logic backing `/requests`, so the ADR-011 invariant ---
   "authorization, policy evaluation, execution mode enforcement, and
   suggestion boundaries apply identically through every interface
   path" --- holds for messages exactly as it holds for direct
   `/requests` calls.

## Rationale

- **A new bounded context, not a `Task` projection**: `Task` and
  `Conversation` differ in cardinality (one Task is one bounded unit of
  work; one Conversation is many turns over an unbounded span) and in
  default behavior (every Task implies orchestration machinery;
  most messages do not). Reusing `/requests`'s projection pattern here
  would force every trivial exchange through a mechanism designed for
  bounded, authorizable units of work.
- **Explicit-only escalation preserves the Human Authority principle**
  (`ARCHITECTURAL-CONTRACT.md` §2.1, §2.2): the system continues to
  execute only what is explicitly authorized, and a chat message is
  conversational input, not an implicit work order, until the user says
  otherwise.
- **Reusing `Execution.ResourceUsage` and the `/requests` machinery**
  avoids duplicating token/cost accounting or authorization logic in
  the new bounded context --- `Message` links to `Task`/`Execution`
  records rather than re-implementing what they already track.

## Consequences

Positive:

- conversational UX (persisted, multi-turn chat) becomes possible
  without diluting the meaning of `Task`, `Authorization`, or the audit
  trail;
- the existing `/requests` invariants (ADR-011) remain intact and
  reusable --- a message that does escalate to a Task is
  indistinguishable, from the domain's perspective, from any other
  `/requests` caller;
- most conversational turns (the majority, in a chat product) impose no
  authorization/audit overhead, matching `ARCHITECTURAL-CONTRACT.md`
  §2.9 (context/effort minimization).

Trade-offs:

- a second persistence subsystem (`Conversation`/`Message`) now exists
  alongside `Task`/`Execution`, with its own migration and repository
  pair to maintain;
- the boundary between "just chat" and "real work" is a UI/UX design
  problem as much as a backend one --- the composer/slash-command
  affordance must make the distinction legible to the user, or the
  explicit-trigger guarantee this ADR relies on becomes confusing in
  practice;
- `Message.content` is mutable while streaming (ADR-013), which is a
  different persistence pattern than the largely-immutable-after-completion
  records used elsewhere in the domain (`Execution`, `Authorization`).

## Non-Goals (this ADR)

- Automatic intent classification from message content to Task
  creation --- explicitly excluded, see point 2 above.
- Multi-user conversation sharing or real-time collaborative editing of
  a single conversation --- out of scope for the single-local-user
  desktop model (ADR-016).
- A generic "memory" or cross-conversation context system --- each
  `Conversation` is independent; cross-conversation retrieval is a
  possible future extension, not part of this decision.

## Invariants

1. `Conversation`/`Message` persistence is independent of `Task`;
   deleting or archiving a `Conversation` does not affect any `Task` it
   ever linked to, and vice versa.
2. A `Message` escalates to a `Task` only through an explicit user
   action that maps to a known `(role, action)` pair --- never through
   inferred intent.
3. Escalation reuses the existing `/requests` authorization/policy/
   suggestion path unmodified; it introduces no alternate route to
   `Execution`.

## Implementation Note (Phase 3): the conversational AI provider call

This ADR did not originally specify how a non-escalated message's AI
reply is actually produced. `AIProviderExecutionRequest` (ADR-013,
`application/executions/ports.py`) requires `task_id`, `execution_id`,
`role: RoleName`, and `action: ActionName` -- all mandatory, because
that DTO exists for the Task/Role/Action-bounded pipeline. Most
conversation turns have none of these (per this ADR's core distinction,
§ above), so routing plain chat through that DTO would force fabricated
values and reintroduce the exact vocabulary distortion this ADR exists
to avoid.

Implemented instead: a second, narrower port,
`ConversationAIProviderPort.complete()`
(`application/conversations/ports.py`), taking only a model string, a
system prompt, and a plain `(role, content)` turn history --- no
Task/Role/Action concept at all. `infrastructure/ai/litellm_provider.py`'s
`LiteLLMProvider` implements both `AIProviderPort` and
`ConversationAIProviderPort` (one adapter, two application-facing
shapes); `infrastructure/ai/stub.py`'s `StubAIProviderAdapter` does the
same for tests. `ConversationService.send_message()`
(`application/conversations/service.py`) calls `complete()` directly ---
never `execute()` --- for every non-escalated message. Escalation
(Phase 5) is unaffected: an escalated message still goes through
`/requests` and therefore `AIProviderPort.execute()`/`execute_stream()`
exactly as ADR-011/ADR-013 describe.

## Supersedes

None. Extends ADR-011 (Chat-First Request Interface) by adding a
persistent conversational layer above it, and depends on ADR-013 for
how streaming responses populate `Message.content` incrementally.
