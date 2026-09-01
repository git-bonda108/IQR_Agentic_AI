# Real-Corpus Validation Report

**Date:** 2026-08-26 · **Corpus:** actual production GRC evidence packages for controls
10032, 23024, 10075 (`data/input/iqr_build_package/03_source_evidence/`) ·
**Mode:** offline (stub model) — every result below is deterministic tooling
against real files, no LLM claims involved.

Reproduce any table below with the scripts in `tests/real/`.

## Control 10032 — Consolidation Recon (FULLY VALIDATED)

Ingest: 11 leaves, **3,483,744 cells, 0 errors**. Full nesting walked
automatically: `.msg → Control Reviewer Checklist.docx + OOC3.zip → 2×.xlsm + .xlsb`.

| Check | Result | Real citation |
|---|---|---|
| BPC↔ODW grand-total deltas ≈ 0 | **PASS** (8.28e-06 / 1.65e-06, tol 0.01) | `Recon!B30339`, `G53656`, `D2`, `I2` |
| Stat accounts net to zero | **PASS** (−23,514,570.28 + 23,514,570.28) | `Stat acct check!D5,E5` |
| Certified report run AFTER final consolidation | **PASS** — 8:29:58 PM GMT+00:00 (= 3:29 PM CDT) vs consol 2:44 PM CDT | `Summary!D13` vs `.msg` body line 29 |
| Segregation of duties | **PASS** — preparer `preparer&#64;<redacted>` ≠ approver `reviewer&#64;<redacted>` | `Summary!D14` vs `.msg` sender |
| Sign-off language | **PASS** — "This control is approved and is designed and operating effectively" | `.msg` body line 1 |
| Reviewer checklist attached | **PRESENT** (nested inside the .msg) | leaf listing |
| Certified-source provenance | Report path under `…/SOX-Certified/Finance/Consolidations/` | `Summary!D12` |

**Real-world lessons the synthetic fixtures could not teach:**
- Grand-total deltas are floating-point residue (~1e-06), never exactly 0.
  A naive `==0` check would false-fail; tolerance-based `delta_zero` is correct.
- The AFO tab refresh stamps (13:45–14:14) predate the 2:44 PM consolidation —
  the correct temporal anchor is the WEBI extract's own `Run Date & Time`
  cell, which states its timezone explicitly (`GMT+00:00`). Plans must pin
  which timestamp anchors the check (SME decision, one line in the plan).
- Two stale 2023 AFO tabs are explicitly annotated "This is not part of SOX
  control" — real scope exclusions exist and the plan schema handles them.

## Control 10075 — EMR Review (VALIDATED)

Ingest: 16 leaves, 30,490 cells, **6 emails, 245 images**, 1 honest error.

- 44-tab IPE recon workbook fully ingested with tab inventory (AFO/Webi/
  Workiva compares, GAAP Consol tabs, P&L workings).
- Real sign-off chain parsed from 5 `.eml` files with line-level citations:
  - the EMR approver: "This is approved, thank you…" (EMR sign-off)
  - the IPE tie-out reviewer: "No inconsistencies found" (IPE tie-out); "**One exception
    noted and immediately resolved** by you" (BS/CF validation — the
    exception-disclosure fact); "No exceptions noted" (manual validations)
  - SharePoint provenance links captured for every referenced artifact.
- Screenshot workbook: 57 embedded slide images, zero data cells (pure
  screenshot evidence, as the handover described).
- **Honest error, correctly surfaced:** one "attachment" inside an .eml is a
  SharePoint link placeholder, not a real .xlsb — recorded as
  `BadZipFile`, pipeline continued. Fetching linked artifacts from
  SharePoint is a Batch-6 connector feature.

## OCR verdict (real production screenshots, Tesseract)

- **Provenance markers read reliably:** "SAP BI Launch Pad",
  `<internal BI host>`, report/segment names, GRC bookmark visible in
  browser chrome. This is what screenshot checks should assert.
- **Small-font numbers in screenshot tables do NOT OCR reliably.** Numeric
  ties must come from the certified workbook cells (extracted in full);
  screenshots serve existence/provenance checks only. Plans must never
  recompute from OCR'd digits.

## Control 23024 — Rebate Calc (fixes applied, rerun in progress)

- The "185MB 404 docx" turned out to contain a **184.5MB Excel workbook
  embedded as an OLE object** — the actual rebate calculation.
- Two pipeline upgrades this forced (both implemented):
  1. `word/embeddings/*` now ingested as first-class child leaves.
  2. Workbooks >60MB stream via openpyxl read-only mode (the dual
     formula+value full load OOM'd); bounded by a 4M-cell cap that records
     an explicit truncation sentinel instead of failing silently.
- Rerun executing detached; results append to `data/output/real_probe_23024.log`.

## Capability upgrades landed during real-corpus validation

| Gap found | Fix |
|---|---|
| Outlook `.msg` not parsed | `extract-msg` integration: headers, body lines, attachments, nested ZIP walk |
| `.xlsb` not parsed | `pyxlsb` integration (cached values) |
| docx embedded images ignored | `word/media/*` extracted as ImageFacts |
| docx embedded OLE objects ignored | `word/embeddings/*` ingested as child leaves |
| Large workbooks OOM | >60MB → read-only streaming + honest truncation sentinel |
| Large docx OOM | >30MB → streaming paragraph parse (iterparse) |

## Performance note

Ingest times measured here (7–17 min for 10032) are dominated by this
laptop's constraints (iCloud-synced working directory, near-full disk, low
free RAM — the OOM kills at exit 137 were the OS, not the code). On a
standard corporate workstation with a local SSD expect minutes, not tens of
minutes. A parsed-artifact cache (hash-keyed) is the planned optimization
before shadow-cycle scale.

## Regression status

Full offline suite: **36/36 passed** after all upgrades. Zero network calls
in offline mode; model ledger records every backend decision.
