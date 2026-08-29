"""
transaction_reader.py — Sequential transaction file reader.

COBOL origin:
  Replaces the PS sequential file opened as INPUT in FILE-CONTROL:
      SELECT TRANS-FILE ASSIGN TO INDD
          ORGANIZATION IS SEQUENTIAL
          FILE STATUS IS TRANS-STATUS.

  The FD TRANS-FILE record layout was (LRECL=80, RECFM=FB):
      05 TRANS-ACCT-ID  PIC X(5).     positions  1-5
      05 TRANS-TYPE     PIC X(1).     position   6
      05 TRANS-AMOUNT   PIC 9(5)V99.  positions  7-13  (7 digits, implied dec)
      05 FILLER         PIC X(67).    positions 14-80  (ignored)

  Python reads the file line-by-line (equivalent to READ TRANS-FILE
  AT END / NOT AT END), parses each fixed-width record, and yields
  TransactionRecord objects.

  Amount decoding: PIC 9(5)V99 stores 7 packed digits with an implied
  decimal point after the 5th digit.  E.g. the raw string '0050000'
  represents 500.00.  We insert the decimal by slicing [0:5] + '.' + [5:7].
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterator


@dataclass(frozen=True)
class TransactionRecord:
    """
    Mirrors COBOL 01 TRANS-REC under FD TRANS-FILE.

    Fields correspond to:
        05 TRANS-ACCT-ID  PIC X(5)     -> acct_id  (str)
        05 TRANS-TYPE     PIC X(1)     -> ttype    ('D' | 'W' | other)
        05 TRANS-AMOUNT   PIC 9(5)V99  -> amount   (Decimal, 2 d.p.)
    """

    acct_id: str
    ttype: str        # 'D' = Deposit, 'W' = Withdrawal (unknown types silently ignored)
    amount: Decimal

    # Source line kept for diagnostic messages (no COBOL analogue)
    raw_line: str


def _parse_amount(raw: str) -> Decimal:
    """
    Decode a PIC 9(5)V99 field stored as 7 ASCII digits.

    PIC 9(5)V99: 5 integer digits + implied decimal + 2 fractional digits.
    E.g. '0050000' -> Decimal('500.00')
         '0060000' -> Decimal('600.00')
         '0000100' -> Decimal('1.00')

    Equivalent to COBOL's handling of the V (implied decimal) in a
    numeric DISPLAY field.
    """
    if len(raw) != 7 or not raw.isdigit():
        raise ValueError(
            f"Invalid PIC 9(5)V99 field: {raw!r} — expected 7 decimal digits"
        )
    return Decimal(f"{raw[:5]}.{raw[5:7]}")


class TransactionReader:
    """
    Sequential reader for the TRANS-FILE (PS, LRECL=80).

    COBOL analogue:
        OPEN INPUT TRANS-FILE       -> TransactionReader.open()
        READ TRANS-FILE AT END ...  -> TransactionReader.read_all() iteration
        CLOSE TRANS-FILE            -> automatic (context-manager / generator)

    Usage:
        reader = TransactionReader("transactions.txt")
        for txn in reader.read_all():
            ...
    """

    # Fixed-width field offsets (0-based, matching the COBOL PIC layout)
    _ACCT_ID_SLICE = slice(0, 5)     # PIC X(5)
    _TYPE_SLICE    = slice(5, 6)     # PIC X(1)
    _AMOUNT_SLICE  = slice(6, 13)    # PIC 9(5)V99 — 7 digits

    def __init__(self, path: str) -> None:
        self._path = path

    def read_all(self) -> Iterator[TransactionRecord]:
        """
        Open the file, yield one TransactionRecord per non-blank line,
        then close automatically.

        COBOL analogue:
            OPEN INPUT TRANS-FILE.
            PERFORM UNTIL EOF
               READ TRANS-FILE
                 AT END SET EOF TO TRUE
                 NOT AT END PERFORM PROCESS-TRANSACTION
               END-READ
            END-PERFORM.
            CLOSE TRANS-FILE.

        Blank lines (trailing newline of the last record, etc.) are skipped
        just as COBOL would stop at EOF rather than process a short record.
        Raises ValueError for malformed record fields, equivalent to
        a non-'00' FILE STATUS triggering STOP RUN.
        """
        with open(self._path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.rstrip("\r\n")
                if not line.strip():
                    continue           # skip blank / trailing newline
                if len(line) < 13:
                    raise ValueError(
                        f"Short record (< 13 chars): {line!r} — "
                        "expected ACCT-ID(5) + TYPE(1) + AMOUNT(7)"
                    )
                acct_id = line[self._ACCT_ID_SLICE]
                ttype   = line[self._TYPE_SLICE]
                amount  = _parse_amount(line[self._AMOUNT_SLICE])
                yield TransactionRecord(
                    acct_id=acct_id,
                    ttype=ttype,
                    amount=amount,
                    raw_line=line,
                )
