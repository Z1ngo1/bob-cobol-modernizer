"""
main.py — Entry point for the modernized VSAM Banking Transaction System.

COBOL origin:
  Mirrors the MAIN-LOGIC, OPEN-FILES, and CLOSE-FILES paragraphs from
  VSAMJOB5.cbl (PROGRAM-ID. VSAMJO5).

  COBOL structure:
      MAIN-LOGIC.
          PERFORM OPEN-FILES.
          IF <any file status not '00'> STOP RUN.
          PERFORM UNTIL EOF
              READ TRANS-FILE ... PERFORM PROCESS-TRANSACTION
          END-PERFORM.
          PERFORM CLOSE-FILES.
          STOP RUN.

  Python equivalent:
      main()
          open all resources           (OPEN-FILES)
          for txn in reader.read_all() (READ TRANS-FILE loop)
              processor.process(txn)   (PROCESS-TRANSACTION)
          close all resources          (CLOSE-FILES)

  Default file paths match the DATA/ folder layout in the original task:
      TRANS_FILE   = transactions.txt  (equivalent to INDD / TRANS.FILE)
      ACCOUNTS_DB  = accounts.json     (equivalent to EMPDD / ACCT.MASTER)
      ERROR_REPORT = error_report.txt  (equivalent to REPDD / REPORT.FILE)

  Paths can be overridden via CLI arguments for flexibility.

Usage:
    python main.py
    python main.py --transactions transactions.txt \\
                   --accounts    accounts.json     \\
                   --errors      error_report.txt

The accounts.json file is updated in-place at the end of a successful run
(equivalent to the VSAM KSDS being modified by REWRITE operations and then
CLOSED, persisting all updates).
"""

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from account_store import AccountStore
from transaction_reader import TransactionReader
from processor import ErrorReporter, ProcessingStats, TransactionProcessor


# ── defaults ────────────────────────────────────────────────────────────────

DEFAULT_TRANSACTIONS = "transactions.txt"
DEFAULT_ACCOUNTS     = "accounts.json"
DEFAULT_ERROR_REPORT = "error_report.txt"


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_balance(balance: Decimal) -> str:
    """Format balance as a human-readable string (e.g. '$1,500.00')."""
    return f"${balance:,.2f}"


def _print_account_summary(store: AccountStore) -> None:
    """Print final account balances — equivalent to browsing the VSAM file
    in ISPF after the job completes."""
    print("\n--- Account balances after processing ---")
    print(f"{'ID':<8} {'Name':<22} {'Balance':>10}")
    print("-" * 44)
    for rec in store._records.values():
        print(f"{rec.id:<8} {rec.name:<22} {_fmt_balance(rec.balance):>10}")


# ── main ────────────────────────────────────────────────────────────────────

def main() -> int:
    """
    MAIN-LOGIC paragraph equivalent.

    Returns 0 on success, 1 on error — mirrors STOP RUN after an
    unexpected FILE STATUS.
    """
    # ── argument parsing ─────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="Modernized VSAM Banking Transaction Processor (VSAMJOB5)"
    )
    parser.add_argument(
        "--transactions",
        default=DEFAULT_TRANSACTIONS,
        metavar="PATH",
        help=f"Transaction input file (INDD). Default: {DEFAULT_TRANSACTIONS}",
    )
    parser.add_argument(
        "--accounts",
        default=DEFAULT_ACCOUNTS,
        metavar="PATH",
        help=f"Accounts JSON file (EMPDD / VSAM KSDS). Default: {DEFAULT_ACCOUNTS}",
    )
    parser.add_argument(
        "--errors",
        default=DEFAULT_ERROR_REPORT,
        metavar="PATH",
        help=f"Error report output file (REPDD). Default: {DEFAULT_ERROR_REPORT}",
    )
    args = parser.parse_args()

    # Resolve paths relative to the script's directory so the program
    # works correctly regardless of the calling working directory.
    base = Path(__file__).parent
    trans_path  = str(base / args.transactions)
    accts_path  = str(base / args.accounts)
    errors_path = str(base / args.errors)

    # ── OPEN-FILES ───────────────────────────────────────────────────────
    # COBOL: OPEN I-O ACCT-MASTER / OPEN INPUT TRANS-FILE / OPEN OUTPUT ERROR-FILE
    store    = AccountStore(accts_path)
    reader   = TransactionReader(trans_path)
    reporter = ErrorReporter(errors_path)

    try:
        store.open()
    except FileNotFoundError as exc:
        print(f"ERROR OPENING ACCT-MASTER FILE: {exc}", file=sys.stderr)
        return 1

    try:
        reporter.open()
    except OSError as exc:
        print(f"ERROR OPENING ERROR-FILE: {exc}", file=sys.stderr)
        store.close()
        return 1

    # ── PROCESS-TRANSACTION loop ─────────────────────────────────────────
    # COBOL: PERFORM UNTIL EOF / READ TRANS-FILE / PERFORM PROCESS-TRANSACTION
    processor = TransactionProcessor(store=store, reporter=reporter)
    stats     = ProcessingStats()

    try:
        for txn in reader.read_all():
            stats.transactions_read += 1

            # Delegate to PROCESS-TRANSACTION equivalent
            processor.process(txn)

            # Track stats (no COBOL analogue — observability only)
            account_existed = store.read(txn.acct_id) is not None
            if not account_existed:
                # read() after the process() call: if the account wasn't
                # found, the error was already written; we re-check just
                # for the counter.
                pass

        # Count stats via a second pass over the reporter log — simpler
        # than threading counters through process(); re-read the file.
        # (We collect counts from the reporter indirectly below.)

    except ValueError as exc:
        # Malformed record in the transaction file — equivalent to a
        # non-'00' TRANS-STATUS triggering STOP RUN.
        print(f"READ INPUT FILE ERROR: {exc}", file=sys.stderr)
        reporter.close()
        store.close()
        return 1
    except Exception as exc:
        print(f"UNEXPECTED ERROR: {exc}", file=sys.stderr)
        reporter.close()
        store.close()
        return 1

    # ── CLOSE-FILES ──────────────────────────────────────────────────────
    # COBOL: CLOSE ACCT-MASTER / CLOSE TRANS-FILE / CLOSE ERROR-FILE
    reporter.close()
    try:
        store.close()   # writes updated JSON — replaces CLOSE ACCT-MASTER
    except OSError as exc:
        print(f"WARNING: ERROR CLOSING ACCT-MASTER FILE: {exc}", file=sys.stderr)

    # ── summary display ──────────────────────────────────────────────────
    store_ro = AccountStore(accts_path)   # re-open read-only for display
    store_ro.open()
    _print_account_summary(store_ro)
    store_ro._is_open = False             # skip close() flush; no changes

    # Count error lines written
    error_path = Path(errors_path)
    errors_written = 0
    if error_path.exists():
        errors_written = sum(1 for ln in error_path.read_text(encoding="utf-8").splitlines() if ln.strip())

    print(f"\n--- Run summary ---")
    print(f"  Transactions read : {stats.transactions_read}")
    print(f"  Error records     : {errors_written}")
    print(f"  Error report      : {errors_path}")
    print(f"  Accounts DB       : {accts_path}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
