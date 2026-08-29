"""
parser.py — Scans each TASK folder and extracts structured metadata.

For each task:
  - Reads every .cbl file:     PROGRAM-ID, CALL targets, COPY targets,
                                EXEC SQL blocks (classified), VSAM file
                                declarations, SORT/SD usage, SYSIN usage
  - Reads every .jcl file:     DEFKSDS / DEFESDS / DEFAIX / DEFGDG /
                                DSQQMFE presence
  - Reads every .cpy file:     records shared copybook names
"""

from __future__ import annotations

import re
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ProgramInfo:
    """Metadata extracted from a single .cbl source file."""
    filename: str
    program_id: str = ""
    calls: list[str] = field(default_factory=list)        # programs CALLed
    copies: list[str] = field(default_factory=list)       # copybooks COPYed

    # DB2
    has_db2: bool = False
    sql_cursor_with_hold: bool = False
    sql_update_where_current: bool = False
    sql_bulk_insert: bool = False
    sql_select_into: bool = False
    sql_include_sqlca: bool = False
    sql_include_dclgen: list[str] = field(default_factory=list)  # INCLUDE names

    # VSAM
    vsam_ksds: bool = False                # ORGANIZATION IS INDEXED
    vsam_esds: bool = False                # explicit ACCESS MODE IS SEQUENTIAL alongside ORGANIZATION IS SEQUENTIAL
    vsam_aix: bool = False                 # ALTERNATE RECORD KEY
    vsam_dynamic: bool = False             # ACCESS MODE IS DYNAMIC
    vsam_random: bool = False              # ACCESS MODE IS RANDOM

    # Structural patterns
    has_sort: bool = False                 # SORT statement
    has_sort_sd: bool = False              # SD (sort work file)
    has_sort_input_proc: bool = False      # INPUT PROCEDURE
    has_sort_output_proc: bool = False     # OUTPUT PROCEDURE
    has_sysin: bool = False                # ASSIGN TO SYSIN
    has_linkage_section: bool = False      # LINKAGE SECTION (subprogram)
    has_goback: bool = False               # GOBACK (subprogram)
    has_return_code: bool = False          # RETURN-CODE
    has_occurs_table: bool = False         # OCCURS in WORKING-STORAGE (in-memory table)
    has_copybook_copy: bool = False        # COPY statement present (shared copybook use)


@dataclass
class TaskInfo:
    """All metadata for one TASK folder."""
    task_id: str           # e.g. "TASK05"
    task_name: str         # e.g. "TASK05-VSAM-BANKING"
    folder: Path

    programs: list[ProgramInfo] = field(default_factory=list)
    copybooks: list[str] = field(default_factory=list)  # .cpy filenames in COPYLIB/

    # JCL signals
    jcl_defksds: bool = False
    jcl_defesds: bool = False
    jcl_defaix: bool = False
    jcl_defgdg: bool = False
    jcl_dsqqmfe: bool = False   # QMF batch executor

    # Derived
    group: str = ""             # A–I, filled by classifier
    group_label: str = ""


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_RE_FLAGS = re.IGNORECASE | re.MULTILINE

def _find(pattern: str, text: str, flags: int = _RE_FLAGS) -> bool:
    return bool(re.search(pattern, text, flags))

def _findall(pattern: str, text: str, flags: int = _RE_FLAGS) -> list[str]:
    return re.findall(pattern, text, flags)

def _strip_comments(text: str) -> str:
    """Remove COBOL column-7 comment lines (* in col 7) and inline remarks."""
    lines = []
    for line in text.splitlines():
        # COBOL fixed format: column 7 is index 6
        if len(line) > 6 and line[6] in ('*', '/'):
            continue
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# COBOL .cbl parser
# ---------------------------------------------------------------------------

