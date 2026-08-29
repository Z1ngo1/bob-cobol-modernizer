# Task 05 — Modernized Python Implementation

Modernized Python port of [`TASKS/TASK05-VSAM-BANKING/COBOL/VSAMJOB5.cbl`](../COBOL-PRACTICE-TASKS/TASKS/TASK05-VSAM-BANKING/COBOL/VSAMJOB5.cbl).

The COBOL program reads a sequential transaction file and updates customer account balances stored in a VSAM KSDS master file, writing rejected transactions (account not found, insufficient funds) to a separate error report.  
This Python port preserves the **exact same business logic and flow** while replacing the mainframe-specific I/O with portable Python equivalents.

---

## Folder layout

```
modernized-task05/
├── main.py               # MAIN-LOGIC / OPEN-FILES / CLOSE-FILES paragraphs
├── processor.py          # PROCESS-TRANSACTION / REWRITE-ACCOUNT paragraphs
├── account_store.py      # VSAM KSDS replacement (JSON-backed, keyed dict)
├── transaction_reader.py # Sequential PS file reader (TRANS-FILE)
├── accounts.json         # Seed data — matches ACCT.MASTER.BEFORE
└── transactions.txt      # Input data — matches TRANS.FILE.INPUT
```

---

## COBOL → Python mapping

| COBOL construct | Python equivalent |
|---|---|
| `SELECT ACCT-MASTER ORGANIZATION IS INDEXED ACCESS MODE IS RANDOM` | `AccountStore` class — dict keyed by `ACCT-ID` |
| `FD ACCT-MASTER` / `01 ACCT-REC` | `AccountRecord` dataclass |
| `SELECT TRANS-FILE ORGANIZATION IS SEQUENTIAL` | `TransactionReader` class |
| `FD TRANS-FILE` / `01 TRANS-REC` | `TransactionRecord` dataclass |
| `FD ERROR-FILE` / `WRITE ERROR-REC` | `ErrorReporter` class |
| `OPEN I-O ACCT-MASTER` | `AccountStore.open()` |
| `CLOSE ACCT-MASTER` | `AccountStore.close()` — flushes JSON to disk |
| `READ ACCT-MASTER INVALID KEY` | `AccountStore.read(key)` → `None` if not found |
| `REWRITE ACCT-REC` | `AccountStore.rewrite(record)` |
| `PIC 9(5)V99` (7-digit implied decimal) | `decimal.Decimal` with 2 d.p. |
| `MAIN-LOGIC` paragraph | `main()` in `main.py` |
| `PROCESS-TRANSACTION` paragraph | `TransactionProcessor.process()` |
| `REWRITE-ACCOUNT` paragraph | `TransactionProcessor._rewrite_account()` |
| File STATUS `'23'` (not found) | `read()` returns `None` |
| `STOP RUN` on unexpected FILE STATUS | `sys.exit(1)` / raise |

### Decimal arithmetic

COBOL's `PIC 9(5)V99` stores monetary values as fixed-point integers with an implied decimal point after the 5th digit. Python's `decimal.Decimal` replicates this precisely — no IEEE 754 floating-point rounding occurs. All account balances and transaction amounts are kept as `Decimal` with exactly two decimal places throughout.

### Persistence model

The JSON file is read into memory at `AccountStore.open()` (equivalent to `OPEN I-O ACCT-MASTER`). All `REWRITE` operations mutate the in-memory dict. At `AccountStore.close()` the dict is serialised back to the JSON file atomically via `os.replace()`. The observable end state is identical to a VSAM KSDS after the job closes.

---

## Business rules (unchanged from COBOL)

| Transaction | Condition | Action |
|---|---|---|
| `D` Deposit | Always | `balance = balance + amount` → rewrite |
| `W` Withdrawal | `balance >= amount` | `balance = balance - amount` → rewrite |
| `W` Withdrawal | `balance < amount` | Write error: `INSUFFICIENT FUNDS` |
| Any | Account not found | Write error: `ACCOUNT NOT FOUND` |
| Unknown type | — | Silently ignored (no update, no error) |

---

## How to run

```bash
cd modernized-task05
python main.py
```

Optional path overrides:

```bash
python main.py \
  --transactions transactions.txt \
  --accounts     accounts.json    \
  --errors       error_report.txt
```

**Reset accounts to initial state** (re-run from scratch):

```bash
# Restore accounts.json to the ACCT.MASTER.BEFORE values
python reset_accounts.py      # see below, or just copy accounts.json from git
```

Because `accounts.json` is modified in-place each run (just as the VSAM KSDS would be), restore it from version control to replay:

```bash
git checkout -- modernized-task05/accounts.json
```

---

## Expected output

After processing `transactions.txt` against the seed `accounts.json`:

### `accounts.json` (equivalent to `ACCT.MASTER.AFTER`)

```
10001  IVAN IVANOV       $1,500.00   (was $1,000.00 + deposit $500.00)
10002  PETR PETROV         $400.50   (was $500.50 - withdraw $100.00; earlier W600 rejected)
10003  MARIA SIDOROVA       $99.00   (deposit $300 - withdraw $200 - withdraw $1)
```

### `error_report.txt` (equivalent to `ERROR.REPORT.OUTPUT`)

```
TRANS ERROR: 10002 INSUFFICIENT FUNDS
TRANS ERROR: 10004 ACCOUNT NOT FOUND
```

These match the COBOL reference output files exactly.

---

## Requirements

- Python 3.10+  
- Standard library only (`decimal`, `json`, `dataclasses`, `argparse`, `pathlib`)  
- No third-party packages required
