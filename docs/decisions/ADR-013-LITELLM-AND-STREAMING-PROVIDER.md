# ADR-013 --- LiteLLM Provider Adapter and Streaming Execution

## Status

Accepted --- Implemented (OrchAI Desktop Phases 3 and 4, see
`docs/architecture/DESKTOP-APPLICATION.md`): `LiteLLMProvider`
(`infrastructure/ai/litellm_provider.py`) implements `execute()`
(Phase 3) and `execute_stream()` (Phase 4) on `AIProviderPort`, plus
`complete()`/`complete_stream()` on the separate
`ConversationAIProviderPort` (ADR-014). `execute_stream()` itself has no
caller yet -- nothing routes a Task-bounded execution through it, since
that only happens once Forge messages escalate to real Tasks (Phase 5)
-- but it is implemented and tested to the same contract Phase 4's
actual, wired-up streaming feature (`ConversationAIProviderPort.complete_stream()`,
consumed by `POST /conversations/{id}/messages` as SSE) already
exercises end-to-end.

## Context

`AIProviderPort` (`src/orchai/application/executions/ports.py`) is
implemented today by two hand-rolled adapters,
`infrastructure/ai/ollama.py` and `infrastructure/ai/openai_codex.py`,
each making a single blocking HTTPX call to one provider's HTTP API and
returning a complete `AIProviderExecutionResult`. `docs/TO-DO.md`
Priority 2 already named the next planned step as writing a third,
equally manual `infrastructure/ai/anthropic.py` adapter, and separately
flagged streaming as "a bigger architectural change" deserving its own
ADR before implementation (`docs/architecture/ADAPTER-CONTRACTS.md`:
"the exact interface may evolve").

The product direction now requires OrchAI to work as a desktop chat
application (`docs/architecture/DESKTOP-APPLICATION.md`) offering the
user a live choice of local and cloud models across multiple providers,
with responses appearing incrementally the way every comparable chat
product (ChatGPT, Claude, Cursor) already does. Writing and maintaining
one hand-rolled HTTPX adapter per provider does not scale to that goal,
and the current `execute()`-only contract cannot express incremental
output at all.

## Decision

Adopt LiteLLM as the concrete implementation behind a new
`infrastructure/ai/litellm_provider.py` adapter, and extend
`AIProviderPort` with a streaming execution method.

1. **One adapter, many providers.** `LiteLLMProvider` implements the
   existing `AIProviderPort` contract (`capabilities()`,
   `validate_request()`, `healthcheck()`, `execute()`, `cancel()`) using
   LiteLLM's unified `completion`/`acompletion` interface, which already
   covers OpenAI, Anthropic, Gemini, Ollama, and other OpenAI-compatible
   local runtimes behind one calling convention. `ollama.py` and
   `openai_codex.py` are retired once `LiteLLMProvider` reaches parity
   with their existing test coverage; `stub.py` is kept as the
   deterministic test/no-op provider. This makes the previously planned
   manual `anthropic.py` adapter (`docs/TO-DO.md` Priority 2.1)
   unnecessary --- LiteLLM already speaks to Anthropic's API.
2. **Provider selection stays declarative.** `AIProviderSettings`
   (`infrastructure/configuration/settings.py`) keeps a `provider`
   setting, but its role narrows to selecting the *default* model
   string LiteLLM should target (e.g. `"ollama/qwen2.5-coder:latest"`,
   `"anthropic/claude-..."`) rather than selecting between adapter
   classes; `provider_from_settings()` (`bootstrap/runtime.py`) now
   returns a single `LiteLLMProvider` in every non-`stub` case.
3. **Streaming is a new method on the same port, not a replacement.**

   ```python
   @dataclass(frozen=True, slots=True)
   class AIProviderStreamChunk:
       delta: str
       finished: bool = False
       finish_reason: str | None = None
       input_tokens: int | None = None
       output_tokens: int | None = None

   class AIProviderPort(Protocol):
       ...
       def execute_stream(
           self, request: AIProviderExecutionRequest,
       ) -> AsyncIterator[AIProviderStreamChunk]:
           """Streaming variant of execute(); yields incremental output."""
   ```

   `execute()` remains mandatory and unchanged in meaning --- it is still
   what `AUTOMATIC`-mode, non-interactive, and CLI callers use when only
   the final result matters. `execute_stream()` is additive; `stub.py`
   gains a trivial fake-streaming implementation (yields the whole
   response as one or two chunks) so it can back tests without a real
   provider.
4. **No change to the `Execution` domain state machine.** Streaming is a
   concern of *how* the application layer calls the provider, not a new
   state. `ExecutionEngine`/`ExecutionService`
   (`application/executions/{engine,service}.py`) call
   `execution.transition_to(STARTED, ...)` once, drain the
   `AsyncIterator`, accumulate `AIProviderStreamChunk.delta` and token
   counts, and call `execution.complete(result, ...)` exactly once when
   the stream ends --- `Execution` still records one atomic result, as
   `ARCHITECTURAL-CONTRACT.md` §2.15 (auditability) requires. The
   incremental text itself is surfaced to callers through the
   `Conversation`/`Message` domain (ADR-014), not through `Execution`.
