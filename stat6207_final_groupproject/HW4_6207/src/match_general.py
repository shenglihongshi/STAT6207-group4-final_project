"""Train an unsupervised AE on the general corpus and rank all CVs for every JD.

Inputs are produced by parse_general.py + extract_keywords.py + cluster_keywords.py.
Optional ground_truth.csv enables Recall@10; without it the script still writes
rankings.csv / rankings.md.

Usage:
  python src/match_general.py
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from train_eval import AutoEncoder  # noqa: E402

DOCS = ROOT / "data" / "general" / "processed" / "documents.jsonl"
CLUSTERS = ROOT / "outputs" / "general" / "clusters"
OUT = ROOT / "outputs" / "general"
MODELS = OUT / "models"
OUT.mkdir(parents=True, exist_ok=True)
MODELS.mkdir(parents=True, exist_ok=True)

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)


def encode(model, X):
    model.eval()
    with torch.no_grad():
        z = model.encoder(torch.tensor(X, dtype=torch.float32))
        return F.normalize(z, dim=1).numpy()


def train_ae(X, epochs=80, bottleneck=32):
    model = AutoEncoder(X.shape[1], hidden=512, bottleneck=bottleneck)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    data = torch.tensor(X, dtype=torch.float32)
    for epoch in range(epochs):
        model.train()
        opt.zero_grad()
        mask = (torch.rand_like(data) > 0.10).float()
        x_hat, _ = model(data * mask)
        loss = F.mse_loss(x_hat, data)
        loss.backward()
        opt.step()
        if epoch % 20 == 0 or epoch == epochs - 1:
            print(f"  epoch {epoch:03d} recon={loss.item():.5f}", flush=True)
    return model


def load_gt(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            jd = (row.get("jd_id") or row.get("jd_file") or "").strip()
            cv = (row.get("cv_id") or row.get("cv_file") or "").strip()
            if jd and cv:
                rows.append((jd, cv))
    return rows


def resolve_gt(gt_rows, docs):
    by_id = {d["doc_id"]: d for d in docs}
    by_file = {d["source_file"]: d for d in docs}
    by_stem = {Path(d["source_file"]).stem: d for d in docs}
    out = []
    for jd, cv in gt_rows:
        jd_doc = by_id.get(jd) or by_file.get(jd) or by_stem.get(Path(jd).stem)
        cv_doc = by_id.get(cv) or by_file.get(cv) or by_stem.get(Path(cv).stem)
        if jd_doc and cv_doc:
            out.append((jd_doc["doc_id"], cv_doc["doc_id"]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--bottleneck", type=int, default=32)
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--gt", default=str(ROOT / "data" / "input" / "ground_truth.csv"))
    args = ap.parse_args()

    docs = [json.loads(line) for line in DOCS.open(encoding="utf-8")]
    doc_ids = json.loads((CLUSTERS / "doc_ids.json").read_text(encoding="utf-8"))
    X = np.load(CLUSTERS / "doc_term_tfidf.npy").astype(np.float32)
    terms = {}
    for line in (CLUSTERS / "doc_terms.jsonl").open(encoding="utf-8"):
        o = json.loads(line)
        terms[o["doc_id"]] = {x["term"]: x["importance"] for x in o["terms"]}

    by_id = {d["doc_id"]: d for d in docs}
    jd_ids = [d["doc_id"] for d in docs if d["doc_type"] == "jd"]
    cv_ids = [d["doc_id"] for d in docs if d["doc_type"] == "cv"]
    if not jd_ids or not cv_ids:
        raise SystemExit("Need at least one JD and one CV in data/input.")

    print(f"JDs={len(jd_ids)} CVs={len(cv_ids)} docs={len(doc_ids)} V={X.shape[1]}")
    model = train_ae(X, epochs=args.epochs, bottleneck=args.bottleneck)
    Z = encode(model, X)
    pos = {d: i for i, d in enumerate(doc_ids)}

    torch.save(model.state_dict(), MODELS / "ae_general.pt")
    np.savez(MODELS / "doc_embeddings.npz", doc_ids=np.array(doc_ids), embeddings=Z)

    rows = []
    md = ["# CV–JD matching results", ""]
    for jd_id in jd_ids:
        jd_doc = by_id[jd_id]
        scores = Z[[pos[c] for c in cv_ids]] @ Z[pos[jd_id]]
        order = np.argsort(-scores)[: args.topk]
        jd_terms = terms.get(jd_id, {})
        md.append(f"## {jd_doc.get('role_title') or jd_doc.get('title') or jd_id}")
        md.append("")
        md.append("| Rank | CV | Score | Shared keywords |")
        md.append("|---:|---|---:|---|")
        for rank, idx in enumerate(order, 1):
            cv_id = cv_ids[int(idx)]
            cv_doc = by_id[cv_id]
            cv_terms = terms.get(cv_id, {})
            shared = sorted(
                set(jd_terms) & set(cv_terms),
                key=lambda t: (-jd_terms.get(t, 0), t),
            )[:8]
            rows.append(
                {
                    "jd_id": jd_id,
                    "jd_title": jd_doc.get("role_title") or jd_doc.get("title") or jd_id,
                    "rank": rank,
                    "cv_id": cv_id,
                    "cv_title": cv_doc.get("title") or cv_doc.get("source_file") or cv_id,
                    "score": float(scores[int(idx)]),
                    "shared_keywords": ", ".join(shared),
                }
            )
            md.append(
                f"| {rank} | {cv_doc.get('title') or cv_id} | {scores[int(idx)]:.3f} | "
                f"{', '.join(shared)} |"
            )
        md.append("")

    with (OUT / "rankings.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["jd_id", "jd_title", "rank", "cv_id", "cv_title", "score", "shared_keywords"],
        )
        w.writeheader()
        w.writerows(rows)
    (OUT / "rankings.md").write_text("\n".join(md), encoding="utf-8")

    # optional evaluation
    gt_rows = resolve_gt(load_gt(Path(args.gt)), docs)
    if gt_rows:
        top = {}
        for r in rows:
            top.setdefault(r["jd_id"], []).append(r)
        for k in top:
            top[k] = sorted(top[k], key=lambda x: x["rank"])[: args.topk]
        hits = 0
        for jd_id, cv_id in gt_rows:
            hit = any(r["cv_id"] == cv_id for r in top.get(jd_id, []))
            hits += int(hit)
        metrics = {
            "queries": len(gt_rows),
            "recall@10": hits / len(gt_rows),
            "hits@10": hits,
        }
        (OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"optional evaluation: Recall@10={metrics['recall@10']:.3f} ({hits}/{len(gt_rows)})")
    else:
        print("no ground_truth.csv; skipped Recall evaluation")

    print(f"rankings: {OUT / 'rankings.csv'}")
    print(f"markdown: {OUT / 'rankings.md'}")


if __name__ == "__main__":
    main()
