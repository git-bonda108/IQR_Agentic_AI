"""The tool-using agent loop.

An agent = the approved model driving a registry of deterministic tools.
The model reasons about WHERE the answer is and WHAT it means; every number,
timestamp, and text extraction comes back from a tool with a Citation.
The runtime (not the model) accumulates citations and tool outputs, so a
Finding's computed_values can only contain tool-produced facts.

In production the same loop is what the OpenAI Agents SDK executes with
DaVinci; offline the StubModelClient plays the policy deterministically.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from iqr import config
from iqr.ledger import RunLedger
from iqr.schemas.finding import Citation

SYSTEM_PROMPT = """You are a SOX control validation agent. You may ONLY obtain
facts by calling the tools listed below - never invent a number, timestamp, or
quotation. Respond with exactly one JSON object per turn:
  {"action": "tool", "tool": "<name>", "args": {...}}   to call a tool
  {"action": "final", "output": {...}}                   to conclude
The value of "action" MUST be exactly "tool" or "final" - never a tool's name.
Pass ONLY the arguments a tool's description asks for (many take none: use
"args": {}). Output the raw JSON object only - no markdown fences, no prose.
Results of YOUR prior tool calls appear in STATE_JSON under "observations" -
read them first, never repeat a call whose result is already there, and
respond with "final" as soon as the observations answer the task.
Available tools:
"""


@dataclass
class ToolSpec:
    name: str
    description: str
    fn: Callable[..., dict]   # returns {"value": ..., "citations": [Citation-dicts]} or {"error": ...}


@dataclass
class AgentRun:
    final: dict
    observations: list[dict] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    steps: int = 0


class AgentError(Exception):
    pass


def _parse_action(raw: str, tool_names: set[str]) -> dict:
    """Parse the model's action JSON, tolerating real-model quirks without
    weakening the protocol: markdown fences or trailing prose around the
    object, and the `{"action": "<tool-name>"}` shorthand. Anything else
    still fails loudly - lenient reading, never lenient semantics."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start = text.find("{")
    if start < 0:
        raise AgentError(f"model returned non-JSON action: {raw[:200]}")
    try:
        action, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as e:
        raise AgentError(f"model returned non-JSON action: {raw[:200]}") from e
    name = action.get("action")
    if name not in ("tool", "final") and (name in tool_names or "tool" in action):
        action = {**action, "action": "tool", "tool": action.get("tool", name)}
    return action


def run_agent(task: str, context: dict, tools: list[ToolSpec],
              ledger: RunLedger | None = None,
              max_steps: int = config.AGENT_MAX_STEPS,
              output_spec: str = "",
              seed_observations: list[dict] | None = None,
              seed_citations: list[Citation] | None = None) -> AgentRun:
    """seed_observations: tool results the check node computed deterministically
    up front (plan-pinned locators leave the agent nothing to decide there).
    Seeding shortens the tool chain, which is both cheaper and less variant."""
    model = config.get_model_client(seat=context.get("task_type"))
    registry = {t.name: t for t in tools}
    # The exact argument names come from the function itself - a model must
    # never have to guess a signature.
    def _sig(t: ToolSpec) -> str:
        import inspect
        try:
            params = ", ".join(inspect.signature(t.fn).parameters)
        except (TypeError, ValueError):
            params = ""
        return f"- {t.name}({params}): {t.description}"
    system = SYSTEM_PROMPT + "\n".join(_sig(t) for t in tools)
    if output_spec:
        system += ("\nWhen you conclude, the \"output\" object MUST have exactly "
                   f"this shape: {output_spec}")
    observations: list[dict] = list(seed_observations or [])
    citations: list[Citation] = list(seed_citations or [])

    for step in range(max_steps):
        state = {"task": task, "context": context, "observations": observations}
        user = f"TASK: {task}\nSTATE_JSON: {json.dumps(state, default=str)}"
        raw = model.complete(system, user)
        action = _parse_action(raw, set(registry))

        if action.get("action") == "final":
            if ledger:
                ledger.log("agent_final", task=task, steps=step + 1,
                           model=getattr(model, "last_served", "") or model.name,
                           output=action.get("output"))
            return AgentRun(final=action.get("output", {}), observations=observations,
                            citations=citations, steps=step + 1)

        tool_name = action.get("tool", "")
        spec = registry.get(tool_name)
        if spec is None:
            observations.append({"tool": tool_name, "args": action.get("args", {}),
                                 "result": {"error": f"unknown tool {tool_name}"}})
            continue
        args = action.get("args", {})
        # Deterministic loop-breaker: an identical successful call is never
        # re-executed - the model is told to conclude from what it has.
        if any(o["tool"] == tool_name and o["args"] == args
               and "error" not in o["result"] for o in observations):
            observations.append({"tool": tool_name, "args": args,
                                 "result": {"error": "duplicate call: this exact result is "
                                            "already in observations - respond with your "
                                            "final conclusion now"}})
            continue
        try:
            result = spec.fn(**args)
        except Exception as e:
            result = {"error": f"{type(e).__name__}: {e}"}
        for c in result.get("citations", []):
            citations.append(Citation.model_validate(c) if isinstance(c, dict) else c)
        # observations hold JSON-safe copies; citations stay typed on the side
        safe = {k: v for k, v in result.items() if k != "citations"}
        observations.append({"tool": tool_name, "args": args, "result": safe})
        if ledger:
            ledger.log("tool_call", task=task, tool=tool_name, args=args,
                       result=json.loads(json.dumps(safe, default=str)))
    raise AgentError(f"agent exceeded {max_steps} steps on task: {task}")
