# OrchAI --- Architectural Contract

## 1. Purpose

The OrchAI is a generic, project-independent orchestration system
designed to coordinate AI-assisted software development workflows.

Its primary purpose is to improve the efficiency, control, traceability,
and consistency of AI-assisted development by coordinating tasks,
contexts, roles, actions, models, authorizations, executions,
validations, and project-specific resources.

The OrchAI must remain independent from any specific project,
programming language, development environment, AI provider, AI model, or
user interface.

------------------------------------------------------------------------

## 2. Core Principles

The following principles are architectural invariants of the OrchAI.

### 2.1 Human Authority

The user remains the ultimate authority over the execution of the
workflow.

The system may:

-   execute explicitly authorized operations;
-   evaluate the current state;
-   provide information;
-   identify possible improvements;
-   generate suggestions;
-   request authorization;
-   enforce configured policies.

The system must not silently replace an explicit user decision with its
own decision unless the configured execution mode explicitly permits
that behavior.

------------------------------------------------------------------------

### 2.2 Suggested by Default

The default execution mode is `SUGGESTED`.

In `SUGGESTED` mode, the system:

1.  respects the configuration explicitly provided by the user;
2.  evaluates the current task, state, configuration, available
    resources, and relevant metrics;
3.  may identify a potentially better alternative;
4.  explains the reason for the suggestion;
5.  waits for explicit user authorization before applying the suggested
    change.

A suggestion is never an implicit authorization.

------------------------------------------------------------------------

### 2.3 Explicit Execution Modes

The system supports three execution modes:

-   `MANUAL`
-   `SUGGESTED`
-   `AUTOMATIC`

`MANUAL` follows explicit user instructions without proactive workflow
suggestions.

`SUGGESTED` may propose improvements or next steps but requires explicit
authorization before proceeding.

`AUTOMATIC` may continue execution within explicitly configured
boundaries.

Automatic execution must not be interpreted as unrestricted autonomy.

------------------------------------------------------------------------

### 2.4 Role, Action, and Model Separation

`ROLE`, `ACTION`, and `MODEL` are independent concepts.

-   `ROLE` defines the responsibility assumed by the agent.
-   `ACTION` defines what the agent is expected to perform.
-   `MODEL` defines which AI model or agent performs the action.

They must not be permanently coupled.

A single `ROLE` may use multiple models.

A single `MODEL` may execute multiple actions.

A single `ACTION` may be available to multiple roles where explicitly
configured.

------------------------------------------------------------------------

### 2.5 Project Independence

The OrchAI must not be intrinsically coupled to a specific project.

Projects are external resources connected through a `PROJECT ADAPTER`.

The OrchAI must operate using generic project capabilities and
abstractions rather than project-specific assumptions.

------------------------------------------------------------------------

### 2.6 Project Isolation

Project-specific information must remain isolated from global OrchAI
configuration.

The following concepts belong to the OrchAI:

-   orchestration rules;
-   task lifecycle;
-   execution modes;
-   role definitions;
-   action definitions;
-   model definitions;
-   authorization policies;
-   audit mechanisms;
-   metrics;
-   global configuration.

The following concepts belong to the connected project:

-   source code;
-   business rules;
-   project documentation;
-   development conventions;
-   project contexts;
-   project status;
-   project-specific tools;
-   project-specific workflows and configuration.

------------------------------------------------------------------------

### 2.7 Event-Driven Coordination

The workflow must be represented through events and state transitions.

An event represents an occurrence within the system.

A state represents the current condition of a task.

The State Machine determines whether an event can produce a valid state
transition.

The Event Engine coordinates the propagation and handling of events.

Components must not bypass the defined state transition mechanism to
arbitrarily modify task state.

------------------------------------------------------------------------

### 2.8 Task-Centered Execution

AI work is organized around `TASK` entities.

A task defines the scope and intent of a unit of work.

A task may contain or reference:

-   project;
-   description;
-   current state;
-   role;
-   action;
-   model;
-   context;
-   acceptance criteria;
-   execution mode;
-   authorization information;
-   execution history.

Agents must operate within the scope established by the task and its
authorized context.

------------------------------------------------------------------------

### 2.9 Context Minimization

The system must prefer focused context over indiscriminate context
loading.

Only the context required for the current task should normally be
provided to an agent.

Context may include:

-   project documentation;
-   development guidelines;
-   project status;
-   specific context documents;
-   task-specific information;
-   acceptance criteria;
-   relevant previous execution information.

The system must not assume that providing more context is inherently
better.

------------------------------------------------------------------------

### 2.10 Context Authorization

Context access is controlled.

A task may explicitly authorize specific project contexts.

An agent must not automatically expand its context scope without
authorization when the configured workflow requires explicit approval.

If additional context is identified as potentially necessary, the system
may request authorization.

------------------------------------------------------------------------

### 2.11 Local and Cloud AI Interoperability

The architecture must support both locally hosted and cloud-hosted AI
models.

The orchestration layer must not fundamentally depend on:

-   Ollama;
-   Codex;
-   Claude;
-   a specific cloud provider;
-   a specific local model;
-   a specific development application.

Local and cloud models are execution resources managed through model
abstractions and adapters.

------------------------------------------------------------------------

### 2.12 Cloud Optimization

The architecture is explicitly designed to reduce unnecessary
consumption of limited or paid cloud AI resources.

Local AI may perform supporting activities such as:

-   task preparation;
-   context discovery;
-   context organization;
-   preliminary analysis;
-   validation;
-   testing;
-   documentation maintenance;
-   post-execution analysis.

Cloud AI may therefore focus primarily on high-value implementation or
reasoning tasks when appropriate.

The architecture must not assume that cloud AI is always superior or
that local AI must always be used.

------------------------------------------------------------------------

### 2.13 Authorization Boundaries

The system must distinguish between:

-   what is allowed by policy;
-   what is configured;
-   what is suggested;
-   what has been explicitly authorized;
-   what has actually been executed.

These concepts must not be conflated.

A capability being allowed does not mean that its execution has been
authorized.

A suggestion does not constitute authorization.

An authorization does not constitute successful execution.

------------------------------------------------------------------------

### 2.14 Cross-Role Automation Boundary

In `AUTOMATIC` mode, automatic progression may occur within explicitly
permitted boundaries.

By default, automatic execution must not silently cross from one `ROLE`
to another unless the cross-role transition has been explicitly
configured as authorized beforehand.

For example:

``` text
DEVELOPER → IMPLEMENT
may continue automatically through actions explicitly permitted for the Developer role.

However:

DEVELOPER → QUALITY AGENT
is a role transition and should require explicit authorization unless such cross-role automation has been explicitly configured.
```

------------------------------------------------------------------------

### 2.15 Auditability

All relevant orchestration activity must be traceable.

The system should preserve enough information to determine:

-   what happened;
-   when it happened;
-   which task was involved;
-   which project was involved;
-   which role was used;
-   which action was executed;
-   which model was used;
-   which context was provided;
-   which authorization enabled the execution;
-   what result was produced;
-   what state transition occurred.

Audit information must not depend solely on agent-generated
documentation.

OrchAI must maintain its own authoritative orchestration history.

------------------------------------------------------------------------

### 2.16 Metrics and Observability

The system must collect metrics that allow users to evaluate AI usage
and workflow efficiency.

Metrics may include:

-   model usage;
-   local versus cloud execution;
-   token consumption;
-   execution duration;
-   task completion rates;
-   validation success rates;
-   rework rates;
-   failure rates;
-   model performance;
-   resource utilization;
-   cloud usage limits;
-   estimated cost.

Metrics are informational and may be used to generate suggestions.

Metrics must not silently override user configuration in `MANUAL` or
`SUGGESTED` modes.

------------------------------------------------------------------------

### 2.17 Model Agnosticism

The system must treat AI models as replaceable execution resources.

The architecture must support adding, removing, replacing, or
reconfiguring models without requiring changes to the core orchestration
concepts.

------------------------------------------------------------------------

### 2.18 Environment Agnosticism

The OrchAI may be used through VS Code, desktop applications,
command-line interfaces, web interfaces, or other clients.

VS Code may be a primary client but must not be a fundamental
architectural dependency.

------------------------------------------------------------------------

### 2.19 Extensibility

The architecture must allow future extension without requiring
fundamental changes to the core orchestration model.

Potential future extensions include:

-   additional AI providers;
-   additional model adapters;
-   additional project adapters;
-   additional roles;
-   additional actions;
-   additional execution policies;
-   parallel task execution;
-   advanced scheduling;
-   additional clients;
-   external integrations.

------------------------------------------------------------------------

## 3. Architectural Non-Goals

The OrchAI is not intended to:

-   replace the developer;
-   become an autonomous software development organization;
-   permanently depend on a specific AI provider;
-   permanently depend on VS Code;
-   directly embed project-specific business rules;
-   automatically make unrestricted workflow decisions;
-   replace Git or project version control;
-   become the project's source of business documentation;
-   require cloud AI;
-   require local AI;
-   assume that one model is universally superior;
-   force a single development workflow on every project.

------------------------------------------------------------------------

## 4. Fundamental Relationship

The fundamental execution relationship is:

``` text
TASK
  ↓
ROLE
  ↓
ACTION
  ↓
MODEL
  ↓
EXECUTION
  ↓
RESULT
  ↓
STATE TRANSITION
```

The execution is constrained by:

``` text
PROJECT
CONTEXT
POLICY
AUTHORIZATION
EXECUTION MODE
```

And observed through:

``` text
EVENTS
AUDIT
METRICS
```

------------------------------------------------------------------------

## 5. Architectural Rule

When a future implementation decision conflicts with this contract, the
implementation must not silently redefine the architecture.

The conflict must be identified and explicitly resolved through an
architectural decision before the implementation changes the established
contract.

------------------------------------------------------------------------
