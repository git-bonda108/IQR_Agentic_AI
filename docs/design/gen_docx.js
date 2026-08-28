// IQR design document - HP-branded Word deliverable (docx-js).
// HP identity: Electric Blue + black typography + white space; Orange Bloom accent.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  ImageRun, LevelFormat, PageBreak, TableOfContents,
} = require("docx");

const BLUE = "0096D6", BLUE_DARK = "00537A", INK = "1A1A1A", GRAY = "6E6E73",
      TINT = "EAF6FC", ORANGE = "FF585D", LINE = "D6DEE4";
const A = path.join(__dirname, "assets");

const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const cellBorders = {
  top: { style: BorderStyle.SINGLE, size: 4, color: LINE },
  bottom: { style: BorderStyle.SINGLE, size: 4, color: LINE },
  left: { style: BorderStyle.SINGLE, size: 4, color: LINE },
  right: { style: BorderStyle.SINGLE, size: 4, color: LINE },
};

function h1(t) { return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 160 }, children: [new TextRun({ text: t, color: BLUE_DARK, bold: true })] }); }
function h2(t) { return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 120 }, children: [new TextRun({ text: t, color: INK, bold: true })] }); }
function p(t, opts = {}) {
  return new Paragraph({
    spacing: { after: 140, line: 300 },
    children: [new TextRun({ text: t, size: opts.size || 22, color: opts.color || INK, bold: !!opts.bold, italics: !!opts.italics })],
  });
}
function bullet(t, level = 0, bold = false) {
  return new Paragraph({
    numbering: { reference: "bul", level },
    spacing: { after: 80, line: 280 },
    children: [new TextRun({ text: t, size: 22, color: INK, bold })],
  });
}
function bulletRuns(runs, level = 0) {
  return new Paragraph({
    numbering: { reference: "bul", level },
    spacing: { after: 80, line: 280 },
    children: runs.map(r => new TextRun({ size: 22, color: INK, ...r })),
  });
}
function mono(t) {
  return new Paragraph({
    spacing: { after: 40 },
    shading: { type: ShadingType.CLEAR, fill: "F4F6F8" },
    children: [new TextRun({ text: t, font: "Courier New", size: 19, color: INK })],
  });
}
function img(file, w, h, capText) {
  const out = [new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 160, after: 60 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(A, file)), transformation: { width: w, height: h } })],
  })];
  if (capText) out.push(new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: capText, size: 18, color: GRAY, italics: true })],
  }));
  return out;
}
function table(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (cells, isHead) => new TableRow({
    children: cells.map((c, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      borders: cellBorders,
      shading: isHead ? { type: ShadingType.CLEAR, fill: TINT } : undefined,
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: c, size: 20, bold: isHead, color: isHead ? BLUE_DARK : INK })] })],
    })),
  });
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, rows: [mk(headers, true), ...rows.map(r => mk(r, false))] });
}

const kids = [];

// ---------------- cover ----------------
kids.push(new Paragraph({ spacing: { before: 1800 }, children: [] }));
kids.push(new Paragraph({
  border: { bottom: { style: BorderStyle.SINGLE, size: 48, color: BLUE, space: 8 } },
  spacing: { after: 300 },
  children: [new TextRun({ text: "IQR — Intelligent Quality Review", size: 64, bold: true, color: INK })],
}));
kids.push(p("Agentic AI validation of SOX 404 controls — a citation for every claim, a reproducible verdict for every run.", { size: 30, color: GRAY }));
kids.push(new Paragraph({ spacing: { before: 300 }, children: [new TextRun({ text: "DESIGN DOCUMENT", size: 24, bold: true, color: BLUE })] }));
kids.push(p("Version 1.0  ·  August 2026  ·  Controls & Compliance", { size: 22, color: GRAY }));
kids.push(p("Repository: https://github.com/git-bonda108/iqr-sox (private)", { size: 22, color: GRAY }));
kids.push(p("Brand: HP Electric Blue / black / white per HP Brand Central; HP Forma DJR substituted with Arial where unavailable.", { size: 18, color: GRAY, italics: true }));
kids.push(new Paragraph({ children: [new PageBreak()] }));

// ---------------- TOC ----------------
kids.push(h1("Contents"));
kids.push(new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }));
kids.push(new Paragraph({ children: [new PageBreak()] }));

