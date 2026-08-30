# IQR — Complete Migration & Deployment Guide

From a **plain machine with VS Code** (no AI assistant needed) to a fully
working, Azure-connected IQR — including creating every cloud resource from
scratch, uploading the data, and securing the console. Every step is a copy-
paste command with a **Verify** line, so you never hunt through portals.
Validated against Azure CLI 2.80 and MS Learn guidance current as of Aug 2026.

**Two scenarios:**
- **Scenario A** — connect to the EXISTING resources (`rg-iqr-sox`).
- **Scenario B** — create everything from scratch in a new subscription
  (corporate tenant, new region). Same steps, plus Phase 3.

---

## Phase 0 · Prerequisites (10 min, once per machine)

| Tool | Install | Verify |
|---|---|---|
| Python 3.12+ | python.org or `brew install python@3.12` / `winget install Python.Python.3.12` | `python3 --version` |
| git | git-scm.com | `git --version` |
| Azure CLI | `brew install azure-cli` / `winget install Microsoft.AzureCLI` | `az version` |
| Tesseract (OCR) | `brew install tesseract` / `winget install UB-Mannheim.TesseractOCR` | `tesseract --version` |
| VS Code (optional) | code.visualstudio.com + Python extension | — |

> **Windows note:** wherever this guide says `.venv/bin/python`, use
> `.venv\Scripts\python`.

> **Do NOT clone into OneDrive/iCloud-synced folders.** File eviction stalls
> reads. Use a plain path like `C:\src\IQR` or `~/src/IQR`.

---

## Phase 1 · Clone and install (5 min)

```bash
git clone https://github.com/git-bonda108/IQR_Agentic_AI.git IQR
cd IQR
python3 -m venv .venv
.venv/bin/pip install -e .
```

**Verify:** `.venv/bin/python -c "import iqr; print('ok')"` prints `ok`.

---

## Phase 2 · Prove the platform OFFLINE (5 min, no Azure, no keys)

The entire test suite runs against a deterministic offline stub — this is the
acceptance gate before any cloud work:

```bash
.venv/bin/python tests/fixtures/build_fixtures.py
.venv/bin/python -m pytest tests/ -q
```

**Verify:** all tests pass (58+ green). If this is green, every invariant —
no model math, citation gate, reproducibility, honest missing, scope, blinded
verify, chain of custody — holds on this machine.

Optional local look: `.venv/bin/python -m iqr.cli serve` → http://127.0.0.1:8400
(runs fully offline; intake, validation, eval all work on the stub).

---

## Phase 3 · Create the Azure resources (Scenario B only, ~10 min)

```bash
az login                       # sign in to the target tenant/subscription
az account set --subscription "<your subscription name>"
```

One script provisions everything (resource group, storage + containers +
tables, AI Foundry account + project + model deployment, AI Search):

```bash
export IQR_AZ_LOCATION=eastus2          # pick your approved region
export IQR_AZ_STORAGE=stiqrsox<uniq>    # storage names are global: add a suffix
export IQR_AZ_FOUNDRY=iqr-foundry-<uniq>
export IQR_AZ_SEARCH=iqr-search-<uniq>
bash scripts/azure/provision.sh
```

The script prints the exact `.env` block to paste. It creates:

| Resource | Purpose |
|---|---|
| Resource group `rg-iqr-sox` | everything lives here |
| Storage account | containers: `evidence-store`, `run-ledgers`, `audit-packs`, `plans`, `knowledge`, `source-evidence` · tables: `runs`, `exceptions` |
| AI Foundry (AIServices) + project `iqr-sox` | the model seats |
| Model deployment(s) | `gpt-41-mini` (checks); optionally add `gpt-5-mini` (verifier) and `model-router` (plan compiler) — see Phase 5 |
| AI Search | the Foundry IQ knowledge index (see Phase 7) |

Add the extra model deployments (recommended):

