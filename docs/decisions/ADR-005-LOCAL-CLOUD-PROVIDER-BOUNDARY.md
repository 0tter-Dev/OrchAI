# ADR-005 --- Local and Cloud Provider Boundary

## Status

Accepted

## Context

The architecture supports local and cloud AI resources while protecting
project context and avoiding provider lock-in.

## Decision

All AI resources are accessed through the AI Provider Adapter boundary.

The execution model distinguishes:

``` text
LOCAL
CLOUD
EXTERNAL AGENT
```

Provider SDKs remain infrastructure dependencies.

## Rationale

This preserves model replaceability and allows authorization policies to
distinguish local from external execution.

## Consequences

Positive:

-   provider independence;
-   explicit trust boundary;
-   model substitution;
-   consistent execution records.

Trade-offs:

-   adapters require translation logic;
-   provider-specific advanced features require explicit adapter
    extensions.

## Security Rule

Cloud execution must not receive sensitive project context unless
applicable policy and authorization permit it.
