"""
processor.py — Transaction processing logic.

COBOL origin:
  Implements the PROCESS-TRANSACTION and REWRITE-ACCOUNT paragraphs from
  VSAMJOB5.cbl, plus the error-report writing that was inline in those
  paragraphs.

  COBOL paragraph mapping:
      PROCESS-TRANSACTION  ->  TransactionProcessor.process()
      REWRITE-ACCOUNT      ->  TransactionProcessor._rewrite_account()
      (inline WRITE ERROR-REC) -> ErrorReporter.write_error()

  Business rules preserved verbatim from the COBOL source:
      DEPOSIT  (D): ACCT-BAL = ACCT-BAL + TRANS-AMOUNT  -> REWRITE
      WITHDRAW (W): IF ACCT-BAL >= TRANS-AMOUNT
                        ACCT-BAL = ACCT-BAL - TRANS-AMOUNT -> REWRITE
                    ELSE
                        WRITE ERROR 'INSUFFICIENT FUNDS'
      ACCT NOT FOUND (no record in store):
                        WRITE ERROR 'ACCOUNT NOT FOUND'
      Unknown type: silently ignored — no update, no error.
        (Mirrors the COBOL note: "UNKNOWN TRANS-TYPE IS SILENTLY IGNORED")

  Decimal arithmetic:
      All monetary values use decimal.Decimal so the + and >= operations
      match COBOL's fixed-point PIC 9(5)V99 arithmetic exactly, with no
      floating-point rounding drift.

  Error record layout (mirrors FD ERROR-FILE, LRECL=80):
      05 REP-MSG-CONST  PIC X(13)  'TRANS ERROR: '
      05 REP-ID         PIC X(5)   account ID
      05 FILLER         PIC X(1)   ' '
      05 REP-DESC       PIC X(61)  description
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import List

from account_store import AccountRecord, AccountStore
from transaction_reader import TransactionRecord


# ── error reporter ──────────────────────────────────────────────────────────

class ErrorReporter:
    """
    Writes error records to the sequential error report file.

    COBOL analogue:
        FD ERROR-FILE / 01 ERROR-REC layout
        OPEN OUTPUT ERROR-FILE  -> ErrorReporter.open()
        WRITE ERROR-REC         -> ErrorReporter.write_error(...)
        CLOSE ERROR-FILE        -> ErrorReporter.close()

    Error record format (matches the COBOL FD layout exactly):
        'TRANS ERROR: ' + acct_id(5) + ' ' + description
    """

    # Mirrors REP-MSG-CONST PIC X(13)
    _PREFIX = "TRANS ERROR: "

    def __init__(self, path: str) -> None:
        self._path = path
        self._fh = None

    def open(self) -> None:
        """COBOL analogue: OPEN OUTPUT ERROR-FILE"""
        self._fh = open(self._path, "w", encoding="utf-8")

    def close(self) -> None:
        """COBOL analogue: CLOSE ERROR-FILE"""
        if self._fh:
            self._fh.close()
            self._fh = None

    def write_error(self, acct_id: str, description: str) -> None:
        """
        Write one error record.

        COBOL analogue (inline in PROCESS-TRANSACTION):
            MOVE TRANS-ACCT-ID TO REP-ID
            MOVE 'ACCOUNT NOT FOUND' TO REP-DESC   (or 'INSUFFICIENT FUNDS')
            WRITE ERROR-REC
            END-WRITE

        Format: 'TRANS ERROR: ' + acct_id + ' ' + description
        """
        if self._fh is None:
            raise RuntimeError("ErrorReporter is not open")
        line = f"{self._PREFIX}{acct_id} {description}"
        self._fh.write(line + "\n")


# ── counters ────────────────────────────────────────────────────────────────

@dataclass
class ProcessingStats:
    """
    Run-time statistics printed at end of job.
    No direct COBOL analogue — added for observability.
    """

    transactions_read: int = 0
    deposits_applied: int = 0
    withdrawals_applied: int = 0
    account_not_found: int = 0
    insufficient_funds: int = 0
    unknown_type_skipped: int = 0

    @property
    def errors_written(self) -> int:
        return self.account_not_found + self.insufficient_funds


# ── processor ───────────────────────────────────────────────────────────────

class TransactionProcessor:
    """
    Core business logic — mirrors the PROCESS-TRANSACTION paragraph.

    Dependencies are injected so each component can be tested
    independently:
        store    -> AccountStore   (ACCT-MASTER VSAM KSDS)
        reporter -> ErrorReporter  (REPORT.FILE PS output)
    """

    def __init__(self, store: AccountStore, reporter: ErrorReporter) -> None:
        self._store = store
        self._reporter = reporter

    def process(self, txn: TransactionRecord) -> None:
        """
        Process a single transaction record.

        COBOL analogue: PROCESS-TRANSACTION paragraph.

        Steps (matching COBOL flow exactly):
          1. SET NOT-FOUND TO TRUE.
          2. MOVE TRANS-ACCT-ID TO ACCT-ID.
          3. READ ACCT-MASTER INVALID KEY -> write error, return.
          4. SET FOUND TO TRUE.
          5a. IF TRANS-TYPE = 'D' -> ADD TRANS-AMOUNT TO ACCT-BAL -> REWRITE.
          5b. IF TRANS-TYPE = 'W'
                 IF ACCT-BAL >= TRANS-AMOUNT -> SUBTRACT -> REWRITE
                 ELSE -> write error 'INSUFFICIENT FUNDS'.
          5c. Unknown type: fall through silently (no-op).
        """
        # Step 3: random READ on key (mirrors READ ACCT-MASTER INVALID KEY)
        record = self._store.read(txn.acct_id)

        if record is None:
            # FILE STATUS '23' — INVALID KEY branch
            # MOVE TRANS-ACCT-ID TO REP-ID
            # MOVE 'ACCOUNT NOT FOUND' TO REP-DESC
            # WRITE ERROR-REC
            self._reporter.write_error(txn.acct_id, "ACCOUNT NOT FOUND")
            return

        # Step 5a — DEPOSIT
        # IF TRANS-TYPE = 'D'
        #    ADD TRANS-AMOUNT TO ACCT-BAL
        #    PERFORM REWRITE-ACCOUNT
        if txn.ttype == "D":
            updated = AccountRecord(
                id=record.id,
                name=record.name,
                balance=record.balance + txn.amount,
            )
            self._rewrite_account(updated)
            return

        # Step 5b — WITHDRAWAL
        # IF TRANS-TYPE = 'W'
        #    IF ACCT-BAL >= TRANS-AMOUNT
        #       SUBTRACT TRANS-AMOUNT FROM ACCT-BAL
        #       PERFORM REWRITE-ACCOUNT
        #    ELSE
        #       WRITE ERROR-REC 'INSUFFICIENT FUNDS'
        if txn.ttype == "W":
            if record.balance >= txn.amount:
                updated = AccountRecord(
                    id=record.id,
                    name=record.name,
                    balance=record.balance - txn.amount,
                )
                self._rewrite_account(updated)
            else:
                # MOVE ACCT-ID TO REP-ID
                # MOVE 'INSUFFICIENT FUNDS' TO REP-DESC
                # WRITE ERROR-REC
                self._reporter.write_error(record.id, "INSUFFICIENT FUNDS")
            return

        # Unknown TRANS-TYPE: silently ignored — no update, no error.
        # Mirrors the COBOL comment:
        #   "UNKNOWN TRANS-TYPE (NOT 'D' OR 'W') IS SILENTLY IGNORED"

    def _rewrite_account(self, record: AccountRecord) -> None:
        """
        Persist an updated account record.

        COBOL analogue: REWRITE-ACCOUNT paragraph.
            REWRITE ACCT-REC
                INVALID KEY  CONTINUE
            END-REWRITE.
            IF ACCT-STATUS NOT = '00'
               DISPLAY 'REWRITE FAILED: ' ACCT-STATUS
               STOP RUN
            END-IF.
        """
        self._store.rewrite(record)
