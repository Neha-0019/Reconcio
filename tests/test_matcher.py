from datetime import date, timedelta
from src.matcher import MatchConfig, reconcile
from src.models import SourceRecord


def record(source, tx, amount=100, when=date(2026, 8, 1), reference="RZP ABC", name="Aarav"):
    return SourceRecord(source=source, transaction_id=tx, amount=amount, transaction_date=when, reference=reference, payer_name=name)


def test_tier_one_exact_match():
    records = {source: [record(source, "pay_1")] for source in ("gateway", "bank", "ledger")}
    matches, exceptions = reconcile(records)
    assert len(matches) == 1 and matches[0].tier == "tier_1_exact"
    assert exceptions == []


def test_tier_two_tags_amount_and_date_tolerance():
    when = date(2026, 8, 1)
    records = {"gateway": [record("gateway", "pay_1", 100, when)], "bank": [record("bank", "pay_1", 98, when + timedelta(days=2))], "ledger": [record("ledger", "pay_1", 100, when)]}
    matches, _ = reconcile(records, MatchConfig(amount_tolerance=3, date_window_days=3))
    rule_prefixes = {r.split(":")[0] for r in matches[0].rules_fired}
    assert {"amount_tolerance", "date_tolerance", "fuzzy_reference_match"}.issubset(rule_prefixes)


def test_missing_and_duplicate_are_exceptions_not_matches():
    records = {"gateway": [record("gateway", "pay_a"), record("gateway", "pay_a")], "bank": [record("bank", "pay_a"), record("bank", "pay_b")], "ledger": [record("ledger", "pay_a"), record("ledger", "pay_b")]}
    matches, exceptions = reconcile(records)
    reasons = {item.transaction_id: item.reason_code for item in exceptions}
    assert matches == []
    assert reasons["pay_a"] == "duplicate_id"
    assert reasons["pay_b"] == "missing_in_gateway"
