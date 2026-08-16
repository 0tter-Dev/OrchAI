# OrchAI --- Component Map

## 1. Purpose

This document defines the primary architectural components of the OrchAI
and establishes their responsibilities, boundaries, and relationships.

It describes what each component is responsible for without defining its
concrete implementation.

Implementation-specific decisions belong to the relevant development and
implementation documentation.

------------------------------------------------------------------------

## 2. Component Overview

The OrchAI is composed of the following major components:

``` text
CLIENT / UI
     │
     ▼
ORCHESTRATION CORE
     │
     ├── Task Manager
     ├── State Machine
     ├── Event Engine
     ├── Execution Engine
     ├── Project Manager
     ├── Context Manager
     ├── Role Manager
     ├── Action Manager
     ├── Model Manager
     ├── Authorization Manager
     ├── Policy Engine
     └── Suggestion Engine
     │
     ├── Project Adapter
     └── Model / Agent Adapters
     
OBSERVABILITY
     ├── Audit Manager
     ├── Metrics
     └── Persistence
```

------------------------------------------------------------------------

## 3. Component Responsibilities

### 3.1 Client / UI

#### Responsibility

Provides the user-facing interface for interacting with the
Orchestrator.

#### May

-   create tasks;
-   select projects;
-   configure execution parameters;
-   review task state;
-   review execution results;
-   approve or reject authorization requests;
-   review suggestions;
-   inspect audit information;
-   inspect metrics.

#### Must not

-   contain core orchestration rules;
-   directly modify task state;
-   bypass authorization;
-   directly invoke project operations outside the Orchestrator.

------------------------------------------------------------------------

### 3.2. Task Manager

#### Responsibility

Owns the administrative lifecycle of tasks.

#### May

-   create tasks;
-   load tasks;
-   update task metadata;
-   associate tasks with projects;
-   retrieve task information;
-   archive tasks.

#### Consumes

-   project information;
-   task configuration;
-   user commands.

#### Produces

-   task lifecycle events.

#### Must not

-   execute AI models;
-   directly modify project code;
-   independently authorize execution;
-   determine the next role autonomously.

------------------------------------------------------------------------

### 3.3 State Machine

#### Responsibility

Controls valid task state transitions.

#### May

-   evaluate whether a transition is valid;
-   apply valid state transitions;
-   reject invalid transitions;
-   expose the current state;
-   emit state transition events.

#### Consumes

-   task events;
-   task state;
-   workflow rules;
-   execution results.

#### Produces

-   state transitions;
-   state-related events.

#### Must not

-   independently choose AI models;
-   independently authorize user-controlled transitions;
-   execute AI agents;
-   bypass defined transition rules.

------------------------------------------------------------------------

### 3.4 Event Engine

#### Responsibility

Coordinates the event-driven behavior of the system.

#### May

-   receive events;
-   dispatch events;
-   trigger registered handlers;
-   preserve event ordering where required;
-   report event processing failures.

#### Must not

-   redefine business rules;
-   directly bypass the State Machine;
-   interpret events as implicit user authorization.

------------------------------------------------------------------------

### 3.5 Execution Engine

#### Responsibility

Coordinates the actual execution of an authorized task action.

#### Input

``` text
TASK
ROLE
ACTION
MODEL
CONTEXT
EXECUTION MODE
AUTHORIZATION
```

#### May

-   validate execution parameters;
-   prepare an execution request;
-   invoke the selected model adapter;
-   capture execution output;
-   capture execution metadata;
-   report execution results.

#### Must not

-   silently change the user's selected model;
-   silently expand context authorization;
-   silently change role;
-   independently cross role boundaries;
-   interpret suggestions as authorization.

------------------------------------------------------------------------

### 3.6 Project Manager

#### Responsibility

Manages projects known to the Orchestrator.

#### May

-   register projects;
-   configure projects;
-   select the active project;
-   inspect project capabilities;
-   activate or deactivate project connections.

#### Must not

-   interpret project business rules;
-   own project source code;
-   replace the Project Adapter.