// ---------------- 1 executive summary ----------------
kids.push(h1("1. Executive summary"));
kids.push(p("IQR validates a SOX 404 control end to end: the performer's GRC evidence package goes in; an audit-ready, fully cited validation pack comes out. The engine is built once and configured per control — a compiled, SME-approved Validation Plan decides what runs; a fixed LangGraph topology decides how it runs; tool-using agents supply judgment where evidence is messy; deterministic Python supplies every number."));
kids.push(p("Three invariants govern every design choice, and each is enforced by an automated test, not a convention:"));
kids.push(bullet("Numbers are computed by deterministic Python, never by a model (a test fails if a model is invoked on any numeric path).", 0, true));
kids.push(bullet("Every claim carries a citation that mechanically resolves against hashed evidence (the citation gate rejects anything else).", 0, true));
kids.push(bullet("Same input + same plan version ⇒ identical verdict (reproducibility is asserted across repeated runs).", 0, true));
kids.push(p("Status: v1 is implemented, green on 36 automated tests, and passing all five evaluation gates (100% defect recall, 0% false exceptions, 100% citation validity, 100% abstention correctness, 100% reproducibility) against three golden fixture controls with seeded defects. v1 ships in Shadow mode: it runs beside the human reviewer; nothing auto-submits."));

// ---------------- 2 problem ----------------
kids.push(h1("2. The problem"));
kids.push(p("One control is a tree of nested evidence. The 404 process document branches into Excel workpapers (multi-tab, live formulas), approval emails whose reply chains carry ZIP attachments, which in turn hold more workbooks and checklists, plus screenshots embedded inside workbook tabs, SharePoint links, and reviewer checklists — nesting three levels deep (email → ZIP → workbook → screenshot), nine or more artifacts per control, four different check modalities: recompute the numbers, read the screenshots, order the timestamps, verify the sign-offs."));
kids.push(p("Today a reviewer validates this by hand, artifact by artifact. It costs hours per control every period, scales only with headcount, produces tickmarks rather than citations, and fatigue drives the costliest failure: missed defects."));
kids.push(p("Why the obvious alternatives fail:", { bold: true }));
kids.push(bullet("RPA moves without understanding — a recorded script cannot judge an approval email or notice missing evidence; every layout change is an engineering ticket."));
kids.push(bullet("A lone model understands but loses the thread — one prompt cannot coherently hold 9+ artifacts; it hallucinates arithmetic, self-approves its own findings, and two runs give two answers. An auditor cannot accept either."));

// ---------------- 3 architecture ----------------
kids.push(h1("3. Architecture"));
kids.push(p("The decided architecture is a compiled-plan, deterministic-runtime LangGraph with tool-using agents inside nodes and a hard judgment/arithmetic split. Planning — the one genuinely non-deterministic activity — happens once, at design time, under human review. Runtime only executes."));
kids.push(...img("d1_layers.png", 620, 366, "Figure 1 — Three layers: deterministic ingestion, versioned knowledge, agentic reasoning."));
kids.push(h2("3.1 Layer responsibilities"));
kids.push(table(
  ["Layer", "Responsibility", "Key property"],
  [
    ["Ingestion", "Unpack the nested evidence tree, extract cells/text/images/emails, SHA-256 every leaf, build the addressable Evidence Graph", "Pure Python — zero model calls; content-addressed custody"],
    ["Knowledge", "Control KB (404s → compiled plans) and Golden Library (adjudicated exemplars), both vector-indexed", "Versioned; retrieval-anchored grounding — agents never free-associate"],
    ["Reasoning", "Match evidence, run the four check modalities, blinded verification, adjudication", "Agents judge within a check; tools do all extraction and computation"],
  ],
  [1500, 4800, 3060]));
kids.push(h2("3.2 The lifecycle: design once, run every period, learn governed"));
kids.push(...img("d2_lifecycle.png", 620, 384, "Figure 2 — Compiled-plan lifecycle. The SME approval gate separates judgment about WHAT to check from the mechanical HOW."));
kids.push(bulletRuns([{ text: "Design (once per control): ", bold: true }, { text: "a Plan Compiler agent reads the 404 document (grounded by Control-KB retrieval) and drafts a Validation Plan — expected evidence with match hints, ordered checks with types and tolerances, scope exclusions, sign-off rules. An SME reviews and approves; the plan freezes as versioned, immutable JSON. The runtime refuses unapproved plans." }]));
kids.push(bulletRuns([{ text: "Run (every period): ", bold: true }, { text: "the fixed graph executes the frozen plan. Agents have judgment within a check (what does this screenshot show? is this the right approval?) but never choose which checks run." }]));
kids.push(bulletRuns([{ text: "Learn (governed): ", bold: true }, { text: "verifier disagreements and human overrides land in the Golden Library only after the regression eval passes and an SME signs off — versioned, never silent." }]));

