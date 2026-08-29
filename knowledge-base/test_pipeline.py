"""
test_pipeline.py — Minimal pytest suite for the cobol_knowledge_builder pipeline.

Covers exactly the three classes of bugs that were found and fixed:

  Bug 1 — Hyphenated cursor names
            DECLARE CUR-SALARY CURSOR WITH HOLD -> regex must use [\\w-]+, not \\w+

  Bug 2 — Multi-line UPDATE WHERE CURRENT OF
            UPDATE … and WHERE CURRENT OF can be on separate lines inside
            EXEC SQL … END-EXEC; the regex must use re.DOTALL.

  Bug 3 — Group priority ordering
            a) TASK09: VSAM KSDS + SD → must be Group D, not A
            b) TASK30: VSAM KSDS + SYSIN → must be Group D, not A
            c) TASK32: VSAM KSDS + copybook → must be Group D, not A
            d) Group E vs D: OCCURS table → E; no OCCURS table → D

Each test is kept self-contained; no filesystem access beyond what the
already-generated knowledge-base package provides.
"""

from __future__ import annotations

import sys
import textwrap
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Make sure the knowledge-base package is importable when running from the
# knowledge-base/ directory OR from the workspace root.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent           # knowledge-base/
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from cobol_knowledge_builder.parser import (
    ProgramInfo,
    TaskInfo,
    _strip_comments,
    _parse_cbl,
)
from cobol_knowledge_builder.classifier import _classify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(programs: list[ProgramInfo], **jcl_flags) -> TaskInfo:
    """Build a minimal TaskInfo with the supplied programs and JCL flags."""
    task = TaskInfo(task_id="TESTXX", task_name="TESTXX-FIXTURE", folder=Path("."))
    task.programs = programs
    for k, v in jcl_flags.items():
        setattr(task, k, v)
    return task


def _parse_text(cobol_text: str) -> ProgramInfo:
    """Write *cobol_text* to a temp file and parse it via _parse_cbl."""
    # Dedent so callers can use indented triple-quoted strings naturally
    src = textwrap.dedent(cobol_text)
    with tempfile.NamedTemporaryFile(
        suffix=".cbl", mode="w", encoding="utf-8", delete=False
    ) as fh:
        fh.write(src)
        tmp = Path(fh.name)
    try:
        return _parse_cbl(tmp)
    finally:
        tmp.unlink(missing_ok=True)


# ===========================================================================
# Bug 1 — Hyphenated cursor names  ([\w-]+ required)
# ===========================================================================

class TestHyphenatedCursorName:
    """DECLARE CUR-SALARY CURSOR WITH HOLD — the hyphen must be matched."""

    _CURSOR_SRC = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTPROG.
       PROCEDURE DIVISION.
           EXEC SQL
               DECLARE CUR-SALARY CURSOR WITH HOLD FOR
               SELECT * FROM TB_EMP_SALARY
           END-EXEC.
    """

    def test_cursor_with_hold_detected(self):
        prog = _parse_text(self._CURSOR_SRC)
        assert prog.sql_cursor_with_hold is True, (
            "sql_cursor_with_hold should be True for 'CUR-SALARY' "
            "(hyphenated cursor name)"
        )

    def test_has_db2_set(self):
        """Sanity: EXEC SQL also sets has_db2."""
        prog = _parse_text(self._CURSOR_SRC)
        assert prog.has_db2 is True

    def test_plain_cursor_name_still_works(self):
        """A cursor without a hyphen (CURSALARY) must also be detected."""
        src = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTPROG.
       PROCEDURE DIVISION.
           EXEC SQL
               DECLARE CURSALARY CURSOR WITH HOLD FOR
               SELECT * FROM TB_EMP_SALARY
           END-EXEC.
        """
        prog = _parse_text(src)
        assert prog.sql_cursor_with_hold is True


# ===========================================================================
# Bug 2 — Multi-line UPDATE WHERE CURRENT OF  (re.DOTALL required)
# ===========================================================================

