# IQR — User Acceptance Test Script

Run these in order from the console (`.venv/bin/python -m iqr.cli serve` →
http://127.0.0.1:8400). Each case states the exact steps and the expected
result. Total time: ~20 minutes.

## UAT-0 · Intake — bulk upload and the package's story
1. **New validation** tab → drag ALL files from
   `tests/fixtures/controls/C10032/package` into the drop zone (mixed formats:
   xlsx, eml, zip, docx) — or paste the folder path and click **Analyze folder**.
- **Expect:** artifact/cell/email counts and format chips; a grounded story
  naming the control and its checks; **C10032 suggested at 100% evidence**
  (other controls ranked below with coverage bars); missing evidence, if any,
  declared BEFORE the run. Confirm and click **Run validation · C10032**.

## UAT-1 · Run a clean control end to end
1. **New validation** tab → analyze `tests/fixtures/controls/C23024/package`
   (per UAT-0) → confirm **C23024** → **Run validation**.
2. Watch the **Live run** tab: ledger events stream (INGEST → MATCH →
   SENTINEL → CHECK → VERIFY → ADJUDICATE).
- **Expect:** verdict chip **pass**; three findings each with citations
  (e.g. `Sales!B7`, `email:...#L1`); "Download audit-ready pack" link works
  and the zip contains `verdict.json`, `checklist.md`, `citations.json`,
  `gaps_and_observations.md`, `artifact_manifest.json`, `plan.json`.

## UAT-2 · Honest gap — remove required evidence
1. Copy the C23024 package folder; delete the approval `.eml` from the copy.
2. Run C23024 against the copy.
- **Expect:** result **pass_with_gaps** (never pass); the sign-off check
  reports a gap naming the missing evidence. Nothing is invented.

## UAT-3 · Defect caught — tamper with a number
1. Copy the C23024 package; open the workbook and change one regional sales
   cell (e.g. add 1,000 to B2). Save.
2. Run against the copy.
- **Expect:** numeric check **fail** with the recomputed vs recorded values
  and the delta in the detail; citations point at the exact cells.

## UAT-4 · Temporal + timezone (the GMT/CDT case)
1. Run **C10032** against `tests/fixtures/controls/C10032/package`.
- **Expect:** pass; the temporal check's detail shows both UTC-normalized
  stamps and "correctly ordered".

## UAT-5 · Vision tie-out (OCR)
1. Run **C10075** against `tests/fixtures/controls/C10075/package`.
- **Expect:** pass; the vision check detail shows the screenshot value tying
  out to the workbook cell.

## UAT-6 · Live model attribution
1. With Azure configured (`IQR_MODEL=auto`), run any control; open the run in
   **Live run** and read the agent lines.
- **Expect:** `agent[foundry] concluded …` on judgment checks. Pull the
  network cable / break the key and rerun: `agent[stub]` — visible fallback,
  and the run still completes with honest results.

## UAT-7 · Evaluation gates
1. **Evaluation** tab → **Run evaluation**.
- **Expect:** all five gates PASS (defect recall, false exceptions, citation
  validity, abstention, reproducibility).

## UAT-8 · Batch scoring + confidence
1. **Evaluation** tab → **Batch ×3 with scoring**.
- **Expect:** per-gate mean/min/max plus a per-check confidence table with
  stability bars and HIGH/MEDIUM/LOW levels. (Under a live model, an
  occasional LOW simply routes more review attention — verify no false pass.)

## UAT-9 · HITL adjudication → reinforcement learning
1. **Governance** tab. Adjudicate an exception via API or console; include
   what IQR concluded:
   ```bash
   curl -X POST localhost:8400/api/exceptions/adjudicate \
     -H 'Content-Type: application/json' \
     -d '{"control_id":"C10032","check_id":"t1","pattern":"stamp equals approval minute","human_verdict":"pass","iqr_verdict":"pass","rationale":"simultaneous stamps acceptable","run_id":"uat"}'
   ```
2. Click **Run learning pass**.
- **Expect:** "Applied 1 new adjudication(s)"; the Earned-confidence table
  shows the check with confidence moved off 0.50 (up for agreement, down for
  override), observation count, and review priority. Re-clicking applies 0 —
  idempotent.

## UAT-10 · Citation gate (anti-hallucination)
1. `pytest tests/test_citation_gate.py -q`
- **Expect:** green — a fabricated locator is mechanically rejected before it
  can enter a verdict or pack.

## UAT-11 · Reproducibility
1. Run the same control twice; compare the two packs' `verdict.json`
   (ignoring run_id).
- **Expect:** identical verdicts, evidence sets, and computed values.

## UAT-12 · MCP surface
1. `IQR_MCP_TRANSPORT=stdio .venv/bin/python -m iqr.mcp_server` from an MCP
   client (or Claude), call `list_controls` then `run_control` on a fixture.
- **Expect:** typed verdict JSON with citations and a pack path; unapproved
  plans are refused.
