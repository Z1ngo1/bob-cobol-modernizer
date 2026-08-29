#!/usr/bin/env python3
"""
main.py — Entry point for the cobol-knowledge-builder tool.

Usage (run from the knowledge-base/ directory, or anywhere):

    python main.py [--tasks-root PATH] [--out-dir PATH]

Defaults:
    --tasks-root  ../COBOL-PRACTICE-TASKS/TASKS   (sibling folder to knowledge-base/)
    --out-dir     ./                               (the knowledge-base/ folder itself)

Pipeline
--------
1. parser.parse_tasks()         →  list[TaskInfo]     (source code analysis)
2. classifier.classify_tasks()  →  in-place group A–I  (taxonomy rules)
3. report_generator.generate_task_readme()  →  per-task README.md
4. report_generator.generate_index()        →  master INDEX.md
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running as `python main.py` from the knowledge-base/ directory
# even if the package is not installed.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from cobol_knowledge_builder import parser, classifier, report_generator


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cobol-knowledge-builder",
        description="Analyse COBOL tasks, classify them A–I, and generate READMEs + INDEX.",
    )
    p.add_argument(
        "--tasks-root",
        type=Path,
        default=None,
        help=(
            "Path to the TASKS/ folder. "
            "Default: auto-detected as <knowledge-base-parent>/COBOL-PRACTICE-TASKS/TASKS/ "
            "or <knowledge-base-parent>/TASKS/"
        ),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=_HERE,
        help="Directory where knowledge-base output is written. Default: same directory as main.py",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-task details during processing.",
    )
    return p


def _resolve_tasks_root(given: Path | None) -> Path:
    """Try to locate the TASKS/ folder relative to main.py."""
    if given is not None:
        resolved = given.resolve()
        if not resolved.exists():
            print(f"[ERROR] --tasks-root does not exist: {resolved}", file=sys.stderr)
            sys.exit(1)
        return resolved

    # Auto-detect: walk up from knowledge-base/ looking for a TASKS/ sibling
    candidates = [
        _HERE.parent / "COBOL-PRACTICE-TASKS" / "TASKS",   # nested repo layout
        _HERE.parent / "TASKS",                             # flat layout
        _HERE.parent.parent / "COBOL-PRACTICE-TASKS" / "TASKS",
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()

    print(
        "[ERROR] Could not locate the TASKS/ folder automatically.\n"
        "        Pass --tasks-root <path> explicitly.",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(tasks_root: Path, out_dir: Path, verbose: bool = False) -> None:
    t0 = time.perf_counter()

    # ---- Step 1: Parse -------------------------------------------------------
    print(f"[1/4] Scanning tasks in: {tasks_root}")
    tasks = parser.parse_tasks(tasks_root)
    print(f"      Found {len(tasks)} task folders.")

    # ---- Step 2: Classify ----------------------------------------------------
    print("[2/4] Classifying tasks into groups A-I ...")
    classifier.classify_tasks(tasks)

    if verbose:
        for t in tasks:
            progs = ", ".join(p.program_id or p.filename for p in t.programs) or "(none)"
            print(f"      {t.task_id:<8}  Group {t.group}  [{progs}]")

    # ---- Step 3: Per-task READMEs --------------------------------------------
    print(f"[3/4] Generating per-task READMEs in: {out_dir}")
    readme_paths: list[Path] = []
    for t in tasks:
        path = report_generator.generate_task_readme(t, out_dir)
        readme_paths.append(path)
        if verbose:
            print(f"      Wrote {path.relative_to(out_dir)}")

    print(f"      Generated {len(readme_paths)} README files.")

    # ---- Step 4: Master INDEX ------------------------------------------------
    print("[4/4] Generating master INDEX.md ...")
    index_path = report_generator.generate_index(tasks, out_dir)
    print(f"      Wrote {index_path}")

    elapsed = time.perf_counter() - t0
    print(f"\nDone in {elapsed:.2f}s")
    print(f"  Output directory : {out_dir}")
    print(f"  Tasks processed  : {len(tasks)}")

    # Print group summary
    from collections import Counter
    counts = Counter(t.group for t in tasks)
    print("\n  Group breakdown:")
    for g in sorted(counts):
        label = classifier.GROUP_LABELS.get(g, "")
        print(f"    Group {g} ({label:<42}) : {counts[g]} task(s)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    tasks_root = _resolve_tasks_root(args.tasks_root)
    out_dir    = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    run(tasks_root, out_dir, verbose=args.verbose)
