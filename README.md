# bob-cobol-modernizer

**IBM TechXchange 2026 Pre-conference Dev Day Hackathon submission.** Team **dobeg**.
Theme: *Build with purpose using IBM Bob 2.0*.

---

## The problem

Mainframe teams have thousands of COBOL programs and almost no documentation. Understanding
what one program does takes time. Understanding a whole codebase, and finding the patterns
that repeat across dozens of programs, takes many hours of manual reading.

This repo uses my own COBOL practice codebase (28 tasks with VSAM, JCL, and DB2) as a
stand-in for that problem, and uses Bob to solve it.

## What Bob built (the actual hackathon deliverable)

### 1. [`knowledge-base/`](knowledge-base/) — automated COBOL documentation tool

A Python tool (`cobol_knowledge_builder`) that scans the whole COBOL codebase below,
classifies every program into one of 9 technology groups (VSAM KSDS, DB2 cursors, GDG,
multi-program CALL, DB2+VSAM hybrids, and so on), and generates a `README.md` for every
task plus a master [`INDEX.md`](knowledge-base/INDEX.md) with a Mermaid dependency diagram.
Runs on all 28 tasks in under 0.2 seconds.

While building the classifier, Bob found and fixed 3 real bugs in its own code, then wrote
18 pytest tests so they don't come back. See [`knowledge-base/test_pipeline.py`](knowledge-base/test_pipeline.py).

**Start here:** [`knowledge-base/INDEX.md`](knowledge-base/INDEX.md)

### 2. [`modernized-task05/`](modernized-task05/) — a modernized COBOL program

`knowledge-base` found that VSAM KSDS core operations is the most common pattern in the
codebase. TASK05 (a banking transaction program) was picked as the representative example
and modernized into Python, replacing VSAM with a JSON-backed store while keeping the exact
same business logic (deposit, withdrawal, overdraft check, decimal arithmetic). The output
was verified byte-for-byte against the original COBOL reference files.

**Start here:** [`modernized-task05/README.md`](modernized-task05/README.md)

### Bob session evidence

Screenshots of the Bob IDE task sessions used to build this project are in
[`bob_sessions/`](bob_sessions/).

## What the rest of this repository is

`TASKS/`, `JCL SAMPLES/`, and `JCLPROC/` are **not** part of the hackathon build. They are
my personal COBOL/JCL/VSAM/DB2 practice codebase, written before the hackathon as I was
studying IBM mainframe development. Bob used this codebase as its input dataset. The
original description of that codebase is kept below for background.

---

<details>
<summary><strong>Original "COBOL Practice Tasks" README (background on the source dataset, TASK05-TASK32)</strong></summary>

COBOL practice tasks with DB2, JCL, and VSAM examples

# COBOL Practice Tasks

> ⚠️ **Disclaimer:** All programs in this repository are **personal learning exercises** - written,
> designed, and tested entirely by me while studying IBM mainframe development. They may be
> **incomplete**, may not cover all edge cases or error conditions, and are not intended for
> production use. Some tasks may share **similar structure, logic, or concepts** - this is
> intentional, as certain patterns (table lookup, control break, batch commit, etc.) are repeated
> across different contexts to reinforce understanding. Think of this repository as a solid
> **reference point for beginners** who are just getting started with COBOL, JCL, VSAM, DB2, and
> related mainframe technologies. 

---

## About This Repository

This repository contains hands-on COBOL batch programs built on IBM z/OS as part of my self-study of mainframe technologies. Each task is a standalone project with its own COBOL source, JCL, test data, and README. The programs cover a wide range of real-world batch patterns: sequential file processing, VSAM KSDS/ESDS operations, DB2 embedded SQL, internal sorts, control-break reporting, table lookups, and more.

**Technologies used across the repo:**
`COBOL` · `JCL` · `VSAM (KSDS, ESDS, AIX)` · `DB2 for z/OS` · `IDCAMS` · `GDG` · `SORT` · `IBM z/OS`

---

```
## Repository Structure
COBOL-PRACTICE-TASKS/  
├── JCL SAMPLES/ - Reusable JCL templates (compile, run, VSAM setup, etc.)  
├── JCLPROC/ - Catalogued JCL procedure used by all tasks  
└── TASKS/ - Individual practice tasks (TASK01 through TASK32)  
```

---

