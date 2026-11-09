"""Train the autoencoder and evaluate top-10 retrieval.

Modes:
  baselines  -- TF-IDF cosine, keyword-overlap cosine, BM25 (no training)
  in_sample  -- train on all 10 GT pairs, evaluate the same 10 (upper bound)
  lopo       -- leave-one-pair-out, 10 folds (primary, fair estimate)
  all        -- baselines + in_sample + lopo
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
CLUSTERS = ROOT / "outputs" / "clusters"
GT = ROOT / "data" / "processed" / "ground_truth.json"
OUT_METRICS = ROOT / "outputs" / "metrics"
OUT_RET = ROOT / "outputs" / "retrieval"
OUT_MODELS = ROOT / "outputs" / "models"
for p in (OUT_METRICS, OUT_RET, OUT_MODELS):
    p.mkdir(parents=True, exist_ok=True)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

K = 10


class AutoEncoder(nn.Module):
    def __init__(self, input_dim: int, hidden: int = 512, bottleneck: int = 64):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.GELU(),
            nn.Dropout(0.20),
            nn.Linear(hidden, hidden // 2),
            nn.GELU(),
            nn.Linear(hidden // 2, bottleneck),
        )
        self.decoder = nn.Sequential(
            nn.Linear(bottleneck, hidden // 2),
            nn.GELU(),
            nn.Linear(hidden // 2, hidden),
            nn.GELU(),
            nn.Linear(hidden, input_dim),
        )

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z), z


def load_data():
    doc_ids = json.loads((CLUSTERS / "doc_ids.json").read_text(encoding="utf-8"))
    X_tfidf = np.load(CLUSTERS / "doc_term_tfidf.npy").astype(np.float32)
    X_counts = np.load(CLUSTERS / "doc_term_counts.npy").astype(np.float32)
    pairs = json.loads(GT.read_text(encoding="utf-8"))["pairs"]
    idx_of = {d: i for i, d in enumerate(doc_ids)}
    cv_ids = [d for d in doc_ids if d.startswith("CV-") or d.startswith("HIRED_")]
    jd_ids = [d for d in doc_ids if d.startswith("JD_")]
    return doc_ids, X_tfidf, X_counts, pairs, idx_of, cv_ids, jd_ids


def rank_of(scores: np.ndarray, pos: int) -> int:
    order = np.argsort(-scores)
    return int(np.where(order == pos)[0][0]) + 1


def wilson_ci(k: int, n: int, z: float = 1.96):
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return [max(0.0, centre - half), min(1.0, centre + half)]


def summarize(rows: list[dict], name: str) -> dict:
    n = len(rows)
    r10 = [r["recall@10"] for r in rows]
    r5 = [r["recall@5"] for r in rows]
    mrr = [r["mrr@10"] for r in rows]
    ranks = [r["rank"] for r in rows]
    return {
        "name": name,
        "n": n,
        "recall@10": float(np.mean(r10)),
        "recall@5": float(np.mean(r5)),
        "mrr@10": float(np.mean(mrr)),
        "mean_rank": float(np.mean(ranks)),
        "hits@10": int(sum(r10)),
        "ci95_recall@10": wilson_ci(int(sum(r10)), n),
    }


def evaluate_scores(score_fn, pairs, cv_ids, idx_of, method: str, train_pairs=None):
    rows = []
    for p in pairs:
        jd_idx = idx_of[p["jd_id"]]
        pos = cv_ids.index(p["cv_id"])
        cand_idx = [idx_of[c] for c in cv_ids]
        scores = score_fn(jd_idx, cand_idx)
        rank = rank_of(scores, pos)
        rows.append(
            {
                "method": method,
                "pair_id": p["pair_id"],
                "jd_id": p["jd_id"],
                "cv_id": p["cv_id"],
                "rank": rank,
                "recall@10": int(rank <= 10),
                "recall@5": int(rank <= 5),
                "mrr@10": (1.0 / rank) if rank <= 10 else 0.0,
                "top10": "|".join(cv_ids[i] for i in np.argsort(-scores)[:10]),
            }
        )
    return rows


def baseline_scores(X_tfidf, X_counts):
    def tfidf_cos(jd_idx, cand_idx):
        q = X_tfidf[jd_idx]
        D = X_tfidf[cand_idx]
        return D @ q

    def overlap_cos(jd_idx, cand_idx):
        q = X_counts[jd_idx]
        D = X_counts[cand_idx]
        qn = np.linalg.norm(q) + 1e-9
        dn = np.linalg.norm(D, axis=1) + 1e-9
        return (D @ q) / (dn * qn)

    def bm25(jd_idx, cand_idx, k1=1.5, b=0.75):
        D = X_counts[cand_idx]
        q = X_counts[jd_idx]
        N = D.shape[0]
        dl = D.sum(axis=1)
        avgdl = dl.mean() + 1e-9
        df = (D > 0).sum(axis=0)
        idf = np.log((N - df + 0.5) / (df + 0.5) + 1.0)
        qnz = np.where(q > 0)[0]
        if len(qnz) == 0:
            return np.zeros(N)
        tf = D[:, qnz]
        denom = tf + k1 * (1 - b + b * dl[:, None] / avgdl)
        score = ((tf * (k1 + 1)) / (denom + 1e-9)) @ (q[qnz] * idf[qnz])
        return score

    return {"tfidf_cosine": tfidf_cos, "keyword_overlap_cos": overlap_cos, "bm25": bm25}


def train_ae(
    X_tfidf,
    train_idx,
    pairs,
    cv_ids,
    idx_of,
    bottleneck=64,
    epochs=120,
    warmup=40,
    lr=1e-3,
    seed=SEED,
):
    torch.manual_seed(seed)
    np.random.seed(seed)
    V = X_tfidf.shape[1]
    model = AutoEncoder(V, hidden=512, bottleneck=bottleneck)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    X_train = torch.tensor(X_tfidf[train_idx], dtype=torch.float32)
    X_cand = torch.tensor(X_tfidf[[idx_of[c] for c in cv_ids]], dtype=torch.float32)
    X_jd = torch.tensor(X_tfidf[[idx_of[p["jd_id"]] for p in pairs]], dtype=torch.float32)
    pos_idx = torch.tensor([cv_ids.index(p["cv_id"]) for p in pairs], dtype=torch.long)

    for epoch in range(epochs):
        model.train()
        opt.zero_grad()

        # denoising reconstruction
        mask = (torch.rand_like(X_train) > 0.10).float()
        x_in = X_train * mask
        x_hat, _ = model(x_in)
        recon = F.mse_loss(x_hat, X_train)

        if epoch >= warmup and len(pairs) > 0:
            z_cv = F.normalize(model.encoder(X_cand), dim=1)
            z_jd = F.normalize(model.encoder(X_jd), dim=1)
            logits = (z_jd @ z_cv.T) * 10.0
            ret = F.cross_entropy(logits, pos_idx)
            loss = recon + ret
        else:
            ret = torch.tensor(0.0)
            loss = recon

        loss.backward()
        opt.step()

        if epoch % 20 == 0 or epoch == epochs - 1:
            print(
                f"    epoch {epoch:03d} recon={recon.item():.5f} "
                f"ret={float(ret):.4f}",
                flush=True,
            )
    return model


def encode(model, X):
    model.eval()
    with torch.no_grad():
        z = model.encoder(torch.tensor(X, dtype=torch.float32))
        z = F.normalize(z, dim=1).numpy()
    return z


def eval_model(model, X, pairs, cv_ids, idx_of, method):
    Z = encode(model, X)
    rows = []
    for p in pairs:
        jd_idx = idx_of[p["jd_id"]]
        pos = cv_ids.index(p["cv_id"])
        cand_idx = [idx_of[c] for c in cv_ids]
        scores = Z[cand_idx] @ Z[jd_idx]
        rank = rank_of(scores, pos)
        rows.append(
            {
                "method": method,
                "pair_id": p["pair_id"],
                "jd_id": p["jd_id"],
                "cv_id": p["cv_id"],
                "rank": rank,
                "recall@10": int(rank <= 10),
                "recall@5": int(rank <= 5),
                "mrr@10": (1.0 / rank) if rank <= 10 else 0.0,
                "top10": "|".join(cv_ids[i] for i in np.argsort(-scores)[:10]),
            }
        )
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baselines", "in_sample", "lopo", "all"], default="all")
    ap.add_argument("--epochs", type=int, default=120)
    ap.add_argument("--bottleneck", type=int, default=64)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""

    doc_ids, X_tfidf, X_counts, pairs, idx_of, cv_ids, jd_ids = load_data()
    titles = {}
    for line in (ROOT / "data" / "processed" / "jd_10.jsonl").open(encoding="utf-8"):
        obj = json.loads(line)
        titles[obj["doc_id"]] = obj.get("role_title", "")
    print(f"docs={len(doc_ids)} cv_pool={len(cv_ids)} jds={len(jd_ids)} pairs={len(pairs)} V={X_tfidf.shape[1]}")

    all_rows = []
    metrics = {}

    if args.mode in ("baselines", "all"):
        for name, fn in baseline_scores(X_tfidf, X_counts).items():
            rows = evaluate_scores(fn, pairs, cv_ids, idx_of, name)
            all_rows.extend(rows)
            metrics[name] = summarize(rows, name)
            print(f"{name}: Recall@10={metrics[name]['recall@10']:.3f}")

    if args.mode in ("in_sample", "all"):
        train_idx = list(range(len(doc_ids)))
        model = train_ae(
            X_tfidf, train_idx, pairs, cv_ids, idx_of,
            bottleneck=args.bottleneck, epochs=args.epochs,
        )
        rows = eval_model(model, X_tfidf, pairs, cv_ids, idx_of, "ae_supervised_in_sample")
        all_rows.extend(rows)
        metrics["ae_supervised_in_sample"] = summarize(rows, "ae_supervised_in_sample")
        print(f"in_sample: Recall@10={metrics['ae_supervised_in_sample']['recall@10']:.3f}")
        torch.save(model.state_dict(), OUT_MODELS / "ae_in_sample.pt")
        Z = encode(model, X_tfidf)
        np.savez(
            OUT_MODELS / "doc_embeddings_in_sample.npz",
            doc_ids=np.array(doc_ids),
            embeddings=Z,
        )

    if args.mode in ("lopo", "all"):
        lopo_rows = []
        for k, held in enumerate(pairs):
            print(f"LOPO fold {k+1}/{len(pairs)} held={held['pair_id']}", flush=True)
            train_pairs = [p for p in pairs if p["pair_id"] != held["pair_id"]]
            train_idx = [idx_of[d] for d in doc_ids if d not in {held["jd_id"], held["cv_id"]}]
            model = train_ae(
                X_tfidf, train_idx, train_pairs, cv_ids, idx_of,
                bottleneck=args.bottleneck, epochs=args.epochs,
            )
            rows = eval_model(model, X_tfidf, [held], cv_ids, idx_of, "ae_supervised_lopo")
            lopo_rows.extend(rows)
        all_rows.extend(lopo_rows)
        metrics["ae_supervised_lopo"] = summarize(lopo_rows, "ae_supervised_lopo")
        print(f"LOPO: Recall@10={metrics['ae_supervised_lopo']['recall@10']:.3f}")

    # write per-query and metrics
    for r in all_rows:
        r["role_title"] = titles.get(r["jd_id"], "")
    if all_rows:
        with (OUT_RET / f"per_query{suffix}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
    (OUT_METRICS / f"metrics{suffix}.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== SUMMARY ===")
    for name, m in metrics.items():
        print(
            f"{name}: R@10={m['recall@10']:.3f} R@5={m['recall@5']:.3f} "
            f"MRR@10={m['mrr@10']:.3f} mean_rank={m['mean_rank']:.1f} "
            f"CI={m['ci95_recall@10']}"
        )


if __name__ == "__main__":
    main()
