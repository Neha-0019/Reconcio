from __future__ import annotations

from fastapi import FastAPI
from src.db import get_run_history
from src.pipeline import run_reconciliation

app = FastAPI(title="Reconcio", version="0.1.0")
_latest_report: dict | None = None


@app.post("/reconcile")
def reconcile_batch() -> dict:
    global _latest_report
    _latest_report = run_reconciliation()
    return _latest_report


@app.get("/report/latest")
def latest_report() -> dict:
    return _latest_report or {"message": "No reconciliation run in this API process yet."}


@app.get("/runs")
def runs() -> list[dict]:
    return get_run_history()