## Tasks Quick Reference

A grouped overview of all tasks by the main technology combination used. Click any task name to jump to its folder.

### Pure Sequential (PS only)

> No VSAM, no DB2 - only flat sequential files and core COBOL logic.

| Task | Name | Key Technique |
|------|------|---------------|
| [TASK12](TASKS/TASK12-CONTROL-BREAK-REPORT/) | Multi-Level Sales Report | Control Break - 3-level totals (shop → region → grand) |
| [TASK13](TASKS/TASK13-MASTER-SYNC/) | Master File Synchronization | Match-Merge (Balance Line) algorithm |
| [TASK14](TASKS/TASK14-TAX-CALCULATION/) | Tax Calculation | Table Lookup - linear search, `OCCURS` array |
| [TASK15](TASKS/TASK15-COMMISSION-TIERS/) | Commission Tiers | Tiered Bracket Lookup - `>=` range search |
| [TASK16](TASKS/TASK16-BINARY-SEARCH/) | Wholesale Warehouse | `SEARCH ALL` - binary search, `ASCENDING KEY` |
| [TASK17](TASKS/TASK17-INTERNAL-SORT/) | Academic Performance Rating | `SORT` with `INPUT PROCEDURE` / `OUTPUT PROCEDURE`, filter before sort |
| [TASK22](TASKS/TASK22-SALES-COMM-CALL/) | Sales Commission with CALL | `CALL` / `LINKAGE SECTION` - subprogram design |
| [TASK30](TASKS/TASK30-SYSIN-FILTER-OPR-REPORT/) | SYSIN Filter Operations Report | Runtime parameters from JCL `SYSIN` inline data |
| [TASK32](TASKS/TASK32-COPYBOOK-CUST-IMPORT-REPORT/) | Copybook Customer Import Report | `COPY` statement - shared record layouts via copybooks |

---

### VSAM KSDS

> Programs that read, update, or delete records in Key-Sequenced Data Sets.

| Task | Name | Access Mode | Key Technique |
|------|------|-------------|---------------|
| [TASK05](TASKS/TASK05-VSAM-BANKING/) | Banking Transaction System | RANDOM | `READ` + `REWRITE`, FILE STATUS `23`, PS + KSDS |
| [TASK06](TASKS/TASK06-VSAM-CLIENT-ARCHIVE/) | Client Database Cleanup & Archiving | DYNAMIC | `START` + `READ NEXT` + `DELETE`, PS + KSDS |
| [TASK09](TASKS/TASK09-VSAM-DUPLCT-DETECT/) | Client Duplicate Detection | SEQUENTIAL | Internal `SORT` + OUTPUT PROCEDURE, KSDS + PS |
| [TASK10](TASKS/TASK10-INVOICE-GENERATE/) | Invoice Generation | RANDOM | Random lookup, `COMPUTE` enrichment, PS + KSDS |
| [TASK11](TASKS/TASK11-CARD-VALIDATION/) | Credit Card Transaction Validation | RANDOM | 3-step validation cascade, `ACCEPT DATE`, PS + KSDS |
| [TASK23](TASKS/TASK23-VSAM-CREDIT-APPROVAL/) | VSAM Credit Approval | RANDOM | Multi-condition approval, PS split output, PS + KSDS |
| [TASK25](TASKS/TASK25-PRICE-UPDATE-SYNC/) | Price Update Sync | RANDOM | Batch `REWRITE`, error logging, PS + KSDS |

---

### VSAM KSDS + Alternate Index (AIX)

> Accessing VSAM records by a non-primary key field via AIX and PATH.

| Task | Name | Key Technique |
|------|------|---------------|
| [TASK18](TASKS/TASK18-LIBRARY-AIX/) | Library Book Finder | `START KEY IS EQUAL TO` on AIX + `READ NEXT`, `NONUNIQUEKEY`, `UPGRADE`, full IDCAMS setup |

---

### VSAM ESDS

> Entry-Sequenced Data Sets - append-only sequential VSAM files used as logs or queues.

| Task | Name | Key Technique |
|------|------|---------------|
| [TASK28](TASKS/TASK28-ESDS-CLIENT-TRANS-REPORT/) | ESDS Client Transaction Report | Sequential `READ` from ESDS, grouped PS report |
| [TASK29](TASKS/TASK29-ESDS-OPR-LOG-RECON/) | ESDS Operations Log Reconciliation | ESDS as audit log, sequential mismatch detection |