class TestMultiLineUpdateWhereCurrent:
    """UPDATE … WHERE CURRENT OF may span multiple lines — needs DOTALL."""

    _UPDATE_SRC = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTPROG.
       PROCEDURE DIVISION.
           EXEC SQL
               UPDATE TB_EMP_SALARY
                   SET SALARY = :NEW-SALARY
                   WHERE CURRENT OF CUR-SALARY
           END-EXEC.
    """

    def test_update_where_current_multiline(self):
        prog = _parse_text(self._UPDATE_SRC)
        assert prog.sql_update_where_current is True, (
            "sql_update_where_current should be True when UPDATE and "
            "WHERE CURRENT OF are on separate lines"
        )

    def test_update_where_current_singleline(self):
        """Single-line variant must still work."""
        src = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTPROG.
       PROCEDURE DIVISION.
           EXEC SQL
               UPDATE TB SET C = :V WHERE CURRENT OF CUR-X
           END-EXEC.
        """
        prog = _parse_text(src)
        assert prog.sql_update_where_current is True

    def test_full_cursor_block_detection(self):
        """Both cursor and update-where-current set → Group F routing possible."""
        src = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTPROG.
       PROCEDURE DIVISION.
           EXEC SQL
               DECLARE CUR-SALARY CURSOR WITH HOLD FOR
               SELECT EMPID FROM TB_EMP_SALARY
           END-EXEC.
           EXEC SQL
               UPDATE TB_EMP_SALARY
                   SET SALARY = :NEW-SALARY
                   WHERE CURRENT OF CUR-SALARY
           END-EXEC.
        """
        prog = _parse_text(src)
        assert prog.sql_cursor_with_hold is True
        assert prog.sql_update_where_current is True


# ===========================================================================
# Bug 3a — TASK09 pattern: VSAM KSDS + SD  →  Group D (not A)
# ===========================================================================

class TestGroupDOverridesGroupA_SortSD:
    """Internal SORT with SD must route to Group D even when VSAM KSDS is present."""

    def _make_sort_sd_prog(self) -> ProgramInfo:
        p = ProgramInfo(filename="VSAMJOB9.cbl")
        p.vsam_ksds = True
        p.has_sort_sd = True
        return p

    def test_sort_sd_gives_group_d(self):
        task = _make_task([self._make_sort_sd_prog()], jcl_defksds=True)
        assert _classify(task) == "D", (
            "VSAM KSDS + SORT SD should be Group D (Sort takes priority over VSAM)"
        )

    def test_vsam_without_sort_sd_gives_group_a(self):
        """Confirm that without SD the same VSAM task still lands in Group A."""
        p = ProgramInfo(filename="PLAIN.cbl")
        p.vsam_ksds = True
        task = _make_task([p], jcl_defksds=True)
        assert _classify(task) == "A"


# ===========================================================================
# Bug 3b — TASK30 pattern: VSAM KSDS + SYSIN  →  Group D (not A)
# ===========================================================================

class TestGroupDOverridesGroupA_Sysin:
    """SYSIN-driven filter must route to Group D even when VSAM KSDS is present."""

    def _make_sysin_prog(self) -> ProgramInfo:
        p = ProgramInfo(filename="SYSIN30.cbl")
        p.vsam_ksds = True
        p.has_sysin = True
        return p

    def test_sysin_gives_group_d(self):
        task = _make_task([self._make_sysin_prog()], jcl_defksds=True)
        assert _classify(task) == "D", (
            "VSAM KSDS + SYSIN should be Group D (SYSIN takes priority over VSAM)"
        )

    def test_vsam_without_sysin_gives_group_a(self):
        p = ProgramInfo(filename="PLAIN.cbl")
        p.vsam_ksds = True
        task = _make_task([p], jcl_defksds=True)
        assert _classify(task) == "A"


# ===========================================================================
# Bug 3c — TASK32 pattern: VSAM KSDS + shared copybook  →  Group D (not A)
# ===========================================================================

class TestGroupDOverridesGroupA_Copybook:
    """Shared copybook pair must route to Group D even when VSAM KSDS is present."""

    def _make_copy_prog(self) -> ProgramInfo:
        p = ProgramInfo(filename="COP1LB32.cbl")
        p.vsam_ksds = True
        p.has_copybook_copy = True
        p.copies = ["TASK32"]
        return p

    def test_copybook_copy_gives_group_d(self):
        task = _make_task([self._make_copy_prog()], jcl_defksds=True)
        task.copybooks = ["TASK32"]   # .cpy file present in COPYLIB/
        assert _classify(task) == "D", (
            "VSAM KSDS + shared copybook should be Group D "
            "(copybook architecture takes priority over VSAM)"
        )

    def test_task_copybooks_alone_gives_group_d(self):
        """task.copybooks non-empty is sufficient — even if no VSAM."""
        p = ProgramInfo(filename="COP2.cbl")
        task = _make_task([p])
        task.copybooks = ["SHAREDCPY"]
        assert _classify(task) == "D"

    def test_vsam_without_copybook_gives_group_a(self):
        p = ProgramInfo(filename="PLAIN.cbl")
        p.vsam_ksds = True
        task = _make_task([p], jcl_defksds=True)
        assert _classify(task) == "A"


# ===========================================================================
# Bug 3d — Group E vs D disambiguation  (OCCURS table required for E)
# ===========================================================================

class TestGroupEVsGroupD:
    """Group E requires an explicit OCCURS table in WORKING-STORAGE."""

    def test_occurs_table_gives_group_e(self):
        """No VSAM, no DB2, no sort/sysin/copybook, but has OCCURS → Group E."""
        p = ProgramInfo(filename="LOOKUP.cbl")
        p.has_occurs_table = True
        task = _make_task([p])
        assert _classify(task) == "E"

    def test_no_occurs_table_gives_group_d(self):
        """Same flags minus OCCURS → falls through to Group D catch-all."""
        p = ProgramInfo(filename="CTRLBRK.cbl")
        p.has_occurs_table = False
        task = _make_task([p])
        assert _classify(task) == "D"

    def test_occurs_table_with_vsam_gives_group_a(self):
        """OCCURS + VSAM → VSAM wins (Group A), not E."""
        p = ProgramInfo(filename="MIXED.cbl")
        p.vsam_ksds = True
        p.has_occurs_table = True
        task = _make_task([p], jcl_defksds=True)
        assert _classify(task) == "A"


# ===========================================================================
# Integration smoke test — parse the real TASK07 and TASK08 source files
# ===========================================================================

class TestRealFilesParsing:
    """
    Parse the actual .cbl files that exposed the two regex bugs and confirm
    the fixes produce the correct flags (and therefore Group F routing).
    """

    _TASKS_ROOT = Path(__file__).parent.parent / "TASKS"

    def _task07_path(self) -> Path:
        return self._TASKS_ROOT / "TASK07-DB2-SALARY-INDEX" / "COBOL" / "DB2TASK7.cbl"

    def _task08_path(self) -> Path:
        return self._TASKS_ROOT / "TASK08-DB2-SALES-BONUS" / "COBOL" / "DB2TASK8.cbl"

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "TASKS" / "TASK07-DB2-SALARY-INDEX").exists(),
        reason="TASKS/ folder not present relative to knowledge-base/",
    )
    def test_task07_cursor_detected(self):
        path = self._task07_path()
        prog = _parse_cbl(path)
        assert prog.sql_cursor_with_hold is True, (
            f"{path.name}: sql_cursor_with_hold should be True (CUR-SALARY)"
        )
        assert prog.sql_update_where_current is True, (
            f"{path.name}: sql_update_where_current should be True"
        )

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "TASKS" / "TASK08-DB2-SALES-BONUS").exists(),
        reason="TASKS/ folder not present relative to knowledge-base/",
    )
    def test_task08_cursor_detected(self):
        path = self._task08_path()
        prog = _parse_cbl(path)
        assert prog.sql_cursor_with_hold is True, (
            f"{path.name}: sql_cursor_with_hold should be True (CUR-BONUS)"
        )
        assert prog.sql_update_where_current is True, (
            f"{path.name}: sql_update_where_current should be True"
        )
