# IQR Deployment Guide — clone anywhere, run locally

This guide takes any machine (macOS, Linux, or Windows) from `git clone` to a
working local deployment: web console, CLI, tests, and eval harness. No admin
rights, no cloud services, no telemetry. The only optional network dependency
is the LLM endpoint you configure — everything else runs fully offline.

> **Deploying with Azure (AI Foundry model seats, Foundry IQ retrieval, blob
> data estate, cloud console)?** Use **[MIGRATION.md](MIGRATION.md)** — the
> phase-by-phase guide from a fresh machine to a fully Azure-connected
> deployment — with **[AZURE_FOUNDRY.md](AZURE_FOUNDRY.md)** as the
> integration reference and **[PRODUCTION_STANDARDS.md](PRODUCTION_STANDARDS.md)**
> for the enterprise hardening ladder. This document covers the local/offline
> path, which remains the acceptance gate before any cloud work.

---

## 1. Prerequisites

| Requirement | Version | Check | If missing |
|---|---|---|---|
| Python | 3.12+ | `python3 --version` | python.org installer (user-mode install is fine) |
| Git | any recent | `git --version` | git-scm.com |
| Tesseract OCR | 5.x | `tesseract --version` | macOS: `brew install tesseract` · Windows: UB-Mannheim installer (installs to `%LOCALAPPDATA%`, no admin) · Ubuntu: `sudo apt install tesseract-ocr` |

Corporate networks: if `pip` fails with SSL errors, your proxy intercepts TLS —
point pip at the corporate CA bundle once:

```bash
pip config set global.cert /path/to/corporate-ca-bundle.pem
```

## 2. Install

```bash
git clone <repo-url> IQR && cd IQR
python3 -m venv .venv
.venv/bin/pip install -e .          # Windows: .venv\Scripts\pip install -e .
```

Everything installs into the project's own virtualenv. Nothing touches the
system Python.

## 3. Offline smoke test — before any keys

The platform must prove itself with **zero secrets and zero network**:

```bash
.venv/bin/pytest -q                  # full suite must pass
.venv/bin/python -m iqr.cli eval     # five gate metrics, all green, stub model
```

If both are green, the machine is good. The stub model answers every agent
decision deterministically — this is also the permanent fallback, so an LLM
outage never blocks a close.

## 4. Configure the model seat (optional until you need it)

```bash
cp .env.example .env    # then edit .env
```

| Variable | Meaning |
|---|---|
| `IQR_MODEL` | `stub` (offline, default) · `foundry` (Azure AI Foundry deployment) · `davinci` (any OpenAI-compatible endpoint) · `auto` (Foundry → endpoints → stub fallback chain) |
| `AZURE_FOUNDRY_*` | Azure AI Foundry seat: endpoint, key, deployment, API version, embedding deployment — see [AZURE_FOUNDRY.md](AZURE_FOUNDRY.md) |
| `IQR_MODEL_<SEAT>` / `IQR_FOUNDRY_DEPLOYMENT_<SEAT>` | Per-seat model routing (`PLAN_COMPILE`, `VISION`, `TEMPORAL`, `SIGNOFF`, `VERIFY`) |
| `DAVINCI_API_URL` / `DAVINCI_API_KEY` | Your approved OpenAI-compatible chat endpoint (any gateway that speaks `/v1/chat/completions`) |
| `IQR_SECONDARY_API_URL` / `_KEY` | Optional second endpoint, same wire format |
| `ANTHROPIC_API_KEY` | Optional: lets the lab/dev machine use Claude on the agent seats |
| `IQR_STUB_FALLBACK` | Keep `1` so the deterministic stub catches runs when every endpoint is down |
| `IQR_STREAM_THRESHOLD` | Workbooks larger than this many bytes stream in read-only mode (default 60000000; lower on low-RAM machines) |
| `IQR_MAX_CELLS_PER_FILE` | Per-workbook cell cap with an explicit truncation sentinel (default 4000000) |

**Never commit `.env`** — it is gitignored. The template must contain no real
keys. Verify connectivity and see which backend answers:

```bash
.venv/bin/python -m iqr.cli testmodel
```

The run ledger records which backend answered every call, so runs are
attributable to a model version.

## 5. Start the console (the UI)

```bash
.venv/bin/python -m iqr.cli serve
```

