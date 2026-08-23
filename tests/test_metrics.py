from datetime import date
from src.metrics import compute_metrics
from src.models import ExceptionRecord, MatchResult, SourceRecord


def test_metrics_exact_arithmetic():
    rows = {source: [SourceRecord(source=source, transaction_id="pay_1", amount=100, transaction_date=date(2026, 8, 1))] for source in ("gateway", "bank", "ledger")}
    match = MatchResult(transaction_ids={"gateway": "pay_1", "bank": "pay_1", "ledger": "pay_1"}, amounts={"gateway": 100, "bank": 100, "ledger": 100}, tier="tier_1_exact", rules_fired=[], confidence=1)
    metrics = compute_metrics(rows, [match], [ExceptionRecord(transaction_id="pay_x", sources_present=["gateway"], amount=25, reason_code="missing_in_bank")], 0.5)
    assert metrics.matched_pct == 100
    assert metrics.value_matched == 100
    assert metrics.value_in_exceptions == 25
    assert metrics.records_per_second == 6
