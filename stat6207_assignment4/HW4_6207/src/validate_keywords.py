"""Validate the LLM keyword profiles and print coverage statistics."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS = ROOT / "outputs" / "keywords" / "all_keywords.jsonl"
OUT = ROOT / "outputs" / "metrics"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    docs = [json.loads(line) for line in KEYWORDS.open(encoding="utf-8")]
    expected = [
        json.loads(line)["doc_id"]
        for line in (ROOT / "data" / "processed" / "documents.jsonl").open(encoding="utf-8")
    ]
    ids = [d.get("doc_id") for d in docs]
    dup = [k for k, v in Counter(ids).items() if v > 1]
    cats = Counter()
    bad = []
    counts = []
    for d in docs:
        kws = d.get("keywords", [])
        counts.append(len(kws))
        if not kws:
            bad.append(d.get("doc_id"))
        for k in kws:
            cats[k.get("category", "MISSING")] += 1
            if not k.get("term") or k.get("importance") not in (1, 2, 3):
                bad.append(d.get("doc_id"))
                break
    summary = {
        "documents": len(docs),
        "unique_ids": len(set(ids)),
        "duplicates": dup,
        "missing_documents": sorted(set(expected) - set(ids)),
        "documents_without_keywords": sorted(set(bad)),
        "keyword_count": {
            "min": min(counts),
            "max": max(counts),
            "mean": round(sum(counts) / len(counts), 2),
        },
        "categories": dict(cats.most_common()),
    }
    (OUT / "keyword_validation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