Open **http://127.0.0.1:8400**. The console is a single static page over the
local API — no build step, no Node, no external assets. It binds loopback
only: nothing is reachable from the network.

From VS Code instead: open the repo folder and press **F5** — launch
configurations exist for the console, a real-package CLI run, and the eval
harness (`.vscode/launch.json`).

What the console gives a reviewer:

1. **Run a control** — cards for each approved plan. Selecting one shows
   exactly which evidence the plan expects (required vs optional, with the
   name patterns the matcher uses) and what is excluded from scope. This is
   the answer to "what do I upload?" — the frozen plan itself tells you.
2. **Provide evidence** — drag-and-drop files (stored under
   `data/input/uploads/`) or paste the path of a folder already on the machine.
3. **Live run** — ledger events stream into the page: ingest counts, evidence
   matching, sentinel anomalies, every tool call, verifier agreement, the
   citation gate, final verdict.
4. **Verdict** — findings with verdict chips and cell/line citations, gaps,
   exceptions, and one-click download of the audit-ready pack (.zip).
5. **Evaluation** — run the five-gate harness from the browser.
6. **Governance** — exception queue (feeds the Golden Library) and the
   approved-plan register.

## 6. CLI reference

```bash
python -m iqr.cli compile <404.docx> <control_id> <frequency>  # draft a plan (LLM seat)
python -m iqr.cli approve <control_id> <sme-name>              # freeze plan version
python -m iqr.cli run <control_id> <package_dir>               # full validation run
python -m iqr.cli explain <run_id>                             # replay the ledger
python -m iqr.cli eval                                         # five gate metrics
python -m iqr.cli testmodel                                    # model chain probe
python -m iqr.cli serve                                        # console on 127.0.0.1:8400
```

## 7. Directory layout after a run

```
data/
  input/uploads/        # packages uploaded through the console
  evidence_store/       # immutable SHA-256-named blobs (chain of custody)
  plans/<CID>/<ver>.json# frozen SME-approved plans (committed with the repo)
  runs/<run_id>.jsonl   # replayable ledgers (ITGC evidence for the platform)
  packs/<run_id>.zip    # audit-ready packs
  knowledge/            # Control KB + Golden Library persistence
```

Keep `data/` on a local disk (not a cloud-synced folder — sync churn slows
ingest badly and large evidence files don't belong in Dropbox/iCloud/OneDrive).

## 8. Onboarding a new control (the real workflow)

1. Put the control's 404 process document somewhere readable.
2. `compile` → produces a draft plan JSON.
3. SME reviews the draft: pins tolerances, timestamp anchors and their
   timezones, scope exclusions, expected evidence and match hints.
4. `approve` → the plan freezes, versioned. Runtime refuses unapproved plans.
5. Run each period's package through the console. Disagreements and anomalies
   land in the exception queue; adjudications grow the Golden Library behind
   the eval gate.

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `pip install` SSL errors | TLS-intercepting proxy | §1 CA bundle |
| `TesseractNotFoundError` | binary not on PATH | install per §1; on Windows add `%LOCALAPPDATA%\Programs\Tesseract-OCR` to PATH |
| Run killed (exit 137) on huge workbooks | low-RAM machine | lower `IQR_STREAM_THRESHOLD` (e.g. 20000000) and `IQR_MAX_CELLS_PER_FILE` (e.g. 1000000) — truncation is recorded honestly in the graph |
| `no approved plan for <CID>` | plan not frozen | `compile` + `approve` (§8) |
| Console shows no controls | same | same |
| Model probe fails | endpoint/key wrong | `.env` values; `IQR_MODEL=stub` always works offline |
| Port 8400 in use | another instance | `python -m uvicorn iqr.api.app:app --host 127.0.0.1 --port 8401` |

## 10. Production hardening checklist

- Run the console as a service (Task Scheduler / `nssm` on Windows,
  `launchd`/`systemd` elsewhere), still bound to 127.0.0.1.
- Back up `data/` (plans, ledgers, packs are your audit trail).
- Wire the mailbox/SharePoint watcher behind `iqr/ingest/resolver.py` for
  automatic package pull.
- Enforce the release gate: no plan amendment or Golden Library exemplar
  ships unless `python -m iqr.cli eval` passes plus SME sign-off.
