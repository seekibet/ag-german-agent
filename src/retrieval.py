"""BM25 retrieval over the SOP knowledge base."""
import glob
import os
import re
from typing import Dict, List, Tuple

from rank_bm25 import BM25Okapi


def normalize_sop_name(s: str) -> str:
    """'sop-001' / 'SOP_1' / 'SOP_01' -> 'SOP_001'."""
    s = str(s).strip().upper().replace("SOP-", "SOP_")
    m = re.search(r"SOP_(\d+)", s)
    return f"SOP_{int(m.group(1)):03d}" if m else s


def load_sops(sops_dir: str = "data/sops") -> Dict:
    sops = {}
    files = sorted(glob.glob(os.path.join(sops_dir, "sop_*.txt")))
    if not files:
        raise FileNotFoundError(f"No SOPs found in {sops_dir}/")
    for fp in files:
        num = os.path.basename(fp).split("_")[1]
        sop_id = f"SOP_{num}"
        with open(fp, encoding="utf-8") as f:
            content = f.read()
        title = next(l.strip() for l in content.splitlines() if l.strip())
        sops[sop_id] = {"title": title, "content": content}
    return sops


class BM25Retriever:
    def __init__(self, sops_db: Dict):
        self.sops_db = sops_db
        self.sop_ids = list(sops_db.keys())
        corpus = []
        for sid in self.sop_ids:
            s = sops_db[sid]
            combined = f"{s['title']} {s['title']} {s['title']} {s['content']}"
            corpus.append(combined.lower().split())
        self.bm25 = BM25Okapi(corpus)

    def retrieve(self, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
        scores = self.bm25.get_scores(query.lower().split())
        idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(self.sop_ids[i], float(scores[i])) for i in idx]
