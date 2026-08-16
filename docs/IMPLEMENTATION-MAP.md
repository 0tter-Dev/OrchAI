# OrchAI --- Implementation Map

## 1. Purpose

The `IMPLEMENTATION-MAP` is the bridge between the architectural/domain
contracts and the actual implementation of `OrchAI`.

It defines what must be implemented, how responsibilities are separated,
and how the main components interact, while intentionally avoiding
premature commitment to a specific programming language, framework,
database, UI technology, or infrastructure provider.

``` text
ARCHITECTURAL CONTRACT
        ↓
ARCHITECTURE
        ↓
COMPONENT MAP
        ↓
DOMAIN DOCUMENTATION
        ↓
IMPLEMENTATION-MAP
        ↓
IMPLEMENTATION
```

## 2. Core Principles

The implementation must preserve these principles:

1.  `OrchAI` is a generic orchestration application.
2.  Projects remain external domains connected through
    `PROJECT ADAPTER`.
3.  Global orchestration logic must not contain project-specific
    business logic.
4.  `TASK`, `ROLE`, `ACTION`, `MODEL`, `EVENT`, `EXECUTION`, and
    `AUTHORIZATION` remain distinct concepts.
5.  User authorization is the primary control boundary.
6.  `SUGGESTED` is the default execution mode.
7.  `MANUAL` and `AUTOMATIC` are explicit alternatives.
8.  Automatic execution remains bounded by configured authorization and
    role boundaries.
9.  Local and cloud AI resources are replaceable through adapters.
10. Audit and metrics are first-class capabilities.
11. Historical execution and authorization information remains
    traceable.
12. Project-specific details remain behind project boundaries.

## 3. High-Level Runtime Structure

``` text
┌──────────────────────────────────────────────────────────┐
│                         OrchAI                           │
│                                                          │
│  User / UI                                               │
│      │                                                   │
│      ▼                                                   │
│  ORCHESTRATOR                                             │
│      │                                                   │
│      ├── TASK / STATE MANAGEMENT                         │
│      ├── AUTHORIZATION                                   │
│      ├── EXECUTION MANAGEMENT                            │
│      ├── EVENT MANAGEMENT                                │
│      ├── AUDIT / METRICS                                 │
│      └── SUGGESTION ENGINE                               │
│                │                                          │
│                ├── AI PROVIDER ADAPTERS                  │
│                └── PROJECT ADAPTER                       │
└──────────────────────────────────────────────────────────┘
                         │
                         ▼
                   External Project
```

This is a logical structure, not a mandatory process architecture.

## 4. Core Modules

### 4.1 Orchestrator Core

Coordinates the system.

Responsibilities:

-   receive user commands;
-   resolve task operations;
-   evaluate current task state;
-   coordinate authorization;
-   create execution requests;
-   coordinate state transitions;
-   emit domain events;
-   present suggestions;
-   enforce configured execution boundaries.

It must not contain project-specific business logic.

### 4.2 Task Manager

Responsible for task lifecycle management:

-   create and retrieve tasks;
-   maintain task metadata;
-   maintain current state;
-   validate transitions through the State Machine;
-   associate executions;
-   associate context;
-   maintain task relationships.

It must not execute AI models directly.

### 4.3 State Machine

Determines whether requested task state transitions are valid.

``` text
Current State
      +
Requested Transition
      ↓
STATE MACHINE
      ↓
Allowed / Rejected
```

It must remain deterministic and independently testable.

### 4.4 Execution Manager

Transforms an authorized task operation into an execution.

Responsibilities:

-   construct execution requests;
-   resolve effective `ROLE`;
-   resolve effective `ACTION`;
-   resolve effective `MODEL`;
-   resolve authorized context;
-   invoke the appropriate adapter;
-   capture results and resource usage;
-   emit execution events.

### 4.5 Authorization Manager

Responsible for authorization boundaries:

-   create authorization requests;
-   evaluate policies;
-   record decisions;
-   validate authorization before protected operations;
-   handle expiration/revocation;
-   enforce cross-role boundaries;
-   distinguish suggestions from authorization.

