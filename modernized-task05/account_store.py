"""
account_store.py — JSON-backed account data store.

COBOL origin:
  Replaces the VSAM KSDS file opened as I-O in FILE-CONTROL:
      SELECT ACCT-MASTER ASSIGN TO EMPDD
          ORGANIZATION IS INDEXED
          ACCESS MODE IS RANDOM
          RECORD KEY IS ACCT-ID
          FILE STATUS IS ACCT-STATUS.

  The FD ACCT-MASTER record layout was:
      05 ACCT-ID   PIC X(5).
      05 ACCT-NAME PIC X(20).
      05 ACCT-BAL  PIC 9(5)V99.   <- implied 2 decimal places

  In Python the balance is stored as decimal.Decimal with two decimal
  places, exactly matching the fixed-point arithmetic of PIC 9(5)V99.

  Persistence model: the JSON file is read into memory at open() time
  (equivalent to OPEN I-O ACCT-MASTER) and written back atomically at
  close() (equivalent to CLOSE ACCT-MASTER after the run).
"""

import json
import os
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_DOWN
from typing import Optional


# ── data model ──────────────────────────────────────────────────────────────

@dataclass
class AccountRecord:
    """
    Mirrors COBOL 01 ACCT-REC under FD ACCT-MASTER.

    Fields correspond to:
        05 ACCT-ID   PIC X(5)      -> id   (str, left-justified, stripped)
        05 ACCT-NAME PIC X(20)     -> name (str)
        05 ACCT-BAL  PIC 9(5)V99   -> balance (Decimal, 2 d.p.)
    """

    id: str
    name: str
    balance: Decimal

    # Maximum balance enforced by PIC 9(5)V99: 99999.99
    _MAX_BALANCE: Decimal = Decimal("99999.99")

    def __post_init__(self) -> None:
        # Normalise to exactly two decimal places on construction,
        # mirroring the fixed-point storage of PIC 9(5)V99.
        self.balance = Decimal(str(self.balance)).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )


# ── store ────────────────────────────────────────────────────────────────────

class AccountStore:
    """
    JSON-based replacement for the VSAM KSDS ACCT-MASTER file.

    COBOL analogue:
        OPEN I-O ACCT-MASTER        -> AccountStore.open()
        READ ACCT-MASTER / INVALID KEY  -> AccountStore.read(key)
        REWRITE ACCT-REC            -> AccountStore.rewrite(record)
        CLOSE ACCT-MASTER           -> AccountStore.close()

    The store keeps all records in a dict keyed by ACCT-ID (str),
    matching VSAM's indexed-access-by-key semantics.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._records: dict[str, AccountRecord] = {}
        self._is_open: bool = False

    # ── lifecycle ─────────────────────────────────────────────────────────

    def open(self) -> None:
        """
        Load the JSON file into memory.

        COBOL analogue: OPEN I-O ACCT-MASTER
        On success the COBOL FILE STATUS is '00'; any exception here is
        equivalent to a non-'00' status that triggers STOP RUN.
        """
        if not os.path.exists(self._path):
            raise FileNotFoundError(
                f"Account store file not found: {self._path!r}"
            )
        with open(self._path, "r", encoding="utf-8") as fh:
            raw: dict = json.load(fh)
        self._records = {
            k: AccountRecord(
                id=v["id"],
                name=v["name"],
                balance=Decimal(v["balance"]),
            )
            for k, v in raw.items()
        }
        self._is_open = True

    def close(self) -> None:
        """
        Flush all in-memory records back to the JSON file atomically
        (write to a temp file, then rename).

        COBOL analogue: CLOSE ACCT-MASTER
        Unlike VSAM, which writes each REWRITE immediately, we batch the
        flushes to a single I/O at the end of the run — the observable
        end state is identical.
        """
        self._assert_open()
        tmp = self._path + ".tmp"
        serializable = {
            k: {
                "id": rec.id,
                "name": rec.name,
                "balance": str(rec.balance),
            }
            for k, rec in self._records.items()
        }
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(serializable, fh, indent=2)
        os.replace(tmp, self._path)
        self._is_open = False

    # ── I/O operations ───────────────────────────────────────────────────

    def read(self, acct_id: str) -> Optional[AccountRecord]:
        """
        Look up an account by key.

        COBOL analogue:
            MOVE TRANS-ACCT-ID TO ACCT-ID.
            READ ACCT-MASTER
                INVALID KEY     -> returns None  (FILE STATUS '23')
                NOT INVALID KEY -> returns AccountRecord (FILE STATUS '00')
            END-READ.

        Returns None when the key is not found (mirrors FILE STATUS '23').
        """
        self._assert_open()
        return self._records.get(acct_id)

    def rewrite(self, record: AccountRecord) -> None:
        """
        Persist an updated record back into the in-memory store.

        COBOL analogue:
            REWRITE ACCT-REC
                INVALID KEY  CONTINUE
            END-REWRITE.
        Requires that the key already exists (a successful READ must
        have preceded the REWRITE — same contract as VSAM).
        """
        self._assert_open()
        if record.id not in self._records:
            raise KeyError(
                f"REWRITE failed: account {record.id!r} not in store "
                "(no prior successful READ)"
            )
        self._records[record.id] = record

    # ── helpers ──────────────────────────────────────────────────────────

    def _assert_open(self) -> None:
        if not self._is_open:
            raise RuntimeError("AccountStore is not open")