```bash
az cognitiveservices account deployment create -n $IQR_AZ_FOUNDRY -g rg-iqr-sox \
  --deployment-name gpt-5-mini --model-name gpt-5-mini --model-version 2025-08-07 \
  --model-format OpenAI --sku-name GlobalStandard --sku-capacity 50
az cognitiveservices account deployment create -n $IQR_AZ_FOUNDRY -g rg-iqr-sox \
  --deployment-name model-router --model-name model-router --model-version 2025-11-18 \
  --model-format OpenAI --sku-name GlobalStandard --sku-capacity 10
```

**Verify:** `az resource list -g rg-iqr-sox -o table` shows 5+ resources;
`az cognitiveservices account deployment list -n $IQR_AZ_FOUNDRY -g rg-iqr-sox -o table`
shows your deployments.

> **Quota tip:** if a model errors `InsufficientQuota`, list what your
> subscription can deploy: `az cognitiveservices usage list -l <region> -o table`
> and pick a model with headroom. Avoid deprecated versions (the error says so).

---

## Phase 4 · Connect the machine to Azure (5 min)

```bash
cp .env.example .env         # .env is gitignored - NEVER commit it
```

Fill the Azure block. Every value comes from the CLI (no portal digging):

```bash
# model seat key
az cognitiveservices account keys list -n <foundry-name> -g rg-iqr-sox --query key1 -o tsv
# search key
az search admin-key show --service-name <search-name> -g rg-iqr-sox --query primaryKey -o tsv
# storage key
az storage account keys list -n <storage-name> -g rg-iqr-sox --query "[0].value" -o tsv
```

`.env` should contain (with your names):

```
IQR_MODEL=auto
AZURE_FOUNDRY_ENDPOINT=https://<foundry-name>.openai.azure.com
AZURE_FOUNDRY_API_KEY=<key1>
AZURE_FOUNDRY_DEPLOYMENT=gpt-41-mini
AZURE_FOUNDRY_API_VERSION=2024-10-21
FOUNDRY_IQ_ENDPOINT=https://<search-name>.search.windows.net
FOUNDRY_IQ_API_KEY=<primaryKey>
FOUNDRY_IQ_KNOWLEDGE_BASE=iqr-knowledge
IQR_AZ_STORAGE_ACCOUNT=<storage-name>
IQR_AZ_STORAGE_KEY=<storage key>
```

**Verify:** `.venv/bin/python -m iqr.cli testmodel` → `answered by: foundry`.

---

## Phase 5 · Per-seat model routing (2 min, optional but recommended)

Append to `.env`:

```
IQR_FOUNDRY_DEPLOYMENT_VERIFY=gpt-5-mini
IQR_FOUNDRY_DEPLOYMENT_PLAN_COMPILE=model-router
```

Seats: `PLAN_COMPILE, VISION, TEMPORAL, SIGNOFF, VERIFY`. The graduation rule
for any newly approved model: add its deployment → route ONE seat →
`.venv/bin/python -m iqr.cli eval --batch 3` → all gates green → keep it.

**Verify:** run any control; the console's Live-run ledger shows
`agent[foundry]` and, per seat, which deployment answered.

---

## Phase 6 · Upload the data estate to Blob Storage (10 min)

Sign-in–based auth (current MS Learn recommendation, no keys on the command line):

```bash
SUB=$(az account show --query id -o tsv)
ME=$(az ad signed-in-user show --query id -o tsv)
az role assignment create --assignee $ME --role "Storage Blob Data Contributor" \
  --scope /subscriptions/$SUB/resourceGroups/rg-iqr-sox/providers/Microsoft.Storage/storageAccounts/<storage-name>

az storage blob upload-batch --auth-mode login --account-name <storage-name> \
  -s data/plans -d plans --overwrite --no-progress
az storage blob upload-batch --auth-mode login --account-name <storage-name> \
  -s data/runs -d run-ledgers --overwrite --no-progress
az storage blob upload-batch --auth-mode login --account-name <storage-name> \
  -s data/packs -d audit-packs --overwrite --no-progress
az storage blob upload-batch --auth-mode login --account-name <storage-name> \
  -s tests/fixtures/controls -d source-evidence --destination-path fixtures --overwrite --no-progress
az storage blob upload-batch --auth-mode login --account-name <storage-name> \
  -s data/input -d source-evidence --destination-path input --overwrite --no-progress
az storage blob upload-batch --auth-mode login --account-name <storage-name> \
  -s data/evidence_store -d evidence-store --overwrite --no-progress
```

