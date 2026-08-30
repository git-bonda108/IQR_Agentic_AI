/* Generate IQR_Design_Document_v4.docx + IQR_UAT_Guide.docx (Arial, HP blue). */
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow,
  TableCell, WidthType, AlignmentType, BorderStyle, LevelFormat, TableOfContents,
  ShadingType, PageBreak,
} = require("docx");

const BLUE = "0096D6", DARK = "00699B", INK = "101820", GREY = "5A6570";
const LETTER = { size: { width: 12240, height: 15840 },
                 margin: { top: 1160, bottom: 1160, left: 1300, right: 1300 } };

const styles = {
  default: { document: { run: { font: "Arial", size: 21, color: INK } } },
  paragraphStyles: [
    { id: "Title", name: "Title", basedOn: "Normal",
      run: { font: "Arial", size: 52, bold: true, color: INK },
      paragraph: { spacing: { after: 120 } } },
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal",
      quickFormat: true, run: { font: "Arial", size: 30, bold: true, color: DARK },
      paragraph: { spacing: { before: 360, after: 140 } } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal",
      quickFormat: true, run: { font: "Arial", size: 24, bold: true, color: INK },
      paragraph: { spacing: { before: 260, after: 100 } } },
    { id: "Subtle", name: "Subtle", basedOn: "Normal",
      run: { font: "Arial", size: 19, color: GREY, italics: true } },
  ],
};

const numbering = {
  config: [
    { reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "–",
                 style: { paragraph: { indent: { left: 460, hanging: 230 } } } }] },
    { reference: "steps",
      levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
                 style: { paragraph: { indent: { left: 460, hanging: 300 } } } }] },
  ],
};

const p = (text, opts = {}) => new Paragraph({
  children: [new TextRun({ text, ...opts.run })],
  spacing: { after: 110 }, ...opts.para });
const bullet = (text) => new Paragraph({
  children: [new TextRun(text)], numbering: { reference: "bullets", level: 0 },
  spacing: { after: 70 } });
const step = (text, restart) => new Paragraph({
  children: [new TextRun(text)], numbering: { reference: restart, level: 0 },
  spacing: { after: 70 } });
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const law = (t) => new Paragraph({
  children: [new TextRun({ text: t, bold: true })],
  shading: { type: ShadingType.CLEAR, fill: "E6F4FA" },
  border: { left: { style: BorderStyle.SINGLE, size: 24, color: BLUE } },
  spacing: { after: 120 }, indent: { left: 200, right: 200 } });

function table(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (text, bold, fill) => new TableCell({
    width: { size: widths[0], type: WidthType.DXA },
    shading: fill ? { type: ShadingType.CLEAR, fill } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [
      new TextRun({ text, bold: !!bold, size: 18, color: bold ? DARK : INK })] })] });
  const mk = (cells, bold, fill) => new TableRow({
    children: cells.map((t, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      shading: fill ? { type: ShadingType.CLEAR, fill } : undefined,
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
      children: [new Paragraph({ children: [
        new TextRun({ text: t, bold: !!bold, size: 18, color: bold ? DARK : INK })] })] })) });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [mk(headers, true, "F0F6FA"), ...rows.map(r => mk(r))] });
}

/* ------------------------------------------------ design document */
const dd = [];
dd.push(new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun("IQR — Intelligent Quality Review")] }));
dd.push(p("Design Document · v4 · Cloud-Native Agentic Architecture on Azure AI Foundry", { run: { color: BLUE, bold: true } }));
dd.push(new Paragraph({ style: "Subtle", children: [new TextRun(
  "An agentic AI platform that validates internal-control evidence packages end to end and emits a cited, audit-ready pack. " +
  "Agents reason; deterministic tools compute; a frozen, expert-approved plan governs every run; humans hold both gates. " +
  "Organization-agnostic: applies to any controls program (SOX 404 or equivalent).")] }));