---

### DB2 + PS

> Embedded SQL programs with DB2 cursors, updates, and inserts; PS for reports or input.

| Task | Name | Key Technique |
|------|------|---------------|
| [TASK07](TASKS/TASK07-DB2-SALARY-INDEX/) | Employee Salary Indexing | `CURSOR WITH HOLD`, `UPDATE WHERE CURRENT OF`, COMMIT every 100 rows |
| [TASK08](TASKS/TASK08-DB2-SALES-BONUS/) | Sales Bonus Indexing | Two-step calculation, status priority (CAP/HIGHSAL/LOW/OK), COMMIT every 50 rows |
| [TASK19](TASKS/TASK19-DB2-BULK-INSERT/) | DB2 Bulk Insert with Validation | Validation cascade, batch COMMIT, SQLCODE `-803` / `< -900` handling |
| [TASK20](TASKS/TASK20-DB2-UPSERT/) | DB2 Upsert (Merge Pattern) | `UPDATE` → SQLCODE 100 → `INSERT` (upsert pattern) |
| [TASK21](TASKS/TASK21-DB2-FK-VALIDATION/) | DB2 Foreign Key Validation | App-level FK check via `SELECT ... INTO` before `INSERT` |
| [TASK31](TASKS/TASK31-QMF-BATCH-CUST-ACCT-REPORT/) | QMF Batch Customer Account Report | Cursor-driven control-break report from DB2 data |

---

### DB2 + VSAM

> Programs that use both DB2 and VSAM in a single run - cross-technology data processing.

| Task | Name | Key Technique |
|------|------|---------------|
| [TASK24](TASKS/TASK24-DB2-VSAM-RECONCILE/) | DB2 + VSAM Reconciliation | DB2 cursor + VSAM KSDS simultaneous access, balance mismatch detection |
| [TASK26](TASKS/TASK26-DB2-VSAM-PAYMENT-BATCH/) | DB2 + VSAM Payment Batch | DB2 `SELECT` for validation + VSAM `REWRITE` for balance update |

---

### GDG (Generation Data Group)

> Programs that write archive snapshots using rolling GDG generations.

| Task | Name | Key Technique |
|------|------|---------------|
| [TASK27](TASKS/TASK27-GDG-ACCT-ARCHIVE/) | GDG Account Archive | GDG `(+1)` generation write, `DEFGDG.jcl`, daily archive pattern |

## [JCL SAMPLES](JCL%20SAMPLES/)

Reusable JCL templates that support the tasks in this repository. Each member demonstrates a specific JCL pattern or IDCAMS function.

| File | Description |
|---|---|
| [`JCLCOMP.jcl`](JCL%20SAMPLES/JCLCOMP.jcl) | Compile-only JCL - compiles a COBOL source member using IGYWC |
| [`JCLRUN.jcl`](JCL%20SAMPLES/JCLRUN.jcl) | Run-only JCL - executes an already-compiled load module |
| [`COMPRUN.jcl`](JCL%20SAMPLES/COMPRUN.jcl) | Combined compile + run in one job using the `MYCOMPGO` proc |
| [`COBDB2CP.jcl`](JCL%20SAMPLES/COBDB2CP.jcl) | DB2 precompile → COBOL compile → link-edit → run for DB2 programs |
| [`DEFKSDS.jcl`](JCL%20SAMPLES/DEFKSDS.jcl) | Define a VSAM KSDS cluster using IDCAMS `DEFINE CLUSTER` |
| [`DEFESDS.jcl`](JCL%20SAMPLES/DEFESDS.jcl) | Define a VSAM ESDS cluster using IDCAMS |
| [`DEFAIX.jcl`](JCL%20SAMPLES/DEFAIX.jcl) | Define an Alternate Index (AIX) on an existing VSAM cluster |
| [`DEFPATH.jcl`](JCL%20SAMPLES/DEFPATH.jcl) | Define a PATH linking the AIX to the base VSAM cluster |
| [`BLDINDX.jcl`](JCL%20SAMPLES/BLDINDX.jcl) | Build (physically populate) the Alternate Index using IDCAMS BLDINDEX |
| [`DEFGDG.jcl`](JCL%20SAMPLES/DEFGDG.jcl) | Define a Generation Data Group (GDG) base using IDCAMS |
| [`DATAVSAM.jcl`](JCL%20SAMPLES/DATAVSAM.jcl) | Load data into a VSAM cluster from a sequential PS file using IDCAMS REPRO |
| [`DATA2PS.jcl`](JCL%20SAMPLES/DATA2PS.jcl) | Unload data from VSAM back to a sequential PS file using IDCAMS REPRO |

