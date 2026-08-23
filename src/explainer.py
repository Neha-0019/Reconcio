"""Optional, read-only AI annotation for already-created exceptions.

This module deliberately imports no database or matcher write APIs. It returns an
annotation or None; the deterministic matching result cannot be changed here.
"""
from __future__ import annotations

import os
import logging
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


def get_explainer_status() -> tuple[bool, str]:
    """Return configuration status without making an API call."""
    if not os.getenv("OPENAI_API_KEY"):
        return False, "AI explanation unavailable (no API key configured)"
    return True, "AI explanation enabled (read-only annotations)"


def explain_exception(exception: ExceptionRecord) -> ExceptionExplanation | None:
    """Return schema-validated annotation, or None when no configured LLM exists."""
    configured, _ = get_explainer_status()
    if not configured:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        completion = client.beta.chat.completions.parse(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": "Explain only. You cannot change financial data or matching decisions."}, {"role": "user", "content": exception.model_dump_json()}],
            response_format=ExceptionExplanation,
        )
        return completion.choices[0].message.parsed
    except Exception:
        logger.exception("AI explanation failed for exception transaction_id=%s", exception.transaction_id)
        return None