------------------------------------------------------------------------

### 3.7 Project Adapter

#### Responsibility

Provides the abstraction boundary between the Orchestrator and a
connected project.

#### May expose capabilities such as

-   file access;
-   documentation access;
-   Git operations;
-   test execution;
-   build operations;
-   project-specific tools;
-   project configuration.

#### Must

-   isolate project-specific implementation details;
-   expose standardized operations to the Orchestrator.

#### Must not

-   contain global Orchestrator workflow rules;
-   redefine task semantics;
-   decide how tasks should be executed.

------------------------------------------------------------------------

### 3.8 Context Manager

#### Responsibility

Resolves, validates, prepares, and packages context for AI execution.

#### May

-   resolve requested context;
-   locate project documentation;
-   validate context authorization;
-   build focused context packages;
-   identify potentially missing context;
-   report context requirements.

#### Must not

-   silently expand explicitly restricted context;
-   modify project documentation without authorization;
-   determine the business scope of a task.

------------------------------------------------------------------------

### 3.9 Role Manager

#### Responsibility

Manages the definitions and configuration of AI roles.

#### Examples

``` text
TASK PLANNER
DEVELOPER
QUALITY AGENT
```

#### May

-   register roles;
-   retrieve role definitions;
-   validate role capabilities;
-   resolve allowed actions.

#### Must not

-   identify the AI model itself;
-   replace action definitions;
-   execute models.

------------------------------------------------------------------------

### 3.10 Action Manager

#### Responsibility

Manages executable actions available to roles.

#### Examples

``` text
PLAN
ANALYZE
IMPLEMENT
REVIEW
VALIDATE
TEST
DOCUMENT
```

#### May

-   register actions;
-   retrieve action definitions;
-   validate whether a role may execute an action;
-   resolve action requirements.

#### Must not

-   select models;
-   authorize execution;
-   directly execute an AI model.

------------------------------------------------------------------------

### 3.11 Model Manager

#### Responsibility

Manages AI model definitions and resolves models for execution.

#### May track

-   provider;
-   model;
-   execution environment;
-   capabilities;
-   availability;
-   limits;
-   usage information;
-   cost information;
-   performance metrics.

#### Must not

-   silently replace user configuration in `MANUAL` mode;
-   treat metrics as authorization;
-   directly implement provider-specific communication.

------------------------------------------------------------------------

### 3.12 Model / Agent Adapters

#### Responsibility

Translate generic execution requests into provider- or tool-specific
operations.

Examples may include:

``` text
Ollama Adapter
Codex Adapter
Claude Adapter
Future Provider Adapter
```

#### Must

-   isolate provider-specific implementation;
-   expose a common execution interface.

#### Must not

-   implement global task workflow rules;
-   independently change task state;
-   independently authorize execution.

------------------------------------------------------------------------

### 3.13 Authorization Manager

#### Responsibility

Manages explicit authorization required by the workflow.

#### May

-   create authorization requests;
-   record authorization decisions;
-   validate authorization;
-   expire or invalidate authorization where configured;
-   associate authorization with a task and execution.

#### Must distinguish

``` text
Allowed by policy
Configured
Suggested
Authorized
Executed
```

These are separate concepts.

------------------------------------------------------------------------

### 3.14 Policy Engine

#### Responsibility

Determines what operations are permitted according to configured
policies.

#### May evaluate

-   execution mode;
-   role permissions;
-   action permissions;
-   project restrictions;
-   context restrictions;
-   cross-role automation rules;
-   model restrictions;
-   user configuration.

#### Must not

-   convert a suggestion into authorization;
-   override explicit user restrictions in `MANUAL` mode;
-   independently redefine project requirements.

------------------------------------------------------------------------

### 3.15 Suggestion Engine

#### Responsibility

Generates optional recommendations based on the current task and
available information.

#### May consider

-   task state;
-   task configuration;
-   execution history;
-   available models;
-   project configuration;
-   metrics;
-   audit information;
-   workflow patterns.

