# OrchAI --- headless CLI/API deployment image (docs/architecture/DEPLOYMENT-MODEL.md
# "Containerization"). This is a second, independent deployment shape
# alongside OrchAI Desktop (ADR-017, packaged separately via PyInstaller/
# briefcase, never Docker) -- both run the exact same backend process
# unmodified; only how it's reached differs (network here, 127.0.0.1-only
# there). No source change was needed to make this work: `create_app()`
# already skips mounting the desktop UI when ORCHAI_DESKTOP_STATIC_DIR is
# unset, and `ORCHAI_API_HOST`/`ORCHAI_DATABASE_URL` are already ordinary
# environment overrides read by `load_settings()`.
FROM python:3.14-slim

# uv (https://docs.astral.sh/uv/) resolves from pyproject.toml/uv.lock
# directly and is much faster than pip for this; copying the prebuilt
# binary avoids needing a separate installer step.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies before copying the application source so this
# layer is only rebuilt when pyproject.toml/uv.lock actually change, not
# on every source edit. `--no-dev` excludes the dev-only dependency group
# (pytest, ruff); the `desktop` extra (pywebview) is never requested, so
# it is never installed here -- this image only ever needs the core
# dependency set `orchai api serve` requires.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Now install the project itself. Migrations
# (src/orchai/infrastructure/persistence/db/migrations/*.sql) are read at
# runtime via importlib.resources against these same source files, so no
# separate "collect data files" step is needed the way a frozen
# PyInstaller build requires.
COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:${PATH}" \
    ORCHAI_API_HOST=0.0.0.0

# Run as a non-root user -- nothing in this image needs elevated
# privileges, and the application writes no files of its own (persistent
# state lives in the external database configured via ORCHAI_DATABASE_URL,
# per docs/architecture/DEPLOYMENT-MODEL.md's "Persistent Data" invariant).
RUN useradd --create-home --uid 1000 orchai && chown -R orchai:orchai /app
USER orchai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1

ENTRYPOINT ["orchai"]
CMD ["api", "serve"]