// ---------------- 4 orchestration ----------------
kids.push(h1("4. Agentic orchestration"));
kids.push(...img("d3_topology.png", 620, 310, "Figure 3 — The fixed LangGraph topology with parallel check fan-out, blinded verification, the citation gate, and the model fallback chain."));
kids.push(h2("4.1 The graph"));
kids.push(p("ingest → match → [one branch per plan check, in parallel] → verify → adjudicate. The topology is serialized and hashed (topology_signature()); every run ledger pins the hash, so an auditor can prove the control flow never drifted. State is typed (pydantic models flowing through LangGraph) — the Evidence Graph travels as structure, never as re-dumped prompt text, which is what prevents lost-in-the-middle failures."));
kids.push(h2("4.2 Agents and tools — the judgment/arithmetic split"));
kids.push(table(
  ["Check type", "Executor", "Tools used", "Model involvement"],
  [
    ["numeric", "Pure Python", "cell_read, recompute", "NONE — test-enforced"],
    ["vision", "Tool-using agent", "ocr_labeled_number (Tesseract), cell_read", "judges where the value is and what it means"],
    ["temporal", "Tool-using agent", "cell_read, email facts, timestamp_order (tz-normalize)", "judges which stamps matter; tools compute order"],
    ["signoff", "Tool-using agent", "email_parse, cell_read, timestamp tools", "judges validity of approval; SoD facts from tools"],
  ],
  [1300, 1900, 3400, 2760]));
kids.push(p("The agent loop is a strict protocol: the model may only respond with a tool call or a final conclusion; every number, timestamp and quotation in a finding is an echo of a tool result, and the runtime — not the model — accumulates the citations those tools return."));
kids.push(h2("4.3 Blinded verification"));
kids.push(p("The verifier's input type contains exactly three fields — the plan clause, the claimed verdict, and the citations. The executor's reasoning and detail text are structurally absent (enforced by the input schema and a test). The verifier re-performs the check from cited evidence alone: re-reads the cells, re-OCRs the screenshot region, re-parses the email, recomputes. Agreement lets the finding stand; disagreement routes it to the human exception queue and the run cannot report a clean pass."));
kids.push(h2("4.4 Model access and multi-mode fallback"));
kids.push(p("All model calls flow through one factory (iqr/config.py), temperature pinned to 0. In auto mode each completion tries DaVinci, then an optional secondary endpoint (same wire format), then the deterministic offline stub. Which backend answered is recorded per call in the run ledger — fallback is visible, never silent. If every backend fails, the run fails loudly."));

// ---------------- 5 workflow detail ----------------
kids.push(h1("5. The run, step by step"));
kids.push(table(
  ["#", "Node", "Input → Output", "What happens in detail"],
  [
    ["1", "ingest", "package folder → EvidenceGraph", "Recursive unpack (email → zip → workbook → image, 6-level safety bound); SHA-256 per leaf into a content-addressed immutable store; openpyxl extracts every non-empty cell (values and formulas), Tesseract-ready images registered, emails parsed to headers + body lines + attachment links; corrupt containers and unreadable workbooks are recorded in graph.errors — the leaf stays in custody, its facts are absent"],
    ["2", "match", "plan + graph → matches/missing", "Fuzzy name/path matching per expected-evidence hint; emails resolve to message-ids, screenshots to image hashes; required-but-absent evidence becomes an honest gap; artifacts that match a scope exclusion are never flagged"],
    ["3", "check ×N", "matches → Finding per check", "Dispatched by frozen check_type (table above); parallel where independent; a crashed check abstains as a gap and routes to the exception queue — it can never sink the run or fake a pass"],
    ["4", "verify", "findings → verified findings", "Blinded re-performance per finding; gap findings are re-checked against the match table (you cannot re-read absent evidence)"],
    ["5", "adjudicate", "findings → Verdict", "Mechanical citation gate (uncited or unresolvable ⇒ rejected into exceptions); aggregation: any fail ⇒ fail; gaps/exceptions ⇒ pass_with_gaps; else pass"],
    ["6", "pack", "Verdict → audit .zip", "verdict.json, auto-completed checklist.md, artifact_manifest.json (every leaf + hash), gaps_and_observations.md, citations.json, plan.json — assembly re-asserts the citation gate"],
  ],
  [500, 1250, 2050, 5560]));