> See [`JCL SAMPLES/README.md`](JCL%20SAMPLES/README.md) for detailed descriptions and usage notes for each template.

---

## [JCLPROC](JCLPROC/)

Contains the catalogued JCL procedure referenced by nearly all tasks in the `TASKS/` folder.

| File | Description |
|---|---|
| [`MYCOMPGO.jcl`](JCLPROC/MYCOMPGO.jcl) | Two-step catalogued procedure: **COMP** (IGYWC compile + IEWL link-edit) and **GO** (program execution). Used by `COMPRUN.jcl` in each task via `EXEC PROC=MYCOMPGO`. Must be placed in your system PROCLIB before submitting any task JCL. |

---

## [TASKS](TASKS/)

Each task is a self-contained project folder with COBOL source, JCL, sample data, and its own README.

---

### [TASK05 - Banking Transaction System](TASKS/TASK05-VSAM-BANKING/)
**Technologies:** `COBOL` + `VSAM KSDS` + `PS`

Reads a sequential transaction file (PS) and updates customer account balances in a VSAM KSDS master file using `READ` + `REWRITE`. Invalid transactions (account not found, insufficient funds) are written to a separate PS error report. Demonstrates random VSAM access, FILE STATUS `23` handling, and `REWRITE` semantics.

**Key concepts:** `ACCESS MODE IS RANDOM`, `REWRITE`, `INVALID KEY`, `88`-level condition names, FILE STATUS per file.

---

### [TASK06 - Client Database Cleanup & Archiving](TASKS/TASK06-VSAM-CLIENT-ARCHIVE/)
**Technologies:** `COBOL` + `VSAM KSDS` + `PS`

Reads all records from a VSAM KSDS sequentially using Dynamic access mode, deletes inactive clients (last activity date ≤ cutoff date from a PS parameter file), and writes deleted records to a PS archive file. Prints a summary report to SYSOUT.

**Key concepts:** `ACCESS MODE IS DYNAMIC`, `START`, `READ NEXT`, `DELETE` (sequential), date comparison in `YYYYMMDD` format.

---

### [TASK07 - Employee Salary Indexing System](TASKS/TASK07-DB2-SALARY-INDEX/)
**Technologies:** `COBOL` + `DB2` + `PS`

Opens a DB2 cursor (`WITH HOLD`) over the `TB_EMP_SALARY` table, applies department-based salary increases (IT +10%, SAL +5%, others +3%), caps at 100,000, and updates each row in place using `UPDATE WHERE CURRENT OF`. Commits every 100 rows; any SQL error triggers ROLLBACK + STOP RUN. Writes a salary change report to a PS file.

**Key concepts:** `DECLARE CURSOR WITH HOLD`, `FOR UPDATE OF`, `UPDATE WHERE CURRENT OF`, `FETCH`, `COMMIT WORK`, `ROLLBACK WORK`, DCLGEN, `EVALUATE` for multi-branch logic.

---

### [TASK08 - Sales Bonus Indexing System](TASKS/TASK08-DB2-SALES-BONUS/)
**Technologies:** `COBOL` + `DB2` + `PS`

Similar to Task07 but with two-step bonus calculation: base region multiplier (EU +12%, NE +10%, AS +8%, SW +5%) followed by a +5% high-sales boost for employees with annual sales ≥ 150,000. Bonus capped at 20,000. Status assigned by priority (CAP / HIGHSAL / LOW / OK). Commits every 50 rows.

**Key concepts:** `CURSOR WITH HOLD`, `UPDATE WHERE CURRENT OF`, two-step calculation, status priority logic, SQLCODE `-501` handling.

---

### [TASK09 - Client Duplicate Detection](TASKS/TASK09-VSAM-DUPLCT-DETECT/)
**Technologies:** `COBOL` + `VSAM KSDS` + `SORT` + `PS`

