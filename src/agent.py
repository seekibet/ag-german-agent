"""Multi-step FAQ planner: categorize -> retrieve -> generate.

Prompts are versioned files in prompts/ — the agent never hardcodes prompt text.
Every run emits a full JSON trace via src.tracing.
"""
import os

from src.llm_client import AGENT_MODEL, get_client
from src.retrieval import BM25Retriever, load_sops
from src.tracing import Tracer

CATEGORIES = ["SCHOLARSHIP", "JOB", "APPRENTICESHIP", "STUDY",
              "SETTLEMENT", "BUSINESS", "EVENT", "GENERAL"]


def load_prompt(name: str) -> str:
    with open(os.path.join("prompts", name), encoding="utf-8") as f:
        return f.read()


class FAQAgent:
    def __init__(self, top_k: int = 3,
                 categorize_prompt: str = "categorize_v1.txt",
                 generate_prompt: str = "generate_v2.txt",
                 model: str = AGENT_MODEL,
                 sops_dir: str = "data/sops",
                 client=None):
        self.client, self.is_mock = (client, False) if client else get_client()
        self.model = model
        self.top_k = top_k
        self.categorize_tpl = load_prompt(categorize_prompt)
        self.generate_tpl = load_prompt(generate_prompt)
        self.prompt_versions = {"categorize": categorize_prompt,
                                "generate": generate_prompt}
        self.sops_db = load_sops(sops_dir)
        self.retriever = BM25Retriever(self.sops_db)
        self.tracer = Tracer()

    def _call(self, prompt: str, max_tokens: int) -> str:
        msg = self.client.messages.create(
            model=self.model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text.strip()

    def answer(self, question: str) -> dict:
        trace = self.tracer.new_trace(question)
        trace["config"] = {"model": self.model, "top_k": self.top_k,
                           "prompts": self.prompt_versions,
                           "mock": self.is_mock}

        # Step 1 — categorize
        cat_prompt = self.categorize_tpl.format(question=question)
        category = self._call(cat_prompt, 20).upper()
        if category not in CATEGORIES:
            category = "GENERAL"
        self.tracer.log_step(trace, "categorize", category=category)

        # Step 2 — retrieve
        hits = self.retriever.retrieve(f"{question} {category.lower()}", self.top_k)
        retrieved = [{"sop_id": sid, "score": round(sc, 3),
                      "title": self.sops_db[sid]["title"]} for sid, sc in hits]
        self.tracer.log_step(trace, "retrieve", retrieved=retrieved)

        # Step 3 — generate
        context = "\n\n".join(
            f"--- {sid}: {self.sops_db[sid]['title']} ---\n"
            f"{self.sops_db[sid]['content'][:2500]}"
            for sid, _ in hits)
        gen_prompt = self.generate_tpl.format(
            question=question, category=category, context=context)
        answer = self._call(gen_prompt, 1000)
        self.tracer.log_step(trace, "generate", answer=answer)

        trace["result"] = {
            "category": category,
            "retrieved_sops": [r["sop_id"] for r in retrieved],
            "retrieved_context": context,
            "answer": answer,
        }
        trace_path = self.tracer.save(trace)
        trace["trace_path"] = trace_path
        return trace


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or \
        "What scholarships are available for studying in Germany?"
    t = FAQAgent().answer(q)
    print(f"[{t['result']['category']}] SOPs={t['result']['retrieved_sops']}")
    print(t["result"]["answer"])
    print(f"\ntrace -> {t['trace_path']}")