Recommendations must never silently become approvals.

### 4.6 Event Manager

Responsible for domain event handling:

-   publish events;
-   persist events when required;
-   correlate events;
-   route events to consumers;
-   support idempotent processing;
-   preserve traceability.

Possible consumers include:

``` text
STATE MACHINE
AUDIT
METRICS
SUGGESTION ENGINE
NOTIFICATION
```

### 4.7 AI Provider Adapter

Provides a stable interface between `OrchAI` and AI resources.

``` text
Execution Manager
       ↓
AI Provider Interface
       ↓
┌─────────────┬─────────────┬─────────────┐
│ Local Model │ Cloud Agent │ Future Model│
│ Adapter     │ Adapter     │ Adapter     │
└─────────────┴─────────────┴─────────────┘
```

The core must not depend directly on Ollama, Codex, Claude Code, or any
other provider.

### 4.8 Project Adapter

Defines the boundary between `OrchAI` and an external project.

Potential capabilities include:

-   project discovery;
-   file access;
-   documentation access;
-   context resolution;
-   source modification;
-   test execution;
-   Git integration;
-   project-specific validation.

Project-specific implementation details must remain behind this
boundary.

### 4.9 Context Manager

Resolves the context required by an execution.

It must distinguish:

``` text
REQUESTED
AUTHORIZED
RESOLVED
PROVIDED
```

Restricted context must never be accessed merely because an agent
requested it.

### 4.10 Audit Manager

Preserves operational history, including:

-   tasks;
-   state transitions;
-   executions;
-   models;
-   authorization;
-   context;
-   suggestions;
-   user decisions;
-   errors;
-   retries;
-   resource consumption.

Audit data must remain independently queryable.

### 4.11 Metrics Manager

Aggregates measurable operational information, such as:

``` text
Token Usage
Execution Duration
Model Usage
Local vs Cloud Usage
Estimated Cost
Success Rate
Failure Rate
Retry Rate
Task Completion Time
Suggestion Acceptance Rate
```

Metrics should derive from authoritative execution/audit information.

### 4.12 Suggestion Engine

Produces optional recommendations based on factors such as:

-   current task state;
-   configured workflow;
-   model capabilities;
-   project configuration;
-   historical metrics;
-   token consumption;
-   execution history;
-   resource availability.

It produces recommendations only. In `SUGGESTED` mode it does not
authorize or execute them.

## 5. Configuration Layers

Configuration should remain clearly separated:

``` text
GLOBAL CONFIGURATION
        ↓
ORCHAI CONFIGURATION
        ↓
PROJECT CONFIGURATION
        ↓
TASK CONFIGURATION
        ↓
EXECUTION CONFIGURATION
```

Override precedence must be explicit rather than implicit.

## 6. Project Boundary

The dependency direction should remain:

``` text
OrchAI Core
     ↓
Project Adapter Interface
     ↓
Project Adapter Implementation
     ↓
External Project
```

A project must not depend on OrchAI's internal implementation.

## 7. AI Boundary

AI providers should follow:

``` text
Execution Manager
       ↓
AI Provider Interface
       ↓
Provider Adapter
       ↓
AI Resource
```

This allows local, cloud, hybrid, and future providers without changing
the domain model.

## 8. Persistence Boundaries

Distinguish conceptually between:

### Operational State

Current information required to operate the system:

``` text
Current Task State
Current Configuration
Active Authorizations
Active Executions
```

### Historical Records

Information that preserves what happened:

``` text
Events
Audit Records
Execution History
Authorization History
Usage Records
```

Operational storage may optimize current access. Historical storage must
prioritize integrity and traceability.

## 9. User Interaction Boundary

The interface should expose the orchestration model without requiring
knowledge of internal implementation details.

Users should be able to define or confirm:

``` text
PROJECT
TASK
ROLE
ACTION
MODEL
CONTEXT
EXECUTION MODE
```

and inspect:

``` text
CURRENT STATE
NEXT AVAILABLE ACTION
AUTHORIZATION REQUESTS
SUGGESTIONS
EXECUTION HISTORY
AUDIT
METRICS
```