Reads a VSAM KSDS client master file, sorts all records by `NAME + BIRTH-DATE` using the internal COBOL `SORT` verb with `OUTPUT PROCEDURE`, groups consecutive duplicate records, and writes a PS duplicate report. Any group with 2+ records sharing the same name and birth date is flagged.

**Key concepts:** `SORT ... USING ... OUTPUT PROCEDURE`, `SD`, `RETURN ... AT END`, control-break grouping, in-memory group buffer with `OCCURS 50`, `SORT-RETURN` check.

---

### [TASK10 - Invoice Generation](TASKS/TASK10-INVOICE-GENERATE/)
**Technologies:** `COBOL` + `VSAM KSDS` + `PS`

Reads a sequential PS orders file, performs a random VSAM KSDS read for each order to look up product name and unit price, calculates `TOTAL-COST = QUANTITY × UNIT-PRICE`, and writes enriched invoice lines to a PS output file. Orders with unknown product IDs are skipped and logged to SYSOUT.

**Key concepts:** `ACCESS MODE IS RANDOM`, random key lookup pattern (`MOVE key TO vsam-key-field` then `READ`), `FILE STATUS '23'` (not found), `COMPUTE` with implicit decimal, `Z(6).99` edited picture, three separate FILE STATUS variables.

---

### [TASK11 - Credit Card Transaction Validation](TASKS/TASK11-CARD-VALIDATION/)
**Technologies:** `COBOL` + `VSAM KSDS` + `PS`

Reads a daily PS transaction file, validates each transaction against a VSAM KSDS card master through three sequential checks: **card existence → blocked status → expiry date**. Approved transactions go to one PS output file; declined transactions go to another with a reason code (`NOT FOUND`, `BLOCKED`, `EXPIRED`). Current date is read from the OS at startup - no hardcoded dates.

**Key concepts:** `ACCEPT ... FROM DATE YYYYMMDD`, reference modification `(3:2)`, validation cascade (stop on first failure), `$$$$9.99` currency picture, `MOVE SPACES` before each loop iteration to prevent data bleeding.

---

### [TASK12 - Multi-Level Sales Control Break Report](TASKS/TASK12-CONTROL-BREAK-REPORT/)
**Technologies:** `COBOL` + `PS` (sequential only)

Reads a pre-sorted PS sales file and generates a formatted report with **three levels of totals**: shop subtotal → region subtotal → grand total. Uses the classic **Control Break (Level Break)** algorithm with holder variables (`PREV-REGION`, `PREV-SHOP`), first-record priming read, end-of-file flush, and major-break cascade rule (flush shop before flushing region).

**Key concepts:** Control break pattern, holder variables, break hierarchy rule, first-record priming read, EOF flush, `STRING ... DELIMITED BY SIZE`, `FUNCTION TRIM`, `Z(4)9.99` edited pictures.

---

### [TASK13 - Master File Synchronization (Match-Merge)](TASKS/TASK13-MASTER-SYNC/)
**Technologies:** `COBOL` + `PS` + `PS`

Applies a sorted PS transaction file to a sorted PS old master file to produce an updated new master and an error log. Uses the **Match-Merge (Balance Line) algorithm**: two parallel read cursors, `HIGH-VALUES` as EOF sentinel, and a three-way key comparison (TRANS > MASTER → copy, TRANS < MASTER → orphan transaction, TRANS = MASTER → update/delete/error). Supports `A`dd, `U`pdate, and `D`elete transactions.

**Key concepts:** Match-merge algorithm, `HIGH-VALUES` EOF sentinel, deferred write pattern, `WS-DEL-FLAG`, multiple transactions per key, sequential sync without VSAM or DB2.

---

### [TASK14 - Tax Calculation (Table Lookup)](TASKS/TASK14-TAX-CALCULATION/)
**Technologies:** `COBOL` + `PS` + `PS`

Loads a tax rate reference file into an in-memory `OCCURS` table (Phase 1), then processes an employee salary file and calculates tax for each employee using a linear search through the loaded table (Phase 2). Employees whose region code is not in the table get a hardcoded 20% default rate.

**Key concepts:** `OCCURS ... INDEXED BY`, two-phase processing, linear search via `PERFORM VARYING`, fallback default rate, implicit decimal `V999` in tax rates.

---

