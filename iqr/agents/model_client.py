"""The thin model client. DaVinci is the ONLY production model; the stub is a
deterministic offline stand-in so the platform runs and tests locally.

Both speak the same tiny protocol the agent runtime uses:
the model receives (system, user) and returns a JSON action string -
either {"action":"tool","tool":...,"args":{...}} or {"action":"final","output":{...}}.
Determinism note: temperature is pinned to 0 centrally in config; the stub is
a pure function of its input, so stub runs are bit-reproducible.
"""
from __future__ import annotations

import json

import httpx

from iqr import config


class ModelClient:
    name = "base"

    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


class DaVinciClient(ModelClient):
    """OpenAI-compatible chat-completions client. Used for the DaVinci API and
    for any secondary approved endpoint (same wire format, different URL)."""

    name = "davinci"

    def __init__(self, api_url: str, api_key: str, temperature: float,
                 max_tokens: int, name: str = "davinci"):
        if not api_url:
            raise RuntimeError(f"{name}: API URL not configured")
        self.api_url, self.api_key = api_url, api_key
        self.temperature, self.max_tokens = temperature, max_tokens
        self.name = name

    def complete(self, system: str, user: str) -> str:
        config.record_model_call()
        resp = httpx.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"messages": [{"role": "system", "content": system},
                               {"role": "user", "content": user}],
                  "temperature": self.temperature, "max_tokens": self.max_tokens},
            timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class AzureFoundryClient(ModelClient):
    """Azure AI Foundry model seat: a chat-completions deployment on a Foundry
    project (Azure OpenAI wire format - `api-key` header, api-version query).
    Same tiny protocol as every other backend; temperature stays pinned to 0."""

    name = "foundry"

    def __init__(self, endpoint: str, api_key: str, deployment: str,
                 api_version: str, temperature: float, max_tokens: int):
        if not endpoint:
            raise RuntimeError("foundry: AZURE_FOUNDRY_ENDPOINT not configured")
        if "/chat/completions" in endpoint:
            self.api_url = endpoint          # caller supplied the full route
        else:
            if not deployment:
                raise RuntimeError("foundry: AZURE_FOUNDRY_DEPLOYMENT not configured")
            self.api_url = (f"{endpoint.rstrip('/')}/openai/deployments/"
                            f"{deployment}/chat/completions?api-version={api_version}")
        self.api_key = api_key
        self.temperature, self.max_tokens = temperature, max_tokens

    _reasoning_params = False   # set once a deployment rejects pinned params

    def complete(self, system: str, user: str) -> str:
        config.record_model_call()
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        if not self._reasoning_params:
            resp = httpx.post(
                self.api_url,
                headers={"api-key": self.api_key,
                         "Authorization": f"Bearer {self.api_key}"},
                json={"messages": messages,
                      "temperature": self.temperature, "max_tokens": self.max_tokens,
                      "seed": 42},   # best-effort determinism on top of temp 0
                timeout=120)
            if resp.status_code != 400 or "unsupported" not in resp.text.lower():
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            # Reasoning-family deployment (o-series / gpt-5 / model-router):
            # rejects temperature/max_tokens - adapt once, remember for the run.
            self._reasoning_params = True
        resp = httpx.post(
            self.api_url,
            headers={"api-key": self.api_key,
                     "Authorization": f"Bearer {self.api_key}"},
            json={"messages": messages,
                  "max_completion_tokens": max(self.max_tokens, 4096)},
            timeout=180)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class FallbackModelClient(ModelClient):
    """Multi-mode fallback: try each backend in order; the first that answers
    wins. Which backend served each call is recorded (last_served) so the run
    ledger shows exactly what produced every judgment - no silent switching."""

    def __init__(self, chain: list[ModelClient]):
        if not chain:
            raise RuntimeError("empty model chain")
        self.chain = chain
        self.last_served: str = ""
        self.errors: list[str] = []

    @property
    def name(self) -> str:  # type: ignore[override]
        return "+".join(c.name for c in self.chain)

    def complete(self, system: str, user: str) -> str:
        self.errors = []
        for client in self.chain:
            try:
                result = client.complete(system, user)
                self.last_served = client.name
                return result
            except Exception as e:
                self.errors.append(f"{client.name}: {type(e).__name__}: {e}")
        raise RuntimeError("all model backends failed: " + " | ".join(self.errors))


