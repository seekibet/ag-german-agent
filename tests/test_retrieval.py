from src.retrieval import BM25Retriever, load_sops, normalize_sop_name


def test_normalize_variants():
    for v in ["SOP_001", "sop-001", "SOP_1", "sop_01"]:
        assert normalize_sop_name(v) == "SOP_001"


def test_load_all_nine_sops():
    sops = load_sops("data/sops")
    assert len(sops) == 9
    assert "SOP_001" in sops and "SOP_009" in sops


def test_bm25_finds_obvious_sop():
    sops = load_sops("data/sops")
    r = BM25Retriever(sops)
    hits = [sid for sid, _ in r.retrieve("nursing apprenticeship SGAO KCSE", 3)]
    assert "SOP_002" in hits
    hits = [sid for sid, _ in r.retrieve("WIDU africa grant diaspora investment", 3)]
    assert "SOP_005" in hits
