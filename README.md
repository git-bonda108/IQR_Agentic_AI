# IQR — Intelligent Quality Review for SOX 404 Controls

An agentic AI platform that validates SOX 404 control evidence packages end to
end and emits a cited, audit-ready pack. Agents reason; deterministic tools
compute; a frozen, SME-approved plan governs every run.

**Three laws** (every design choice descends from these):
1. Numbers are computed by deterministic Python, never by a model.
2. Every claim in output carries a resolvable evidence locator.
3. Same input produces the same verdict.

## Quickstart

```bash
git clone <repo-url> IQR && cd IQR
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/pytest -q                    # offline, no keys: full suite green
.venv/bin/python -m iqr.cli serve      # console at http://127.0.0.1:8400
```

Or open the folder in VS Code and press **F5** ("IQR Console").

Full setup, configuration, and troubleshooting: **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

## What it does

A GRC evidence package — a nested tree of workbooks, Outlook emails with
zipped attachments, screenshot-laden documents, embedded OLE workbooks — goes
in. Out comes a verdict per check (**pass / pass-with-gaps / fail**) where
every claim cites the exact cell, email line, or image it came from, plus an
auto-completed reviewer checklist, a gaps-and-observations register, and one
downloadable audit pack.

## Architecture in one paragraph

**Design time:** a Plan Compiler agent reads the control's 404 document and
drafts a Validation Plan; an SME reviews, pins tolerances/timezones/scope, and
freezes it (versioned, immutable). **Run time:** a fixed LangGraph topology
(`ingest → match → sentinel → checks (parallel) → verify → adjudicate`)
executes the frozen plan. Numeric checks are pure Python (invariant-tested:
zero model calls). Temporal/sign-off/vision checks are tool-using agents that
reason but obtain every fact from deterministic tools returning citations. An
**Anomaly Sentinel** adversarially screens the package first (recycled
prior-period evidence, link placeholders, pasted constants, tolerance gaming,
single-actor sign-off chains); a **blinded verifier** re-performs every
finding from its citations alone; a mechanical **citation gate** rejects any
claim whose locator does not resolve. Everything lands in a replayable run
ledger. **Governed learning:** human adjudications grow a Golden Library that
ships only behind a five-gate regression eval plus SME sign-off.

Deep design (agent/tool roster, sequence diagrams, eval mechanics, Golden
Library lifecycle): **[docs/design/IQR_Design_Document_v4.docx](docs/design/IQR_Design_Document_v4.docx)** ([html](docs/design/IQR_Design_Document_v4.html)) ·
Real-corpus validation results: **[docs/REAL_VALIDATION.md](docs/REAL_VALIDATION.md)**

## Model seat

One adapter, temperature 0, backend chosen in `.env`: Azure AI Foundry
(chat-completions deployment), any OpenAI-compatible gateway (e.g. an
approved internal DaVinci endpoint), optionally Anthropic Claude for lab
work, and a deterministic offline stub as permanent fallback. The ledger
records which backend answered every call. The demo and the entire test
suite run with no keys at all.

## Azure AI Foundry & MCP

Three opt-in integrations (see **[docs/AZURE_FOUNDRY.md](docs/AZURE_FOUNDRY.md)**):
Foundry as the model seat (`IQR_MODEL=foundry` or first in the `auto` chain);
**Foundry IQ** knowledge retrieval behind the Control KB / Golden Library
(falls back to the local index, visibly, when unreachable); and an **MCP
server** (`python -m iqr.mcp_server`) exposing the platform as typed tools
and resources so a Foundry agent, Claude, or any MCP client can run cited
validations without touching the machinery.

## Repository map

```
iqr/
  schemas/      validation plan, evidence graph, findings (pydantic, the contract)
  ingest/       recursive unpack (email→zip→workbook→image→OLE), extractors, graph builder
  tools/        deterministic tools: cell_read, recompute, timestamp, email_parse, ocr_read, citation
  checks/       numeric (model-free), vision/temporal/signoff (tool-using agents), sentinel
  graph/        LangGraph topology + nodes (ingest, match, sentinel, check, verify, adjudicate)
  plan/         compiler (design-time agent) + SME review/freeze
  knowledge/    Control KB + Golden Library (vector-indexed, eval-gated)
  eval/         harness, five gate metrics, seeded-defect generator
  pack/         audit-ready pack assembly
  api/          FastAPI (127.0.0.1) behind the console
  agents/       model client (Foundry/DaVinci chain + stub) and tool-agent runtime
  mcp_server.py IQR as an MCP server: tools + resources for external agents
webapp/         the console (single static page over the API)
tests/          invariants + fixtures; tests/real/ = real-corpus probes
docs/           deployment guide, system design, validation report
data/plans/     frozen plans (committed - they are deployable configuration)
```

## The seven invariants (enforced by tests)

No model math · citation gate · reproducibility · honest missing (absent
evidence → gap, never pass) · scope respected · blinded verify · SHA-256 chain
of custody.

## Security posture

Loopback-only server, zero telemetry, no outbound traffic except the
configured model endpoint, secrets only in gitignored `.env`, evidence stays
on local disk in a content-addressed immutable store.