5. **Transport to external clients is Server-Sent Events (SSE), not a
   WebSocket**, because the flow is strictly server-to-client. This
   confirms the direction already named as a "Future Consideration" in
   `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` §9. The concrete
   endpoint that streams (`POST /conversations/{id}/messages`) is
   specified in ADR-014, not here --- this ADR governs the provider
   boundary only.

## Rationale

- **LiteLLM over N hand-rolled adapters**: reduces the marginal cost of
  supporting a new provider from "write and test a new HTTPX adapter"
  to "add a model string," and provides retry/backoff behavior for free
  --- closing `docs/TO-DO.md` Priority 2.3 as a side effect, since a
  bespoke retry layer is no longer needed on top of a hand-rolled
  adapter.
- **`AIProviderPort` unchanged in shape, extended in surface**: per
  `ADAPTER-CONTRACTS.md`'s own note that "the exact interface may
  evolve," this is an additive extension, not a redesign --- every
  existing invariant (bounded request, no unrestricted project access,
  provider-independent DTOs, isolation of provider SDK types to
  infrastructure) is preserved unchanged.
- **Streaming does not touch `Execution`'s state machine**: keeping the
  atomic "one execution, one result" model intact avoids a much larger
  change to the domain, audit records, and metrics aggregation, all of
  which already assume a single terminal `ExecutionResult`.
- **SSE over WebSocket**: simpler, unidirectional, and already the
  transport every major hosted chat API (OpenAI, Anthropic) uses for
  the same purpose; it is also the transport already anticipated by the
  existing chat-first documentation.

## Consequences

Positive:

- one new adapter replaces two existing ones and pre-empts a third,
  while adding streaming, retries, and broad provider coverage;
- `AIProviderPort` remains the single seam between domain/application
  code and any provider SDK --- LiteLLM itself never appears above
  `infrastructure/ai/`;
- execution cancellation (`docs/TO-DO.md` Priority 3.2) becomes cheap to
  implement once streaming exists: `cancel()` simply stops draining the
  `AsyncIterator` and forwards LiteLLM's own cancellation where
  supported, instead of needing to interrupt a single blocking call.

Trade-offs:

- LiteLLM becomes a new third-party dependency with its own release
  cadence and transitive dependencies; version pinning and periodic
  review are required, consistent with how `ruff` is already pinned in
  `docs/architecture/TECHNOLOGY-STACK.md`.
- `ollama.py` and `openai_codex.py`, along with their existing unit
  tests, are retired --- this is a deliberate deletion, not a parallel
  maintenance burden, once `LiteLLMProvider` has equivalent test
  coverage.
- Provider-specific quirks are now one layer further from OrchAI's own
  code (inside LiteLLM), which trades direct control for breadth of
  coverage; `validate_request()`/`healthcheck()` remain OrchAI's own
  responsibility and are not delegated to LiteLLM.

## Invariants

1. `AIProviderPort` remains the only seam between application code and
   any AI provider SDK; LiteLLM's own types never appear in `domain/` or
   `application/`.
2. `execute()` continues to return one complete, atomic result; adding
   `execute_stream()` does not change that contract.
3. `Execution`'s state machine records exactly one terminal result per
   execution, streamed or not.
4. Streaming transport is SSE at the interface layer; no WebSocket
   dependency is introduced.

## Implementation Note (Phase 4): no cost estimate for streamed replies

`AIProviderExecutionResult.estimated_cost`/`ConversationCompletionResult.estimated_cost`
(non-streaming) are computed via `litellm.completion_cost()` against the
complete response object. Streaming delivers usage totals (prompt/
completion tokens) in a final chunk when
`stream_options={"include_usage": True}` is set, but not a cost figure
--- computing one accurately would require reassembling the full
response from every chunk first (LiteLLM's `stream_chunk_builder`).
This was judged out of scope for Phase 4, whose goal was the streaming
transport itself: `AIProviderStreamChunk`/`ConversationStreamChunk`
carry `input_tokens`/`output_tokens` but no cost field, and a message
completed from a stream always has `resource_usage.estimated_cost is
None`. Reassembling the full response for cost estimation is a
plausible, narrowly-scoped future addition, not a design change.

## Supersedes

None. Extends ADR-005 (Local/Cloud Provider Boundary) and
`docs/architecture/ADAPTER-CONTRACTS.md`'s AI Provider Adapter section.
Supersedes the "Anthropic adapter" item of `docs/TO-DO.md` Priority 2.1,
which is removed from the backlog as no longer applicable.
