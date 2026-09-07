import asyncio
from datetime import UTC, datetime, timedelta

from orchai.domain.identifiers import ProjectId
from orchai.domain.metrics import MetricRecord
from orchai.infrastructure.persistence import SQLAlchemyDatabase, SQLAlchemyMetricsRepository


def test_summarize_with_no_group_by_returns_one_bucket_per_name(tmp_path) -> None:
    async def run() -> None:
        database = SQLAlchemyDatabase(f"sqlite:///{tmp_path / 'orchai.db'}")
        database.migrate()
        repository = SQLAlchemyMetricsRepository(database)
        await repository.add_many(
            (
                MetricRecord(name="execution.duration", value=100.0, unit="ms"),
                MetricRecord(name="execution.duration", value=200.0, unit="ms"),
                MetricRecord(name="execution.success", value=1.0, unit="count"),
            )
        )

        summaries = await repository.summarize()

        by_name = {summary.name: summary for summary in summaries}
        assert by_name["execution.duration"].count == 2
        assert by_name["execution.duration"].sum == 300.0
        assert by_name["execution.duration"].avg == 150.0
        assert by_name["execution.success"].count == 1

    asyncio.run(run())


def test_summarize_groups_by_requested_dimensions(tmp_path) -> None:
    async def run() -> None:
        database = SQLAlchemyDatabase(f"sqlite:///{tmp_path / 'orchai.db'}")
        database.migrate()
        repository = SQLAlchemyMetricsRepository(database)
        await repository.add_many(
            (
                MetricRecord(
                    name="execution.duration",
                    value=100.0,
                    unit="ms",
                    dimensions={"role": "DEVELOPER", "action": "IMPLEMENT"},
                ),
                MetricRecord(
                    name="execution.duration",
                    value=300.0,
                    unit="ms",
                    dimensions={"role": "DEVELOPER", "action": "IMPLEMENT"},
                ),
                MetricRecord(
                    name="execution.duration",
                    value=50.0,
                    unit="ms",
                    dimensions={"role": "QUALITY_AGENT", "action": "TEST"},
                ),
            )
        )

        summaries = await repository.summarize(group_by=("role", "action"))

        assert len(summaries) == 2
        developer_bucket = next(
            s for s in summaries if s.dimensions["role"] == "DEVELOPER"
        )
        assert developer_bucket.count == 2
        assert developer_bucket.sum == 400.0
        assert developer_bucket.dimensions == {"role": "DEVELOPER", "action": "IMPLEMENT"}
        quality_bucket = next(
            s for s in summaries if s.dimensions["role"] == "QUALITY_AGENT"
        )
        assert quality_bucket.count == 1
        assert quality_bucket.sum == 50.0

    asyncio.run(run())


def test_summarize_filters_by_project_id(tmp_path) -> None:
    async def run() -> None:
        database = SQLAlchemyDatabase(f"sqlite:///{tmp_path / 'orchai.db'}")
        database.migrate()
        repository = SQLAlchemyMetricsRepository(database)
        project_a = ProjectId.new()
        project_b = ProjectId.new()
        await repository.add_many(
            (
                MetricRecord(
                    name="execution.duration", value=10.0, unit="ms", project_id=project_a
                ),
                MetricRecord(
                    name="execution.duration", value=20.0, unit="ms", project_id=project_b
                ),
            )
        )

        summaries = await repository.summarize(project_id=project_a)

        assert len(summaries) == 1
        assert summaries[0].sum == 10.0

    asyncio.run(run())


def test_summarize_filters_by_time_window(tmp_path) -> None:
    async def run() -> None:
        database = SQLAlchemyDatabase(f"sqlite:///{tmp_path / 'orchai.db'}")
        database.migrate()
        repository = SQLAlchemyMetricsRepository(database)
        now = datetime.now(UTC)
        await repository.add_many(
            (
                MetricRecord(
                    name="execution.duration",
                    value=10.0,
                    unit="ms",
                    observed_at=now - timedelta(days=2),
                ),
                MetricRecord(
                    name="execution.duration",
                    value=20.0,
                    unit="ms",
                    observed_at=now,
                ),
            )
        )

        summaries = await repository.summarize(since=now - timedelta(hours=1))

        assert len(summaries) == 1
        assert summaries[0].sum == 20.0

    asyncio.run(run())


def test_summarize_with_no_matching_records_returns_empty(tmp_path) -> None:
    async def run() -> None:
        database = SQLAlchemyDatabase(f"sqlite:///{tmp_path / 'orchai.db'}")
        database.migrate()
        repository = SQLAlchemyMetricsRepository(database)

        summaries = await repository.summarize(name="does.not.exist")

        assert summaries == ()

    asyncio.run(run())


def test_summarize_rejects_an_unsupported_group_by_field(tmp_path) -> None:
    async def run() -> None:
        database = SQLAlchemyDatabase(f"sqlite:///{tmp_path / 'orchai.db'}")
        database.migrate()
        repository = SQLAlchemyMetricsRepository(database)

        try:
            await repository.summarize(group_by=("not_a_real_field",))
            raise AssertionError("expected ValueError")
        except ValueError:
            pass

    asyncio.run(run())
