from data.generate_synthetic_data import main as generate_data
from src.pipeline import run_reconciliation


def test_pipeline_runs_end_to_end(tmp_path):
    generate_data()
    outcome = run_reconciliation(db_path=tmp_path / "reconcio.db")
    assert outcome["metrics"]["matched_count"] > 50
    assert outcome["metrics"]["exception_count_by_reason"]