**Verify:**
`az storage blob list --auth-mode login --account-name <storage-name> -c plans --query "length(@)"`
returns your plan count. Portal path if you prefer eyes-on: Storage account →
Containers → each container shows the files.

> Production hardening (later): enable WORM immutability on `evidence-store`:
> `az storage container immutability-policy create --account-name <storage> -c evidence-store --period 366 --allow-protected-append-writes true`

---

## Phase 7 · AI Search / Foundry IQ — yes, you need it, here's exactly why

**What it does in IQR:** it is the knowledge layer. The Plan Compiler grounds
on it ("how are controls like this structured"), and check/verify agents
retrieve adjudication precedents ("how was this pattern judged before").
Without it, IQR still runs — retrieval silently comes from the local mirror
index (visible as `last_backend: "local"`), you just lose shared, cloud-hosted
knowledge. With it, every machine and every agent shares one governed corpus.

Create + seed the index (idempotent — rerun any time plans/lessons change):

```bash
.venv/bin/python scripts/azure/seed_knowledge.py
```

**Verify:**

```bash
curl -s "https://<search-name>.search.windows.net/indexes/iqr-knowledge/docs/\$count?api-version=2024-07-01" \
  -H "api-key: <primaryKey>"
```

returns ≥ 12 (plans + real-corpus lessons + released exemplars).

---

## Phase 8 · Reinforcement learning — where it is and how it plays out

**Where the code is:** `iqr/learn/reinforce.py`.
**Where the state is:** `data/knowledge/reinforce_state.json` — transparent
per-check counts (`alpha` = human agreed, `beta` = human overrode).
**Where you see it:** console → **Governance → Earned confidence**, or
`GET /api/confidence`.

How it plays out, end to end:
1. A run routes an exception (verifier disagreement, sentinel HIGH, or gap)
   to the queue.
2. A human adjudicates it (console or `POST /api/exceptions/adjudicate`,
   including `iqr_verdict` — what IQR concluded).
3. A learning pass folds every adjudication in as a **reward**
   (agree=1, override=0): console button **Run learning pass**,
   `POST /api/learn`, or `.venv/bin/python -m iqr.cli learn`. Idempotent.
4. The posterior updates confidence per (control, check) and re-ranks review
   priority — most-uncertain first. **Verdicts are never touched**; this
   governs attention and Assist/Primary graduation, not conclusions.

No Azure ML workspace is required — this is bandit-family RL over expert
rewards, stored as auditable counts. (If OCR needs ever outgrow Tesseract,
use the managed Azure Document Intelligence service; still no training.)

**Verify:** run UAT-9 in `docs/UAT.md` — adjudicate twice (one agree, one
override), run the learning pass, watch confidence move 0.50 → 0.67 / 0.33.

---

## Phase 9 · Deploy the console to Azure (App Service, free tier) (~10 min)