class StubModelClient(ModelClient):
    """Deterministic offline policy engine. It plays the model's role in the
    agent loop: reads the task context + observations embedded in the user
    message and decides the next action exactly as the prompted model would.
    Pure function of its input -> reproducible by construction."""

    name = "stub"

    def complete(self, system: str, user: str) -> str:
        config.record_model_call()
        state = _extract_state(user)
        task_type = state.get("context", {}).get("task_type", "")
        handler = _POLICIES.get(task_type)
        if handler is None:
            return json.dumps({"action": "final",
                               "output": {"verdict": "gap",
                                          "detail": f"stub has no policy for task '{task_type}'"}})
        return json.dumps(handler(state["context"], state.get("observations", [])))


def _extract_state(user: str) -> dict:
    marker = "STATE_JSON:"
    idx = user.rfind(marker)
    if idx < 0:
        return {}
    return json.loads(user[idx + len(marker):].strip())


# ---------------- deterministic policies (one per task type) ----------------

def _obs_result(observations, tool_name):
    for o in observations:
        if o["tool"] == tool_name and "error" not in o["result"]:
            return o
    return None


def _obs_error(observations, tool_name):
    for o in observations:
        if o["tool"] == tool_name and "error" in o["result"]:
            return o["result"]["error"]
    return None


def _policy_vision(ctx, obs):
    tried = {o["args"].get("image_hash") for o in obs if o["tool"] == "ocr_labeled_number"}
    found = None
    for o in obs:
        if o["tool"] == "ocr_labeled_number" and o["result"].get("value") is not None:
            found = o
            break
    if found is None:
        untried = [h for h in ctx["images"] if h not in tried]
        if untried:
            return {"action": "tool", "tool": "ocr_labeled_number",
                    "args": {"image_hash": untried[0], "label": ctx["label"]}}
        return {"action": "final", "output": {
            "verdict": "gap",
            "detail": f"label '{ctx['label']}' not found in any of "
                      f"{len(ctx['images'])} screenshot(s); cannot tie out"}}
    cell = _obs_result(obs, "cell_read")
    if cell is None:
        err = _obs_error(obs, "cell_read")
        if err:
            return {"action": "final", "output": {
                "verdict": "gap", "detail": f"workbook cell unreadable: {err}"}}
        t = ctx["target"]
        return {"action": "tool", "tool": "cell_read",
                "args": {"file_hash": t["file_hash"], "sheet": t["sheet"], "cell": t["cell"]}}
    tol = float(ctx.get("tolerance", 0.01))
    img_v = float(found["result"]["value"])
    cell_v = float(cell["result"]["value"])
    ok = abs(img_v - cell_v) <= tol
    return {"action": "final", "output": {
        "verdict": "pass" if ok else "fail",
        "detail": (f"screenshot '{ctx['label']}' = {img_v} vs workbook "
                   f"{ctx['target']['sheet']}!{ctx['target']['cell']} = {cell_v} "
                   f"({'ties out' if ok else 'does NOT tie out'}, tol {tol})")}}


def _policy_temporal(ctx, obs):
    cell = _obs_result(obs, "cell_read")
    if cell is None:
        err = _obs_error(obs, "cell_read")
        if err:
            return {"action": "final", "output": {
                "verdict": "gap", "detail": f"IPE timestamp cell unreadable: {err}"}}
        e = ctx["earlier_cell"]
        return {"action": "tool", "tool": "cell_read",
                "args": {"file_hash": e["file_hash"], "sheet": e["sheet"], "cell": e["cell"]}}
    em = _obs_result(obs, "email_signoff_facts")
    if em is None:
        err = _obs_error(obs, "email_signoff_facts")
        if err:
            return {"action": "final", "output": {
                "verdict": "gap", "detail": f"approval email unreadable: {err}"}}
        return {"action": "tool", "tool": "email_signoff_facts",
                "args": {"message_id": ctx["later_email_message_id"]}}
    order = _obs_result(obs, "timestamp_order")
    if order is None:
        return {"action": "tool", "tool": "timestamp_order",
                "args": {"earlier_raw": str(cell["result"]["value"]),
                         "earlier_tz": ctx.get("earlier_tz", "UTC"),
                         "later_raw": em["result"]["value"]["date_utc"],
                         "later_tz": "UTC"}}
    r = order["result"]["value"]
    ok = bool(r["in_order"])
    return {"action": "final", "output": {
        "verdict": "pass" if ok else "fail",
        "detail": (f"IPE stamp {r['earlier_utc']} vs approval {r['later_utc']} - "
                   f"{'correctly ordered' if ok else 'OUT OF ORDER: approval predates the IPE it approves'}")}}


