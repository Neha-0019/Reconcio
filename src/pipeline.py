from __future__ import annotations

from pathlib import Path
import time
import pandas as pd

from .db import DEFAULT_DB_PATH, persist_run
from .explainer import explain_exception
from .matcher import MatchConfig, reconcile
from .metrics import compute_metrics
from .models import SourceRecord

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REQUIRED_COLUMNS = {"transaction_id", "amount", "transaction_date", "reference", "payer_name", "payment_method"}


class ReconciliationInputError(ValueError):
    """Raised when an uploaded source file cannot be safely reconciled."""


def records_from_frames(frames: dict[str, pd.DataFrame]) -> dict[str, list[SourceRecord]]:
    """Validate standardized source frames and convert them into typed records."""
    required_sources = {"gateway", "bank", "ledger"}
    missing_sources = required_sources - set(frames)
    if missing_sources:
        raise ReconciliationInputError(f"Missing required source file(s): {', '.join(sorted(missing_sources))}.")
    result: dict[str, list[SourceRecord]] = {}
    for source in sorted(required_sources):
        frame = frames[source]
        missing_columns = REQUIRED_COLUMNS - set(frame.columns)
        if missing_columns:
            raise ReconciliationInputError(f"{source} CSV is missing required column(s): {', '.join(sorted(missing_columns))}.")
        if frame.empty:
            raise ReconciliationInputError(f"{source} CSV contains no data rows.")
        records = []
        for row_number, row in enumerate(frame.to_dict(orient="records"), start=2):
            try:
                records.append(SourceRecord(source=source, **row))
            except Exception as error:
                raise ReconciliationInputError(f"{source} CSV row {row_number} is invalid: {error}") from error
        result[source] = records
    total_count = sum(len(records) for records in result.values())
    print(f"Loaded {total_count} records from 3 sources.")
    return result


def load_source_records(data_dir: Path | str = DATA_DIR) -> dict[str, list[SourceRecord]]:
    data_dir = Path(data_dir)
    files = {"gateway": "gateway_settlements.csv", "bank": "bank_statement.csv", "ledger": "internal_ledger.csv"}
    frames = {}
    for source, filename in files.items():
        frames[source] = pd.read_csv(data_dir / filename)
    return records_from_frames(frames)


def run_reconciliation(data_dir: Path | str = DATA_DIR, db_path: Path | str = DEFAULT_DB_PATH, config: MatchConfig | None = None, enable_ai: bool = False) -> dict:
    started = time.perf_counter()
    records = load_source_records(data_dir)
    return run_reconciliation_records(records, db_path, config, enable_ai, started)


def run_reconciliation_from_frames(frames: dict[str, pd.DataFrame], db_path: Path | str = DEFAULT_DB_PATH, config: MatchConfig | None = None, enable_ai: bool = False) -> dict:
    """Run a batch from validated user-uploaded CSV dataframes."""
    started = time.perf_counter()
    records = records_from_frames(frames)
    return run_reconciliation_records(records, db_path, config, enable_ai, started)


def run_reconciliation_records(records: dict[str, list[SourceRecord]], db_path: Path | str = DEFAULT_DB_PATH, config: MatchConfig | None = None, enable_ai: bool = False, started: float | None = None) -> dict:
    started = started or time.perf_counter()
    matches, exceptions = reconcile(records, config)
    if enable_ai:
        for item in exceptions:
            explanation = explain_exception(item)
            item.ai_explanation = {"source": explanation.source, **explanation.explanation.model_dump()}
    metrics = compute_metrics(records, matches, exceptions, 0)
    run_id = persist_run(records, matches, exceptions, metrics, started, db_path)
    return {"run_id": run_id, "metrics": metrics.model_dump(), "matches": [item.model_dump() for item in matches], "exceptions": [item.model_dump() for item in exceptions]}