### [TASK15 - Commission Tiers (Tiered Table Lookup)](TASKS/TASK15-COMMISSION-TIERS/)
**Technologies:** `COBOL` + `PS` + `PS`

Similar to Task14, but uses a **tiered bracket lookup** instead of an exact key match: the table stores salary upper-bound limits sorted ascending, and the program finds the first tier where `WS-LIMIT >= SAL-AMT` to determine the commission rate. Input tiers file must be pre-sorted ascending by limit.

**Key concepts:** Tiered (bracket) lookup with `>=` comparison, `OCCURS ... INDEXED BY`, two-phase processing, catch-all tier pattern, sort order dependency.

---

### [TASK16 - Wholesale Warehouse (Binary Search)](TASKS/TASK16-BINARY-SEARCH/)
**Technologies:** `COBOL` + `PS` + `PS`

Loads a pre-sorted parts catalog into an in-memory table with `OCCURS ... DEPENDING ON`, then processes customer orders using **`SEARCH ALL`** (binary search) for fast part price lookups. Each order produces one invoice line (found: calculated total; not found: `NOT FOUND` line). Demonstrates the difference between `SEARCH` (linear) and `SEARCH ALL` (binary, requires `ASCENDING KEY`).

**Key concepts:** `SEARCH ALL`, `OCCURS ... DEPENDING ON`, `ASCENDING KEY IS`, `AT END` / `WHEN` clauses, O(log N) vs O(N) search comparison.

---

### [TASK17 - Academic Performance Rating (Internal Sort)](TASKS/TASK17-INTERNAL-SORT/)
**Technologies:** `COBOL` + `PS` + `SD`

Reads an unsorted exam results file, filters out failing students (score < 50) in the **INPUT PROCEDURE** via `RELEASE`, sorts passing students by class ascending / score descending, then writes the honor roll in the **OUTPUT PROCEDURE** via `RETURN`. No external sort utility needed.

**Key concepts:** `SORT` with `INPUT PROCEDURE` / `OUTPUT PROCEDURE`, `RELEASE`, `RETURN ... AT END`, `SD` (Sort Description), filter-before-sort pattern, `SORT-RETURN` check.

---

### [TASK18 - Library Book Finder (VSAM Alternate Index)](TASKS/TASK18-LIBRARY-AIX/)
**Technologies:** `COBOL` + `VSAM KSDS` + `VSAM AIX` + `PATH` + `PS`

Reads author names from a PS search request file and for each author performs a VSAM `START` on an Alternate Index (AIX keyed by author name), then uses `READ NEXT` to browse all books by that author in AIX order. Results are written to a PS report. The JCL (`ALLSTEPS.jcl`) handles full setup: define cluster → load data → define AIX → define PATH → BLDINDEX → compile → run.

**Key concepts:** `ACCESS MODE IS DYNAMIC`, `ALTERNATE RECORD KEY WITH DUPLICATES`, `START KEY IS EQUAL TO`, `READ NEXT`, `NONUNIQUEKEY`, `UPGRADE`, `PATH`, end-of-author-group detection by field change.

---

### [TASK19 - DB2 Bulk Insert with Validation](TASKS/TASK19-DB2-BULK-INSERT/)
**Technologies:** `COBOL` + `DB2` + `PS`

Reads new customer records from a PS file, validates each record through a cascade (ID not blank → email contains `@` → phone is 10 numeric digits), and inserts valid records into DB2 table `TB_CUSTOMERS`. Invalid records and DB2 errors are logged to a PS log file. Commits in batches of 100 successful inserts. Duplicate key (`-803`) is handled gracefully; critical errors (SQLCODE < -900) trigger ROLLBACK + STOP RUN.

**Key concepts:** Embedded SQL `INSERT`, batch commit strategy, `COMMIT-COUNTER`, validation cascade, VARCHAR host variables with dynamic length via `FUNCTION REVERSE` + `INSPECT TALLYING`, SQLCODE `-803` / `< -900` handling.

---

### [TASK20 - DB2 Upsert (Merge Pattern)](TASKS/TASK20-DB2-UPSERT/)
**Technologies:** `COBOL` + `DB2` + `PS`

Reads records from a PS input file and performs an "upsert" - attempts to `UPDATE` an existing DB2 row first; if `SQLCODE = 100` (not found), falls back to `INSERT`. This pattern ensures idempotent data loading without requiring a prior `SELECT`. Demonstrates the classic COBOL/DB2 upsert (update-or-insert) technique.

