"""Reinforcement learning over human adjudications - audit-safe by construction.

The reinforcement signal is real: every human adjudication is a reward
(agreement with IQR's verdict -> 1, override -> 0). What it updates is NOT
model weights - it updates a Beta-Bernoulli posterior per (control, check):
transparent counts anyone can read, version, and revoke. This is the bandit
family of reinforcement learning, chosen deliberately over gradient methods:

  - the posterior is inspectable (alpha = times humans agreed, beta = times
    humans overrode) where a weight update is opaque;
  - it learns from the handful of expert adjudications a period actually
    produces, where policy-gradient methods need millions;
  - verdicts stay untouched. Learning changes CONFIDENCE and REVIEW PRIORITY:
    low-confidence checks surface first in the exception queue, high-confidence
    checks earn their way toward Assist/Primary graduation. The verdict itself
    is always tools + citations + verifier, never a learned score.

State is a plain JSON document under the knowledge store (mirrored to the
cloud knowledge container alongside the Golden Library). Updates run offline
(`python -m iqr.cli learn`), are idempotent over the adjudication journal, and
ship through the same release discipline as everything else - the eval gates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from iqr import config

# Prior: one phantom agreement and one phantom override - new checks start at
# 0.5 confidence and maximum review priority, i.e. "not yet trusted".
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0


def _state_path():
    return config.KNOWLEDGE_DIR / "reinforce_state.json"


@dataclass
class Posterior:
    alpha: float   # human agreed with IQR
    beta: float    # human overrode IQR

    @property
    def confidence(self) -> float:
        """Posterior mean: earned agreement rate."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def uncertainty(self) -> float:
        """Posterior variance: how little evidence backs the confidence."""
        n = self.alpha + self.beta
        return (self.alpha * self.beta) / (n * n * (n + 1))

    @property
    def observations(self) -> int:
        return int(self.alpha + self.beta - PRIOR_ALPHA - PRIOR_BETA)


class ReinforcementState:
    def __init__(self):
        config.ensure_dirs()
        self.path = _state_path()
        raw = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.arms: dict[str, dict] = raw.get("arms", {})
        self.applied: set[str] = set(raw.get("applied", []))

    @staticmethod
    def key(control_id: str, check_id: str) -> str:
        return f"{control_id}/{check_id}"

    def posterior(self, control_id: str, check_id: str) -> Posterior:
        arm = self.arms.get(self.key(control_id, check_id),
                            {"alpha": PRIOR_ALPHA, "beta": PRIOR_BETA})
        return Posterior(arm["alpha"], arm["beta"])

    def update(self, control_id: str, check_id: str, agreed: bool,
               event_id: str) -> bool:
        """Apply one adjudication reward. Idempotent per event_id."""
        if event_id in self.applied:
            return False
        k = self.key(control_id, check_id)
        arm = self.arms.setdefault(k, {"alpha": PRIOR_ALPHA, "beta": PRIOR_BETA})
        arm["alpha" if agreed else "beta"] += 1.0
        self.applied.add(event_id)
        return True

    def save(self) -> None:
        self.path.write_text(json.dumps(
            {"arms": self.arms, "applied": sorted(self.applied),
             "updated_at": datetime.now(timezone.utc).isoformat()}, indent=2))

    def review_priorities(self) -> list[dict]:
        """Exception-queue ordering: most uncertain first - the checks where a
        human's judgment buys the most learning."""
        rows = []
        for k, arm in self.arms.items():
            p = Posterior(arm["alpha"], arm["beta"])
            control_id, _, check_id = k.partition("/")
            rows.append({"control_id": control_id, "check_id": check_id,
                         "confidence": round(p.confidence, 4),
                         "uncertainty": round(p.uncertainty, 6),
                         "observations": p.observations})
        rows.sort(key=lambda r: (-r["uncertainty"], r["control_id"], r["check_id"]))
        return rows


def learn_from_adjudications() -> dict:
    """Offline learning pass: fold every recorded human adjudication into the
    posteriors. The reward compares the human's verdict to what IQR concluded
    (recorded with the adjudication). Re-running is a no-op - idempotent."""
    from iqr.knowledge.golden_library import GoldenLibrary
    state = ReinforcementState()
    applied = 0
    for ex in GoldenLibrary().pending_overrides():
        event_id = f"{ex['control_id']}/{ex['check_id']}/{ex['run_id']}"
        agreed = ex.get("human_verdict") == ex.get("iqr_verdict", ex.get("human_verdict"))
        if state.update(ex["control_id"], ex["check_id"], agreed, event_id):
            applied += 1
    state.save()
    return {"applied": applied, "arms": len(state.arms),
            "priorities": state.review_priorities()}