dd.push(new Paragraph({ children: [], spacing: { after: 200 } }));
dd.push(new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-1" }));
dd.push(new Paragraph({ children: [new PageBreak()] }));

dd.push(h1("1. The three laws"));
dd.push(p("Every design decision descends from three laws. When a choice conflicts with one, the choice loses."));
dd.push(law("1 · Numbers are computed by deterministic code, never by a model. A test fails if a model is invoked on any numeric path."));
dd.push(law("2 · Every claim carries a resolvable evidence locator. The citation gate mechanically rejects anything else — 100% citation validity is a hard release gate."));
dd.push(law("3 · Same input produces the same verdict. Same package + same plan version yields an identical verdict and evidence set, replayable from the ledger."));

dd.push(h1("2. What it validates"));
dd.push(p("Input — the evidence package: a nested tree three to six levels deep: a control process document (.docx), workbooks (.xlsx/.xlsm/.xlsb), approval emails (.msg/.eml) whose attachments hold ZIPs with further workbooks and reviewer checklists, screenshots inside workbook tabs and documents, workbooks embedded as OLE objects (observed at 184 MB), and document-management links standing in for files."));
dd.push(p("Output — the audit-ready pack: a verdict per check (pass / pass-with-gaps / fail), the auto-completed reviewer checklist, an artifact manifest with the hash of every leaf, an explicit gaps-and-observations register, and a citation for every claim — down to the exact cell, email line, or screenshot region."));
dd.push(h2("The four check modalities"));
dd.push(table(["Modality", "What it asserts", "Example from the validated corpus"],
  [["Numeric recompute", "Totals/deltas/products re-derived from cells vs a tolerance", "TB deltas net to zero (~1e-06 floating-point residue; tolerance-based, never ==0)"],
   ["Temporal ordering", "Timestamps normalized across timezones, then ordered", "Certified run (in-cell GMT stamp) precedes approval (CDT email header); the plan pins the anchor stamp"],
   ["Vision tie-out", "Screenshot provenance; labeled values tie to cells", "BI-portal screenshots prove the certified source; numeric ties come from cells, never OCR digits"],
   ["Sign-off / SoD", "Approval language; approver ≠ preparer; correct ordering", "Six-email chain parsed with line citations, incl. an exception disclosure"]],
  [1700, 3600, 4340]));

dd.push(h1("3. The layers"));
dd.push(table(["Layer", "Responsibility", "Key property"],
  [["Document intelligence", "Unpack the tree; extract every cell/paragraph/email line/image; SHA-256 every leaf; build the Evidence Graph", "Pure code, zero model calls; every failure recorded, nothing silently skipped"],
   ["Knowledge (Foundry IQ)", "Control KB + Golden Library, retrieval-indexed on Azure AI Search", "Versioned; retrieval-anchored grounding — agents never free-associate"],
   ["Reasoning", "Scoped agents: intake, checks, blinded verification, plan compilation", "Each agent sees only its inputs, calls only its listed tools; every step in the ledger"],
   ["Action (tools)", "Deterministic extraction and computation returning value + citation", "The only source of facts an agent may state"],
   ["Governance", "Frozen plans, citation gate, run ledger, eval harness, HITL queue, governed learning", "Humans own both gates; nothing learns silently"]],
  [2100, 4100, 3440]));

dd.push(h1("4. Intake first — start from the evidence, not a dropdown"));
dd.push(p("A performer bulk-uploads whatever the period produced — any mix, any nesting. Before anything runs, IQR:"));
dd.push(step("Ingests deterministically: hash, extract, address every fact (the same machinery as the run).", "steps"));
dd.push(step("Infers the control mechanically: every frozen plan version is scored by required-evidence coverage. Matching is two-pass: exact name matching first, then SEMANTIC matching by an embedding seat — each artifact's content signals (path, kind, sheet names, email subject and opening lines, document paragraphs) embedded against each plan item's meaning, constrained by the artifact kind the reading checks demand (a sign-off check needs an email; a numeric check needs a workbook), assigned globally best-pair-first. Every match records its method, score, and embedding backend in the ledger. The embedding seat degrades visibly to a deterministic offline vectorizer.", "steps"));
dd.push(step("Narrates the package's story: what this appears to be, what will be validated, what is already missing — every fact from the graph and the plan; the model only phrases it.", "steps"));
dd.push(p("A human confirms the inferred control before the run. Inference ranks; people decide; the frozen plan remains the law."));

dd.push(h1("5. The run, stage by stage"));
dd.push(p("ingest → match → sentinel → check ×N (parallel) → verify → adjudicate → pack. The topology is fixed and versioned (SHA-256 signature recorded in every ledger). State flows as typed structures — the Evidence Graph travels as a graph, never re-dumped prompt text — which both maintains context across the run and enforces the verifier's blindness."));

dd.push(h1("6. Agent roster"));
dd.push(table(["Agent", "Invoked", "Reasons about", "Tools", "Emits"],
  [["Plan Compiler", "Design time, per control", "What the control document requires", "doc readers, KB retrieval", "Draft plan → SME review"],
   ["Intake", "Per upload", "The package's story from mechanical facts", "none (facts arrive pre-computed)", "Narrative + caveats"],
   ["Temporal", "Per temporal check", "Which stamps matter; ordering is computed", "cell_read, email facts, timestamp_order", "Finding + citations"],
   ["Sign-off / SoD", "Per sign-off check", "Validity of approval language", "email facts, cell_read", "Finding + citations"],
   ["Vision", "Per vision check", "Which screenshot; where the value sits", "ocr_labeled_number, cell_read", "Finding + citations"],
   ["Blinded Verifier", "Per finding", "Does the verdict re-derive from citations alone (input type excludes executor reasoning)", "same tools, re-performing", "agree / disagree → queue"]],
  [1500, 1500, 2900, 2100, 1640]));
dd.push(p("The Anomaly Sentinel is deliberately not an agent: six deterministic detectors (recycled artifacts, placeholders, pasted constants, tolerance-edge deltas, duplicate bytes, single-actor sign-off), every anomaly cited."));
dd.push(h2("Protocol hardenings (each earned from an observed live-model failure)"));
dd.push(bullet("Every tool is presented with its exact argument signature derived from code — a model never guesses a parameter name."));
dd.push(bullet("A deterministic loop-breaker refuses to re-execute an identical successful call and instructs the model to conclude."));
dd.push(bullet("Plan-pinned lookups are prefetched deterministically and seeded into observations — where a locator leaves nothing to decide, no model decides it."));
dd.push(h2("Per-seat model routing"));
dd.push(p("Each seat can run a different approved model (economical model for checks, reasoning model for the Verifier, routing meta-model for plan compilation). Graduation for a newly approved model: deployment added → one seat routed → five eval gates green → assignment ships. The ledger attributes every call to its backend. In validation, a two-model configuration passed every gate with 100% verdict stability across batch repeats."));

dd.push(h1("7. Tool catalog — the only source of facts"));
dd.push(table(["Tool", "Contract", "Returns"],
  [["cell_read / range_read", "graph, file hash, sheet, cell(s)", "value(s) + cell citation; missing is a loud error"],
   ["recompute", "op (sum/product/delta-zero/equals), sources, target, tolerance", "ok / computed / delta — pure arithmetic"],
   ["timestamp_order", "two raw stamps + plan-pinned timezones", "UTC-normalized datetimes + ordering"],
   ["email_signoff_facts", "graph, message id", "sender, UTC date, approval line — line-cited"],
   ["ocr_labeled_number / ocr_read", "graph, image hash (+ label)", "OCR text / labeled value + image citation"],
   ["citation.resolve", "citation, graph", "true only if the locator dereferences — the gate"]],
  [2300, 3700, 3640]));

dd.push(h1("8. Human in the loop — two gates, both human-owned"));
dd.push(p("Design gate: the Plan Compiler drafts; an expert pins tolerances, timezones and scope, and freezes the plan as versioned immutable JSON. The runtime refuses unapproved plans."));
dd.push(p("Run gate: sentinel HIGH anomalies, verifier disagreements, and gaps converge on the exception queue; a reviewer adjudicates each with full cited context. In Shadow mode nothing auto-submits; final package approval is always a human signature. Graduation Shadow → Assist → Primary is per control, earned in measured recall, false-exception rate and reproducibility."));

dd.push(h1("9. Continuous learning — reinforcement without gradients"));
dd.push(p("Reinforcement learning IS in the loop — the bandit family, not the gradient family. Every adjudication is a reward (agreement = 1, override = 0) updating a Beta-Bernoulli posterior per (control, check): transparent agree/override counts anyone can read, version, and revoke. The posterior drives confidence and review priority (most-uncertain first) and the evidence for Assist/Primary graduation — never verdicts. Learning passes are offline and idempotent; state lives beside the Golden Library."));
dd.push(p("Why not fine-tuning/gradient RL: a controls program produces orders of magnitude fewer reward events than gradient methods need, and each expert adjudication is too precious to dissolve into an opaque weight update. Golden Library exemplars enter the runtime path only through the eval gates plus SME sign-off — the system is permanently tested against its own history, so quality compounds and cannot silently drift."));

dd.push(h1("10. Evaluation harness — five gates, batch-scored"));
dd.push(table(["Gate", "Meaning", "Bar"],
  [["Defect recall", "Seeded defects caught (altered totals, inverted timestamps, missing sign-off, preparer=reviewer, screenshot mismatch)", "100% of seeded classes"],
   ["False-exception rate", "Clean checks wrongly flagged", "Bounded, tracked"],
   ["Citation validity", "Every claim's locator resolves", "100% — hard gate"],
   ["Abstention correctness", "Missing evidence declared, never invented", "100%"],
   ["Reproducibility", "Identical verdict + evidence set across repeats", "Exact"]],
  [2100, 5100, 2440]));
dd.push(p("Batch mode repeats the harness N times, scores each gate (mean/min/max) and assigns each check a confidence level (HIGH/MEDIUM/LOW) from verdict stability — measured frequency, never model self-report. In validation, batch scoring isolated a single unstable check, the trace named the exact cause, and after the fix every gate passed on every run with every check at 100% stability on a live two-model configuration."));

dd.push(h1("11. Cloud mapping — Azure AI Foundry"));
dd.push(table(["Concern", "Service", "Role"],
  [["Model seats", "Foundry project, multiple deployments", "Per-seat routing; temperature 0 + pinned seed where permitted; offline stub as terminal fallback"],
   ["Embedding seat", "Foundry embedding deployment (text-embedding-3-small)", "Semantic artifact-to-evidence matching; deterministic hashed vectorizer as offline fallback"],
   ["Knowledge retrieval", "Foundry IQ over an AI Search index", "Control KB + Golden Library grounding; degrades visibly to a local mirror"],
   ["Evidence & ledgers", "Blob Storage (immutability-ready)", "Content-addressed custody; append-only replayable ledgers; packs; frozen plans"],
   ["Run index & HITL queue", "Table Storage", "Cheap queryable rows"],
   ["Agent interoperability", "MCP server (stdio / HTTP)", "Foundry agents or any MCP client drive IQR as typed tools without bypassing invariants"],
   ["Reviewer console", "App Service (free tier) + Easy Auth", "Intake, live ledger, batch evals, adjudication, learning pass, pack download; anonymous rejected"],
   ["Analytics (deferred)", "Fabric semantic layer via OneLake shortcuts", "Cross-period trend intelligence; pausable to zero cost"]],
  [2100, 2800, 4740]));

dd.push(h1("12. Productionization — from git clone to governed deployment"));
dd.push(p("The repository is the deployable unit: clone, create a virtual environment, install, run the offline suite (green with no keys), configure endpoints, serve. Full step-by-step: docs/MIGRATION.md."));
dd.push(step("POC (now): platform authentication (Easy Auth) on the console — tenant sign-in required; secrets in a gitignored env file / App Service settings.", "steps"));
dd.push(step("Pilot: managed identities replace every key; Key Vault; three roles — Reviewer (run, adjudicate, download), SME/Approver (plan approval, exemplar release), Admin (deployments). The software enforces the same segregation of duties it audits.", "steps"));
dd.push(step("Production: private endpoints; WORM immutability on the evidence container; diagnostic logs; the run ledger retained as the platform's own ITGC evidence; per-control graduation reviewed with internal audit.", "steps"));

dd.push(h1("13. Roadmap"));
dd.push(step("Shadow (current): runs beside the human reviewer; nothing auto-submits.", "steps"));
dd.push(step("Assist: IQR drafts every finding; the human decides each. Gate: measured recall/precision/reproducibility per control.", "steps"));
dd.push(step("Primary: IQR decides; humans review exceptions and samples. Per-control gating.", "steps"));
dd.push(new Paragraph({ style: "Subtle", children: [new TextRun(
  "Grounding: real-corpus validation across three production-shaped controls (3.4M cells, 245 images, six-email sign-off chains, a 184 MB embedded workbook); 58 passing invariant tests; live five-gate batch eval passes on the deployed Foundry model seats. All identifiers generic by intent.")] }));

/* ------------------------------------------------ UAT guide */
const uatCases = [
  ["UAT-0 · Intake — bulk upload and the package's story",
   ["New validation tab → drag ALL files from tests/fixtures/controls/C10032/package into the drop zone (or paste the folder path → Analyze folder).",
    "Expect: artifact/cell/email counts, format chips, a grounded story naming the control and checks, C10032 suggested at 100% evidence, missing items declared BEFORE the run. Confirm and click Run validation."]],
  ["UAT-1 · Clean control end to end",
   ["Analyze tests/fixtures/controls/C23024/package → confirm C23024 → Run validation.",
    "Expect: verdict PASS; three cited findings; audit pack downloads and contains verdict.json, checklist.md, citations.json, gaps register, manifest, plan.json."]],
  ["UAT-2 · Honest gap — remove required evidence",
   ["Copy the C23024 package; delete the approval .eml; run against the copy.",
    "Expect: PASS_WITH_GAPS (never pass); the sign-off check names the missing evidence."]],
  ["UAT-3 · Defect caught — tamper with a number",
   ["Copy the C23024 package; change one regional sales cell (e.g. +1,000 to B2); run.",
    "Expect: numeric check FAIL with recomputed vs recorded values and the delta; citations point at the exact cells."]],
  ["UAT-4 · Temporal + timezone (GMT/CDT)",
   ["Run C10032 against its fixture package.",
    "Expect: PASS; the temporal detail shows both UTC-normalized stamps and correct ordering."]],
  ["UAT-5 · Vision tie-out (OCR)",
   ["Run C10075 against its fixture package.",
    "Expect: PASS; screenshot value ties to the workbook cell."]],
  ["UAT-6 · Live model attribution and fallback",
   ["With Azure configured, run any control; read the Live-run agent lines.",
    "Expect: agent[foundry] on judgment checks. Break the key and rerun: agent[stub] — visible fallback, run still completes honestly."]],
  ["UAT-7 · Evaluation gates",
   ["Evaluation tab → Run evaluation.",
    "Expect: all five gates PASS."]],
  ["UAT-8 · Batch scoring + confidence",
   ["Evaluation tab → Batch ×3 with scoring.",
    "Expect: per-gate mean/min/max plus a per-check confidence table (stability bars, HIGH/MEDIUM/LOW). Verify no false pass ever."]],
  ["UAT-9 · HITL adjudication → reinforcement learning",
   ["Governance tab: adjudicate an exception (include iqr_verdict), then click Run learning pass.",
    "Expect: 'Applied 1 new adjudication(s)'; confidence moves off 0.50 (up on agreement, down on override); re-running applies 0 (idempotent)."]],
  ["UAT-10 · Citation gate (anti-hallucination)",
   ["Run: pytest tests/test_citation_gate.py -q",
    "Expect: green — a fabricated locator is mechanically rejected."]],
  ["UAT-11 · Reproducibility",
   ["Run the same control twice; diff the two packs' verdict.json (ignore run_id).",
    "Expect: identical verdicts, evidence sets, computed values."]],
  ["UAT-12 · MCP surface",
   ["From an MCP client: python -m iqr.mcp_server; call list_controls then run_control on a fixture.",
    "Expect: typed verdict JSON with citations and a pack path; unapproved plans refused."]],
];
const uat = [];
uat.push(new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun("IQR — User Acceptance Test Guide")] }));
uat.push(p("Thirteen step-by-step cases a reviewer can run from the console (python -m iqr.cli serve → http://127.0.0.1:8400, or the deployed App Service URL). Total time ≈ 25 minutes.", { run: { color: GREY, italics: true } }));
for (const [title, lines] of uatCases) {
  uat.push(h1(title));
  for (const l of lines) uat.push(l.startsWith("Expect:")
    ? new Paragraph({ children: [new TextRun({ text: l, bold: true, color: DARK })], spacing: { after: 110 } })
    : p(l));
}

async function main() {
  const mk = (children) => new Document({
    styles, numbering, features: { updateFields: true },
    sections: [{ properties: { page: LETTER }, children }] });
  fs.writeFileSync("docs/design/IQR_Design_Document_v4.docx", await Packer.toBuffer(mk(dd)));
  fs.writeFileSync("docs/design/IQR_UAT_Guide.docx", await Packer.toBuffer(mk(uat)));
  console.log("written: IQR_Design_Document_v4.docx, IQR_UAT_Guide.docx");
}
main();
