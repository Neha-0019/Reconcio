from __future__ import annotations

from io import BytesIO
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from src.db import get_run_history
from src.pipeline import ReconciliationInputError, run_reconciliation, run_reconciliation_from_frames

app = FastAPI(title="Reconcio", version="0.1.0")
_latest_report: dict | None = None


@app.post("/reconcile")
def reconcile_batch() -> dict:
    global _latest_report
    # Explanations are read-only annotations of exceptions that the
    # deterministic matcher has already finalized.
    _latest_report = run_reconciliation(enable_ai=True)
    return _latest_report


@app.post("/reconcile-upload")
async def reconcile_upload(
    gateway_file: UploadFile = File(...),
    bank_file: UploadFile = File(...),
    ledger_file: UploadFile = File(...),
) -> dict:
    """Validate three uploaded CSVs and reconcile them without writing user files to disk."""
    global _latest_report
    try:
        uploads = {"gateway": gateway_file, "bank": bank_file, "ledger": ledger_file}
        frames = {}
        for source, upload in uploads.items():
            if not upload.filename or not upload.filename.lower().endswith(".csv"):
                raise ReconciliationInputError(f"{source} upload must be a .csv file.")
            frames[source] = pd.read_csv(BytesIO(await upload.read()))
        _latest_report = run_reconciliation_from_frames(frames, enable_ai=True)
        return _latest_report
    except (ReconciliationInputError, UnicodeDecodeError, pd.errors.ParserError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/report/latest")
def latest_report() -> dict:
    return _latest_report or {"message": "No reconciliation run in this API process yet."}


@app.get("/runs")
def runs() -> list[dict]:
    return get_run_history()
