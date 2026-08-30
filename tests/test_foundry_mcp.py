"""Azure Foundry seat + Foundry IQ retrieval + MCP surface - all offline.

The Foundry backend joins the fallback chain by configuration only; Foundry IQ
retrieval degrades loudly to the local mirror; the MCP server exposes the
platform without bypassing any invariant.
"""
import asyncio

from iqr import config
from iqr.agents.model_client import AzureFoundryClient
from iqr.knowledge.foundry_iq import FoundryIQStore, knowledge_store
from iqr.knowledge.store import LocalVectorStore


def test_foundry_joins_auto_chain_when_configured(monkeypatch):
    monkeypatch.setattr(config, "MODEL_NAME", "auto")
    monkeypatch.setattr(config, "AZURE_FOUNDRY_ENDPOINT", "https://proj.example.azure.com")
    monkeypatch.setattr(config, "AZURE_FOUNDRY_DEPLOYMENT", "gpt-4o")
    client = config.get_model_client()
    names = [c.name for c in client.chain]
    assert names[0] == "foundry"
    assert names[-1] == "stub"          # deterministic fallback still guards the chain


def test_per_seat_model_routing(monkeypatch):
    """A newly approved model earns one seat via env, without touching code."""
    monkeypatch.setattr(config, "MODEL_NAME", "stub")
    monkeypatch.setattr(config, "AZURE_FOUNDRY_ENDPOINT", "https://p.example.com")
    monkeypatch.setattr(config, "AZURE_FOUNDRY_DEPLOYMENT", "gpt-41-mini")
    monkeypatch.setenv("IQR_MODEL_VERIFY", "foundry")
    monkeypatch.setenv("IQR_FOUNDRY_DEPLOYMENT_VERIFY", "gpt-5-chat")
    # unrouted seats inherit the global mode
    assert config.get_model_client(seat="signoff").name == "stub"
    # the routed seat gets its own mode AND its own deployment
    verify_client = config.get_model_client(seat="verify")
    assert verify_client.name == "foundry"
    assert "gpt-5-chat" in verify_client.api_url


def test_foundry_absent_from_chain_when_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "MODEL_NAME", "auto")
    monkeypatch.setattr(config, "AZURE_FOUNDRY_ENDPOINT", "")
    client = config.get_model_client()
    assert "foundry" not in [c.name for c in client.chain]


def test_foundry_client_builds_deployment_url():
    c = AzureFoundryClient("https://proj.example.azure.com/", "key", "gpt-4o",
                           "2024-10-21", temperature=0.0, max_tokens=64)
    assert c.api_url == ("https://proj.example.azure.com/openai/deployments/"
                         "gpt-4o/chat/completions?api-version=2024-10-21")
    full = "https://gw.example.com/openai/deployments/d/chat/completions?api-version=x"
    assert AzureFoundryClient(full, "k", "", "x", 0.0, 64).api_url == full


def test_foundry_iq_falls_back_to_local_mirror(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FOUNDRY_IQ_ENDPOINT", "")
    monkeypatch.setattr(config, "FOUNDRY_IQ_API_KEY", "")
    monkeypatch.setattr(config, "FOUNDRY_IQ_KNOWLEDGE_BASE", "")
    local = LocalVectorStore(tmp_path / "kb.json")
    local.add("d1", "quarterly rebate recompute tolerance", {})
    # Unconfigured -> local, transparently.
    assert knowledge_store(local) is local
    # Configured but unreachable -> falls back, and says so via last_backend.
    store = FoundryIQStore(local, endpoint="http://127.0.0.1:1",
                           api_key="k", knowledge_base="kb")
    hits = store.search("rebate tolerance")
    assert store.last_backend == "local"
    assert hits and hits[0]["doc_id"] == "d1"
    # add() always lands in the durable local mirror.
    store.add("d2", "sign-off segregation of duties", {})
    assert local.search("segregation")[0]["doc_id"] == "d2"


def test_mcp_tools_and_resources_registered():
    from iqr.mcp_server import mcp
    tools = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"list_controls", "get_plan", "run_control", "get_run_ledger",
            "run_eval", "compile_plan", "similar_adjudications",
            "pending_exceptions"} <= tools
    templates = {t.uri_template for t in asyncio.run(mcp.list_resource_templates())}
    assert "iqr://plans/{control_id}/{version}" in templates
    assert "iqr://runs/{run_id}/ledger" in templates


def test_mcp_run_control_end_to_end(plans, fixtures_root):
    from iqr.mcp_server import get_plan, list_controls, run_control
    roster = list_controls()
    assert any(c["control_id"] == "C23024" for c in roster)
    plan = get_plan("C23024")
    assert plan["control_id"] == "C23024"
    verdict = run_control("C23024", str(fixtures_root / "C23024" / "package"),
                          plan_version="1.0.0")
    assert verdict["result"] == "pass"
    assert verdict["pack_path"].endswith(".zip")
    assert all(f["citations"] for f in verdict["findings"])