// ---------------- 6 stack ----------------
kids.push(h1("6. Technical stack"));
kids.push(table(
  ["Concern", "Technology", "Why"],
  [
    ["Orchestration", "LangGraph (local)", "fixed, versioned, replayable topology — the audit artifact"],
    ["Agent runtime", "Tool-loop over the approved model (OpenAI Agents SDK-compatible)", "judgment constrained to tool calls + typed conclusions"],
    ["Model", "DaVinci API (primary) → secondary → offline stub", "one approved model; tools decompose what multiple models would"],
    ["Schemas/state", "pydantic v2", "typed plans, graph, findings; blindness enforced by input types"],
    ["Spreadsheets", "openpyxl", "cells, formulas, embedded images"],
    ["OCR", "Tesseract via pytesseract", "deterministic screenshot reads with regions"],
    ["Email", "Python stdlib email (+ extract-msg for .msg)", "headers, body lines, nested attachments"],
    ["Timestamps", "python-dateutil + tz maps", "GMT/CDT/etc. normalized to UTC before any comparison"],
    ["API / console", "FastAPI + single-page web console", "thin client; all logic server-side"],
    ["Storage", "content-addressed file stores + JSONL ledgers", "immutable, inspectable, portable"],
    ["Vector index", "local hashed bag-of-words store behind a VectorStore interface", "swap for the approved vendor without touching callers"],
    ["Tests/eval", "pytest, 36 tests + 5-gate eval harness", "the invariants are executable"],
  ],
  [1800, 3600, 3960]));

// ---------------- 7 storage ----------------
kids.push(h1("7. Storage & data design"));
kids.push(...img("d4_storage.png", 620, 329, "Figure 4 — Deployment and storage. Every store is a plain directory: inspectable, portable, auditable."));
kids.push(bullet("data/evidence_store/ — blobs named by their SHA-256. Same bytes ⇒ same name ⇒ writes are idempotent and tampering is self-evident."));
kids.push(bullet("data/plans/<control>/<version>.json — frozen plans. Freezing the same version twice is an error; changes require a new version and re-approval."));
kids.push(bullet("data/runs/<run_id>.jsonl — the replayable ledger: every node event, tool call (args + results), agent conclusion (with the backend that produced it), verification and adjudication. This is the platform's own ITGC evidence and the explainability trail."));
kids.push(bullet("data/packs/<run_id>.zip — the audit-ready deliverable."));
kids.push(bullet("data/knowledge/ — Control KB and Golden Library indexes plus the pending-overrides journal."));
kids.push(p("The data/ tree is gitignored: the repository carries code, fixtures and tests; runtime state stays local to the machine that produced it."));

// ---------------- 8 API ----------------
kids.push(h1("8. API & CLI reference"));
kids.push(h2("8.1 HTTP API (FastAPI, localhost:8400)"));
kids.push(table(
  ["Method & path", "Purpose"],
  [
    ["POST /api/plans/compile", "draft a Validation Plan from a 404 document (body: doc_path, control_id, frequency)"],
    ["POST /api/plans/{control_id}/approve", "SME approval — freezes the plan (body: sme)"],
    ["GET /api/plans/{control_id}", "latest approved plan"],
    ["POST /api/runs", "execute a control (body: control_id, package_ref, optional plan_version); returns run_id, verdict, pack path"],
    ["GET /api/runs/{run_id}/ledger", "the full replayable ledger"],
    ["GET /api/runs/{run_id}/pack", "download the audit-ready .zip"],
    ["GET /api/exceptions", "pending human adjudications"],
    ["POST /api/exceptions/adjudicate", "record a human adjudication into the Golden Library intake"],
    ["GET /api/topology", "the versioned topology signature (hash)"],
  ],
  [4200, 5160]));
kids.push(h2("8.2 CLI"));
kids.push(mono("python -m iqr.cli compile <404.docx> <control_id> <frequency>   # draft plan"));
kids.push(mono("python -m iqr.cli approve <control_id> <sme>                    # SME freeze"));
kids.push(mono("python -m iqr.cli run <control_id> <package_dir>                # validate + pack"));
kids.push(mono("python -m iqr.cli eval                                          # five gate metrics"));
kids.push(mono("python -m iqr.cli testmodel                                     # verify API keys / fallback chain"));
kids.push(mono("python -m iqr.cli explain <run_id>                              # replay the ledger (XAI)"));
kids.push(mono("python -m iqr.cli serve                                         # web console on :8400"));

