# Moving IQR to another PC / environment — step by step

Everything needed to go from a fresh machine to a working, Azure-connected
IQR in about 15 minutes. Works on macOS, Windows, or Linux. Nothing here
requires admin rights beyond installing Python and (optionally) Tesseract.

## 0. Prerequisites on the new machine

| Requirement | Why | Check |
|---|---|---|
| Python 3.12+ | runtime | `python3 --version` |
| git | clone the repo | `git --version` |
| Tesseract OCR | screenshot checks (optional for first run) | `tesseract --version` |
| Azure CLI | connect to Azure + deploy | `az version` |

Installs: macOS `brew install tesseract azure-cli` · Windows
`winget install UB-Mannheim.TesseractOCR Microsoft.AzureCLI` · Linux
`apt install tesseract-ocr` + [Azure CLI install script](https://learn.microsoft.com/cli/azure/install-azure-cli).

## 1. Clone and install

```bash
git clone https://github.com/git-bonda108/IQR_Agentic_AI.git IQR
cd IQR
python3 -m venv .venv
.venv/bin/pip install -e .          # Windows: .venv\Scripts\pip install -e .
```

## 2. Prove it works OFFLINE first (no keys, no network)

The entire test suite and eval harness run against the deterministic stub —
this is the acceptance step before touching Azure:

```bash
.venv/bin/python tests/fixtures/build_fixtures.py   # golden packages
.venv/bin/python -m pytest tests/ -q                # all tests must pass
```

If tests are green, the platform is healthy on this machine.

## 3. Connect to Azure

```bash
az login          # sign in with the subscription that owns rg-iqr-sox
```

Create `.env` at the repo root (NEVER commit it — it is gitignored):

```bash
cp .env.example .env
```

Fill in the Azure block. Retrieve every value with the CLI — no portal digging:

```bash
# Foundry model seat
az cognitiveservices account keys list -n iqr-foundry-108 -g rg-iqr-sox --query key1 -o tsv
# -> AZURE_FOUNDRY_API_KEY
# AZURE_FOUNDRY_ENDPOINT=https://iqr-foundry-108.openai.azure.com
# AZURE_FOUNDRY_DEPLOYMENT=gpt-41-mini

# Foundry IQ knowledge retrieval
az search admin-key show --service-name iqr-search-108 -g rg-iqr-sox --query primaryKey -o tsv
# -> FOUNDRY_IQ_API_KEY
# FOUNDRY_IQ_ENDPOINT=https://iqr-search-108.search.windows.net
# FOUNDRY_IQ_KNOWLEDGE_BASE=iqr-knowledge

# Storage (evidence, ledgers, packs)
az storage account keys list -n stiqrsox108 -g rg-iqr-sox --query "[0].value" -o tsv
# -> IQR_AZ_STORAGE_KEY ; IQR_AZ_STORAGE_ACCOUNT=stiqrsox108
```

Set `IQR_MODEL=auto` (Foundry first, deterministic stub as fallback).
Optional per-seat routing:

```
IQR_FOUNDRY_DEPLOYMENT_VERIFY=gpt-5-mini
IQR_FOUNDRY_DEPLOYMENT_PLAN_COMPILE=model-router
```

## 4. Verify the Azure connection

```bash
.venv/bin/python -m iqr.cli testmodel     # expect: "answered by: foundry"
.venv/bin/python -m iqr.cli eval          # five gates on the golden fixtures
```

## 5. Run the console

```bash
.venv/bin/python -m iqr.cli serve         # http://127.0.0.1:8400
```

Or provision Azure from scratch in a NEW subscription/region:

```bash
bash scripts/azure/provision.sh                     # all resources
.venv/bin/python scripts/azure/seed_knowledge.py    # knowledge index
```

## 6. Acceptance run

```bash
.venv/bin/python -m iqr.cli run C23024 tests/fixtures/controls/C23024/package
```

Expected: `C23024: pass`, three cited findings, and an audit pack path.
Follow `docs/UAT.md` for the full user-acceptance script.

## Troubleshooting

- **`answered by: stub`** — Azure env vars missing/typo'd in `.env`, or no
  network to the endpoint. The stub keeping things green is by design.
- **Tests fail only online** — they shouldn't: tests are hermetic and never
  dial Azure. Any failure is local (Python version, missing Tesseract for
  two OCR tests).
- **Corporate proxy** — set `HTTPS_PROXY`; httpx honors it.
- **Repo inside a cloud-synced folder (OneDrive/iCloud)** — don't. Evicted
  files stall reads. Clone to a plain local path (e.g. `C:\src\IQR`).
