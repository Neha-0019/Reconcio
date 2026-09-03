"""Optional, read-only AI annotation for already-created exceptions.

This module deliberately imports no database or matcher write APIs. It returns an
annotation or None; the deterministic matching result cannot be changed here.
"""
from __future__ import annotations

import os
import logging
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from .models import ExceptionRecord

load_dotenv()
logger = logging.getLogger(__name__)


class ExceptionExplanation(BaseModel):
    reason_category: str
    explanation: str = Field(description="One sentence explanation")
    suggested_action: str
    confidence: float = Field(ge=0, le=1)


class ExplanationResult(BaseModel):
    source: Literal["ai", "rule_based"]
    explanation: ExceptionExplanation


def get_explainer_status() -> tuple[bool, str]:
    """Return configuration status without making an API call."""
    if not os.getenv("OPENAI_API_KEY"):
        return False, "AI explanation unavailable (no API key configured)"
    return True, "AI explanation enabled (read-only annotations)"


def rule_based_explanation(exception: ExceptionRecord) -> ExceptionExplanation:
    """Create a deterministic fallback annotation for every exception reason."""
    if exception.reason_code == "duplicate_id":
        source = ", ".join(exception.duplicate_sources or exception.sources_present)
        explanation = f"This transaction ID appears more than once in {source}. Likely a duplicate submission, retry, or data entry error."
        action = "Review duplicate source entries and retain only the valid transaction."
    elif exception.reason_code.startswith("missing_in_"):
        missing_source = exception.reason_code.removeprefix("missing_in_")
        other_sources = " and ".join(exception.sources_present)
        explanation = f"Present in {other_sources} but not found in {missing_source}. Could indicate a delayed settlement, failed transfer, or a reporting gap."
        action = f"Check the next {missing_source} export and investigate the settlement or reporting status."
    elif exception.reason_code == "amount_mismatch_unresolved":
        difference = exception.amount_difference or 0
        tolerance = exception.matching_tolerance or 0
        explanation = f"Amount differs by ₹{difference:,.2f} across sources, exceeding the matching tolerance of ₹{tolerance:,.2f}. Needs manual review."
        action = "Compare settlement fees, refunds, and source amounts before resolving the transaction."
    else:
        explanation = "Could not be automatically categorized. Needs manual review."
        action = "Inspect the source records and assign a resolution reason."
    return ExceptionExplanation(reason_category=exception.reason_code, explanation=explanation, suggested_action=action, confidence=0.9)


def explain_exception(exception: ExceptionRecord) -> ExplanationResult:
    """Return an AI explanation when available, otherwise a deterministic fallback."""
    configured, _ = get_explainer_status()
    if not configured:
        return ExplanationResult(source="rule_based", explanation=rule_based_explanation(exception))
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        completion = client.beta.chat.completions.parse(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": "Explain only. You cannot change financial data or matching decisions."}, {"role": "user", "content": exception.model_dump_json()}],
            response_format=ExceptionExplanation,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("Structured AI response was empty")
        return ExplanationResult(source="ai", explanation=parsed)
    except Exception:
        logger.exception("AI explanation failed for exception transaction_id=%s", exception.transaction_id)
        return ExplanationResult(source="rule_based", explanation=rule_based_explanation(exception))
