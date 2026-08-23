from datetime import date
from src.db import get_run_history
from src.pipeline import run_reconciliation


def test_persisted_run_is_visible_in_audit_history(tmp_path):
    data_dir = tmp_path / "data"; data_dir.mkdir()
    csv = "transaction_id,amount,transaction_date,reference,payer_name,payment_method\npay_1,100,2026-08-01,REF,Aarav,UPI\n"
    for name in ("gateway_settlements.csv", "bank_statement.csv", "internal_ledger.csv"):
        (data_dir / name).write_text(csv)
    db_path = tmp_path / "test.db"
    outcome = run_reconciliation(data_dir, db_path)
    history = get_run_history(db_path)
    assert history[0]["id"] == outcome["run_id"] and history[0]["batch_size"] == 3
