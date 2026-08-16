import asyncio

from orchai.application.orchestration import run_local_flow
from orchai.bootstrap import build_sqlalchemy_local_flow_dependencies


def test_local_flow_runs_task_authorization_execution_and_context(tmp_path) -> None:
    async def run() -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")

        result = await run_local_flow(
            project_root=tmp_path,
            context_path="docs/INDEX.md",
            title="Integration flow",
            model="local-demo",
            dependencies=build_sqlalchemy_local_flow_dependencies(
                f"sqlite:///{tmp_path / 'orchai.db'}"
            ),
            storage_label=f"sqlite:///{tmp_path / 'orchai.db'}",
        )

        assert result["task_state"] == "IMPLEMENTED"
        assert result["execution_state"] == "COMPLETED"
        assert result["context_items"] == "1"
        assert result["database"].startswith("sqlite:///")
        assert int(result["events"]) >= 10

    asyncio.run(run())
