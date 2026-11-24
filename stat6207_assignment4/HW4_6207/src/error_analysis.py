"""Build a compact error-analysis table for the LOPO retrieval results."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "outputs" / "metrics"
RET = ROOT / "outputs" / "retrieval"
CLUSTERS = ROOT / "outputs" / "clusters"
GT = ROOT / "data" / "processed" / "ground_truth.json"


def load_terms():
    terms = {}
    for line in (CLUSTERS / "doc_terms.jsonl").open(encoding="utf-8"):
        o = json.loads(line)
        terms[o["doc_id"]] = {x["term"]: x["importance"] for x in o["terms"]}
    return terms


def main() -> None:
    metrics = json.loads((METRICS / "metrics.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((RET / "per_query.csv").open(encoding="utf-8")))
    terms = load_terms()
    pairs = {p["pair_id"]: p for p in json.loads(GT.read_text(encoding="utf-8"))["pairs"]}

    lopo = [r for r in rows if r["method"] == "ae_supervised_lopo"]
    out = []
    for r in lopo:
        p = pairs[r["pair_id"]]
        jd_terms = terms.get(p["jd_id"], {})
        pos_terms = terms.get(p["cv_id"], {})
        top_ids = r["top10"].split("|")
        top1 = top_ids[0] if top_ids else ""
        top1_terms = terms.get(top1, {})
        jd_set = set(jd_terms)
        pos_set = set(pos_terms)
        top1_set = set(top1_terms)
        missing = sorted(
            [t for t in jd_set - pos_set],
            key=lambda t: -jd_terms.get(t, 0),
        )[:8]
        out.append(
            {
                "pair_id": r["pair_id"],
                "jd_id": p["jd_id"],
                "role_title": p.get("role_title", ""),
                "cv_id": p["cv_id"],
                "rank": int(r["rank"]),
                "hit@10": int(r["recall@10"]),
                "top1": top1,
                "jd_terms": sorted(jd_set, key=lambda t: -jd_terms.get(t, 0))[:12],
                "positive_terms": sorted(pos_set, key=lambda t: -pos_terms.get(t, 0))[:12],
                "top1_terms": sorted(top1_set, key=lambda t: -top1_terms.get(t, 0))[:12],
                "overlap_jd_positive": sorted(jd_set & pos_set),
                "overlap_jd_top1": sorted(jd_set & top1_set),
                "missing_from_positive": missing,
            }
        )

    (METRICS / "error_analysis.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = ["# LOPO error analysis", ""]
    for o in out:
        lines.append(
            f"## {o['pair_id']} · {o['role_title']} — rank {o['rank']} "
            f"({'hit' if o['hit@10'] else 'miss'})"
        )
        lines.append(
            f"- JD: {o['jd_id']} ({o['role_title']}); positive: {o['cv_id']}; top1: {o['top1']}"
        )
        lines.append(f"- JD terms: {', '.join(o['jd_terms'])}")
        lines.append(f"- positive terms: {', '.join(o['positive_terms'])}")
        lines.append(f"- top1 terms: {', '.join(o['top1_terms'])}")
        lines.append(f"- JD∩positive: {', '.join(o['overlap_jd_positive'])}")
        lines.append(f"- JD∩top1: {', '.join(o['overlap_jd_top1'])}")
        lines.append(f"- missing from positive: {', '.join(o['missing_from_positive'])}")
        lines.append("")
    (METRICS / "error_analysis.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(out)} rows")
    for o in out:
        print(f"{o['pair_id']}: rank={o['rank']:3d} hit={o['hit@10']} top1={o['top1']}")


if __name__ == "__main__":
    main()