**Key concepts:** Upsert pattern (`UPDATE` → check SQLCODE 100 → `INSERT`), idempotent batch loading, SQLCODE 100 as "not found" sentinel.

---

### [TASK21 - DB2 Foreign Key Validation](TASKS/TASK21-DB2-FK-VALIDATION/)
**Technologies:** `COBOL` + `DB2` + `PS`

Reads records from a PS input file and validates referential integrity against a parent DB2 table before inserting into a child table. Invalid records (parent key not found) are logged to an error file. Demonstrates how to perform application-level FK validation using a `SELECT` before `INSERT` when DB2-enforced FK constraints are not available.

**Key concepts:** Application-level referential integrity check, `SELECT ... INTO` for existence check, SQLCODE 100 (not found), conditional `INSERT`, error logging.

---

### [TASK22 - Sales Commission with CALL](TASKS/TASK22-SALES-COMM-CALL/)
**Technologies:** `COBOL` + `PS` (subprogram CALL)

Separates commission calculation logic into a called subprogram. The main program reads a PS sales file and passes each record to a subordinate COBOL program via `CALL ... USING LINKAGE SECTION`. The subprogram calculates the commission and returns the result. Demonstrates modular COBOL design with the `CALL` / `LINKAGE SECTION` pattern.

**Key concepts:** `CALL ... USING`, `LINKAGE SECTION`, `PROCEDURE DIVISION USING`, static vs dynamic CALL, subprogram return, modular program design.

---

### [TASK23 - VSAM Credit Approval](TASKS/TASK23-VSAM-CREDIT-APPROVAL/)
**Technologies:** `COBOL` + `VSAM KSDS` + `PS`

Reads credit application records from a PS input file, looks up each applicant in a VSAM KSDS master file to check existing credit history, applies approval rules based on credit score and outstanding balance, and splits records into approved and declined PS output files.

**Key concepts:** VSAM random read, multi-condition approval logic, PS file splitting (two output files), FILE STATUS handling.

---

### [TASK24 - DB2 + VSAM Reconciliation](TASKS/TASK24-DB2-VSAM-RECONCILE/)
**Technologies:** `COBOL` + `DB2` + `VSAM KSDS` + `PS`

Reads records from both a DB2 table (via cursor) and a VSAM KSDS file, compares balances for matching keys, and writes a PS reconciliation report listing matches, mismatches, and records present in only one source. Demonstrates how to correlate data across two different storage technologies in a single COBOL program.

**Key concepts:** DB2 cursor + VSAM simultaneous access, balance comparison logic, reconciliation report pattern, mismatch detection.

---

### [TASK25 - Price Update Sync](TASKS/TASK25-PRICE-UPDATE-SYNC/)
**Technologies:** `COBOL` + `VSAM KSDS` + `PS`

Reads a PS price update file and applies bulk price changes to a VSAM KSDS product master using `REWRITE`. Records not found in VSAM are logged to an error report. Demonstrates a batch price synchronization pattern common in retail and inventory systems.

**Key concepts:** VSAM `REWRITE`, sequential update from PS driving file, FILE STATUS `23` error logging, batch sync pattern.

---

### [TASK26 - DB2 + VSAM Payment Batch](TASKS/TASK26-DB2-VSAM-PAYMENT-BATCH/)
**Technologies:** `COBOL` + `DB2` + `VSAM KSDS` + `PS`

Processes a batch of payment transactions: reads payment records from a PS file, validates the payer against a DB2 accounts table, applies the payment to a VSAM KSDS balance master via `REWRITE`, and writes a PS summary report. Shows how DB2 and VSAM can be used together in a single transaction processing program.

**Key concepts:** DB2 `SELECT ... INTO` for validation, VSAM `REWRITE` for balance update, cross-technology batch processing, commit strategy.

---

### [TASK27 - GDG Account Archive](TASKS/TASK27-GDG-ACCT-ARCHIVE/)
**Technologies:** `COBOL` + `GDG` + `PS`

Reads an account master file and writes a new Generation Data Group (GDG) generation as an archive snapshot. Demonstrates how GDG datasets work in JCL (`GDG(0)`, `GDG(+1)`) and how COBOL programs write to them like regular sequential files. Useful for daily/weekly archiving patterns.

