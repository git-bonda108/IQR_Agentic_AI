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


def run_agent(task: str, context: dict, tools: list[ToolSpec],
              ledger: RunLedger | None = None,
              max_steps: int = config.AGENT_MAX_STEPS) -> AgentRun:
    model = config.get_model_client()
    registry = {t.name: t for t in tools}
    system = SYSTEM_PROMPT + "\n".join(f"- {t.name}: {t.description}" for t in tools)
    observations: list[dict] = []
    citations: list[Citation] = []

    for step in range(max_steps):
        state = {"task": task, "context": context, "observations": observations}
        user = f"TASK: {task}\nSTATE_JSON: {json.dumps(state, default=str)}"
        raw = model.complete(system, user)
        try:
            action = json.loads(raw)
        except json.JSONDecodeError as e:
            raise AgentError(f"model returned non-JSON action: {raw[:200]}") from e

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
