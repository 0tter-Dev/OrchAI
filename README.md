# OrchAI

OrchAI is a generic orchestration system for AI-assisted software
development workflows.

The project coordinates tasks, authorization, execution attempts,
context resolution, project adapters, events, audit, metrics, roles,
actions, and model/provider boundaries without embedding project-specific
business logic in the core.

## Current Status

The current implementation is an executable foundation, not a complete
product.

Implemented and tested:

- task lifecycle and state transitions;
- authorization requests and decisions;
- execution lifecycle and results;
- role, action, model, and capability vocabularies;
- context references and context packages;
- local filesystem project adapter;
- Typer CLI with a minimal local flow;
- SQLAlchemy persistence with SQLite support and initial migrations.

Still pending or partial:

- durable event/audit persistence;
- metrics and suggestions;
- policy engine;
- AI provider adapters;
- FastAPI interface;
- PostgreSQL integration validation;
- deployment/container setup.

## Requirements

- Python 3.14
- uv

## Setup

``` powershell
uv sync
```

If `uv` is not available in the current shell, use the project virtual
environment directly:

``` powershell
.venv\Scripts\python.exe -m pytest
```

## Configuration

The current configuration surface is environment-backed.

``` powershell
$env:ORCHAI_DATABASE_URL = "sqlite:///.orchai/orchai.db"
```

SQLite is the default local backend. PostgreSQL URLs are accepted and
normalized to the SQLAlchemy `postgresql+psycopg` driver form.

``` powershell
$env:ORCHAI_DATABASE_URL = "postgresql://orchai:password@localhost:5432/orchai"
```

## CLI

Apply database migrations:

``` powershell
uv run orchai db migrate
```

Create a PostgreSQL database when the server is already running:

``` powershell
$env:ORCHAI_DATABASE_URL = "postgresql://postgres:password@localhost:5432/orchai"
uv run orchai db create
uv run orchai db migrate
```

Run the minimal local orchestration flow:

``` powershell
uv run orchai local-flow . docs/INDEX.md --title "Local flow"
```

The local flow registers a project, creates a task, records explicit
authorization, creates an execution, resolves only authorized context,
and completes the execution.

## Tests

``` powershell
uv run pytest
```

The current suite covers unit and integration behavior, including CLI
execution and SQLite restart-surviving persistence.

## Architecture

Start with [docs/INDEX.md](docs/INDEX.md) for the documentation map.
Important architectural boundaries are captured in:

- [docs/ARCHITECTURAL-CONTRACT.md](docs/ARCHITECTURAL-CONTRACT.md)
- [docs/architecture/APPLICATION-STRUCTURE.md](docs/architecture/APPLICATION-STRUCTURE.md)
- [docs/architecture/PERSISTENCE-STRATEGY.md](docs/architecture/PERSISTENCE-STRATEGY.md)
- [docs/IMPLEMENTATION-MAP.md](docs/IMPLEMENTATION-MAP.md)

## License

MIT. See [LICENSE](LICENSE).
