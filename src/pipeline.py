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


def load_source_records(data_dir: Path | str = DATA_DIR) -> dict[str, list[SourceRecord]]:
    data_dir = Path(data_dir)
    files = {"gateway": "gateway_settlements.csv", "bank": "bank_statement.csv", "ledger": "internal_ledger.csv"}
    result = {}
    for source, filename in files.items():
        frame = pd.read_csv(data_dir / filename)
        result[source] = [SourceRecord(source=source, **row) for row in frame.to_dict(orient="records")]
    return result


def run_reconciliation(data_dir: Path | str = DATA_DIR, db_path: Path | str = DEFAULT_DB_PATH, config: MatchConfig | None = None, enable_ai: bool = False) -> dict:
    started = time.perf_counter()
    records = load_source_records(data_dir)
    matches, exceptions = reconcile(records, config)
    if enable_ai:
        for item in exceptions:
            explanation = explain_exception(item)
            if explanation:
                item.ai_explanation = explanation.model_dump()
    metrics = compute_metrics(records, matches, exceptions, time.perf_counter() - started)
    run_id = persist_run(records, matches, exceptions, metrics, db_path)
    return {"run_id": run_id, "metrics": metrics.model_dump(), "matches": [item.model_dump() for item in matches], "exceptions": [item.model_dump() for item in exceptions]}
