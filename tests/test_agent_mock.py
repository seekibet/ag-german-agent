"""End-to-end pipeline test, fully offline via the deterministic mock client."""
import json
import os

from src.agent import FAQAgent
from src.llm_client import MockClient


def make_agent(top_k=3):
    return FAQAgent(top_k=top_k, client=MockClient())


def test_full_pipeline_offline():
    t = make_agent().answer("How do I apply for the nursing apprenticeship via SGAO?")
    res = t["result"]
    assert res["category"] == "APPRENTICESHIP"
    assert "SOP_002" in res["retrieved_sops"]
    assert len(res["answer"]) > 50
    assert os.path.exists(t["trace_path"])
    with open(t["trace_path"]) as f:
        saved = json.load(f)
    assert [s["step"] for s in saved["steps"]] == ["categorize", "retrieve", "generate"]


def test_mock_is_deterministic():
    a1 = make_agent().answer("What scholarships exist for DAAD STEM?")["result"]
    a2 = make_agent().answer("What scholarships exist for DAAD STEM?")["result"]
    assert a1["category"] == a2["category"]
    assert a1["retrieved_sops"] == a2["retrieved_sops"]
    assert a1["answer"] == a2["answer"]


def test_trace_records_config_and_prompt_versions():
    t = make_agent(top_k=5).answer("first steps after arriving in Germany?")
    assert t["config"]["top_k"] == 5
    assert t["config"]["prompts"]["generate"].startswith("generate_v")