```bash
az appservice plan create -n plan-iqr -g rg-iqr-sox -l <region> --is-linux --sku F1
az webapp create -n <app-name> -g rg-iqr-sox --plan plan-iqr --runtime "PYTHON:3.12"
az webapp config set -n <app-name> -g rg-iqr-sox \
  --startup-file "python -m uvicorn iqr.api.app:app --host 0.0.0.0 --port 8000"
az webapp config appsettings set -n <app-name> -g rg-iqr-sox --settings \
  IQR_MODEL=auto AZURE_FOUNDRY_ENDPOINT=... AZURE_FOUNDRY_API_KEY=... \
  AZURE_FOUNDRY_DEPLOYMENT=gpt-41-mini FOUNDRY_IQ_ENDPOINT=... \
  FOUNDRY_IQ_API_KEY=... FOUNDRY_IQ_KNOWLEDGE_BASE=iqr-knowledge \
  IQR_FOUNDRY_DEPLOYMENT_VERIFY=gpt-5-mini SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

Build the deploy bundle and ship it:

```bash
bash scripts/azure/build_webapp_bundle.sh          # creates deploy.zip
az webapp deploy -n <app-name> -g rg-iqr-sox --src-path deploy.zip --type zip
```

**Verify:** `curl -s https://<app-name>.azurewebsites.net/api/topology`
returns the topology JSON.

### Lock it with Easy Auth (Microsoft Entra) — required before sharing the URL

CLI (matches the current MS Learn portal flow):

```bash
APPID=$(az ad app create --display-name iqr-console \
  --web-redirect-uris https://<app-name>.azurewebsites.net/.auth/login/aad/callback \
  --enable-id-token-issuance true --sign-in-audience AzureADMyOrg --query appId -o tsv)
TENANT=$(az account show --query tenantId -o tsv)
az webapp auth config-version upgrade -n <app-name> -g rg-iqr-sox
az webapp auth microsoft update -n <app-name> -g rg-iqr-sox \
  --client-id $APPID --issuer https://login.microsoftonline.com/$TENANT/v2.0 --yes
az webapp auth update -n <app-name> -g rg-iqr-sox --enabled true \
  --action RedirectToLoginPage --redirect-provider AzureActiveDirectory
```

Portal equivalent: App → **Authentication** → **Add identity provider** →
Microsoft → Workforce, current tenant → Create new app registration →
**Require authentication**, **HTTP 302 redirect**.

**Verify:** `curl -s -o /dev/null -w "%{http_code}" https://<app-name>.azurewebsites.net/`
returns **401**; a browser gets a Microsoft sign-in page, and your tenant
account gets through. (Later production ladder: managed identities replacing
keys, Key Vault, role-based Reviewer/Approver/Admin, private endpoints — see
docs/AZURE_FOUNDRY.md and the design document §11.)

---

## Phase 10 · End-to-end acceptance (10 min)

1. Open the console (local or the App Service URL).
2. **New validation** → drag the whole contents of
   `tests/fixtures/controls/C10032/package` into the drop zone (multiple
   files, mixed formats).
3. Read the intake story: artifact/cell/email counts, format chips, inferred
   control **C10032 at 100% evidence**, the checks that will run, caveats.
4. **Run validation · C10032** → watch the live ledger → verdict **pass** →
   download the audit pack.
5. **Evaluation → Batch ×3 with scoring** → all gates PASS, per-check
   confidence HIGH.
6. Full UAT script: `docs/UAT.md` (12 cases).

---

## Quick reference — where everything lives

| Thing | Location |
|---|---|
| Agents (seats) | `iqr/checks/agent_checks.py`, `iqr/graph/nodes/verify_node.py`, `iqr/plan/compiler.py`; loop in `iqr/agents/runtime.py` |
| Deterministic tools | `iqr/tools/` |
| Intake (bulk upload → story) | `iqr/intake.py` + console New-validation tab |
| Model seats / routing | `iqr/config.py` (`IQR_MODEL_*`, `IQR_FOUNDRY_DEPLOYMENT_*`) |
| Knowledge / Foundry IQ | `iqr/knowledge/` + `scripts/azure/seed_knowledge.py` |
| Reinforcement learning | `iqr/learn/reinforce.py`; state `data/knowledge/reinforce_state.json` |
| Eval harness (five gates, batch) | `iqr/eval/harness.py`, `iqr/eval/batch.py` |
| MCP server | `iqr/mcp_server.py` |
| Azure provisioning | `scripts/azure/provision.sh` |
| Run ledgers / packs / plans | `data/runs`, `data/packs`, `data/plans` (mirrored to Blob) |
