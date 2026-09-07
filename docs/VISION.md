# OrchAI --- Vision

## Purpose

This document is the short, product-level narrative of what OrchAI is
for and where it is going. It does not restate architectural rules
(`ARCHITECTURAL-CONTRACT.md`), current implementation state
(`STATUS.md`), or backlog (`TO-DO.md`) --- it exists because none of
those documents answer "why does this exist, and for whom," and no such
document existed before this one.

## What OrchAI Is

OrchAI is a Windows desktop application for working with AI --- visually
and in day-to-day use, comparable to Claude Desktop, ChatGPT, or
Cursor: a native window, a project/folder picker, persistent
conversations, and models chosen per conversation from both local and
cloud providers.

What sets it apart is not the chat surface --- it is what sits behind
it. Every AI-assisted action that touches a real project runs through
an orchestration core that keeps a human in control: a proposed change
is a suggestion until explicitly approved, every execution is
authorized and audited, and roles/actions/models stay independent and
swappable rather than hardwired to one provider or one workflow. A
casual question in the chat is answered like any chat product would;
asking OrchAI to actually change a project surfaces that difference
immediately, as an explicit approval step in the conversation itself,
not as a separate tool you have to switch to.

## Structure: A General Layer, and Modules

OrchAI's general layer provides what every use of the product shares:
multi-provider chat, conversation and project/folder management, a
local user profile, and metrics/audit --- with plugins, connectors, and
skills planned as future extensions of this same layer.

**Modules** are specialized experiences within that layer, each with
its own default system prompt, suggested models, and capabilities ---
analogous to how a general chat product and a code-specialized one can
coexist as distinct experiences on the same foundation:

- **Forge** --- for code. Connects to a local project or folder to
  analyze, document, maintain, and continue its development, using
  OrchAI's existing task/authorization/execution pipeline.
- **Studio** --- for multimedia planning and generation. Connects to
  folders, attaches and reads files, and helps plan and produce visual,
  audio, or written assets.

The module boundary is deliberately open-ended: the architecture is
built so a third, fourth, or later module can be added without
redesigning the orchestration core underneath it. See
`docs/architecture/MODULES.md` for how a module is defined and added.

## Why This Direction

OrchAI's orchestration core --- Task/Role/Action/Execution/Authorization,
audit, metrics, project adapters --- was built first, as an API-first
backend. That core turned out to be the right foundation for something
larger: instead of asking a future, unspecified client to consume it,
OrchAI becomes the client itself, built as the desktop product it was
always meant to be reached through, with the orchestration core as its
engine rather than as its entire product.

## Where To Go Next

- `docs/architecture/DESKTOP-APPLICATION.md` --- how the desktop shell
  is built and phased.
- `docs/architecture/MODULES.md` --- how Forge, Studio, and future
  modules are defined.
- `docs/decisions/INDEX.md` --- the ADRs recording why each major choice
  (LiteLLM, conversations, modules, single-user identity, the desktop
  shell itself) was made.
- `docs/STATUS.md` --- current implementation state.
- `docs/TO-DO.md` --- current backlog.