Authorization decisions must remain explicit.

## 10. Execution Modes

### MANUAL

``` text
User Request
    ↓
Execute Requested Operation
```

No additional workflow progression is inferred.

### SUGGESTED

``` text
User Request
    ↓
Evaluate
    ↓
Suggestion
    ↓
User Decision
    ↓
Execute
```

### AUTOMATIC

``` text
User Request
    ↓
Evaluate
    ↓
Authorized Automatic Operation
    ↓
Execute
    ↓
Continue Within Allowed Boundary
```

Cross-role progression remains explicitly controlled.

## 11. Event-Oriented Integration

A representative flow is:

``` text
User Command
     ↓
Orchestrator
     ↓
Task / Authorization Validation
     ↓
Execution
     ↓
Event
     ├── State Machine
     ├── Audit
     ├── Metrics
     └── Suggestion Engine
```

The event mechanism should reduce direct coupling between these
components.

## 12. Typical Task Flow

``` text
1. User creates or selects TASK
2. OrchAI reads current TASK STATE
3. User defines or confirms ROLE
4. User defines or confirms ACTION
5. User defines or confirms MODEL
6. Context is identified and authorized
7. Authorization requirements are evaluated
8. Execution request is prepared
9. Selected AI adapter is invoked
10. Execution result is recorded
11. Project changes are observed through PROJECT ADAPTER
12. Events are emitted
13. TASK STATE is updated
14. Audit and metrics are updated
15. Suggestion Engine may identify a next operation
16. User decides whether to continue when required
```

## 13. Conceptual Implementation Order

### Foundation

``` text
Configuration
Domain Models
Persistence Abstractions
Event Abstractions
```

### Core Lifecycle

``` text
TASK
STATE MACHINE
EVENTS
AUTHORIZATION
```

### Execution

``` text
ROLE
ACTION
MODEL
EXECUTION
AI ADAPTER
```

### Project Integration

``` text
PROJECT
PROJECT ADAPTER
CONTEXT
PROJECT CAPABILITIES
```

### Operational Intelligence

``` text
AUDIT
METRICS
SUGGESTIONS
```

### User Experience

``` text
CLI / UI
TASK MANAGEMENT
EXECUTION CONTROL
AUTHORIZATION UI
AUDIT / METRICS UI
```

The actual technical sequence may vary, but dependency direction must be
preserved.

## 14. Capability Model

Capabilities should be explicit where appropriate.

Examples:

``` text
READ_PROJECT
READ_DOCUMENTATION
WRITE_SOURCE
WRITE_DOCUMENTATION
RUN_TESTS
RUN_COMMANDS
USE_LOCAL_MODEL
USE_CLOUD_MODEL
ACCESS_GIT
```

Capability availability does not itself constitute authorization.

## 15. Error and Recovery Boundaries

Errors should remain associated with their originating layer:

``` text
DOMAIN ERROR
AUTHORIZATION ERROR
STATE TRANSITION ERROR
AI PROVIDER ERROR
PROJECT ADAPTER ERROR
CONTEXT ERROR
EXECUTION ERROR
PERSISTENCE ERROR
```

An error does not automatically imply task failure unless the State
Machine defines that behavior.

Possible recovery paths include:

``` text
RETRY
REPLAN
REQUEST USER DECISION
CHANGE MODEL
REQUEST CONTEXT
REPEAT VALIDATION
ROLL BACK
CANCEL TASK
```

Recovery remains subject to authorization policy.

## 16. Concurrency Readiness

The first implementation does not need full parallel-task execution, but
the architecture should remain compatible with it.

Each task and execution should have:

-   stable identity;
-   isolated state;
-   explicit project association;
-   explicit affected scope where known;
-   traceable modifications.

Future conflict detection can then be introduced without redefining the
task model.

## 17. Testing Boundaries

Major components should be independently testable.

Particularly important tests include:

``` text
State Transition Rules
Authorization Rules
Execution Construction
Event Processing
Context Resolution
Project Adapter Contract
AI Adapter Contract
Suggestion Generation
Audit Recording
Metrics Aggregation
```

