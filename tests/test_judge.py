from src.judge import Judge
from src.llm_client import JUDGE_MODEL, MockClient


def test_judge_uses_pinned_model_and_versioned_rubric():
    j = Judge(client=MockClient())
    assert j.model == JUDGE_MODEL                  # pinned, not agent model
    assert j.rubric_version == "judge_rubric_v1.txt"


def test_judge_returns_valid_verdict():
    j = Judge(client=MockClient())
    v = j.judge("What is DAAD?", "DAAD is the German Academic Exchange Service.",
                "DAAD", "B2 required")
    assert v["verdict"] in ("good", "partial", "bad")
    assert v["judge_model"] == JUDGE_MODEL


def test_judge_is_deterministic():
    j = Judge(client=MockClient())
    v1 = j.judge("Q", "A", "F", "P")
    v2 = j.judge("Q", "A", "F", "P")
    assert v1["verdict"] == v2["verdict"]
