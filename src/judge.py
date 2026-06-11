"""LLM-as-judge. Uses a PINNED judge model (JUDGE_MODEL) deliberately distinct
from the agent model, with a versioned rubric prompt in prompts/.

Pinning the judge means eval scores stay comparable across agent upgrades.
"""
import json
import os
import re

from src.llm_client import JUDGE_MODEL, get_client


class Judge:
    def __init__(self, rubric: str = "judge_rubric_v1.txt",
                 model: str = JUDGE_MODEL, client=None):
        self.client, self.is_mock = (client, False) if client else get_client()
        self.model = model
        self.rubric_version = rubric
        with open(os.path.join("prompts", rubric), encoding="utf-8") as f:
            self.rubric_tpl = f.read()

    def judge(self, question: str, answer: str,
              key_facts: str = "", policy_details: str = "") -> dict:
        prompt = self.rubric_tpl.format(
            question=question, answer=answer,
            key_facts=key_facts, policy_details=policy_details)
        msg = self.client.messages.create(
            model=self.model, max_tokens=200,
            messages=[{"role": "user", "content": prompt}])
        text = msg.content[0].text.strip()
        m = re.search(r"\{.*\}", text, re.S)
        try:
            out = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            out = {}
        verdict = out.get("verdict", "bad")
        if verdict not in ("good", "partial", "bad"):
            verdict = "bad"
        return {"verdict": verdict,
                "reason": out.get("reason", "unparseable judge output"),
                "judge_model": self.model,
                "rubric_version": self.rubric_version}
