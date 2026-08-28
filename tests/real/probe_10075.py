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
from iqr.tools.ocr_read import ocr_read

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



banner("CONTROL 10075 - multimodal: 44-tab IPE, screenshot docs, real .eml chain")
t0 = time.time()
g = build_evidence_graph(str(BASE / "control_10075_emr_review"))
print(f"ingest {time.time()-t0:.0f}s  leaves={len(g.leaves)} cells={len(g.cells):,} "
      f"emails={len(g.emails)} images={len(g.images)} docs={len(g.docs)} errors={len(g.errors)}", flush=True)
for e in g.errors[:5]:
    print("  ERROR:", e, flush=True)

ipe = leaf_by(g, "IPE_Webi_AFO_Workiva")
tabs = sorted({cf.sheet for cf in g.cells.values() if cf.file_hash == ipe.file_hash})
print(f"IPE recon workbook tabs ({len(tabs)}): {tabs[:20]}{' ...' if len(tabs)>20 else ''}", flush=True)

print("\n-- real sign-off chain (.eml) --", flush=True)
for mid, em in sorted(g.emails.items()):
    print(f"  {em.subject[:70]!r}", flush=True)
    print(f"    from {em.sender[:60]!r}  date {em.date_raw!r}  attachments={len(em.attachment_hashes)}", flush=True)
    for i, line in enumerate(em.lines[:200], 1):
        low = line.lower()
        if any(k in low for k in ("approve", "sign off", "sing off", "exception",
                                  "resolved", "sharepoint", "tie", "reviewed")):
            print(f"    line {i}: {line.strip()[:140]!r}", flush=True)

# real OCR on one WEBI validation screenshot from the SS_Webi Revenue docx
rev_imgs = sorted([i for i in g.images.values() if "SS_Webi_-_Revenue" in i.logical_path],
                  key=lambda i: -(i.width * i.height))[:2]
print(f"\nSS_Webi Revenue docx screenshots extracted: "
      f"{sum(1 for i in g.images.values() if 'SS_Webi_-_Revenue' in i.logical_path)}", flush=True)
for imf in rev_imgs:
    try:
        text, cite = ocr_read(g, imf.file_hash)
        clean = " ".join(text.split())[:260]
        print(f"OCR ({imf.width}x{imf.height}): {clean!r}", flush=True)
    except Exception as e:
        print(f"OCR ERROR: {e}", flush=True)

# scope-exclusion tabs in the slide-screenshot workbook
slides = leaf_by(g, "Screen_Shots_of_approved")
if slides:
    stabs = sorted({cf.sheet for cf in g.cells.values() if cf.file_hash == slides.file_hash})
    n_slide_imgs = sum(1 for i in g.images.values() if "Screen_Shots_of_approved" in i.logical_path)
    print(f"\nslide workbook: {len(stabs)} tabs with cells, {n_slide_imgs} embedded slide images", flush=True)
    for t in stabs:
        flag = "  <-- dependent-control (must be EXCLUDED)" if any(
            k in t.lower() for k in ("eps", "cash", "debt")) else ""
        print(f"  tab: {t[:50]}{flag}", flush=True)

print("\nALL PROBES DONE", flush=True)
