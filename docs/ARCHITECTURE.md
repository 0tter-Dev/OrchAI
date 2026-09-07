# OrchAI --- Architecture

## 1. Overview

The OrchAI is a generic orchestration platform for AI-assisted software
development.

It coordinates users, tasks, AI agents, models, project resources,
context, execution policies, authorization, state transitions, auditing,
and metrics through a unified workflow.

The system is intentionally independent from the projects it operates
on.

Its purpose is not to replace existing development environments or AI
tools, but to provide an orchestration layer capable of coordinating
them.

------------------------------------------------------------------------

## 2. Architectural Vision

The OrchAI provides a controlled bridge between human intent and
AI-assisted execution.

Conceptually:

``` text
USER
  ↓
OrchAI
  ↓
TASK
  ↓
ROLE + ACTION + MODEL
  ↓
AI EXECUTION
  ↓
PROJECT
  ↓
RESULT
  ↓
VALIDATION / REVIEW
  ↓
DOCUMENTATION / AUDIT
```

The same workflow may use local AI, cloud AI, or a combination of both.

------------------------------------------------------------------------

## 3. Core Architectural Layers

The architecture can be understood through the following layers.

### 3.1 Human Interaction Layer

Provides interaction between the user and the Orchestrator.

Responsibilities include:

-   creating tasks;
-   selecting projects;
-   configuring execution parameters;
-   reviewing suggestions;
-   granting or rejecting authorization;
-   monitoring execution;
-   reviewing results;
-   inspecting audit and metrics.

The client must not contain the core orchestration rules.

------------------------------------------------------------------------

### 3.2 Orchestration Core

The Orchestration Core controls the lifecycle and coordination of tasks.

It contains the fundamental mechanisms for:

-   task management;
-   state management;
-   event processing;
-   execution coordination;
-   authorization;
-   policies;
-   suggestions.

This layer is project-independent.

------------------------------------------------------------------------

### 3.3 Agent Execution Layer

This layer connects the orchestration system to AI agents and models.

It provides:

-   role management;
-   action management;
-   model management;
-   model/agent adapters;
-   execution preparation;
-   execution result handling.

The execution layer must support local and cloud AI.

------------------------------------------------------------------------

### 3.4 Project Integration Layer

The Project Integration Layer provides access to connected projects.

Projects are accessed through a `PROJECT ADAPTER`.

The Orchestrator interacts with generic capabilities rather than
directly depending on project-specific implementation details.

------------------------------------------------------------------------

### 3.5 Observability Layer

The Observability Layer provides:

-   audit;
-   metrics;
-   execution history;
-   event history;
-   resource usage information;
-   workflow analysis.

It allows the user to understand not only what happened, but also how
efficiently the AI resources were used.

------------------------------------------------------------------------

## 4. High-Level Architecture

``` text
                         ┌───────────────────┐
                         │       USER        │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │  CLIENT / UI      │
                         └─────────┬─────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION CORE                          │
│                                                                │
│  ┌────────────┐   ┌───────────────┐   ┌────────────────────┐   │
│  │ Task       │   │ State         │   │ Event              │   │
│  │ Manager    │   │ Machine       │   │ Engine             │   │
│  └─────┬──────┘   └───────┬───────┘   └──────────┬─────────┘   │
│        │                  │                      │             │
│        └──────────────────┼──────────────────────┘             │
│                           ▼                                    │
│                  ┌──────────────────┐                          │
│                  │ Execution Engine │                          │
│                  └────────┬─────────┘                          │
│                           │                                    │
│       ┌───────────────────┼────────────────────┐               │
│       ▼                   ▼                    ▼               │
│  ┌──────────┐       ┌──────────┐       ┌──────────────┐        │
│  │ Role     │       │ Action   │       │ Model        │        │
│  │ Manager  │       │ Manager  │       │ Manager      │        │
│  └──────────┘       └──────────┘       └──────┬───────┘        │
│                                               │                │
│                                    ┌──────────▼──────────┐     │
│                                    │ Model / Agent       │     │
│                                    │ Adapters            │     │
│                                    └──────────┬──────────┘     │
│                                               │                │
│                         ┌─────────────────────┴──────────┐     │
│                         ▼                                ▼     │
│                    LOCAL AI                          CLOUD AI  │
│                                                                │
│  ┌──────────────────┐   ┌────────────────┐   ┌─────────────┐   │
│  │ Context Manager  │   │ Policy Engine  │   │ Suggestion  │   │
│  │                  │   │ + Authorization│   │ Engine      │   │
│  └────────┬─────────┘   └────────────────┘   └─────────────┘   │
│           │                                                    │
│           ▼                                                    │
│  ┌──────────────────┐                                          │
│  │ Project Manager  │                                          │
│  └────────┬─────────┘                                          │
└───────────┼────────────────────────────────────────────────────┘
            │
            ▼
   ┌───────────────────┐
   │ PROJECT ADAPTER   │
   └─────────┬─────────┘
             │
             ▼
   ┌───────────────────┐
   │ CONNECTED PROJECT │
   │                   │
   │ Code / Docs / Git │
   │ Tests / Tools     │
   └───────────────────┘



   ┌───────────────────────┐
   │ AUDIT / METRICS       │
   └───────────────────────┘
```

