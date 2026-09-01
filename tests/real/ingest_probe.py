"""Honest ingestion probe against the REAL evidence corpus in data/input.

Usage: python tests/real/ingest_probe.py <control_dir_name>

Prints exactly what the Evidence Graph captured - leaves, cells, emails,
images, nesting, errors, timings - and control-specific fact probes so the
claims are verifiable, not asserted.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from iqr.ingest.graph_builder import build_evidence_graph

BASE = Path(__file__).resolve().parents[2] / "data/input/iqr_build_package/03_source_evidence"


def main(control: str) -> None:
    pkg = BASE / control
    t0 = time.time()
    graph = build_evidence_graph(str(pkg))
    dt = time.time() - t0

    print(f"=== {control}  ({dt:.1f}s) ===", flush=True)
    print(f"leaves={len(graph.leaves)} cells={len(graph.cells)} "
          f"emails={len(graph.emails)} images={len(graph.images)} "
          f"docs={len(graph.docs)} errors={len(graph.errors)}", flush=True)

    print("\n-- leaves (nesting shown by '!') --", flush=True)
    for leaf in sorted(graph.leaves.values(), key=lambda l: l.logical_path):
        print(f"  [{leaf.kind:5s}] {leaf.logical_path}  "
              f"({leaf.size:,}B  {leaf.file_hash[:10]})", flush=True)

    if graph.errors:
        print("\n-- ERRORS (honest) --", flush=True)
        for e in graph.errors:
            print(f"  ! {e}", flush=True)

    print("\n-- emails --", flush=True)
    for mid, em in graph.emails.items():
        print(f"  {mid}", flush=True)
        print(f"    from: {em.sender!r}  date: {em.date_raw!r}", flush=True)
        print(f"    subj: {em.subject!r}", flush=True)
        print(f"    body: {len(em.lines)} lines, attachments: {len(em.attachment_hashes)}", flush=True)
        for i, line in enumerate(em.lines[:400], 1):
            low = line.lower()
            if any(k in low for k in ("final consolidation", "approved", "approve",
                                      "sign", "exception", "resolved", "completed",
                                      "2:44", "pm", "checklist")):
                print(f"    line {i}: {line.strip()[:150]!r}", flush=True)

    # sheet inventory per workbook
    sheets: dict[tuple[str, str], int] = {}
    for cf in graph.cells.values():
        leaf = graph.leaves.get(cf.file_hash)
        name = leaf.logical_path if leaf else cf.file_hash[:10]
        sheets[(name, cf.sheet)] = sheets.get((name, cf.sheet), 0) + 1
    print("\n-- workbook sheets (non-empty cells) --", flush=True)
    for (name, sheet), n in sorted(sheets.items()):
        print(f"  {name[:60]} :: {sheet[:40]} -> {n} cells", flush=True)

    # fact probes: cells whose value mentions delta/total/timestamp-ish strings
    print("\n-- probe: cells containing 'delta'/'total'/timestamps --", flush=True)
    hits = 0
    for key, cf in graph.cells.items():
        v = cf.value
        if isinstance(v, str) and any(k in v.lower() for k in
                                      ("delta", "total", "gmt", "cdt", "timestamp",
                                       "run date", "wos", "sign")):
            leaf = graph.leaves.get(cf.file_hash)
            name = leaf.logical_path[:40] if leaf else "?"
            print(f"  {name} {cf.sheet[:24]}!{cf.cell}: {str(v)[:80]!r}", flush=True)
            hits += 1
            if hits >= 40:
                print("  ... (capped at 40)", flush=True)
                break


if __name__ == "__main__":
    main(sys.argv[1])