def _policy_signoff(ctx, obs):
    em = _obs_result(obs, "email_signoff_facts")
    if em is None:
        err = _obs_error(obs, "email_signoff_facts")
        if err:
            return {"action": "final", "output": {
                "verdict": "gap", "detail": f"approval email unreadable: {err}"}}
        return {"action": "tool", "tool": "email_signoff_facts",
                "args": {"message_id": ctx["approval_email_message_id"]}}
    facts = em["result"]["value"]
    if facts.get("approval_line") is None:
        return {"action": "final", "output": {
            "verdict": "gap",
            "detail": f"no approval language found in email from {facts['sender']}"}}
    preparer = ctx["preparer"].lower()
    approver_addr = facts["sender"].lower()
    distinct = preparer not in approver_addr
    problems = []
    if ctx.get("require_distinct", True) and not distinct:
        problems.append(f"SoD violation: approver '{facts['sender']}' is the preparer")
    if ctx.get("prepared_at_utc") and ctx.get("require_order", True):
        if facts["date_utc"] <= ctx["prepared_at_utc"]:
            problems.append("approval predates preparation")
    if problems:
        return {"action": "final", "output": {"verdict": "fail", "detail": "; ".join(problems)}}
    return {"action": "final", "output": {
        "verdict": "pass",
        "detail": (f"approved by {facts['sender']} on {facts['date_utc']} "
                   f"('{facts['approval_text']}'), distinct from preparer '{ctx['preparer']}'")}}


def _policy_verify(ctx, obs):
    """Blinded verifier policy: re-perform the check from citations + clause only."""
    ct = ctx["check_type"]
    if ct == "numeric":
        rec = _obs_result(obs, "recompute_from_citations")
        if rec is None:
            return {"action": "tool", "tool": "recompute_from_citations", "args": {}}
        r = rec["result"]["value"]
        claimed = ctx["claimed_verdict"]
        rederived = "pass" if r["ok"] else "fail"
        return _verify_final(claimed, rederived, r)
    if ct == "vision":
        rec = _obs_result(obs, "reperform_vision")
        if rec is None:
            return {"action": "tool", "tool": "reperform_vision", "args": {}}
        r = rec["result"]["value"]
        return _verify_final(ctx["claimed_verdict"], r["verdict"], r)
    if ct == "temporal":
        rec = _obs_result(obs, "reperform_temporal")
        if rec is None:
            return {"action": "tool", "tool": "reperform_temporal", "args": {}}
        r = rec["result"]["value"]
        return _verify_final(ctx["claimed_verdict"], r["verdict"], r)
    if ct == "signoff":
        rec = _obs_result(obs, "reperform_signoff")
        if rec is None:
            return {"action": "tool", "tool": "reperform_signoff", "args": {}}
        r = rec["result"]["value"]
        return _verify_final(ctx["claimed_verdict"], r["verdict"], r)
    return {"action": "final", "output": {"agree": False, "note": f"unknown check_type {ct}"}}


def _verify_final(claimed, rederived, evidence):
    agree = claimed == rederived
    note = (f"re-performed from cited evidence alone -> {rederived}; "
            f"{'matches' if agree else 'CONTRADICTS'} executor verdict '{claimed}'")
    return {"action": "final", "output": {"agree": agree, "note": note,
                                          "rederived": rederived, "evidence": evidence}}


def _policy_plan(ctx, obs):
    """Plan-compiler policy: structure a 404 document's text into a draft plan.
    The stub parses the conventionally-structured sections a 404 contains."""
    from iqr.plan.compiler import heuristic_plan_from_404
    return {"action": "final",
            "output": heuristic_plan_from_404(ctx["control_id"], ctx["frequency"],
                                              ctx["doc_paragraphs"])}


_POLICIES = {
    "vision": _policy_vision,
    "temporal": _policy_temporal,
    "signoff": _policy_signoff,
    "verify": _policy_verify,
    "plan_compile": _policy_plan,
}
