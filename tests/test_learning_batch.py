"""Batch eval scoring + the reinforcement learner - offline, hermetic."""
from iqr.eval.batch import confidence_level, run_eval_batch
from iqr.learn.reinforce import (PRIOR_ALPHA, PRIOR_BETA, ReinforcementState,
                                 learn_from_adjudications)


def test_batch_eval_scores_and_confidence(plans, fixtures_root):
    report = run_eval_batch(plans, fixtures_root, n=2)
    assert report.runs == 2
    assert report.batch_gates_passed          # stub model: perfectly stable
    for gate, s in report.gate_scores.items():
        assert s["min"] <= s["mean"] <= s["max"], gate
    # every clean check is fully stable across the batch -> HIGH confidence
    assert report.check_confidence
    for key, c in report.check_confidence.items():
        assert c["stability"] == 1.0 and c["level"] == "HIGH", key


def test_confidence_bands():
    assert confidence_level(1.0) == "HIGH"
    assert confidence_level(0.85) == "MEDIUM"
    assert confidence_level(0.5) == "LOW"


def test_reinforcement_posterior_updates_and_idempotency(tmp_path, monkeypatch):
    from iqr import config
    monkeypatch.setattr(config, "KNOWLEDGE_DIR", tmp_path)
    st = ReinforcementState()
    # fresh check: uninformative prior -> 0.5 confidence, "not yet trusted"
    p0 = st.posterior("C1", "n1")
    assert p0.confidence == PRIOR_ALPHA / (PRIOR_ALPHA + PRIOR_BETA) == 0.5
    # three agreements, one override
    for i, agreed in enumerate([True, True, True, False]):
        assert st.update("C1", "n1", agreed, f"ev{i}")
    assert not st.update("C1", "n1", True, "ev0")     # idempotent per event
    st.save()
    p = ReinforcementState().posterior("C1", "n1")    # survives reload
    assert p.confidence == (1 + 3) / (1 + 3 + 1 + 1)  # (prior+3)/(total)
    assert p.observations == 4


def test_learning_reward_comes_from_agreement(tmp_path, monkeypatch):
    """Adjudications where the human overrides IQR lower confidence; agreement
    raises it - and the learner never touches verdicts, only posteriors."""
    from iqr import config
    monkeypatch.setattr(config, "KNOWLEDGE_DIR", tmp_path)
    from iqr.knowledge.golden_library import GoldenLibrary
    gl = GoldenLibrary()
    gl.record_adjudication("C9", "t1", "tz ordering", "pass", "ok", "r1",
                           iqr_verdict="pass")     # agreement
    gl.record_adjudication("C9", "t1", "tz ordering", "pass", "stamp fine", "r2",
                           iqr_verdict="fail")     # human overrode IQR
    result = learn_from_adjudications()
    assert result["applied"] == 2
    p = ReinforcementState().posterior("C9", "t1")
    assert p.alpha == PRIOR_ALPHA + 1 and p.beta == PRIOR_BETA + 1
    # most-uncertain-first priority listing exists for the console
    assert result["priorities"][0]["control_id"] == "C9"
    assert learn_from_adjudications()["applied"] == 0   # idempotent pass
