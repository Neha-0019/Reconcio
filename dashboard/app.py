from __future__ import annotations

import sys
import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.db import get_run_history
from src.explainer import get_explainer_status
from src.pipeline import run_reconciliation

st.set_page_config(page_title="Reconcio", page_icon="💸", layout="wide")
st.title("Reconcio")
st.caption("Deterministic 3-way reconciliation with honest, explainable exceptions.")

if st.button("Run Reconciliation", type="primary"):
    with st.spinner("Reconciling gateway, bank, and ledger records..."):
        st.session_state.report = run_reconciliation(enable_ai=True)

report = st.session_state.get("report")
if report:
    metrics = report["metrics"]
    has_tier_breakdown = "tier_1_exact_pct" in metrics and "tier_2_fuzzy_pct" in metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Match rate", f"{metrics['matched_pct']}%")
    col2.metric("Tier 1 exact", f"{metrics['tier_1_exact_pct']}%" if has_tier_breakdown else "Run again")
    col3.metric("Tier 2 fuzzy", f"{metrics['tier_2_fuzzy_pct']}%" if has_tier_breakdown else "Run again")
    col4.metric("Value matched", f"₹{metrics['value_matched']:,.2f}")
    col5.metric("Throughput", f"{metrics['records_per_second']:,.0f} records/sec")
    if not has_tier_breakdown:
        st.info("This is a legacy in-memory report. Click Run Reconciliation to calculate the tier breakdown.")

    st.subheader("Matched Records")
    match_rows = []
    for match in report["matches"]:
        rules = list(match["rules_fired"])
        if match["similarity_score"] is not None:
            rules = [
                f"{rule}:rapidfuzz_score={match['similarity_score']}"
                if rule == "fuzzy_reference_match"
                else rule
                for rule in rules
            ]
        match_rows.append({
            "transaction_id": match["transaction_ids"]["gateway"],
            "tier": match["tier"],
            "rule_trace": ", ".join(rules),
            "confidence": match["confidence"],
        })
    match_frame = pd.DataFrame(match_rows)
    tier_filter = st.selectbox("Filter matched records by tier", ["All tiers", "tier_1_exact", "tier_2_fuzzy"])
    if tier_filter != "All tiers":
        match_frame = match_frame[match_frame["tier"] == tier_filter]
    st.dataframe(match_frame, use_container_width=True, hide_index=True)

    st.subheader("Exceptions")
    exception_frame = pd.DataFrame(report["exceptions"])
    if exception_frame.empty:
        st.success("No exceptions in this batch.")
    else:
        ai_enabled, ai_status = get_explainer_status()
        if ai_enabled:
            st.success(ai_status)
        else:
            st.info(ai_status)
        display_status = ai_status if not ai_enabled else "AI explanation unavailable (request failed; check application log)"
        exception_frame["ai_explanation"] = exception_frame["ai_explanation"].apply(
            lambda value: json.dumps(value, ensure_ascii=False) if value else display_status
        )
        st.bar_chart(exception_frame["reason_code"].value_counts())
        query = st.text_input("Search exceptions")
        if query:
            exception_frame = exception_frame[exception_frame.astype(str).apply(lambda row: row.str.contains(query, case=False).any(), axis=1)]
        st.dataframe(exception_frame, use_container_width=True, hide_index=True)

st.subheader("Run History / Audit Trail")
history = pd.DataFrame(get_run_history())
if not history.empty:
    st.dataframe(history, use_container_width=True, hide_index=True)
else:
    st.info("Run a reconciliation to create the first append-only audit entry.")
