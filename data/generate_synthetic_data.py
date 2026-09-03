"""Generate a repeatable, intentionally imperfect Razorpay-style demo batch."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import argparse
import random
import sys

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
            fee = 500.00 if index == 56 else round(min(amount * 0.015, 4.75), 2)
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


def generate_scaled(total_transactions: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate a larger batch with the same classes of reconciliation outcomes."""
    if total_transactions < TOTAL_TRANSACTIONS:
        raise ValueError(f"Scaled batches must contain at least {TOTAL_TRANSACTIONS} transactions.")
    random.seed(RANDOM_SEED)
    base_date = date.today() - timedelta(days=29)
    gateway, bank, ledger = [], [], []
    counts = {
        "settlement_lag": round(total_transactions * 0.06),
        "fee_tolerance": round(total_transactions * 0.03),
        "rounding": round(total_transactions * 0.03),
        "fuzzy_reference": round(total_transactions * 0.015),
        "amount_unresolved": round(total_transactions * 0.015),
        "missing_bank": round(total_transactions * 0.03),
        "missing_gateway": round(total_transactions * 0.015),
        "duplicates": round(total_transactions * 0.015),
    }
    ranges: dict[str, range] = {}
    cursor = 0
    for category in ("settlement_lag", "fee_tolerance", "rounding", "fuzzy_reference", "amount_unresolved", "missing_bank", "missing_gateway"):
        ranges[category] = range(cursor, cursor + counts[category])
        cursor += counts[category]

    for index in range(total_transactions):
        txn_id = f"pay_{index + 1:014d}"
        amount = round(random.uniform(149, 14999), 2)
        txn_date = base_date + timedelta(days=index % 29)
        payer = NAMES[index % len(NAMES)]
        reference = f"RZP-{index + 1:05d}-{payer.split()[0].upper()}"
        method = METHODS[index % len(METHODS)]
        source_row = _row(txn_id, amount, txn_date, reference, payer, method)
        if index not in ranges["missing_gateway"]:
            gateway.append(source_row)
        ledger.append(source_row.copy())
        if index in ranges["missing_bank"]:
            continue
        bank_row = source_row.copy()
        if index in ranges["settlement_lag"]:
            bank_row["transaction_date"] = (txn_date + timedelta(days=(index % 3) + 1)).isoformat()
        elif index in ranges["fee_tolerance"]:
            bank_row["amount"] = round(amount - min(amount * 0.015, 4.75), 2)
            bank_row["reference"] = f"SETTLEMENT {reference}"
        elif index in ranges["rounding"]:
            bank_row["amount"] = round(amount - (0.25 if index % 2 else 0.49), 2)
        elif index in ranges["fuzzy_reference"]:
            bank_row["transaction_id"] = f"bank_ref_{index + 1:08d}"
            bank_row["reference"] = reference.replace("-", " ")
        elif index in ranges["amount_unresolved"]:
            bank_row["amount"] = round(amount - 500.00, 2)
        bank.append(bank_row)

    for index in range(counts["duplicates"]):
        duplicate = gateway[index].copy()
        duplicate["reference"] = f"{duplicate['reference']}-DUP"
        gateway.append(duplicate)
    return pd.DataFrame(gateway), pd.DataFrame(bank), pd.DataFrame(ledger)


def write_csvs(gateway: pd.DataFrame, bank: pd.DataFrame, ledger: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    gateway.to_csv(output_dir / "gateway_settlements.csv", index=False)
    bank.to_csv(output_dir / "bank_statement.csv", index=False)
    ledger.to_csv(output_dir / "internal_ledger.csv", index=False)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate Reconcio synthetic reconciliation data.")
    parser.add_argument("--scale", type=int, default=1, help="Multiplier for the 65-transaction demo batch.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Destination directory for CSV files.")
    args = parser.parse_args(argv if argv is not None else [])
    if args.scale == 1:
        gateway, bank, ledger = generate()
        output_dir = args.output_dir or OUTPUT_DIR
    else:
        gateway, bank, ledger = generate_scaled(TOTAL_TRANSACTIONS * args.scale)
        output_dir = args.output_dir or OUTPUT_DIR / f"large_scale_{args.scale}"
    write_csvs(gateway, bank, ledger, output_dir)
    print(f"Generated gateway={len(gateway)}, bank={len(bank)}, ledger={len(ledger)} source records in {output_dir}.")


if __name__ == "__main__":
    main(sys.argv[1:])
