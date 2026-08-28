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


# ---------------------------------------------------------------- 10032
banner("CONTROL 10032 - real deterministic checks")
t0 = time.time()
g = build_evidence_graph(str(BASE / "control_10032_consolidation_recon"))
print(f"ingest {time.time()-t0:.0f}s  cells={len(g.cells):,} errors={len(g.errors)}", flush=True)

recon = leaf_by(g, "OOC3.zip!OOC3/BPC Consol TB vs ODW")
afo = leaf_by(g, "BPC_Analysis_Report")

# C1: BPC vs ODW grand-total deltas ~ 0 within tolerance (real fp residue!)
for sheet, cell, label in [("Recon", "B30339", "BPC-side Grand Total delta"),
                           ("Recon", "G53656", "ODW-side Grand Total delta"),
                           ("Recon", "D2", "BPC delta column sum"),
                           ("Recon", "I2", "ODW delta column sum")]:
    v, cite = cell_read(g, recon.file_hash, sheet, cell)
    r = recompute("delta_zero", [float(v), 0.0], 0.0, tolerance=0.01)
    print(f"C1 {label}: {float(v):.10f} -> {'PASS' if r.ok else 'FAIL'} "
          f"(tol 0.01)  cite={cite.locator_str()}", flush=True)

# C2: stat accounts net to zero (D5 + E5 on Stat acct check)
d5, c_d5 = cell_read(g, afo.file_hash, "Stat acct check", "D5")
e5, c_e5 = cell_read(g, afo.file_hash, "Stat acct check", "E5")
r = recompute("sum_equals", [float(d5), float(e5)], 0.0, tolerance=0.01)
print(f"C2 stat netting: {d5} + {e5} = {r.computed:.2f} -> "
      f"{'PASS' if r.ok else 'FAIL'}  cites={c_d5.locator_str()},{c_e5.locator_str()}", flush=True)

# C3: temporal - AFO 'Last Data Update' stamps vs email 'final consolidation 2:44 PM CDT'
em = next(iter(g.emails.values()))
consol_line = None
for i, line in enumerate(em.lines, 1):
    if "final consolidation" in line.lower():
        consol_line = (i, line.strip())
        break
print(f"C3 email anchor line {consol_line[0]}: {consol_line[1][:120]!r}", flush=True)
consol = parse_timestamp("May 14, 2026 2:44 PM", assume_tz="CDT")
for row in (1, 3, 6, 9):
    v, cite = cell_read(g, afo.file_hash, "Run timestamp", f"C{row}")
    stamp_cdt = parse_timestamp(str(v), assume_tz="CDT")
    stamp_gmt = parse_timestamp(str(v), assume_tz="GMT")
    print(f"C3 AFO refresh C{row} = {v}  as-CDT:{'AFTER' if stamp_cdt>=consol else 'BEFORE'} "
          f"consol | as-GMT:{'AFTER' if stamp_gmt>=consol else 'BEFORE'} consol  "
          f"cite={cite.locator_str()}", flush=True)
print("C3 NOTE: cell timezone is not stated in the workbook - the compiled plan "
      "must pin it (SME input); the tooling normalizes either way.", flush=True)

# C4: sign-off from the real .msg
approval = None
for i, line in enumerate(em.lines, 1):
    if "approved" in line.lower():
        approval = (i, line.strip())
        break
print(f"C4 approver: {em.sender!r}  date(hdr): {em.date_raw!r}", flush=True)
print(f"C4 approval line {approval[0]}: {approval[1][:140]!r}", flush=True)
chk = leaf_by(g, "Control Reviewer Checklist")
print(f"C4 reviewer checklist present in pack: {'YES - ' + chk.logical_path[:80] if chk else 'NO'}", flush=True)

del g  # free memory before the big ones

# ---------------------------------------------------------------- 23024
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
del g

# ---------------------------------------------------------------- 10075
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