#### May suggest

-   a different model;
-   additional context;
-   a validation;
-   a review;
-   a next action;
-   a possible workflow optimization.

#### Must not

-   execute suggestions directly in `SUGGESTED` mode;
-   reinterpret suggestions as authorization;
-   silently modify task configuration.

------------------------------------------------------------------------

### 3.16 Audit Manager

#### Responsibility

Maintains authoritative orchestration history.

#### Should record

-   task lifecycle;
-   events;
-   state transitions;
-   authorization requests;
-   authorization decisions;
-   executions;
-   selected role;
-   selected action;
-   selected model;
-   context references;
-   execution results;
-   errors;
-   relevant configuration changes.

#### Must not

-   modify workflow state as a side effect of recording information.

------------------------------------------------------------------------

### 3.17 Metrics

#### Responsibility

Collects measurable information about system and AI usage.

#### Examples

``` text
Token consumption
Execution duration
Model usage
Local/cloud distribution
Success rate
Failure rate
Validation rate
Rework rate
Cloud limit utilization
Estimated cost
```

#### Purpose

Metrics support:

-   operational monitoring;
-   optimization;
-   auditing;
-   user decisions;
-   suggestion generation.

Metrics do not directly control execution.

------------------------------------------------------------------------

### 3.18 Persistence

#### Responsibility

Provides durable storage for Orchestrator state and history.

The persistence layer may contain:

``` text
Projects
Tasks
Task States
Events
Executions
Authorizations
Suggestions
Audit Records
Metrics
Configuration
```

Persistence implementation is intentionally unspecified by this
document.

------------------------------------------------------------------------

## 4. Component Interaction Model

The primary interaction pattern is:

``` text
USER
  │
  ▼
CLIENT
  │
  ▼
COMMAND / EVENT
  │
  ▼
TASK MANAGER
  │
  ▼
STATE MACHINE
  │
  ▼
POLICY ENGINE
  │
  ▼
AUTHORIZATION
  │
  ▼
EXECUTION ENGINE
  │
  ├── ROLE MANAGER
  ├── ACTION MANAGER
  ├── MODEL MANAGER
  ├── CONTEXT MANAGER
  └── MODEL / AGENT ADAPTER
            │
            ▼
       AI EXECUTION
            │
            ▼
       EXECUTION RESULT
            │
            ├──────────────► AUDIT
            ├──────────────► METRICS
            └──────────────► EVENT ENGINE
                                  │
                                  ▼
                             STATE MACHINE
```

------------------------------------------------------------------------

### 5. Decision Boundaries

The following decision boundaries must remain explicit.

  -----------------------------------------------------------------------
  Component       May Decide                   Must Not Decide
  --------------- ---------------------------- --------------------------
  Client          User interaction             Core workflow rules

  Task Manager    Task metadata operations     AI execution

  State Machine   Valid state transition       Model selection

  Event Engine    Event routing                User authorization

  Execution       Execution orchestration      Unconfigured workflow
  Engine                                       changes

  Role Manager    Role capability resolution   Model selection

  Action Manager  Action capability resolution Authorization

  Model Manager   Model resolution             User authorization

  Context Manager Context resolution within    Context expansion without
                  authorization                permission

  Policy Engine   Policy validity              User-controlled
                                               authorization

  Suggestion      Recommendations              Silent execution
  Engine                                       

  Authorization   Authorization validation     Autonomous authorization
  Manager                                      

  Project Adapter Project resource translation Global workflow decisions

  Audit Manager   Audit recording              Workflow modification

  Metrics         Measurement                  Execution control
  -----------------------------------------------------------------------

------------------------------------------------------------------------

### 6. Local and Cloud Execution Boundary

The system must treat local and cloud AI as execution providers rather
than architectural layers.

Conceptually:

``` text
                    EXECUTION ENGINE
                           │
                    MODEL MANAGER
                           │
                  MODEL / AGENT ADAPTER
                     ┌─────┴─────┐
                     ▼           ▼
                  LOCAL        CLOUD
                    AI           AI
```