------------------------------------------------------------------------

## 5. Core Concepts

### 5.1 Project

A project is an external software system connected to the Orchestrator.

The project contains its own source code, documentation, development
rules, and project-specific resources.

------------------------------------------------------------------------

### 5.2 Task

A task represents a unit of work requested by the user.

A task provides the scope within which AI-assisted work occurs.

------------------------------------------------------------------------

### 5.3 Role

A role represents the responsibility assumed by an AI agent during an
execution.

Examples include:

-   `TASK PLANNER`
-   `DEVELOPER`
-   `QUALITY AGENT`

------------------------------------------------------------------------

### 5.4 Action

An action defines what the selected role is expected to perform.

Examples include:

-   `PLAN`
-   `IMPLEMENT`
-   `REVIEW`
-   `VALIDATE`
-   `TEST`
-   `DOCUMENT`

------------------------------------------------------------------------

### 5.5 Model

A model identifies the AI resource used to execute an action.

Models may be local or cloud-based.

------------------------------------------------------------------------

### 5.6 Context

Context represents the information made available to an AI execution.

Context must be focused on the current task and controlled according to
authorization and project configuration.

------------------------------------------------------------------------

### 5.7 Execution

An execution is an actual attempt to perform a specific action using a
selected role and model against a task.

------------------------------------------------------------------------

### 5.8 Event

An event represents something that happened within the workflow.

Examples:

``` text
TASK_CREATED
PLANNING_COMPLETED
IMPLEMENTATION_STARTED
IMPLEMENTATION_COMPLETED
REVIEW_FAILED
REVIEW_PASSED
```

------------------------------------------------------------------------

### 5.9 State

A state represents the current condition of a task.

States are changed through valid state transitions triggered by events.

------------------------------------------------------------------------

### 5.10 Authorization

Authorization represents explicit permission to perform an operation or
continue a workflow.

Authorization is distinct from policy, configuration, and suggestion.

------------------------------------------------------------------------

## 6. Human-in-the-Loop

The user remains the authority over workflow progression.

The system may identify:

-   a possible next action;
-   a better model;
-   additional context;
-   a validation opportunity;
-   a possible review;
-   an optimization based on metrics.

However, under `SUGGESTED` mode, the system must present the
recommendation and wait for explicit user confirmation.

------------------------------------------------------------------------

## 7. Execution Modes

### MANUAL

The system follows the explicitly defined operation.

No automatic workflow progression occurs.

------------------------------------------------------------------------

### SUGGESTED

The system follows the user's configuration while identifying possible
improvements.

Suggestions require explicit user authorization.

This is the default mode.

------------------------------------------------------------------------

### AUTOMATIC

The system may automatically execute configured actions within
explicitly defined boundaries.

Automatic execution does not grant unrestricted autonomy.

Cross-role transitions remain subject to explicit configuration or
authorization.

------------------------------------------------------------------------

## 8. Local and Cloud AI Strategy

