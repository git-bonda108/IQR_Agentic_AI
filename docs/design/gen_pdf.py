"""IQR design document - HP-branded PDF deliverable (reportlab/platypus).
Mirrors IQR_Design_Document.docx content."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

HERE = Path(__file__).parent
A = HERE / "assets"

BLUE = colors.HexColor("#0096D6")
BLUE_DARK = colors.HexColor("#00537A")
INK = colors.HexColor("#1A1A1A")
GRAY = colors.HexColor("#6E6E73")
TINT = colors.HexColor("#EAF6FC")
LINE = colors.HexColor("#D6DEE4")
CODEBG = colors.HexColor("#F4F6F8")

S_TITLE = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=30, leading=36, textColor=INK, spaceAfter=10)
S_SUB = ParagraphStyle("sub", fontName="Helvetica", fontSize=14, leading=19, textColor=GRAY, spaceAfter=8)
S_H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=22, textColor=BLUE_DARK, spaceBefore=18, spaceAfter=8)
S_H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=INK, spaceBefore=12, spaceAfter=6)
S_P = ParagraphStyle("p", fontName="Helvetica", fontSize=10.5, leading=15.5, textColor=INK, spaceAfter=7)
S_B = ParagraphStyle("b", parent=S_P, leftIndent=16, bulletIndent=6, spaceAfter=4)
S_CAP = ParagraphStyle("cap", fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=GRAY, alignment=1, spaceAfter=12)
S_CODE = ParagraphStyle("code", fontName="Courier", fontSize=9, leading=13, textColor=INK, backColor=CODEBG, borderPadding=4, spaceAfter=3)
S_CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK)
S_CELLH = ParagraphStyle("cellh", fontName="Helvetica-Bold", fontSize=9, leading=12.5, textColor=BLUE_DARK)


def P(t, s=S_P):
    return Paragraph(t, s)


def B(t):
    return Paragraph(t, S_B, bulletText="•")


def code(t):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(t.replace(" ", "&nbsp;"), S_CODE)


def img(name, width):
    path = A / name
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    return Image(str(path), width=width, height=width * h / w)


def tbl(headers, rows, widths):
    data = [[Paragraph(h, S_CELLH) for h in headers]] + \
           [[Paragraph(c, S_CELL) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TINT),
        ("GRID", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    t.hAlign = "LEFT"
    return t


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BLUE)
    canvas.rect(0, LETTER[1] - 14, LETTER[0], 14, stroke=0, fill=1)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(0.75 * inch, 0.5 * inch, "IQR - Design Document · v1.0 · HP Controls & Compliance")
    canvas.drawRightString(LETTER[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


CW = LETTER[0] - 1.5 * inch  # content width

story = []

# cover
story.append(Spacer(1, 1.6 * inch))
story.append(P("IQR — Intelligent Quality Review", S_TITLE))
t = Table([[""]], colWidths=[CW], rowHeights=[4])
t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUE)]))
t.hAlign = "LEFT"
story.append(t)
story.append(Spacer(1, 14))
story.append(P("Agentic AI validation of SOX 404 controls — a citation for every claim, a reproducible verdict for every run.", S_SUB))
story.append(Spacer(1, 20))
story.append(P('<font color="#0096D6"><b>DESIGN DOCUMENT</b></font>', S_P))
story.append(P("Version 1.0 · August 2026 · Controls &amp; Compliance", ParagraphStyle("m", parent=S_P, textColor=GRAY)))
story.append(P("Repository: https://github.com/git-bonda108/iqr-sox (private)", ParagraphStyle("m2", parent=S_P, textColor=GRAY)))
story.append(P("Brand: HP Electric Blue / black / white per HP Brand Central; HP Forma DJR substituted with Helvetica/Arial.", ParagraphStyle("m3", parent=S_P, textColor=GRAY, fontSize=8.5)))
story.append(PageBreak())

# 1 exec summary
story.append(P("1. Executive summary", S_H1))
story.append(P("IQR validates a SOX 404 control end to end: the performer's GRC evidence package goes in; an audit-ready, fully cited validation pack comes out. The engine is built once and configured per control — a compiled, SME-approved Validation Plan decides what runs; a fixed LangGraph topology decides how it runs; tool-using agents supply judgment where evidence is messy; deterministic Python supplies every number."))
story.append(P("Three invariants govern every design choice, each enforced by an automated test:"))
story.append(B("<b>Numbers are computed by deterministic Python, never by a model</b> (a test fails if a model is invoked on any numeric path)."))
story.append(B("<b>Every claim carries a citation that mechanically resolves against hashed evidence</b> (the citation gate rejects anything else)."))
story.append(B("<b>Same input + same plan version ⇒ identical verdict</b> (asserted across repeated runs)."))
story.append(P("Status: v1 is implemented, green on 36 automated tests, and passing all five evaluation gates (100% defect recall, 0% false exceptions, 100% citation validity, 100% abstention correctness, 100% reproducibility) against three golden fixture controls with seeded defects. v1 ships in Shadow mode: it runs beside the human reviewer; nothing auto-submits."))

# 2 problem
story.append(P("2. The problem", S_H1))
story.append(P("One control is a tree of nested evidence. The 404 process document branches into Excel workpapers (multi-tab, live formulas), approval emails whose reply chains carry ZIP attachments holding more workbooks and checklists, screenshots embedded inside workbook tabs, SharePoint links, and reviewer checklists — nesting three levels deep (email → ZIP → workbook → screenshot), nine or more artifacts per control, and four check modalities: recompute the numbers, read the screenshots, order the timestamps, verify the sign-offs."))
story.append(P("Today a reviewer validates this by hand. It costs hours per control every period, scales only with headcount, produces tickmarks rather than citations, and fatigue drives the costliest failure: missed defects."))
story.append(B("<b>RPA moves without understanding</b> — a recorded script cannot judge an approval email or notice missing evidence; every layout change is an engineering ticket."))
story.append(B("<b>A lone model understands but loses the thread</b> — one prompt cannot coherently hold 9+ artifacts; it hallucinates arithmetic, self-approves its own findings, and two runs give two answers."))

# 3 architecture
story.append(P("3. Architecture", S_H1))
story.append(P("The decided architecture is a <b>compiled-plan, deterministic-runtime LangGraph</b> with tool-using agents inside nodes and a hard judgment/arithmetic split. Planning — the one genuinely non-deterministic activity — happens once, at design time, under human review. Runtime only executes."))
story.append(img("d1_layers.png", CW))
story.append(P("Figure 1 — Three layers: deterministic ingestion, versioned knowledge, agentic reasoning.", S_CAP))
story.append(P("3.1 Layer responsibilities", S_H2))
story.append(tbl(["Layer", "Responsibility", "Key property"], [
    ["Ingestion", "Unpack the nested tree, extract cells/text/images/emails, SHA-256 every leaf, build the addressable Evidence Graph", "Pure Python — zero model calls; content-addressed custody"],
    ["Knowledge", "Control KB (404s → compiled plans) and Golden Library (adjudicated exemplars), vector-indexed", "Versioned; retrieval-anchored grounding"],
    ["Reasoning", "Match evidence, run four check modalities, blinded verification, adjudication", "Agents judge within a check; tools do all extraction and computation"],
], [0.9 * inch, 3.4 * inch, 2.2 * inch]))
story.append(P("3.2 The lifecycle: design once, run every period, learn governed", S_H2))
story.append(img("d2_lifecycle.png", CW))
story.append(P("Figure 2 — Compiled-plan lifecycle. The SME approval gate separates judgment about WHAT to check from the mechanical HOW.", S_CAP))
story.append(B("<b>Design (once per control):</b> a Plan Compiler agent reads the 404 document (grounded by Control-KB retrieval) and drafts a Validation Plan — expected evidence with match hints, ordered checks with types and tolerances, scope exclusions, sign-off rules. An SME approves; the plan freezes as versioned, immutable JSON. The runtime refuses unapproved plans."))
story.append(B("<b>Run (every period):</b> the fixed graph executes the frozen plan. Agents have judgment within a check but never choose which checks run."))
story.append(B("<b>Learn (governed):</b> verifier disagreements and human overrides enter the Golden Library only after the regression eval passes and an SME signs off — versioned, never silent."))
story.append(PageBreak())

# 4 orchestration
story.append(P("4. Agentic orchestration", S_H1))
story.append(img("d3_topology.png", CW))
story.append(P("Figure 3 — The fixed LangGraph topology with parallel check fan-out, blinded verification, the citation gate, and the model fallback chain.", S_CAP))
story.append(P("4.1 The graph", S_H2))
story.append(P("ingest → match → [one branch per plan check, in parallel] → verify → adjudicate. The topology is serialized and hashed (topology_signature()); every run ledger pins the hash, so an auditor can prove the control flow never drifted. State is typed (pydantic models flowing through LangGraph) — the Evidence Graph travels as structure, never re-dumped prompt text, which is what prevents lost-in-the-middle failures."))
story.append(P("4.2 Agents and tools — the judgment/arithmetic split", S_H2))
story.append(tbl(["Check type", "Executor", "Tools used", "Model involvement"], [
    ["numeric", "Pure Python", "cell_read, recompute", "NONE — test-enforced"],
    ["vision", "Tool-using agent", "ocr_labeled_number (Tesseract), cell_read", "judges where the value is and what it means"],
    ["temporal", "Tool-using agent", "cell_read, email facts, timestamp_order", "judges which stamps matter; tools compute order"],
    ["signoff", "Tool-using agent", "email_parse, cell_read, timestamp tools", "judges validity of approval; SoD facts from tools"],
], [0.8 * inch, 1.2 * inch, 2.4 * inch, 2.1 * inch]))
story.append(P("The agent loop is a strict protocol: the model may only respond with a tool call or a final conclusion; every number, timestamp and quotation in a finding is an echo of a tool result, and the runtime — not the model — accumulates the citations those tools return."))
story.append(P("4.3 Blinded verification", S_H2))
story.append(P("The verifier's input type contains exactly three fields — the plan clause, the claimed verdict, and the citations. The executor's reasoning is structurally absent (enforced by the input schema and a test). The verifier re-performs the check from cited evidence alone. Agreement lets the finding stand; disagreement routes it to the human exception queue and the run cannot report a clean pass."))
story.append(P("4.4 Model access and multi-mode fallback", S_H2))
story.append(P("All model calls flow through one factory (iqr/config.py), temperature pinned to 0. In <b>auto</b> mode each completion tries DaVinci, then an optional secondary endpoint (same wire format), then the deterministic offline stub. Which backend answered is recorded per call in the run ledger — fallback is visible, never silent. If every backend fails, the run fails loudly."))

# 5 run step by step
story.append(P("5. The run, step by step", S_H1))
story.append(tbl(["#", "Node", "Input → Output", "Detail"], [
    ["1", "ingest", "package folder → EvidenceGraph", "Recursive unpack (email → zip → workbook → image); SHA-256 per leaf into a content-addressed immutable store; cells (values + formulas), images, emails extracted; corrupt containers and unreadable workbooks recorded in graph.errors — the leaf stays in custody, its facts are absent"],
    ["2", "match", "plan + graph → matches / missing", "Fuzzy name/path matching per hint; emails resolve to message-ids, screenshots to image hashes; required-but-absent evidence becomes an honest gap; scope-excluded artifacts are never flagged"],
    ["3", "check ×N", "matches → Finding per check", "Dispatched by frozen check_type; parallel where independent; a crashed check abstains as a gap and routes to the exception queue — it can never sink the run or fake a pass"],
    ["4", "verify", "findings → verified findings", "Blinded re-performance per finding; gap findings re-checked against the match table (you cannot re-read absent evidence)"],
    ["5", "adjudicate", "findings → Verdict", "Mechanical citation gate (uncited ⇒ rejected into exceptions); any fail ⇒ fail; gaps/exceptions ⇒ pass_with_gaps; else pass"],
    ["6", "pack", "Verdict → audit .zip", "verdict.json, auto-completed checklist.md, artifact_manifest.json (every leaf + hash), gaps_and_observations.md, citations.json, plan.json — assembly re-asserts the citation gate"],
], [0.35 * inch, 0.75 * inch, 1.7 * inch, 3.7 * inch]))
story.append(PageBreak())

# 6 stack
story.append(P("6. Technical stack", S_H1))
story.append(tbl(["Concern", "Technology", "Why"], [
    ["Orchestration", "LangGraph (local)", "fixed, versioned, replayable topology — the audit artifact"],
    ["Agent runtime", "Tool-loop over the approved model (Agents SDK-compatible)", "judgment constrained to tool calls + typed conclusions"],
    ["Model", "DaVinci API → secondary → offline stub", "one approved model; tools decompose the work"],
    ["Schemas / state", "pydantic v2", "typed plans, graph, findings; blindness enforced by types"],
    ["Spreadsheets", "openpyxl", "cells, formulas, embedded images"],
    ["OCR", "Tesseract via pytesseract", "deterministic screenshot reads with regions"],
    ["Email", "Python stdlib email (+ extract-msg)", "headers, body lines, nested attachments"],
    ["Timestamps", "python-dateutil + tz maps", "GMT/CDT/etc. normalized to UTC before comparison"],
    ["API / console", "FastAPI + single-page console", "thin client; all logic server-side"],
    ["Storage", "content-addressed stores + JSONL ledgers", "immutable, inspectable, portable"],
    ["Vector index", "local store behind a VectorStore interface", "swap in the approved vendor without touching callers"],
    ["Tests / eval", "pytest — 36 tests + 5-gate harness", "the invariants are executable"],
], [1.15 * inch, 2.55 * inch, 2.8 * inch]))

# 7 storage
story.append(P("7. Storage &amp; data design", S_H1))
story.append(img("d4_storage.png", CW))
story.append(P("Figure 4 — Deployment and storage. Every store is a plain directory: inspectable, portable, auditable.", S_CAP))
story.append(B("<b>data/evidence_store/</b> — blobs named by SHA-256. Same bytes ⇒ same name ⇒ idempotent writes; tampering is self-evident."))
story.append(B("<b>data/plans/&lt;control&gt;/&lt;version&gt;.json</b> — frozen plans; re-freezing a version is an error; changes require a new version and re-approval."))
story.append(B("<b>data/runs/&lt;run_id&gt;.jsonl</b> — the replayable ledger: every node event, tool call, agent conclusion (with serving backend), verification, adjudication. The platform's own ITGC evidence and its explainability trail."))
story.append(B("<b>data/packs/&lt;run_id&gt;.zip</b> — the audit-ready deliverable."))
story.append(B("<b>data/knowledge/</b> — Control KB + Golden Library indexes and the pending-overrides journal."))
story.append(P("The data/ tree is gitignored: the repository carries code, fixtures and tests; runtime state stays local."))

# 8 API
story.append(P("8. API &amp; CLI reference", S_H1))
story.append(P("8.1 HTTP API (FastAPI, localhost:8400)", S_H2))
story.append(tbl(["Method &amp; path", "Purpose"], [
    ["POST /api/plans/compile", "draft a Validation Plan from a 404 document (doc_path, control_id, frequency)"],
    ["POST /api/plans/{id}/approve", "SME approval — freezes the plan"],
    ["GET /api/plans/{id}", "latest approved plan"],
    ["POST /api/runs", "execute a control (control_id, package_ref); returns run_id, verdict, pack path"],
    ["GET /api/runs/{run_id}/ledger", "the full replayable ledger"],
    ["GET /api/runs/{run_id}/pack", "download the audit-ready .zip"],
    ["GET /api/exceptions", "pending human adjudications"],
    ["POST /api/exceptions/adjudicate", "record a human adjudication (Golden Library intake)"],
    ["GET /api/topology", "the versioned topology signature (hash)"],
], [2.6 * inch, 3.9 * inch]))
story.append(P("8.2 CLI", S_H2))
for c in ["python -m iqr.cli compile <404.docx> <control_id> <frequency>",
          "python -m iqr.cli approve <control_id> <sme>",
          "python -m iqr.cli run <control_id> <package_dir>",
          "python -m iqr.cli eval          # five gate metrics",
          "python -m iqr.cli testmodel     # verify API keys / fallback chain",
          "python -m iqr.cli explain <run_id>   # replay the ledger (XAI)",
          "python -m iqr.cli serve         # web console on :8400"]:
    story.append(code(c))
story.append(PageBreak())

# 9 getting started
story.append(P("9. Getting started (clone → keys → validate)", S_H1))
for c in ["git clone https://github.com/git-bonda108/iqr-sox.git IQR && cd IQR",
          "python3 -m venv .venv && .venv/bin/pip install -e .",
          "brew install tesseract   # macOS (Windows: UB-Mannheim installer; Linux: apt/yum)",
          "cp .env.example .env     # add DAVINCI_API_URL + DAVINCI_API_KEY; keep IQR_MODEL=auto",
          ".venv/bin/python -m iqr.cli testmodel",
          ".venv/bin/python tests/fixtures/build_fixtures.py",
          ".venv/bin/python -m pytest tests/ -q",
          ".venv/bin/python -m iqr.cli eval",
          ".venv/bin/python -m iqr.cli serve"]:
    story.append(code(c))
story.append(P("<i>Security: keys live only in .env, which is gitignored — never commit it. The stub fallback keeps the platform testable with no keys; the ledger shows which backend served every call.</i>"))

# 10 quality
story.append(P("10. Quality: invariants, evaluation, results", S_H1))
story.append(P("10.1 Seven hard invariants (each is a test)", S_H2))
story.append(tbl(["Invariant", "Enforced by"], [
    ["No model math on numeric paths", "model-call counter asserted unchanged"],
    ["Citation gate — uncited claims cannot ship", "fabricated locators rejected at adjudication AND pack assembly"],
    ["Reproducibility — identical verdict across runs", "verdict fingerprints compared over repeated runs"],
    ["Honest missing — absent evidence ⇒ gap, never pass", "sign-off removal variant"],
    ["Scope respected — excluded items never flagged", "IC-eliminations exclusion vs a stray artifact"],
    ["Blinded verify — reasoning cannot reach the critic", "verifier input schema has no such field; tamper test"],
    ["Chain of custody — stable hashes in citations", "re-ingest hash equality"],
], [3.25 * inch, 3.25 * inch]))
story.append(P("10.2 Five-gate evaluation harness", S_H2))
story.append(P("Three golden controls (quarterly rebate recompute; monthly consolidation reconciliation with GMT-vs-CDT ordering and email→ZIP→workbook nesting; quarterly EMR review with real-OCR screenshot tie-outs) run clean twice plus five seeded-defect variants: altered total, inverted timestamps, missing sign-off, preparer = reviewer, screenshot mismatch."))
story.append(tbl(["Gate metric", "Meaning", "v1 result"], [
    ["Defect recall", "share of planted defects caught (existential)", "100%"],
    ["False-exception rate", "clean checks wrongly flagged (reviewer trust)", "0%"],
    ["Citation validity", "claims whose citation resolves (hard gate)", "100%"],
    ["Abstention correctness", "absent evidence declared, never invented (honesty)", "100%"],
    ["Reproducibility", "identical verdict for the same pack (consistency)", "100%"],
], [1.5 * inch, 3.6 * inch, 1.4 * inch]))

# 11 rollout
story.append(P("11. Rollout &amp; roadmap", S_H1))
story.append(B("<b>Shadow (v1, now):</b> runs beside the human reviewer; results compared; nothing auto-submits."))
story.append(B("<b>Assist:</b> drafts findings; the human decides each one. Gate: measured recall / precision / reproducibility per control."))
story.append(B("<b>Primary:</b> the platform decides; humans review exceptions and samples. Per-control gating — each control advances only as fast as its demonstrated accuracy."))
story.append(P("Next steps: point the Plan Compiler at the real 404 documents and GRC packages; wire the approved vector-store vendor behind the existing interface; connect mailbox/SharePoint watchers behind the resolver interface; run one full Shadow cycle and let the eval gates decide graduation."))

doc = SimpleDocTemplate(str(HERE / "IQR_Design_Document.pdf"), pagesize=LETTER,
                        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
                        title="IQR - Design Document",
                        author="HP Controls & Compliance")
doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
print("written", HERE / "IQR_Design_Document.pdf")