This allows the workflow to change without changing the core
architecture.

For example:

``` text
TASK PLANNER → Local Model
DEVELOPER    → Cloud Model
QUALITY      → Local Model
```

or:

``` text
TASK PLANNER → Cloud Model
DEVELOPER    → Local Model
QUALITY      → Cloud Model
```

The architecture remains unchanged.

------------------------------------------------------------------------

### 7. Future Parallel Execution

The architecture should allow multiple tasks to execute concurrently in
the future.

Parallel execution must be coordinated through:

-   task isolation;
-   project resource awareness;
-   execution locks where necessary;
-   conflict detection;
-   state management;
-   authorization;
-   audit history.

Parallel execution is an extension of the architecture and must not
invalidate task boundaries.

------------------------------------------------------------------------

------------------------------------------------------------------------

## 4. Implementation Boundary Mapping

The logical components above map to the physical architecture as
follows:

  Logical Component         Primary Layer          Typical Module
  ------------------------- ---------------------- ---------------------------------
  Task Engine               Application            `application/tasks/`
  Execution Engine          Application            `application/executions/`
  Orchestration             Application            `application/orchestration/`
  Agent Coordination        Application            `application/agents/`
  Model Manager             Application            `application/models/`
  Context Manager           Application            `application/context/`
  Project Coordination      Application            `application/projects/`
  Event Coordination        Application            `application/events/`
  Task State Machine        Domain                 `domain/tasks/`
  Execution State Machine   Domain                 `domain/executions/`
  Authorization             Domain + Application   `domain/authorization/`
  Policies                  Domain + Application   `domain/policies/`
  Roles                     Domain                 `domain/roles/`
  Actions                   Domain                 `domain/actions/`
  Models                    Domain                 `domain/models/`
  Context                   Domain                 `domain/context/`
  Projects                  Domain                 `domain/projects/`
  Capabilities              Domain                 `domain/capabilities/`
  Events                    Domain                 `domain/events/`
  Persistence               Infrastructure         `infrastructure/persistence/`
  AI Providers              Infrastructure         `infrastructure/ai/`
  Project Adapters          Infrastructure         `infrastructure/projects/`
  Messaging                 Infrastructure         `infrastructure/messaging/`
  Observability             Infrastructure         `infrastructure/observability/`
  API                       Interfaces             `interfaces/api/`
  CLI                       Interfaces             `interfaces/cli/`
  Composition Root          Bootstrap              `bootstrap/`

This mapping is intentionally not one-to-one. A logical component may
span multiple layers when its domain contract, application coordination,
and infrastructure implementation are separate concerns.

------------------------------------------------------------------------

## 5. Engine Ownership Rules

### Task Engine

The Task Engine controls the lifecycle of Tasks and coordinates
Task-level use cases.

It does not execute AI operations directly.

### Execution Engine

The Execution Engine controls individual Execution attempts inside
Tasks.

An Execution represents one concrete attempt to perform an Action.
Failed or interrupted attempts remain historical records and are not
overwritten by later attempts.

### State Machines

State Machines are deterministic domain mechanisms that authorize
lifecycle transitions.

They do not perform orchestration, invoke providers, or make
authorization decisions unrelated to transition validity.

------------------------------------------------------------------------

## 6. Project and Context Ownership

The Project Manager and Project Adapter must not be interpreted as a
project-content database.

``` text
Project Manager
    ↓
Project Adapter
    ↓
External Project
```

The Context Manager requests and assembles information from the
connected project when needed.

OrchAI may persist references and context-resolution metadata, but does
not mirror complete project documentation or source trees by default.

------------------------------------------------------------------------

## 7. Runtime and Infrastructure Boundary

The first implementation uses `asyncio` tasks for long-running
execution.

The Event Engine is initially backed by an in-process dispatcher. A
future broker or durable job system may be introduced behind
infrastructure contracts when deployment requirements justify it.

No component may assume that in-process execution is the only possible
runtime topology.
