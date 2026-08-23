from __future__ import annotations

from collections import Counter
from .models import SourceRecord


def duplicate_ids(records: list[SourceRecord]) -> set[str]:
    counts = Counter(record.transaction_id for record in records)
    return {transaction_id for transaction_id, count in counts.items() if count > 1}


def missing_reason(sources_present: set[str]) -> str:
    for source, reason in (("bank", "missing_in_bank"), ("gateway", "missing_in_gateway"), ("ledger", "missing_in_ledger")):
        if source not in sources_present:
            return reason
    return "unclassified"