def _parse_cbl(path: Path) -> ProgramInfo:
    raw = path.read_text(encoding="utf-8", errors="replace")
    src = _strip_comments(raw)
    upper = src.upper()

    info = ProgramInfo(filename=path.name)

    # PROGRAM-ID
    m = re.search(r'PROGRAM-ID\s*\.\s*(\w+)', upper)
    if m:
        info.program_id = m.group(1)

    # CALL 'name'  or  CALL "name"
    for m in re.finditer(r'\bCALL\s+[\'"](\w+)[\'"]', upper):
        name = m.group(1)
        if name not in info.calls:
            info.calls.append(name)

    # COPY name
    for m in re.finditer(r'\bCOPY\s+(\w+)', upper):
        name = m.group(1)
        if name not in info.copies:
            info.copies.append(name)

    # --- DB2 ---
    if 'EXEC SQL' in upper:
        info.has_db2 = True

        info.sql_include_sqlca = _find(r'INCLUDE\s+SQLCA', upper)

        # DCLGEN includes: INCLUDE <name> (not SQLCA)
        for m in re.finditer(r'INCLUDE\s+(\w+)', upper):
            n = m.group(1)
            if n != 'SQLCA' and n not in info.sql_include_dclgen:
                info.sql_include_dclgen.append(n)

        # Cursor names can contain hyphens (e.g. CUR-SALARY), so use [\w-]+
        info.sql_cursor_with_hold = _find(r'DECLARE\s+[\w-]+\s+CURSOR\s+WITH\s+HOLD', upper)
        # UPDATE and WHERE CURRENT OF may span multiple lines inside EXEC SQL
        info.sql_update_where_current = _find(
            r'UPDATE\b.*WHERE\s+CURRENT\s+OF', upper, re.IGNORECASE | re.DOTALL
        )
        info.sql_bulk_insert = _find(r'\bINSERT\s+INTO\b', upper)
        info.sql_select_into = _find(r'\bSELECT\b.*\bINTO\b', upper, re.IGNORECASE | re.DOTALL)

    # --- VSAM ---
    info.vsam_ksds    = _find(r'ORGANIZATION\s+IS\s+INDEXED', upper)
    info.vsam_aix     = _find(r'ALTERNATE\s+RECORD\s+KEY', upper)
    info.vsam_dynamic = _find(r'ACCESS\s+MODE\s+IS\s+DYNAMIC', upper)
    info.vsam_random  = _find(r'ACCESS\s+MODE\s+IS\s+RANDOM', upper)

    # ESDS: explicit ACCESS MODE IS SEQUENTIAL in FILE-CONTROL section
    # (PS files also use ORGANIZATION IS SEQUENTIAL but rarely declare
    # ACCESS MODE IS SEQUENTIAL explicitly in COBOL)
    info.vsam_esds = _find(
        r'ORGANIZATION\s+IS\s+SEQUENTIAL[^\n]*\n[^\n]*ACCESS\s+MODE\s+IS\s+SEQUENTIAL',
        upper
    )

    # --- SORT ---
    info.has_sort_sd          = _find(r'^\s+SD\s+\w+', upper)
    info.has_sort             = _find(r'^\s+SORT\s+\w+', upper)
    info.has_sort_input_proc  = _find(r'INPUT\s+PROCEDURE\s+IS\b', upper)
    info.has_sort_output_proc = _find(r'OUTPUT\s+PROCEDURE\s+IS\b', upper)

    # --- SYSIN ---
    info.has_sysin = _find(r'ASSIGN\s+TO\s+SYSIN\b', upper)

    # --- Subprogram markers ---
    info.has_linkage_section = _find(r'LINKAGE\s+SECTION', upper)
    info.has_goback          = _find(r'\bGOBACK\b', upper)
    info.has_return_code     = _find(r'RETURN-CODE', upper)

    # --- In-memory table (OCCURS in WORKING-STORAGE, not in FILE SECTION) ---
    # Heuristic: OCCURS N TIMES in working-storage section (not a file FD)
    ws_match = re.search(r'WORKING-STORAGE\s+SECTION(.*)', upper, re.DOTALL)
    if ws_match:
        ws_text = ws_match.group(1)
        info.has_occurs_table = _find(r'\bOCCURS\s+\d+', ws_text)

    # --- Shared copybook flag ---
    info.has_copybook_copy = bool(info.copies)

    return info


# ---------------------------------------------------------------------------
# JCL scanner
# ---------------------------------------------------------------------------

def _scan_jcl(folder: Path, task: TaskInfo) -> None:
    """Read all .jcl files in the task folder tree and set JCL signal flags."""
    for jcl_path in folder.rglob("*.jcl"):
        try:
            text = jcl_path.read_text(encoding="utf-8", errors="replace").upper()
        except OSError:
            continue

        # IDCAMS DEFINE CLUSTER … INDEXED  →  KSDS
        if re.search(r'DEFINE\s+CLUSTER\b.*INDEXED', text, re.DOTALL):
            task.jcl_defksds = True
        # IDCAMS DEFINE CLUSTER … NONINDEXED  →  ESDS
        if re.search(r'DEFINE\s+CLUSTER\b.*NONINDEXED', text, re.DOTALL):
            task.jcl_defesds = True
        # DEFINE AIX
        if re.search(r'DEFINE\s+AIX\b', text):
            task.jcl_defaix = True
        # DEFINE GDG
        if re.search(r'DEFINE\s+GDG\b', text):
            task.jcl_defgdg = True
        # QMF batch executor
        if 'DSQQMFE' in text:
            task.jcl_dsqqmfe = True


# ---------------------------------------------------------------------------
# Copybook scanner
# ---------------------------------------------------------------------------

def _scan_copybooks(folder: Path, task: TaskInfo) -> None:
    """Collect all .cpy filenames (in any subfolder) for this task."""
    for cpy_path in folder.rglob("*.cpy"):
        name = cpy_path.stem.upper()
        if name not in task.copybooks:
            task.copybooks.append(name)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_tasks(tasks_root: Path) -> list[TaskInfo]:
    """
    Scan *tasks_root* (the TASKS/ folder) and return one TaskInfo per task.
    Folders are expected to be named TASK##-<NAME>.
    """
    tasks: list[TaskInfo] = []

    for entry in sorted(tasks_root.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name          # e.g. "TASK05-VSAM-BANKING"
        m = re.match(r'^(TASK\d+)', name, re.IGNORECASE)
        if not m:
            continue

        task = TaskInfo(
            task_id=m.group(1).upper(),
            task_name=name,
            folder=entry,
        )

        # Parse all .cbl files
        for cbl_path in sorted(entry.rglob("*.cbl")):
            prog = _parse_cbl(cbl_path)
            task.programs.append(prog)

        # Copybooks
        _scan_copybooks(entry, task)

        # JCL signals
        _scan_jcl(entry, task)

        tasks.append(task)

    return tasks
