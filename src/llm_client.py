"""LLM client abstraction: real Anthropic client or deterministic mock.

The mock makes the ENTIRE pipeline (agent, judge, eval, CI) runnable offline
with zero API keys. Determinism: responses are pure functions of the prompt.
"""
import hashlib
import json
import os
import re

try:
    from dotenv import load_dotenv
    load_dotenv()          # reads .env from the current working directory
except ImportError:
    pass                   # dotenv not installed — rely on shell environment


AGENT_MODEL = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-haiku-4-5-20251001")  # pinned

_CATEGORY_KEYWORDS = {
    "SCHOLARSHIP": ["scholarship", "daad", "kas", "ips", "solitude", "stipend",
                    "fellowship", "green talents", "bundestag"],
    "APPRENTICESHIP": ["nursing", "apprenticeship", "ausbildung", "sgao", "kcse c "],
    "STUDY": ["study", "enroll", "university", "degree", "uni-assist", "anabin",
              "recognis", "recognize", "kcse", "block account", "master"],
    "SETTLEMENT": ["arriv", "anmeldung", "register", "bank account", "steuer",
                   "first steps", "first weeks", "settling"],
    "BUSINESS": ["widu", "invest", "business", "real estate", "freelanc",
                 "self-employ", "entrepreneur"],
    "JOB": ["job", "employment", "hiring", "career path", "labour mobility",
            "basf", "internship", "work in germany"],
    "EVENT": ["event", "meetup", "networking", "meet-up", "career fair"],
}


class MockClient:
    """Deterministic offline stand-in for the Anthropic client."""

    class _Msg:
        def __init__(self, text):
            self.content = [type("Block", (), {"text": text})()]

    def _categorize(self, prompt: str) -> str:
        q = re.search(r'Question:\s*"(.*?)"', prompt, re.S)
        question = (q.group(1) if q else prompt).lower()
        scores = {cat: sum(1 for kw in kws if kw in question)
                  for cat, kws in _CATEGORY_KEYWORDS.items()}
        best = max(scores, key=lambda c: (scores[c], c))
        return best if scores[best] > 0 else "GENERAL"

    def _generate(self, prompt: str) -> str:
        """Echo distinctive fact tokens from the retrieved context so that
        grounding/coverage metrics behave realistically offline."""
        ctx = re.search(r"Retrieved SOP Knowledge:\s*(.*?)\*\*Instructions",
                        prompt, re.S)
        context = ctx.group(1) if ctx else prompt
        facts = re.findall(r"€[\d,]+|\b[A-Z]{2,6}\b|\b\d{4}\b|https?://\S+",
                           context)
        seen, uniq = set(), []
        for f in facts:
            if f not in seen:
                seen.add(f)
                uniq.append(f)
        fact_str = ", ".join(uniq[:25])
        return (
            "Here is a direct answer based on the retrieved SOPs.\n"
            f"- Key facts: {fact_str}\n"
            "- All amounts and deadlines should be verified at the official "
            "source (verify current status at the official source).\n"
            "Next step: visit https://www.ag-careerhub.com for guidance."
        )

    def _judge(self, prompt: str) -> str:
        # Deterministic verdict from prompt hash; biased toward "good".
        h = int(hashlib.sha256(prompt.encode()).hexdigest(), 16) % 10
        verdict = "good" if h < 7 else ("partial" if h < 9 else "bad")
        return json.dumps({"verdict": verdict, "reason": "mock deterministic verdict"})

    @property
    def messages(self):
        outer = self

        class _Messages:
            def create(self, model, max_tokens, messages):
                prompt = messages[0]["content"]
                if "Reply with ONLY the category name" in prompt:
                    text = outer._categorize(prompt)
                elif "evaluation judge" in prompt:
                    text = outer._judge(prompt)
                else:
                    text = outer._generate(prompt)
                return MockClient._Msg(text)

        return _Messages()


def get_client():
    """Return real Anthropic client if API key present, else MockClient."""
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if key:
        import anthropic
        return anthropic.Anthropic(api_key=key), False
    return MockClient(), True
