"""
report_generator.py -- Generates two kinds of output:

1. Per-task README.md (written into knowledge-base/<task_name>/README.md)
   Sections:  Overview · Technology Stack · Programs & Dependencies
              Data Flow · Group Classification

2. Master INDEX.md  (written into knowledge-base/INDEX.md)
   Sections:  Full classification table · Repeated patterns · Mermaid dependency diagram
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Optional

from .parser import TaskInfo, ProgramInfo
from .classifier import GROUP_LABELS


# ---------------------------------------------------------------------------
# Tech-stack badges (plain Markdown text tags)
# ---------------------------------------------------------------------------

def _tech_stack(task: TaskInfo) -> list[str]:
    tags: list[str] = []

    if task.jcl_defksds or any(p.vsam_ksds for p in task.programs):
        tags.append("VSAM KSDS")
    if task.jcl_defaix or any(p.vsam_aix for p in task.programs):
        tags.append("VSAM AIX")
    if task.jcl_defesds or any(p.vsam_esds for p in task.programs):
        tags.append("VSAM ESDS")
    if task.jcl_defgdg:
        tags.append("GDG")
    if task.jcl_dsqqmfe:
        tags.append("QMF")
    if any(p.has_db2 for p in task.programs):
        tags.append("DB2")
        if any(p.sql_cursor_with_hold for p in task.programs):
            tags.append("DB2 cursor WITH HOLD")
        if any(p.sql_bulk_insert and not p.sql_select_into for p in task.programs):
            tags.append("DB2 bulk INSERT")
        if any(p.sql_select_into and p.sql_bulk_insert for p in task.programs):
            tags.append("DB2 upsert (SELECT+UPDATE/INSERT)")
        if any(p.sql_select_into and not p.sql_bulk_insert for p in task.programs):
            tags.append("DB2 SELECT INTO")
    if any(p.has_sort for p in task.programs):
        if any(p.has_sort_input_proc for p in task.programs):
            tags.append("SORT with INPUT PROCEDURE")
        if any(p.has_sort_output_proc for p in task.programs):
            tags.append("SORT with OUTPUT PROCEDURE")
        else:
            tags.append("Internal SORT")
    if any(p.has_sysin for p in task.programs):
        tags.append("SYSIN parameter parsing")
    if task.copybooks:
        tags.append(f"Shared copybook ({', '.join(task.copybooks)})")
    if any(p.has_linkage_section for p in task.programs):
        tags.append("CALL / LINKAGE SECTION")

    # Always PS sequential files
    tags.append("Sequential PS files")

    return tags


# ---------------------------------------------------------------------------
# Data-flow description (human-readable sentence)
# ---------------------------------------------------------------------------

def _data_flow(task: TaskInfo) -> str:
    """Build a one-paragraph data-flow description from detected signals."""
    parts: list[str] = []

    main_progs = [p for p in task.programs if not p.has_goback and not p.has_linkage_section]
    sub_progs  = [p for p in task.programs if p.has_goback or p.has_linkage_section]

    if task.jcl_dsqqmfe:
        return (
            "No COBOL program -- the pipeline is driven entirely by JCL, QMF batch executor "
            "(`DSQQMFE`), QMF PROC, QMF queries, and DFSORT. The QMF PROC runs SQL queries "
            "against DB2, exports results to PS datasets, and DFSORT merges them into a final "
            "dated report using GDG generations as section separators."
        )

    # Inputs
    inputs: list[str] = []
    if task.jcl_defksds or any(p.vsam_ksds for p in task.programs):
        mode = "RANDOM" if any(p.vsam_random for p in task.programs) else \
               "DYNAMIC" if any(p.vsam_dynamic for p in task.programs) else "SEQUENTIAL"
        inputs.append(f"VSAM KSDS (access mode: {mode})")
    if task.jcl_defesds or any(p.vsam_esds for p in task.programs):
        inputs.append("VSAM ESDS (sequential log)")
    if task.jcl_defaix or any(p.vsam_aix for p in task.programs):
        inputs.append("VSAM KSDS with Alternate Index (AIX)")
    if any(p.has_db2 for p in task.programs):
        inputs.append("DB2 table(s)")
    inputs.append("sequential PS file(s)")

    parts.append("**Inputs:** " + ", ".join(inputs) + ".")

    # Processing
    proc: list[str] = []
    if any(p.sql_cursor_with_hold for p in task.programs):
        proc.append("cursor-driven DB2 update (FETCH + UPDATE WHERE CURRENT OF)")
    if any(p.sql_bulk_insert for p in task.programs):
        proc.append("batched DB2 INSERT (commit every N records)")
    if any(p.sql_select_into and p.sql_bulk_insert for p in task.programs):
        proc.append("upsert logic (SELECT to check existence, then UPDATE or INSERT)")
    if any(p.has_sort for p in task.programs):
        ip = any(p.has_sort_input_proc for p in task.programs)
        op = any(p.has_sort_output_proc for p in task.programs)
        desc = "internal SORT"
        if ip:
            desc += " with INPUT PROCEDURE (pre-filter)"
        if op:
            desc += " with OUTPUT PROCEDURE (post-process)"
        proc.append(desc)
    if sub_progs:
        names = ", ".join(p.program_id or p.filename for p in sub_progs)
        proc.append(f"CALL to subprogram(s): {names}")
    if task.copybooks:
        proc.append(f"shared copybook COPY statement ({', '.join(task.copybooks)})")
    if any(p.has_sysin for p in task.programs):
        proc.append("SYSIN parameter parsing (KEY=VALUE filter)")
    if task.jcl_defgdg:
        proc.append("output routed to multiple GDG generations")

    if proc:
        parts.append("**Processing:** " + "; ".join(proc) + ".")

    # Output
    parts.append("**Output:** report/log written to sequential PS file(s).")

    return "  \n".join(parts)


# ---------------------------------------------------------------------------
# Programs & Dependencies section
# ---------------------------------------------------------------------------

def _programs_section(task: TaskInfo) -> str:
    if not task.programs:
        return "_No COBOL programs (JCL/QMF only task)._\n"

    lines: list[str] = []
    for p in task.programs:
        role = "subprogram" if (p.has_goback or p.has_linkage_section) else "main program"
        calls_str  = (", ".join(f"`{c}`" for c in p.calls)  if p.calls  else "--")
        copies_str = (", ".join(f"`{c}`" for c in p.copies) if p.copies else "--")

        db2_detail = ""
        if p.has_db2:
            flags: list[str] = []
            if p.sql_cursor_with_hold:      flags.append("cursor WITH HOLD")
            if p.sql_update_where_current:  flags.append("UPDATE WHERE CURRENT OF")
            if p.sql_bulk_insert:           flags.append("INSERT INTO")
            if p.sql_select_into:           flags.append("SELECT INTO")
            dclgens = [d for d in p.sql_include_dclgen if d not in ("SQLCA",)]
            if dclgens:
                flags.append(f"DCLGEN: {', '.join(dclgens)}")
            db2_detail = f" · DB2: {', '.join(flags)}" if flags else " · DB2: yes"

        vsam_detail = ""
        if p.vsam_ksds or p.vsam_aix or p.vsam_esds:
            v: list[str] = []
            if p.vsam_ksds:    v.append("KSDS")
            if p.vsam_aix:     v.append("AIX")
            if p.vsam_esds:    v.append("ESDS")
            if p.vsam_random:  v.append("RANDOM")
            if p.vsam_dynamic: v.append("DYNAMIC")
            vsam_detail = f" · VSAM: {', '.join(v)}"

        sort_detail = ""
        if p.has_sort:
            s: list[str] = ["SORT"]
            if p.has_sort_input_proc:  s.append("INPUT PROC")
            if p.has_sort_output_proc: s.append("OUTPUT PROC")
            sort_detail = f" · {'/'.join(s)}"

        lines.append(
            f"| `{p.filename}` | `{p.program_id}` | {role} "
            f"| {calls_str} | {copies_str} "
            f"|{db2_detail}{vsam_detail}{sort_detail} |"
        )

    header = (
        "| File | PROGRAM-ID | Role | CALLs | COPYs | Notes |\n"
        "|------|------------|------|-------|-------|-------|"
    )
    return header + "\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Per-task README
# ---------------------------------------------------------------------------

def generate_task_readme(task: TaskInfo, out_dir: Path) -> Path:
    """Write knowledge-base/<task_name>/README.md and return the path."""
    task_dir = out_dir / task.task_name
    task_dir.mkdir(parents=True, exist_ok=True)
    out_path = task_dir / "README.md"

    # Human-readable title
    slug = task.task_name.replace("-", " ").title()

    # Technology stack bullet list
    stack_md = "\n".join(f"- {t}" for t in _tech_stack(task))

    # JCL signals
    jcl_lines: list[str] = []
    if task.jcl_defksds:  jcl_lines.append("- DEFKSDS (IDCAMS DEFINE CLUSTER ... INDEXED)")
    if task.jcl_defesds:  jcl_lines.append("- DEFESDS (IDCAMS DEFINE CLUSTER ... NONINDEXED)")
    if task.jcl_defaix:   jcl_lines.append("- DEFAIX  (IDCAMS DEFINE AIX)")
    if task.jcl_defgdg:   jcl_lines.append("- DEFGDG  (IDCAMS DEFINE GDG)")
    if task.jcl_dsqqmfe:  jcl_lines.append("- DSQQMFE (QMF batch executor)")
    jcl_md = "\n".join(jcl_lines) if jcl_lines else "- N/A"

    # Pre-compute every value (including the boolean Yes/No flags) BEFORE
    # building the template, so the template string itself contains only
    # plain {placeholder} tokens and no inline expressions.
    db2_yn          = "Yes" if any(p.has_db2 for p in task.programs) else "No"
    vsam_ksds_yn    = "Yes" if (task.jcl_defksds or any(p.vsam_ksds for p in task.programs)) else "No"
    vsam_aix_yn     = "Yes" if (task.jcl_defaix or any(p.vsam_aix for p in task.programs)) else "No"
    vsam_esds_yn    = "Yes" if (task.jcl_defesds or any(p.vsam_esds for p in task.programs)) else "No"
    gdg_yn          = "Yes" if task.jcl_defgdg else "No"
    qmf_yn          = "Yes" if task.jcl_dsqqmfe else "No"
    multi_call_yn   = "Yes" if any(p.calls for p in task.programs) else "No"
    copybooks_str   = ", ".join(f"`{c}`" for c in task.copybooks) if task.copybooks else "No"

    # IMPORTANT: dedent() must run on the RAW template (only {placeholder}
    # tokens, no interpolated content yet). If multi-line values such as
    # stack_md / _programs_section(...) are interpolated first (e.g. via an
    # f-string), their own lines start at column 0, so dedent() can no
    # longer find a common leading whitespace across *all* lines and ends
    # up stripping nothing -- leaving the static template lines indented
    # and breaking Markdown tables/lists. So: dedent first, .format() after.
    template = dedent("""\
        # {slug}

        ## Overview

        > **Group {group} -- {group_label}**

        Task folder: `TASKS/{task_name}/`

        ---

        ## Technology Stack

        {stack_md}

        ### JCL Infrastructure Detected

        {jcl_md}

        ---

        ## Programs and Dependencies

        {programs_section}

        ---

        ## Data Flow

        {data_flow}

        ---

        ## Group Classification

        | Property | Value |
        |----------|-------|
        | **Task ID** | `{task_id}` |
        | **Group** | {group} |
        | **Group Label** | {group_label} |
        | **DB2** | {db2_yn} |
        | **VSAM KSDS** | {vsam_ksds_yn} |
        | **VSAM AIX** | {vsam_aix_yn} |
        | **VSAM ESDS** | {vsam_esds_yn} |
        | **GDG** | {gdg_yn} |
        | **QMF** | {qmf_yn} |
        | **Multi-program CALL** | {multi_call_yn} |
        | **Shared Copybook** | {copybooks_str} |

        ---

        _Auto-generated by `cobol-knowledge-builder`. Source of truth: `TASKS/{task_name}/`._
    """)

    content = template.format(
        slug=slug,
        group=task.group,
        group_label=task.group_label,
        task_name=task.task_name,
        task_id=task.task_id,
        stack_md=stack_md,
        jcl_md=jcl_md,
        programs_section=_programs_section(task),
        data_flow=_data_flow(task),
        db2_yn=db2_yn,
        vsam_ksds_yn=vsam_ksds_yn,
        vsam_aix_yn=vsam_aix_yn,
        vsam_esds_yn=vsam_esds_yn,
        gdg_yn=gdg_yn,
        qmf_yn=qmf_yn,
        multi_call_yn=multi_call_yn,
        copybooks_str=copybooks_str,
    )

    out_path.write_text(content, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Mermaid diagram
# ---------------------------------------------------------------------------

def _build_mermaid(tasks: list[TaskInfo]) -> str:
    """
    Build a Mermaid graph LR diagram showing:
     - CALL edges between programs
     - COPY edges between programs and copybooks
    Only tasks/programs that have actual dependencies are included.
    """
    lines: list[str] = ["```mermaid", "graph LR"]

    for task in tasks:
        for prog in task.programs:
            if not prog.program_id:
                continue
            node_id = prog.program_id

            for called in prog.calls:
                lines.append(f"    {node_id} -->|CALL| {called}")

            for copybook in prog.copies:
                cb_node = f"CPY_{copybook}"
                lines.append(f"    {node_id} -.->|COPY| {cb_node}[/{copybook}.cpy/]")

    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Repeated patterns section
# ---------------------------------------------------------------------------

_PATTERNS = [
    {
        "id": "P1",
        "title": "VSAM KSDS Random-Read + Status-23 Error Path",
        "description": (
            "Canonical pattern: `MOVE key -> READ KSDS; INVALID KEY / status '23' -> log/skip; "
            "NOT INVALID KEY -> process`. Appears in 8 tasks."
        ),
        "tasks": ["TASK05", "TASK10", "TASK11", "TASK23", "TASK25", "TASK26", "TASK27", "TASK29"],
    },
    {
        "id": "P2",
        "title": "DB2 Cursor WITH HOLD + UPDATE WHERE CURRENT OF",
        "description": (
            "Identical skeleton: DECLARE CUR WITH HOLD FOR UPDATE -> OPEN -> FETCH loop "
            "-> EVALUATE dept/region -> COMPUTE new value -> cap -> UPDATE WHERE CURRENT OF "
            "-> ROLLBACK on error -> COMMIT threshold."
        ),
        "tasks": ["TASK07", "TASK08"],
    },
    {
        "id": "P3",
        "title": "DB2 Batched INSERT with Validation + Commit Threshold",
        "description": (
            "Pattern: validate -> reject-log -> INSERT -> SQLCODE 0 / -803 / OTHER "
            "-> batch COMMIT every 100 -> final COMMIT in CLOSE."
        ),
        "tasks": ["TASK19", "TASK21"],
    },
    {
        "id": "P4",
        "title": "DB2 Upsert (SELECT INTO -> UPDATE or INSERT)",
        "description": (
            "SELECT INTO first; SQLCODE 0 = exists -> UPDATE; SQLCODE 100 = new -> INSERT; "
            "critical SQLCODE < -900 -> ROLLBACK + STOP."
        ),
        "tasks": ["TASK20", "TASK25"],
    },
    {
        "id": "P5",
        "title": "In-memory Table Lookup (OCCURS + PERFORM VARYING / SEARCH ALL)",
        "description": (
            "Two-phase load-then-process: read reference file into OCCURS table, "
            "then PERFORM VARYING (linear) or SEARCH ALL (binary) for each data record."
        ),
        "tasks": ["TASK14", "TASK15", "TASK16", "TASK24"],
    },
    {
        "id": "P6",
        "title": "Internal SORT with INPUT/OUTPUT PROCEDURE",
        "description": (
            "Both use SD sort file and RELEASE/RETURN verbs. "
            "TASK09 uses SORT USING + OUTPUT PROCEDURE for group duplicate detection. "
            "TASK17 uses INPUT PROCEDURE (filter) + OUTPUT PROCEDURE (write)."
        ),
        "tasks": ["TASK09", "TASK17"],
    },
    {
        "id": "P7",
        "title": "VSAM KSDS Sequential Scan (START + READ NEXT / ACCESS SEQUENTIAL)",
        "description": (
            "TASK06 uses ACCESS MODE IS DYNAMIC, START LOW-VALUES, then READ NEXT. "
            "TASK30 and TASK32/COP2LB32 use ACCESS MODE IS SEQUENTIAL for full scan."
        ),
        "tasks": ["TASK06", "TASK30", "TASK32"],
    },
    {
        "id": "P8",
        "title": "Match-Merge / Master File Sync Algorithm",
        "description": (
            "Classic balance-line: two sorted inputs, compare keys, route to "
            "add/update/delete/copy, HIGH-VALUES sentinel for EOF."
        ),
        "tasks": ["TASK13", "TASK24", "TASK25"],
    },
    {
        "id": "P9",
        "title": "RETURN-CODE-Based Error Severity Reporting",
        "description": (
            "RETURN-CODE set in WORKING-STORAGE based on error counts after the loop; "
            "allows JCL COND= checks. RC 0/4/8/12/16 (TASK26), RC 0/4/12 (TASK27)."
        ),
        "tasks": ["TASK26", "TASK27"],
    },
    {
        "id": "P10",
        "title": "ESDS Sequential Scan",
        "description": (
            "TASK28 opens/closes ESDS per client (nested lifecycle for full scan). "
            "TASK29 opens ESDS once and reads it for each operation record."
        ),
        "tasks": ["TASK28", "TASK29"],
    },
]


# ---------------------------------------------------------------------------
# Master INDEX.md
# ---------------------------------------------------------------------------

def generate_index(tasks: list[TaskInfo], out_dir: Path) -> Path:
    """Write knowledge-base/INDEX.md and return the path."""
    out_path = out_dir / "INDEX.md"

    # --- Full classification table ---
    from collections import defaultdict
    by_group: dict[str, list[TaskInfo]] = defaultdict(list)
    for t in tasks:
        by_group[t.group].append(t)

    table_rows: list[str] = []
    for grp in sorted(by_group.keys()):
        label = GROUP_LABELS.get(grp, "")
        task_ids = ", ".join(
            f"[{t.task_id}]({t.task_name}/README.md)" for t in by_group[grp]
        )
        table_rows.append(f"| **{grp}** | {label} | {task_ids} | {len(by_group[grp])} |")

    classification_table = (
        "| Group | Label | Tasks | Count |\n"
        "|-------|-------|-------|-------|\n"
        + "\n".join(table_rows)
    )

    # --- Repeated patterns section ---
    pattern_md_parts: list[str] = []
    for pat in _PATTERNS:
        task_links = ", ".join(
            f"[{tid}]({_find_task_name(tasks, tid)}/README.md)" if _find_task_name(tasks, tid)
            else tid
            for tid in pat["tasks"]
        )
        pattern_md_parts.append(
            f"### {pat['id']} -- {pat['title']}\n\n"
            f"{pat['description']}\n\n"
            f"**Tasks:** {task_links}\n"
        )
    patterns_md = "\n---\n\n".join(pattern_md_parts)

    # --- Task summary table (all tasks) ---
    all_rows: list[str] = []
    for t in tasks:
        db2 = "OK" if any(p.has_db2 for p in t.programs) else ""
        vsam_ksds = "OK" if (t.jcl_defksds or any(p.vsam_ksds for p in t.programs)) else ""
        vsam_aix  = "OK" if (t.jcl_defaix or any(p.vsam_aix for p in t.programs)) else ""
        vsam_esds = "OK" if (t.jcl_defesds or any(p.vsam_esds for p in t.programs)) else ""
        gdg       = "OK" if t.jcl_defgdg else ""
        qmf       = "OK" if t.jcl_dsqqmfe else ""
        call_sub  = "OK" if any(p.calls for p in t.programs) else ""
        prog_names = ", ".join(
            f"`{p.program_id or p.filename}`" for p in t.programs
        ) or "_none_"
        all_rows.append(
            f"| [{t.task_id}]({t.task_name}/README.md) "
            f"| {t.group} | {t.group_label} "
            f"| {prog_names} "
            f"| {db2} | {vsam_ksds} | {vsam_aix} | {vsam_esds} | {gdg} | {qmf} | {call_sub} |"
        )

    all_tasks_table = (
        "| Task | Grp | Group Label | Program(s) | DB2 | KSDS | AIX | ESDS | GDG | QMF | CALL |\n"
        "|------|-----|-------------|------------|-----|------|-----|------|-----|-----|------|\n"
        + "\n".join(all_rows)
    )

    # --- Mermaid diagram ---
    mermaid = _build_mermaid(tasks)

    # Same fix as generate_task_readme(): dedent the RAW template (plain
    # {placeholder} tokens only) before interpolating any multi-line
    # content, otherwise dedent() can't find a common indent and leaves
    # the static template lines indented, breaking Markdown rendering.
    template = dedent("""\
        # COBOL Practice Tasks -- Knowledge Base Index

        > Auto-generated by `cobol-knowledge-builder`.  
        > Source of truth: `TASKS/` folder.  
        > Do not edit manually -- re-run `python main.py` to refresh.

        ---

        ## Classification Taxonomy

        {classification_table}

        ---

        ## All Tasks -- Quick Reference

        {all_tasks_table}

        ---

        ## Repeated Patterns Across Tasks

        {patterns_md}

        ---

        ## CALL / COPY Dependency Diagram

        The diagram below shows every inter-program `CALL` dependency (solid arrow)
        and every `COPY` copybook reference (dashed arrow) across the entire repository.
        Only programs that have at least one such dependency are shown.

        {mermaid}

        ---

        _Generated by `cobol-knowledge-builder` -- parser + classifier + report_generator pipeline._
    """)

    content = template.format(
        classification_table=classification_table,
        all_tasks_table=all_tasks_table,
        patterns_md=patterns_md,
        mermaid=mermaid,
    )

    out_path.write_text(content, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _find_task_name(tasks: list[TaskInfo], task_id: str) -> str:
    for t in tasks:
        if t.task_id == task_id:
            return t.task_name
    return ""
