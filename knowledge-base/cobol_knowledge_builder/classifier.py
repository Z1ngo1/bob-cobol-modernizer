"""
classifier.py — Assigns each TaskInfo to one of the 9 taxonomy groups
                identified by the full source-code analysis.

Groups
------
A  VSAM KSDS Core          (random read/rewrite/delete — banking/archive/invoice/card/dup-detect)
B  VSAM AIX / ESDS         (alternate index, ESDS sequential log)
C  GDG                     (Generation Data Groups)
D  Sequential / Pure PS    (control-break, match-merge, internal sort, SYSIN filter, copybook pair)
E  In-memory Table Lookup  (linear search, tiered lookup, SEARCH ALL binary)
F  DB2 Cursor WITH HOLD    (cursor-driven UPDATE WHERE CURRENT OF)
G  DB2 Bulk Insert/Upsert  (INSERT batches, upsert, FK product validation)
H  Multi-program CALL      (main + subprograms via CALL/LINKAGE)
I  DB2 + VSAM Hybrid       (both stores used for read + write in one program)
"""

from __future__ import annotations

from .parser import TaskInfo, ProgramInfo


# ---------------------------------------------------------------------------
# Group labels (used in reports)
# ---------------------------------------------------------------------------

GROUP_LABELS: dict[str, str] = {
    "A": "VSAM KSDS Core Operations",
    "B": "VSAM Alternate Index (AIX) & ESDS",
    "C": "GDG (Generation Data Groups)",
    "D": "Sequential / Pure PS Processing",
    "E": "In-memory Table Lookup",
    "F": "DB2 Cursor WITH HOLD + UPDATE WHERE CURRENT OF",
    "G": "DB2 Bulk Insert / Upsert / FK Validation",
    "H": "Multi-program CALL Architecture",
    "I": "DB2 + VSAM Hybrid",
}


# ---------------------------------------------------------------------------
# Helper accessors
# ---------------------------------------------------------------------------

def _any_prog(task: TaskInfo, pred) -> bool:
    return any(pred(p) for p in task.programs)

def _all_progs_db2(task: TaskInfo) -> bool:
    """True if at least one program uses DB2."""
    return _any_prog(task, lambda p: p.has_db2)

def _has_vsam(task: TaskInfo) -> bool:
    """True if any program declares KSDS or JCL defines KSDS/ESDS/AIX."""
    return (
        task.jcl_defksds or task.jcl_defesds or task.jcl_defaix
        or _any_prog(task, lambda p: p.vsam_ksds or p.vsam_aix)
    )

def _has_real_esds(task: TaskInfo) -> bool:
    return task.jcl_defesds or _any_prog(task, lambda p: p.vsam_esds)

def _has_call_subprogram(task: TaskInfo) -> bool:
    """True if any program calls another and at least one .cbl has LINKAGE SECTION."""
    has_caller = _any_prog(task, lambda p: bool(p.calls))
    has_callee = _any_prog(task, lambda p: p.has_linkage_section or p.has_goback)
    return has_caller and has_callee

def _main_programs(task: TaskInfo) -> list[ProgramInfo]:
    """Programs that are NOT subprograms (no GOBACK / LINKAGE SECTION)."""
    return [p for p in task.programs
            if not p.has_goback and not p.has_linkage_section]

def _db2_and_vsam(task: TaskInfo) -> bool:
    """True if the task uses both DB2 and VSAM in a combined pipeline."""
    db2 = _all_progs_db2(task)
    vsam = _has_vsam(task)
    return db2 and vsam


# ---------------------------------------------------------------------------
# Group decision rules (priority-ordered)
# ---------------------------------------------------------------------------

def _classify(task: TaskInfo) -> str:  # noqa: C901

    # --- Group I: DB2 + VSAM Hybrid (both stores actively used) ---
    # TASK24 (reconcile), TASK25 (price sync), TASK26 (payment batch).
    # TASK29 (ESDS+KSDS+DB2 read-only) is dominated by ESDS → Group B.
    if _db2_and_vsam(task) and not _has_real_esds(task):
        return "I"

    # --- Group H: Multi-program CALL ---
    # Must have a caller AND at least one callee with LINKAGE/GOBACK.
    if _has_call_subprogram(task):
        return "H"

    # --- Group F: DB2 Cursor WITH HOLD + UPDATE WHERE CURRENT OF ---
    # TASK07, TASK08 — checked before G because they also have INSERT/SELECT.
    if _any_prog(task, lambda p: p.sql_cursor_with_hold and p.sql_update_where_current):
        return "F"

    # --- Group G: DB2 Bulk Insert / Upsert / FK Validation ---
    # Pure DB2 (no VSAM) with INSERT INTO or SELECT INTO.
    if _all_progs_db2(task) and not _has_vsam(task):
        if _any_prog(task, lambda p: p.sql_bulk_insert or p.sql_select_into):
            return "G"

    # --- Group C: GDG ---
    if task.jcl_defgdg or task.jcl_dsqqmfe:
        return "C"

    # --- Group B: VSAM AIX / ESDS ---
    if task.jcl_defaix or _any_prog(task, lambda p: p.vsam_aix):
        return "B"
    if _has_real_esds(task):
        return "B"

    # --- Group D overrides before Group A/E ---
    # TASK30: SYSIN-driven parameter filter — primary feature is SYSIN parsing
    if _any_prog(task, lambda p: p.has_sysin):
        return "D"
    # TASK32: shared copybook pair — primary feature is COPY/copybook architecture
    if task.copybooks or _any_prog(task, lambda p: p.has_copybook_copy):
        return "D"
    # TASK12: control-break report (no SORT SD, no VSAM, no DB2, no OCCURS table)
    # TASK13: match-merge (no VSAM KSDS — uses plain sequential PS files)
    # TASK17: internal SORT (has SORT SD → catches here)
    if _any_prog(task, lambda p: p.has_sort_sd):
        return "D"

    # --- Group A: VSAM KSDS Core (no DB2, no AIX, no ESDS, no GDG, no CALL sub) ---
    if _has_vsam(task) and not _all_progs_db2(task):
        return "A"

    # --- Group E: In-memory Table Lookup ---
    # TASK14, TASK15, TASK16 — no VSAM, no DB2, no SORT, but have OCCURS table
    # in working-storage loaded from a reference file.
    if _any_prog(task, lambda p: p.has_occurs_table) and not _has_vsam(task):
        return "E"

    # --- Group D: Sequential / Pure PS (catch-all for remaining PS-only tasks) ---
    return "D"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def classify_tasks(tasks: list[TaskInfo]) -> None:
    """
    Assign .group and .group_label on every TaskInfo in-place.
    """
    for task in tasks:
        task.group = _classify(task)
        task.group_label = GROUP_LABELS.get(task.group, "Unknown")
