# Azure AI Foundry integration — model seat, Foundry IQ, and MCP

IQR's Azure integration has three independent pieces. Each is opt-in by
configuration; with nothing configured the platform behaves exactly as before
(offline stub, local retrieval, no MCP process running). The three laws are
unaffected: agents still obtain every fact from deterministic tools, verdicts
still carry resolvable citations, and runs stay reproducible.

## 1. Foundry as the model seat

A chat-completions deployment on an Azure AI Foundry project can serve the
agent seats (temporal / sign-off / vision / verifier / plan compiler). Add to
`.env`:

```
AZURE_FOUNDRY_ENDPOINT=https://<project>.openai.azure.com
AZURE_FOUNDRY_API_KEY=<key>
AZURE_FOUNDRY_DEPLOYMENT=<deployment-name>       # e.g. gpt-4o
AZURE_FOUNDRY_API_VERSION=2024-10-21
```

- `IQR_MODEL=foundry` — Foundry only; fails hard if unreachable.
- `IQR_MODEL=auto` — Foundry first, then DaVinci, then the secondary
  endpoint, then the deterministic stub. As always, the run ledger records
  which backend answered every call, so fallback is visible, never silent.

If your gateway exposes a full route, set `AZURE_FOUNDRY_ENDPOINT` to the
complete `.../chat/completions?...` URL and leave the deployment blank.

Verify with:

```bash
.venv/bin/python -m iqr.cli testmodel
```

### Per-seat model routing and the model graduation process

Each agent seat (`PLAN_COMPILE`, `VISION`, `TEMPORAL`, `SIGNOFF`, `VERIFY`)
can run a different approved model:

```
IQR_MODEL_VERIFY=davinci                      # mode override for one seat
IQR_FOUNDRY_DEPLOYMENT_PLAN_COMPILE=gpt-5-chat  # different deployment, one seat
```

Graduation process for a newly approved model: security approves it → add a
Foundry deployment → run `python -m iqr.cli eval` with the seat routed to it →
all five gates green → the seat assignment ships. The run ledger attributes
every call to its backend, so a seat change is a diffable, auditable event.
Judgment-heavy seats (Plan Compiler, Verifier) benefit most from stronger
models; check seats stay on the cheap fast tier.

## 2. Foundry IQ as the knowledge layer

Foundry IQ serves agentic retrieval over a knowledge base (grounded in blob
storage, SharePoint, Fabric, or Azure AI Search indexes). IQR points its two
retrieval consumers — the Control KB (plan compiler grounding) and the Golden
Library (adjudication exemplars) — at a knowledge base when configured:

```
FOUNDRY_IQ_ENDPOINT=https://<search-service>.search.windows.net
FOUNDRY_IQ_API_KEY=<key>
FOUNDRY_IQ_KNOWLEDGE_BASE=<knowledge-base-name>
```

Behavior (`iqr/knowledge/foundry_iq.py`):

- `search()` asks the knowledge base first; on any failure it falls back to
  the local hashed index and records `last_backend = "local"` — degradation
  is observable, never silent.
- `add()` always writes the durable local mirror. Feeding the knowledge base
  itself happens through Foundry's own ingestion sources, not the runtime —
  the Golden Library's governed-learning gate (eval green + SME sign-off)
  still decides what is exposed to agents.

## 3. IQR as an MCP server (agents, tools, resources, data)

`iqr/mcp_server.py` exposes the platform to any MCP client — an Azure AI
Foundry agent, Claude, an IDE — as typed tools and resources:

| Kind | Name | What it does |
|---|---|---|
| tool | `list_controls` | approved plans, versions, check roster |
| tool | `get_plan` | a frozen validation plan |
| tool | `run_control` | validate an evidence folder → cited verdict + audit pack |
| tool | `get_run_ledger` | replay a run's explainability trail |
| tool | `run_eval` | the five-gate harness |
| tool | `compile_plan` | draft a plan from a 404 doc (SME approval still required) |
| tool | `similar_adjudications` | Golden Library retrieval |
| tool | `pending_exceptions` | governed-learning intake queue |
| resource | `iqr://plans/{control_id}/{version}` | plan JSON |
| resource | `iqr://runs/{run_id}/ledger` | run ledger |
| resource | `iqr://topology` | versioned topology signature |

Run it:

```bash
.venv/bin/python -m iqr.mcp_server                          # stdio
IQR_MCP_TRANSPORT=streamable-http .venv/bin/python -m iqr.mcp_server   # HTTP
```

### Wiring it into a Foundry agent

1. Start the server with `IQR_MCP_TRANSPORT=streamable-http` on a host the
   Foundry project can reach (it binds the MCP default port; front it with
   your approved ingress/auth).
2. In the Foundry portal (or via the Agents SDK), add an **MCP tool** to your
   agent with the server URL and label `iqr`.
3. Give the agent instructions like: *"Use the iqr tools to validate SOX 404
   evidence. Never assert a number or verdict yourself — call run_control and
   report its cited findings."*

The MCP surface never bypasses invariants: only frozen, SME-approved plans
can run; drafts from `compile_plan` are not runnable until approved; every
verdict that crosses this boundary carries its citations.

### Claude Code / desktop client config

```json
{
  "mcpServers": {
    "iqr": {
      "command": "/Users/<you>/Documents/IQR/.venv/bin/python",
      "args": ["-m", "iqr.mcp_server"],
      "cwd": "/Users/<you>/Documents/IQR"
    }
  }
}
```

## Tests

`tests/test_foundry_mcp.py` covers all three pieces offline: chain
composition with/without Foundry configured, URL construction, Foundry IQ
fallback-with-visibility, MCP tool/resource registration, and an end-to-end
`run_control` through the MCP tool against a golden fixture.
