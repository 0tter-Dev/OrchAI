"""Pure aggregation logic shared by every `MetricsRepository` implementation.

Kept independent of any persistence technology so `SQLAlchemyMetricsRepository`
and `InMemoryMetricsRepository` compute identical results from the same
already-loaded `MetricRecord`s, rather than each repository re-implementing
grouping/summing on its own.
"""

from __future__ import annotations

from collections import defaultdict

from orchai.application.metrics.ports import SUMMARY_GROUP_BY_FIELDS
from orchai.domain.metrics import MetricRecord, MetricSummary


def summarize_records(
    records: tuple[MetricRecord, ...],
    *,
    group_by: tuple[str, ...] = (),
) -> tuple[MetricSummary, ...]:
    """Aggregate `records` into one `MetricSummary` per (name, group_by key)."""

    invalid = set(group_by) - SUMMARY_GROUP_BY_FIELDS
    if invalid:
        raise ValueError(f"unsupported group_by field(s): {sorted(invalid)}")

    buckets: dict[tuple[str, ...], list[MetricRecord]] = defaultdict(list)
    for record in records:
        key = (record.name, *(_dimension_value(record, field) for field in group_by))
        buckets[key].append(record)

    summaries = []
    for key, bucket in buckets.items():
        total = sum(record.value for record in bucket)
        summaries.append(
            MetricSummary(
                name=key[0],
                unit=bucket[0].unit,
                count=len(bucket),
                sum=total,
                avg=total / len(bucket),
                dimensions=dict(zip(group_by, key[1:], strict=True)),
            )
        )
    return tuple(
        sorted(summaries, key=lambda summary: (summary.name, tuple(summary.dimensions.items())))
    )


def _dimension_value(record: MetricRecord, field: str) -> str:
    if field == "project_id":
        return str(record.project_id) if record.project_id is not None else ""
    return str(record.dimensions.get(field, ""))
