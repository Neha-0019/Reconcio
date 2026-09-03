from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

SourceName = Literal["gateway", "bank", "ledger"]


class SourceRecord(BaseModel):
    source: SourceName
    transaction_id: str
    amount: float = Field(ge=0)
    transaction_date: date
    reference: str = ""
    payer_name: str = ""
    payment_method: str = ""


class MatchResult(BaseModel):
    transaction_ids: dict[SourceName, str]
    amounts: dict[SourceName, float]
    tier: Literal["tier_1_exact", "tier_2_fuzzy"]
    rules_fired: list[str]
    confidence: float = Field(ge=0, le=1)
    similarity_score: float | None = None


class ExceptionRecord(BaseModel):
    transaction_id: str
    sources_present: list[SourceName]
    amount: float
    reason_code: str
    rule_trace: list[str] = []
    confidence: float = Field(default=0, ge=0, le=1)
    amount_difference: float | None = None
    matching_tolerance: float | None = None
    duplicate_sources: list[SourceName] = []
    ai_explanation: dict | None = None


class ReconciliationMetrics(BaseModel):
    total_records_per_source: dict[str, int]
    matched_count: int
    matched_pct: float
    tier_1_count: int
    tier_2_count: int
    tier_1_exact_pct: float
    tier_2_fuzzy_pct: float
    exception_count_by_reason: dict[str, int]
    value_matched: float
    value_in_exceptions: float
    processing_time_seconds: float
    records_per_second: float
