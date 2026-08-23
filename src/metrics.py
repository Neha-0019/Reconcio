from __future__ import annotations

from collections import Counter
from .models import ExceptionRecord, MatchResult, ReconciliationMetrics, SourceRecord


def compute_metrics(records_by_source: dict[str, list[SourceRecord]], matches: list[MatchResult], exceptions: list[ExceptionRecord], duration: float) -> ReconciliationMetrics:
    total_unique = len(set().union(*(set(r.transaction_id for r in records) for records in records_by_source.values())))
    matched_count = len(matches)
    tier_1_count = sum(match.tier == "tier_1_exact" for match in matches)
    tier_2_count = sum(match.tier == "tier_2_fuzzy" for match in matches)
    total_records = sum(len(records) for records in records_by_source.values())
    return ReconciliationMetrics(
        total_records_per_source={source: len(records) for source, records in records_by_source.items()},
        matched_count=matched_count,
        matched_pct=round((matched_count / total_unique * 100) if total_unique else 0, 2),
        tier_1_count=tier_1_count,
        tier_2_count=tier_2_count,
        tier_1_exact_pct=round((tier_1_count / total_unique * 100) if total_unique else 0, 2),
        tier_2_fuzzy_pct=round((tier_2_count / total_unique * 100) if total_unique else 0, 2),
        exception_count_by_reason=dict(Counter(item.reason_code for item in exceptions)),
        value_matched=round(sum(match.amounts["gateway"] for match in matches), 2),
        value_in_exceptions=round(sum(item.amount for item in exceptions), 2),
        processing_time_seconds=round(duration, 6),
        records_per_second=round(total_records / duration, 2) if duration else 0,
    )
