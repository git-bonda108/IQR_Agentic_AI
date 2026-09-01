"""Probe 2: extract the exact fact cells the 10032 checks need - real values."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from iqr.ingest.graph_builder import build_evidence_graph

BASE = Path(__file__).resolve().parents[2] / "data/input/iqr_build_package/03_source_evidence"

t0 = time.time()
g = build_evidence_graph(str(BASE / "control_10032_consolidation_recon"))
print(f"built in {time.time()-t0:.1f}s  leaves={len(g.leaves)} cells={len(g.cells):,} "
      f"emails={len(g.emails)} images={len(g.images)} docs={len(g.docs)} errors={len(g.errors)}",
      flush=True)
for e in g.errors:
    print("  ERROR:", e, flush=True)

print("\n-- all leaves --", flush=True)
for leaf in sorted(g.leaves.values(), key=lambda l: l.logical_path):
    print(f"  [{leaf.kind:5s}] {leaf.logical_path[:100]}  ({leaf.size:,}B)", flush=True)

def by_path(frag):
    for leaf in g.leaves.values():
        if frag.lower() in leaf.logical_path.lower():
            return leaf
    return None

def dump_region(leaf, sheet, rows, cols):
    print(f"\n-- {leaf.logical_path[:60]} :: {sheet} rows {rows[0]}-{rows[-1]} --", flush=True)
    for r in rows:
        vals = []
        for c in cols:
            cf = g.get_cell(leaf.file_hash, sheet, f"{c}{r}")
            if cf is not None and cf.value is not None:
                vals.append(f"{c}{r}={str(cf.value)[:40]!r}" + (" [f]" if cf.is_formula else ""))
        if vals:
            print("   " + "  ".join(vals), flush=True)

# the recon workbook arrived nested inside the .msg
recon = None
for leaf in g.leaves.values():
    if "!" in leaf.logical_path and leaf.kind == "xlsx" and leaf.size > 10_000_000:
        recon = leaf
for leaf in g.leaves.values():
    if "BPC_Consol_TB_vs_ODW" in leaf.logical_path:
        recon = leaf  # prefer the named recon workbook
if recon:
    dump_region(recon, "Recon", range(1, 6), "ABCDEFGHIJ")
    dump_region(recon, "Recon", range(30336, 30342), "ABCDEFGHIJ")
    dump_region(recon, "Recon", range(53653, 53659), "ABCDEFGHIJ")

afo = by_path("BPC_Analysis_Report")
if afo:
    dump_region(afo, "Run timestamp", range(1, 12), "ABCDEF")
    dump_region(afo, "Stat acct check", range(1, 15), "ABCDEFG")
    dump_region(afo, "Data Release", range(1, 8), "ABCDEF")

webi = by_path("RP-ERPODW-INC-Cons_Trial_Balance")
if webi:
    dump_region(webi, "Summary", range(1, 12), "ABCDE")
    dump_region(webi, "Query Details", range(1, 3), "ABCD")

xlsb = by_path(".xlsb")
if xlsb:
    n = sum(1 for cf in g.cells.values() if cf.file_hash == xlsb.file_hash)
    sheets = sorted({cf.sheet for cf in g.cells.values() if cf.file_hash == xlsb.file_hash})
    print(f"\n-- xlsb {xlsb.logical_path[:60]}: {n:,} cells, sheets={sheets}", flush=True)

doc = by_path("SOX_404_Control_Documentation")
if doc and doc.file_hash in g.docs:
    paras = g.docs[doc.file_hash].paragraphs
    print(f"\n-- 404 doc: {len(paras)} paragraphs; first lines:", flush=True)
    for p in paras[:12]:
        print("   |", p[:110], flush=True)
    n_img = sum(1 for i in g.images.values() if doc.logical_path.split('!')[0] in i.logical_path)
    print(f"   images extracted from 404 doc: {n_img}", flush=True)

# the nested checklist inside the msg's zip
print("\n-- nested-from-msg leaves --", flush=True)
for leaf in sorted(g.leaves.values(), key=lambda l: l.logical_path):
    if "!" in leaf.logical_path:
        print(f"   {leaf.logical_path[:110]}", flush=True)