**Key concepts:** GDG base definition (`DEFGDG.jcl`), GDG relative generation numbers `(+1)` / `(0)` / `(-1)`, sequential write to GDG, archiving pattern, rolling generation retention.

---

### [TASK28 - ESDS Client Transaction Report](TASKS/TASK28-ESDS-CLIENT-TRANS-REPORT/)
**Technologies:** `COBOL` + `VSAM ESDS` + `PS`

Reads client transaction records sequentially from a VSAM ESDS (Entry-Sequenced Data Set), generates a formatted PS report summarizing transactions per client, and writes total counts to SYSOUT. Demonstrates ESDS access patterns (sequential-only, append-only, no keyed access).

**Key concepts:** `ORGANIZATION IS SEQUENTIAL` for ESDS, sequential `READ`, ESDS characteristics (no primary key, no delete, append via `WRITE`), transaction grouping and reporting.

---

### [TASK29 - ESDS Operations Log Reconciliation](TASKS/TASK29-ESDS-OPR-LOG-RECON/)
**Technologies:** `COBOL` + `VSAM ESDS` + `PS`

Reads an operations log stored in VSAM ESDS, reconciles log entries against a PS reference file to identify unmatched or duplicate log events, and writes a PS reconciliation output. Shows how ESDS is used as an append-only audit log and how to detect anomalies in sequential log data.

**Key concepts:** ESDS as audit log, sequential reconciliation, unmatched record detection, log analysis pattern.

---

### [TASK30 - SYSIN Filter Operations Report](TASKS/TASK30-SYSIN-FILTER-OPR-REPORT/)
**Technologies:** `COBOL` + `PS` + `SYSIN`

Reads filter parameters directly from the JCL `SYSIN` DD (inline data) and uses them to filter a PS operations file, writing matching records to a PS output report. Demonstrates how COBOL programs read runtime parameters from JCL inline data rather than a separate dataset.

**Key concepts:** `SYSIN` DD as parameter input, runtime filter parameters, conditional record selection, PS report output.

---

### [TASK31 - QMF Batch Customer Account Report](TASKS/TASK31-QMF-BATCH-CUST-ACCT-REPORT/)
**Technologies:** `COBOL` + `DB2` + `PS`

Generates a formatted customer account report from DB2 using a cursor-driven COBOL program. Applies grouping and subtotals similar to a QMF batch report. Demonstrates how to replicate QMF-style reports programmatically in COBOL with full control over formatting.

**Key concepts:** DB2 cursor, control-break report from DB2 data, formatted PS output, QMF-style batch reporting alternative.

---

### [TASK32 - Copybook Customer Import Report](TASKS/TASK32-COPYBOOK-CUST-IMPORT-REPORT/)
**Technologies:** `COBOL` + `PS` + `COPY`

Reads customer import data from a PS file using shared record layouts defined in copybooks (`COPY` members). Generates a formatted import summary report. Demonstrates how copybooks promote reuse and consistency across multiple programs that share the same record layouts.

**Key concepts:** `COPY` statement, copybook-based record layout sharing, structured PS input, formatted report generation, code reuse via copybooks.

---

## Getting Started

1. **Clone or browse** this repository
2. Each `TASKS/TASKxx-*/` folder contains:
   - `COBOL/` - COBOL source program
   - `JCL/` - JCL to compile and run (uses [`MYCOMPGO`](JCLPROC/MYCOMPGO.jcl) proc)
   - `DATA/` - Sample input files and expected output
   - `SQL/` - DB2 DDL/DML scripts *(DB2 tasks only)*
   - `DCLGEN/` - DCLGEN copybooks *(DB2 tasks only)*
   - `OUTPUT/` - `SYSOUT.txt` with actual job output
   - `README.md` - Detailed description of the task
3. Review the task README for prerequisites (VSAM definitions, DB2 table creation)
4. Make sure [`MYCOMPGO`](JCLPROC/MYCOMPGO.jcl) is in your system `PROCLIB`
5. For DB2 tasks, use [`COBDB2CP.jcl`](JCL%20SAMPLES/COBDB2CP.jcl) instead of the standard `COMPRUN`

---

## Author

Self-taught mainframe developer. All programs were written from scratch as practice exercises on IBM z/OS with Enterprise COBOL and DB2 for z/OS.

</details>