The architecture treats local and cloud AI as interchangeable execution
resources.

A typical optimized workflow may be:

``` text
USER REQUEST
     ↓
TASK PLANNER
     ↓
LOCAL AI
     ↓
TASK PREPARATION
     ↓
USER AUTHORIZATION
     ↓
DEVELOPER
     ↓
CLOUD AI
     ↓
IMPLEMENTATION
     ↓
USER AUTHORIZATION
     ↓
QUALITY AGENT
     ↓
LOCAL AI
     ↓
REVIEW / VALIDATION / TESTING
     ↓
DOCUMENTATION
```

This is a strategy rather than a mandatory workflow.

Different projects may configure different combinations of local and
cloud execution.

------------------------------------------------------------------------

## 9. Project Boundary

The Orchestrator and the connected project are separate systems.

``` text
┌─────────────────────────────┐
│           OrchAI            │
│                             │
│ Tasks                       │
│ Roles                       │
│ Actions                     │
│ Models                      │
│ Policies                    │
│ Authorization               │
│ Audit                       │
│ Metrics                     │
└──────────────┬──────────────┘
               │
        PROJECT ADAPTER
               │
               ▼
┌─────────────────────────────┐
│          PROJECT            │
│                             │
│ Code                        │
│ Business Documentation      │
│ Development Guide           │
│ Contexts                    │
│ Status                      │
│ Tests                       │
│ Git                         │
└─────────────────────────────┘
```

The adapter is the architectural boundary between the two.

------------------------------------------------------------------------

## 10. Audit and Metrics

Every meaningful execution should be observable.

The system should preserve:

``` text
Task
Project
Role
Action
Model
Context
Authorization
Execution
Events
State transitions
Result
Metrics
```

This enables analysis of:

-   cloud AI usage;
-   local AI usage;
-   token consumption;
-   workflow efficiency;
-   model performance;
-   task rework;
-   validation success;
-   resource utilization.

------------------------------------------------------------------------

## 11. Extensibility

The architecture is designed to support future additions without
changing the fundamental orchestration model.

Examples include:

-   new AI providers;
-   new models;
-   new project adapters;
-   new roles;
-   new actions;
-   new clients;
-   parallel task execution;
-   additional automation policies;
-   additional metrics;
-   external integrations.

------------------------------------------------------------------------

## 12. Architectural Boundaries

The following boundaries must remain explicit:

``` text
USER
≠
ORCHESTRATOR

ORCHESTRATOR
≠
PROJECT

ROLE
≠
ACTION
≠
MODEL

POLICY
≠
AUTHORIZATION

SUGGESTION
≠
DECISION

EVENT
≠
STATE

AUDIT
≠
PROJECT LOG

LOCAL AI
≠
CLOUD AI
```

These distinctions are fundamental to the architecture.

------------------------------------------------------------------------

## 13. Architectural Outcome

The resulting system should provide a generic orchestration platform in
which:

``` text
ONE ORCHESTRATOR
        │
        ├── PROJECT A
        ├── PROJECT B
        ├── PROJECT C
        └── PROJECT N
```

while independently supporting:

``` text
LOCAL MODELS
CLOUD MODELS
MULTIPLE ROLES
MULTIPLE ACTIONS
MULTIPLE EXECUTION MODES
MULTIPLE PROJECT CONFIGURATIONS
```

without requiring the core architecture to change.

------------------------------------------------------------------------

## 14. Implementation Baseline

The concepts above are realized as a modular monolith following
Clean/Hexagonal Architecture principles, an async-first runtime, and
an explicit Project/AI Provider adapter boundary. The physical module
structure, dependency direction, runtime baseline, and selected
technology stack are engineering-discipline concerns, not product
architecture — they live in
[`DEVELOPMENT-GUIDE.md`](DEVELOPMENT-GUIDE.md) and the relevant
`docs/context/*.md` files (`modules-and-domain-structure.md`,
`execution-engine.md`, `project-adapter-and-security.md`,
`context-management.md`, `technology-and-test-strategy.md`), so this
document can stay focused on the conceptual model above without
drifting out of sync with implementation detail.
