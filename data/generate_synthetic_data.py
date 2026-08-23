"""Generate a repeatable, intentionally imperfect Razorpay-style demo batch."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import random

import pandas as pd

RANDOM_SEED = 20260823
TOTAL_TRANSACTIONS = 65
OUTPUT_DIR = Path(__file__).parent
METHODS = ["UPI", "Card", "Netbanking"]
NAMES = ["Aarav Sharma", "Diya Patel", "Kabir Singh", "Ananya Iyer", "Rohan Mehta", "Isha Nair"]


def _row(txn_id: str, amount: float, txn_date: date, reference: str, payer: str, method: str) -> dict:
    return {
        "transaction_id": txn_id,
        "amount": round(amount, 2),
        "transaction_date": txn_date.isoformat(),
        "reference": reference,
        "payer_name": payer,
        "payment_method": method,
    }


def generate() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    random.seed(RANDOM_SEED)
    base_date = date.today() - timedelta(days=29)
    gateway, bank, ledger = [], [], []
    # 52 exact, 4 settlement lags, 3 fee deductions, 2 rounding variations,
    # 1 reference/ID formatting variation, and 3 deliberately missing records.
    for index in range(TOTAL_TRANSACTIONS):
        txn_id = f"pay_{index + 1:014d}"
        amount = round(random.uniform(149, 14999), 2)
        txn_date = base_date + timedelta(days=index % 29)
        payer = NAMES[index % len(NAMES)]
        reference = f"RZP-{index + 1:05d}-{payer.split()[0].upper()}"
        method = METHODS[index % len(METHODS)]
        source_row = _row(txn_id, amount, txn_date, reference, payer, method)
        # This transaction is deliberately absent from the gateway only.
        if index != 63:
            gateway.append(source_row)
        ledger.append(source_row.copy())

        if index in {61, 62}:  # absent from bank
            continue
        bank_row = source_row.copy()
        if index in {52, 53, 54, 55}:
            bank_row["transaction_date"] = (txn_date + timedelta(days=(index % 3) + 1)).isoformat()
        elif index in {56, 57, 58}:
            fee = round(min(amount * 0.015, 4.75), 2)
            bank_row["amount"] = round(amount - fee, 2)
            bank_row["reference"] = f"SETTLEMENT {reference}"
        elif index in {59, 60}:
            bank_row["amount"] = round(amount - (0.25 if index == 59 else 0.49), 2)
        elif index == 64:  # no direct ID match, but clear fuzzy reference match
            bank_row["transaction_id"] = "bank_ref_00065"
            bank_row["reference"] = reference.replace("-", " ")
        bank.append(bank_row)

    # A duplicate gateway ID is an explicit edge case and must never be matched twice.
    duplicate = gateway[10].copy()
    duplicate["reference"] = f"{duplicate['reference']}-DUP"
    gateway.append(duplicate)
    return pd.DataFrame(gateway), pd.DataFrame(bank), pd.DataFrame(ledger)


def main() -> None:
    gateway, bank, ledger = generate()
    gateway.to_csv(OUTPUT_DIR / "gateway_settlements.csv", index=False)
    bank.to_csv(OUTPUT_DIR / "bank_statement.csv", index=False)
    ledger.to_csv(OUTPUT_DIR / "internal_ledger.csv", index=False)
    print(f"Generated gateway={len(gateway)}, bank={len(bank)}, ledger={len(ledger)} source records.")


if __name__ == "__main__":
    main()
