from __future__ import annotations

import sys
import json
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.db import get_run_history
from src.explainer import get_explainer_status
from src.pipeline import ReconciliationInputError, run_reconciliation, run_reconciliation_from_frames

st.set_page_config(page_title="Reconcio", page_icon="💸", layout="wide")
st.title("Reconcio")
st.caption("Deterministic 3-way reconciliation with honest, explainable exceptions.")

if "report" not in st.session_state:
    st.session_state.report = run_reconciliation(enable_ai=True)

if st.button("Run Reconciliation", type="primary"):
    with st.spinner("Reconciling gateway, bank, and ledger records..."):
        st.session_state.report = run_reconciliation(enable_ai=True)

with st.expander("Upload CSV batch (optional)"):
    st.caption("Upload all three standardized CSV files to reconcile your own batch. Required columns: transaction_id, amount, transaction_date, reference, payer_name, payment_method.")
    upload_columns = st.columns(3)
    gateway_upload = upload_columns[0].file_uploader("Gateway settlements CSV", type=["csv"], key="gateway_upload")
    bank_upload = upload_columns[1].file_uploader("Bank statement CSV", type=["csv"], key="bank_upload")
    ledger_upload = upload_columns[2].file_uploader("Internal ledger CSV", type=["csv"], key="ledger_upload")
    uploads_ready = all((gateway_upload, bank_upload, ledger_upload))
    if st.button("Run Uploaded Reconciliation", disabled=not uploads_ready):
        try:
            uploaded_frames = {
                "gateway": pd.read_csv(gateway_upload),
                "bank": pd.read_csv(bank_upload),
                "ledger": pd.read_csv(ledger_upload),
            }
            with st.spinner("Validating and reconciling uploaded files..."):
                st.session_state.report = run_reconciliation_from_frames(uploaded_frames, enable_ai=True)
            st.success("Uploaded CSV batch reconciled successfully.")
        except (ReconciliationInputError, UnicodeDecodeError, pd.errors.ParserError) as error:
            st.error(f"Upload validation failed: {error}")
    elif any((gateway_upload, bank_upload, ledger_upload)):
        st.info("Upload all three source CSVs to enable reconciliation.")

report = st.session_state.get("report")
if report:
    metrics = report["metrics"]
    has_tier_breakdown = "tier_1_exact_pct" in metrics and "tier_2_fuzzy_pct" in metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Match rate", f"{metrics['matched_pct']}%")
    col2.metric("Tier 1 exact", f"{metrics['tier_1_exact_pct']}%" if has_tier_breakdown else "Run again")
    col3.metric("Tier 2 fuzzy", f"{metrics['tier_2_fuzzy_pct']}%" if has_tier_breakdown else "Run again")
    col4.metric("Value matched", f"₹{metrics['value_matched']:,.2f}")
    col5.metric("Unreconciled cash exposure", f"₹{metrics['value_in_exceptions']:,.2f}")
    col6.metric("Throughput", f"{metrics['records_per_second']:,.0f} records/sec")
    st.caption("Unreconciled cash exposure is the value represented by unresolved exceptions. It is not a bank-balance forecast.")
    if not has_tier_breakdown:
        st.info("This is a legacy in-memory report. Click Run Reconciliation to calculate the tier breakdown.")

    st.subheader("Matched Records")
    match_rows = []
    for match in report["matches"]:
        rules = [
            f"{rule}:rapidfuzz_score={match['similarity_score']}"
            if rule == "fuzzy_reference_match" and match["similarity_score"] is not None
            else rule
            for rule in match["rules_fired"]
        ]
        match_rows.append({
            "transaction_id": match["transaction_ids"]["gateway"],
            "tier": match["tier"],
            "amount_difference": round(max(match["amounts"].values()) - min(match["amounts"].values()), 2),
            "rule_trace": ", ".join(rules),
            "confidence": match["confidence"],
        })
    match_frame = pd.DataFrame(match_rows)
    tier_filter = st.selectbox("Filter matched records by tier", ["All tiers", "tier_1_exact", "tier_2_fuzzy"])
    if tier_filter != "All tiers":
        match_frame = match_frame[match_frame["tier"] == tier_filter]
    st.dataframe(match_frame, use_container_width=True, hide_index=True)

    st.subheader("Exceptions")
    st.caption("Exceptions show confidence 0; their displayed rule trace confirms that no matching rule fired.")
    exception_frame = pd.DataFrame(report["exceptions"])
    if exception_frame.empty:
        st.success("No exceptions in this batch.")
    else:
        ai_enabled, ai_status = get_explainer_status()
        if ai_enabled:
            st.success(ai_status)
        else:
            st.info("No AI API key configured — showing deterministic rule-based explanations for all exceptions below.")
        exception_frame["rule_trace"] = exception_frame["rule_trace"].apply(
            lambda value: ", ".join(value) if value else "No matching rule fired"
        )
        exception_frame["ai_explanation"] = exception_frame["ai_explanation"].apply(
            lambda value: (
                f"[AI]: {value['explanation']}"
                if value and value.get("source") == "ai"
                else f"[Rule-based]: {value['explanation']}"
                if value and value.get("explanation")
                else "[Rule-based]: Could not be automatically categorized. Needs manual review."
            )
        )
        exception_counts = (
            exception_frame["reason_code"]
            .value_counts()
            .rename_axis("reason_code")
            .reset_index(name="count")
        )
        exception_chart = alt.Chart(exception_counts).mark_bar().encode(
            x=alt.X(
                "reason_code:N",
                title=None,
                axis=alt.Axis(labelAngle=0, labelLimit=250, labelPadding=12),
            ),
            y=alt.Y("count:Q", title="Exceptions", axis=alt.Axis(tickMinStep=1)),
            tooltip=[alt.Tooltip("reason_code:N", title="Reason"), alt.Tooltip("count:Q", title="Count")],
        ).properties(height=280)
        st.altair_chart(exception_chart, use_container_width=True)

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
