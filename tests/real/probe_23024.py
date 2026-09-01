"""Real-data validation probes, all three controls, sequential.

10032: run the ACTUAL deterministic tools against real cells (delta-zero with
tolerance, stat netting, temporal normalize, .msg sign-off parse).
23024: ingest the 185MB screenshot-docx; real OCR on embedded images; find the
WOS working sheet in the 33MB summary.
10075: ingest the multi-tab IPE + screenshot workbooks + 5 real .eml chain;
real OCR on a WEBI validation screenshot; SoD facts from the real chain.

Honest output: every claim printed with the real cell/line it came from.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from iqr.ingest.graph_builder import build_evidence_graph
from iqr.tools.recompute import recompute
from iqr.tools.timestamp import parse_timestamp
from iqr.tools.cell_read import cell_read

BASE = Path(__file__).resolve().parents[2] / "data/input/iqr_build_package/03_source_evidence"


def banner(t):
    print("\n" + "=" * 78, flush=True)
    print(t, flush=True)
    print("=" * 78, flush=True)


def leaf_by(g, frag):
    for leaf in sorted(g.leaves.values(), key=lambda l: l.logical_path):
        if frag.lower() in leaf.logical_path.lower():
            return leaf
    return None



banner("CONTROL 23024 - 185MB screenshot-docx ingest + real OCR + WOS sheet")
t0 = time.time()
g = build_evidence_graph(str(BASE / "control_23024_rebate_calc"))
print(f"ingest {time.time()-t0:.0f}s  leaves={len(g.leaves)} cells={len(g.cells):,} "
      f"images={len(g.images)} docs={len(g.docs)} errors={len(g.errors)}", flush=True)
for e in g.errors[:5]:
    print("  ERROR:", e, flush=True)

doc404 = leaf_by(g, "SOX_404_Buy_Sell")
if doc404 and doc404.file_hash in g.docs:
    print(f"404 doc paragraphs: {len(g.docs[doc404.file_hash].paragraphs)}", flush=True)
doc_imgs = [i for i in g.images.values() if "SOX_404_Buy_Sell" in i.logical_path]
print(f"images extracted from the 185MB 404 docx: {len(doc_imgs)}", flush=True)

# real OCR on up to 3 of the larger embedded screenshots
from iqr.tools.ocr_read import ocr_read
big = sorted(doc_imgs, key=lambda i: -(i.width * i.height))[:3]
for imf in big:
    try:
        text, cite = ocr_read(g, imf.file_hash)
        clean = " ".join(text.split())[:220]
        print(f"OCR {imf.logical_path.split('!')[-1]} ({imf.width}x{imf.height}): {clean!r}", flush=True)
    except Exception as e:
        print(f"OCR {imf.logical_path[-40:]}: ERROR {e}", flush=True)

summary = leaf_by(g, "Q226-BS_Control")
sheets = sorted({cf.sheet for cf in g.cells.values() if cf.file_hash == summary.file_hash})
print(f"summary workbook sheets ({len(sheets)}): {sheets}", flush=True)
wos_hits = 0
for key, cf in g.cells.items():
    if cf.file_hash == summary.file_hash and isinstance(cf.value, str) and \
            any(k in cf.value.lower() for k in ("wos", "weeks of supply", "deferral", "cmar", "consumption")):
        print(f"  WOS-probe {cf.sheet[:30]}!{cf.cell}: {cf.value[:80]!r}", flush=True)
        wos_hits += 1
        if wos_hits >= 15:
            break

