# OrchAI --- Actions Domain

## Purpose

An `ACTION` defines what an execution is intended to perform.

Actions remain independent from roles and models.

## Initial Action Vocabulary

``` text
PLAN
IMPLEMENT
FIX
REFACTOR
REVIEW
VALIDATE
TEST
DOCUMENT
```

The catalogue may evolve as workflow requirements become clearer.

## Action Identity

An action may define:

-   name;
-   description;
-   required capabilities;
-   expected outputs;
-   allowed roles;
-   validation requirements;
-   authorization requirements.

## Scope

An action must remain inside task scope.

Out-of-scope work should follow:

``` text
REPORT
    ↓
SUGGEST
    ↓
REQUEST AUTHORIZATION
```

when required.

## Action and Role

``` text
ROLE:
DEVELOPER

ACTION:
IMPLEMENT
```

The effective operation is determined by both dimensions.

## Action Completion

An action may produce execution output, project changes, validation
results, findings, suggestions, and events.

Action completion does not imply task completion.

## Invariants

1.  An action represents an operation.
2.  An action does not identify a model.
3.  An action does not bypass authorization.
4.  An action remains bounded by task scope.
5.  Results remain traceable to the producing execution.