Integration tests should cover complete and failure/rework flows:

``` text
TASK
 → PLAN
 → AUTHORIZATION
 → IMPLEMENT
 → REVIEW
 → VALIDATION
 → COMPLETION
```

## 18. Security and Trust Boundaries

The implementation should explicitly identify:

``` text
USER
OrchAI
PROJECT
LOCAL AI
CLOUD AI
EXTERNAL PROVIDER
```

Sensitive project information must not be sent to an external model
unless the applicable context and authorization rules permit it.

AI providers are not authorities over task scope or authorization.

## 19. Observability

Every significant operation should be traceable through common
correlation information.

The system should be able to connect:

``` text
TASK
  ↓
EVENT
  ↓
AUTHORIZATION
  ↓
EXECUTION
  ↓
MODEL
  ↓
PROJECT CHANGE
  ↓
VALIDATION
```

This is required for debugging, auditing, and metrics.

## 20. Implementation Decision Records

Technology decisions should be documented separately when they
materially affect the architecture.

Examples:

-   persistence technology;
-   event transport;
-   UI architecture;
-   adapter protocol;
-   local model integration;
-   cloud provider integration;
-   authentication;
-   deployment model.

The `IMPLEMENTATION-MAP` defines responsibilities. Decision records
capture the chosen technology and rationale.

## 21. Architectural Readiness Criteria

The implementation foundation is structurally ready when:

-   domain boundaries are represented in code;
-   the Task State Machine is independently enforceable;
-   authorization is independently enforceable;
-   execution is adapter-based;
-   AI providers are replaceable;
-   projects connect through Project Adapter;
-   events can be emitted and consumed;
-   audit information can be persisted;
-   metrics can be derived;
-   execution modes can be enforced;
-   suggestions cannot silently become authorization;
-   cross-role boundaries are enforceable;
-   historical operations remain traceable.

## 22. Technology and Runtime Baseline

The technology baseline has now been decided and must remain consistent
with this implementation map.

``` text
Python 3.14
uv + pyproject.toml
FastAPI
Typer
Pydantic
SQLAlchemy 2.x
PostgreSQL
SQLite
HTTPX
asyncio
pytest
Docker
```

PostgreSQL is the primary persistence target. SQLite remains supported
for lightweight/local operation.

The first runtime uses `asyncio` tasks for long-running execution and
does not require RabbitMQ, Redis, Celery, Kafka, or another distributed
broker. The messaging and execution boundaries remain replaceable so
persistent workers or a broker can be introduced later.

## 23. Physical Code Structure

The implementation follows a modular monolith with Clean/Hexagonal
principles:

``` text
src/orchai/
├── domain/
├── application/
├── infrastructure/
├── interfaces/
└── bootstrap/
```

The domain owns business rules, application owns use-case orchestration,
infrastructure implements external contracts, interfaces translate
external requests, and bootstrap assembles the runtime.

The detailed module mapping is defined in
`docs/architecture/APPLICATION-STRUCTURE.md` and
`docs/architecture/DOMAIN-MODULE-STRUCTURE.md`.

## 24. Project Content Boundary

Connected project source, documentation, and other project-owned content
remain external to OrchAI.

The Project Adapter is the access boundary. OrchAI persists project
identity, adapter configuration, references, capabilities,
context-resolution metadata, and orchestration history rather than
mirroring complete project contents.

## 25. AI Provider Boundary

The Model Manager resolves provider-independent model definitions and
capabilities. Concrete local, cloud, and external-agent integrations
remain infrastructure adapters.

## 26. Final Implementation Readiness

The documentation foundation is considered ready for initial
implementation when the accepted ADRs, architecture documents, domain
contracts, navigation documents, and this map agree on:

-   modular monolith structure;
-   dependency direction;
-   Task/Execution ownership;
-   State Machine authority;
-   async-first runtime;
-   provider adapter boundaries;
-   Project Adapter ownership;
-   persistence baseline;
-   API/CLI boundaries;
-   testing boundaries;
-   authorization invariants.

Concrete implementation work may begin after repository-level bootstrap
files and the first domain slice are defined.
