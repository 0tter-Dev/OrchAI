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
- first policy slice separated from authorization;
- execution lifecycle and results;
- async execution through a provider-independent AI adapter boundary;
- role, action, model, and capability vocabularies;
- context references, context packages, and context-resolution metadata;
- local filesystem project adapter discovery and context reads;
- durable event and audit history;
- operational metrics derived from execution events with idempotent record ids;
- task-state suggestions with `SUGGESTED`/`AUTOMATIC` enforcement;
- architectural boundary checks for layer imports;
- Typer CLI with a minimal local flow and inspection commands;
- SQLAlchemy persistence with SQLite and PostgreSQL migration support.

Still pending or partial:

- richer policy configuration beyond the initial local policy slice;
- provider configuration and richer provider adapter contracts;
- FastAPI interface;
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

The current configuration surface reads the process environment first
and then a local `.env` file.

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
uv run orchai local-flow . docs/INDEX.md --title "Local flow" --approve-suggestion
```

The local flow registers a project, creates a task, records explicit
authorization, creates an execution, resolves only authorized context,
and completes the execution. Without `--approve-suggestion`, the default
`SUGGESTED` mode presents the generated suggestion and stops before
authorization/execution.

Run the same initial operation through bounded automatic mode:

``` powershell
uv run orchai local-flow . docs/INDEX.md --execution-mode AUTOMATIC
```

Discover project resources through the filesystem Project Adapter:

``` powershell
uv run orchai projects discover . --limit 20
```

Inspect persisted history:

``` powershell
uv run orchai events list --limit 10
uv run orchai audit list --limit 10
uv run orchai metrics list --limit 10
uv run orchai suggestions list --limit 10
```

## Tests

``` powershell
uv run pytest
```

The current suite covers unit and integration behavior, including CLI
execution, SQLite restart-surviving persistence, policy enforcement,
recovery paths for provider/context failures, architectural dependency
checks, and the async execution engine with fake providers.

## Architecture

Start with [docs/INDEX.md](docs/INDEX.md) for the documentation map.
Important architectural boundaries are captured in:

- [docs/ARCHITECTURAL-CONTRACT.md](docs/ARCHITECTURAL-CONTRACT.md)
- [docs/architecture/APPLICATION-STRUCTURE.md](docs/architecture/APPLICATION-STRUCTURE.md)
- [docs/architecture/PERSISTENCE-STRATEGY.md](docs/architecture/PERSISTENCE-STRATEGY.md)
- [docs/IMPLEMENTATION-MAP.md](docs/IMPLEMENTATION-MAP.md)

## License

MIT. See [LICENSE](LICENSE).