// ---------------- 9 getting started ----------------
kids.push(h1("9. Getting started (clone → keys → validate)"));
kids.push(mono("git clone https://github.com/git-bonda108/iqr-sox.git IQR && cd IQR"));
kids.push(mono("python3 -m venv .venv && .venv/bin/pip install -e ."));
kids.push(mono("brew install tesseract        # macOS   (Windows: UB-Mannheim installer; Linux: apt/yum)"));
kids.push(mono("cp .env.example .env          # add DAVINCI_API_URL + DAVINCI_API_KEY; keep IQR_MODEL=auto"));
kids.push(mono(".venv/bin/python -m iqr.cli testmodel                       # which backend answers?"));
kids.push(mono(".venv/bin/python tests/fixtures/build_fixtures.py           # golden packs"));
kids.push(mono(".venv/bin/python -m pytest tests/ -q                        # 36-test regression"));
kids.push(mono(".venv/bin/python -m iqr.cli eval                            # all five gates must PASS"));
kids.push(mono(".venv/bin/python -m iqr.cli serve                           # console at http://localhost:8400"));
kids.push(p("Security: keys live only in .env, which is gitignored — never commit it. The stub fallback keeps the platform testable with no keys at all; the ledger shows which backend served every call.", { italics: true }));

// ---------------- 10 quality ----------------
kids.push(h1("10. Quality: invariants, evaluation, results"));
kids.push(h2("10.1 Seven hard invariants (each is a test)"));
kids.push(table(
  ["Invariant", "Enforced by"],
  [
    ["No model math on numeric paths", "model-call counter asserted unchanged"],
    ["Citation gate — uncited claims cannot ship", "fabricated locators rejected at adjudication AND pack assembly"],
    ["Reproducibility — identical verdict across runs", "verdict fingerprints compared over repeated runs"],
    ["Honest missing — absent evidence ⇒ gap, never pass", "sign-off removal variant"],
    ["Scope respected — excluded items never flagged", "IC-eliminations exclusion vs a stray artifact"],
    ["Blinded verify — reasoning cannot reach the critic", "verifier input schema has no such field; tamper test"],
    ["Chain of custody — stable hashes, custody in citations", "re-ingest hash equality"],
  ],
  [4700, 4660]));
kids.push(h2("10.2 Five-gate evaluation harness"));
kids.push(p("Three golden controls (quarterly rebate recompute; monthly consolidation reconciliation with GMT-vs-CDT ordering and email→ZIP→workbook nesting; quarterly EMR review with real-OCR screenshot tie-outs) run clean twice plus five seeded-defect variants: altered total, inverted timestamps, missing sign-off, preparer = reviewer, screenshot mismatch."));
kids.push(table(
  ["Gate metric", "Meaning", "v1 result"],
  [
    ["Defect recall", "share of planted defects caught (existential)", "100%"],
    ["False-exception rate", "clean checks wrongly flagged (reviewer trust)", "0%"],
    ["Citation validity", "claims whose citation resolves (hard gate)", "100%"],
    ["Abstention correctness", "absent evidence declared, never invented (honesty)", "100%"],
    ["Reproducibility", "identical verdict, same pack (consistency)", "100%"],
  ],
  [2400, 4800, 2160]));

// ---------------- 11 rollout ----------------
kids.push(h1("11. Rollout & roadmap"));
kids.push(bulletRuns([{ text: "Shadow (v1, now): ", bold: true }, { text: "the platform runs beside the human reviewer; results are compared; nothing auto-submits." }]));
kids.push(bulletRuns([{ text: "Assist: ", bold: true }, { text: "the platform drafts findings; the human decides each one. Gate: measured recall / precision / reproducibility on that control." }]));
kids.push(bulletRuns([{ text: "Primary: ", bold: true }, { text: "the platform decides; humans review exceptions and samples. Per-control gating — each control advances only as fast as its demonstrated accuracy." }]));
kids.push(p("Next steps: point the Plan Compiler at the real 404 documents and GRC packages to replace the synthesized fixtures; wire the approved vector-store vendor behind the existing interface; connect mailbox/SharePoint watchers behind the resolver interface; run one full Shadow cycle and let the eval gates decide graduation."));

// ---------------- build ----------------
const doc = new Document({
  styles: { default: { document: { run: { font: "Arial", size: 22, color: INK } } } },
  numbering: { config: [{ reference: "bul", levels: [
    { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 420, hanging: 210 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 840, hanging: 210 } } } },
  ] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1180, right: 1180 } } },
    children: kids,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = path.join(__dirname, "IQR_Design_Document.docx");
  fs.writeFileSync(out, buf);
  console.log("written", out, buf.length);
});
