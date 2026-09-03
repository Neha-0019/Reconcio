"""Deterministic, explainable three-way reconciliation logic."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from rapidfuzz.fuzz import token_sort_ratio

from .exceptions import duplicate_ids, missing_reason
from .models import ExceptionRecord, MatchResult, SourceRecord


@dataclass(frozen=True)
class MatchConfig:
    amount_tolerance: float = 5.0
    fee_percent_tolerance: float = 0.02
    date_window_days: int = 3
    min_similarity_score: float = 85.0


def _index(records: list[SourceRecord]) -> dict[str, list[SourceRecord]]:
    result: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        result[record.transaction_id].append(record)
    return result


def _reference_key(record: SourceRecord) -> str:
    """Normalize references for candidate lookup; RapidFuzz still scores the final match."""
    return "".join(character.lower() for character in record.reference if character.isalnum())


def _reference_index(records: list[SourceRecord]) -> dict[str, list[SourceRecord]]:
    result: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        key = _reference_key(record)
        if key:
            result[key].append(record)
    return result


def _candidate_records(record: SourceRecord, id_index: dict[str, list[SourceRecord]], reference_index: dict[str, list[SourceRecord]]) -> list[SourceRecord]:
    """Return only records that share an ID or normalized reference with the anchor."""
    candidates = [*id_index.get(record.transaction_id, []), *reference_index.get(_reference_key(record), [])]
    return list({id(candidate): candidate for candidate in candidates}.values())


def _match_result(gateway: SourceRecord, bank: SourceRecord, ledger: SourceRecord, tier: str, rules: list[str], similarity: float | None = None, confidence: float | None = None) -> MatchResult:
    if confidence is None:
        confidence = 1.0 if tier == "tier_1_exact" else 0.8
    return MatchResult(
        transaction_ids={"gateway": gateway.transaction_id, "bank": bank.transaction_id, "ledger": ledger.transaction_id},
        amounts={"gateway": gateway.amount, "bank": bank.amount, "ledger": ledger.amount},
        tier=tier, rules_fired=rules, confidence=confidence, similarity_score=round(similarity, 2) if similarity is not None else None,
    )


def _within_amount(reference: float, candidate: float, config: MatchConfig) -> bool:
    difference = abs(reference - candidate)
    return difference <= config.amount_tolerance or difference <= abs(reference) * config.fee_percent_tolerance


def _fuzzy_score(left: SourceRecord, right: SourceRecord) -> float:
    return max(token_sort_ratio(left.reference, right.reference), token_sort_ratio(left.payer_name, right.payer_name))


def reconcile(records_by_source: dict[str, list[SourceRecord]], config: MatchConfig | None = None) -> tuple[list[MatchResult], list[ExceptionRecord]]:
    """Apply exact, then fuzzy matching; return only deterministic decisions."""
    config = config or MatchConfig()
    gateway = records_by_source.get("gateway", [])
    bank = records_by_source.get("bank", [])
    ledger = records_by_source.get("ledger", [])
    indexes = {"gateway": _index(gateway), "bank": _index(bank), "ledger": _index(ledger)}
    reference_indexes = {"gateway": _reference_index(gateway), "bank": _reference_index(bank), "ledger": _reference_index(ledger)}
    duplicate_by_source = {source: duplicate_ids(records) for source, records in records_by_source.items()}
    duplicate_keys = set().union(*duplicate_by_source.values())
    matches: list[MatchResult] = []
    used: dict[str, set[int]] = {"gateway": set(), "bank": set(), "ledger": set()}

    # Tier 1: IDs uniquely present in all sources and equal amounts to paise precision.
    for transaction_id in set(indexes["gateway"]) & set(indexes["bank"]) & set(indexes["ledger"]):
        if transaction_id in duplicate_keys:
            continue
        g, b, l = indexes["gateway"][transaction_id][0], indexes["bank"][transaction_id][0], indexes["ledger"][transaction_id][0]
        if max(g.amount, b.amount, l.amount) - min(g.amount, b.amount, l.amount) <= 0.01:
            matches.append(_match_result(g, b, l, "tier_1_exact", ["transaction_id_exact", "amount_exact"], similarity=100.0, confidence=1.0))
            used["gateway"].add(id(g)); used["bank"].add(id(b)); used["ledger"].add(id(l))

    # Tier 2: indexed candidate lookup avoids comparing every possible 3-way combination.
    candidates: list[tuple[float, SourceRecord, SourceRecord, SourceRecord, list[str], float]] = []
    for g in gateway:
        bank_candidates = _candidate_records(g, indexes["bank"], reference_indexes["bank"])
        ledger_candidates = _candidate_records(g, indexes["ledger"], reference_indexes["ledger"])
        for b in bank_candidates:
            for l in ledger_candidates:
                if any(id(item) in used[source] for source, item in (("gateway", g), ("bank", b), ("ledger", l))):
                    continue
                if g.transaction_id in duplicate_keys or b.transaction_id in duplicate_keys or l.transaction_id in duplicate_keys:
                    continue
                if not (_within_amount(g.amount, b.amount, config) and _within_amount(g.amount, l.amount, config)):
                    continue
                day_delta = max(abs((g.transaction_date - b.transaction_date).days), abs((g.transaction_date - l.transaction_date).days))
                if day_delta > config.date_window_days:
                    continue
                similarity = min(_fuzzy_score(g, b), _fuzzy_score(g, l))
                if similarity < config.min_similarity_score:
                    continue
                amt_diff = max(abs(g.amount - b.amount), abs(g.amount - l.amount))
                rules = ["fuzzy_reference_match"]
                scores = [similarity / 100.0]
                if amt_diff > 0.01:
                    rules.append("amount_tolerance")
                    scores.append(max(0.0, 1.0 - (amt_diff / config.amount_tolerance)))
                if day_delta > 0:
                    rules.append("date_tolerance")
                    scores.append(max(0.0, 1.0 - (day_delta / config.date_window_days)))
                candidates.append((similarity, g, b, l, rules, round(sum(scores) / len(scores), 2)))

    for similarity, g, b, l, rules, confidence in sorted(candidates, key=lambda item: (item[0], item[5]), reverse=True):
        if any(id(item) in used[source] for source, item in (("gateway", g), ("bank", b), ("ledger", l))):
            continue
        matches.append(_match_result(g, b, l, "tier_2_fuzzy", rules, similarity=similarity, confidence=confidence))
        used["gateway"].add(id(g)); used["bank"].add(id(b)); used["ledger"].add(id(l))

    exceptions: list[ExceptionRecord] = []
    emitted_duplicates: set[str] = set()
    remaining: dict[str, list[SourceRecord]] = {
        source: [record for record in records if id(record) not in used[source]] for source, records in records_by_source.items()
    }
    by_id: dict[str, list[SourceRecord]] = defaultdict(list)
    for records in remaining.values():
        for record in records:
            by_id[record.transaction_id].append(record)
    for transaction_id, records in by_id.items():
        present = sorted({record.source for record in records})
        amount_difference = round(max(record.amount for record in records) - min(record.amount for record in records), 2)
        duplicate_sources = sorted(source for source, ids in duplicate_by_source.items() if transaction_id in ids)
        if transaction_id in duplicate_keys:
            if transaction_id in emitted_duplicates:
                continue
            reason, emitted_duplicates = "duplicate_id", emitted_duplicates | {transaction_id}
        elif len(present) < 3:
            reason = missing_reason(set(present))
        elif len({round(record.amount, 2) for record in records}) > 1:
            reason = "amount_mismatch_unresolved"
        else:
            reason = "unclassified"
        exceptions.append(ExceptionRecord(
            transaction_id=transaction_id,
            sources_present=present,
            amount=records[0].amount,
            reason_code=reason,
            amount_difference=amount_difference,
            matching_tolerance=config.amount_tolerance,
            duplicate_sources=duplicate_sources,
        ))
    return matches, exceptions
