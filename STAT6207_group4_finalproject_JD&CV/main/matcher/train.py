# -*- coding: utf-8 -*-
"""训练匹配器权重。

思路：把每个 JD 当成一个「查询」，候选池是 100 份简历，标签只说池里哪一份是好的。
用 listwise softmax 损失，让正例在池里的概率最大——其余简历只当竞争者，从未被断言为负例。
"""
import json
import os
import sys

import numpy as np
import openpyxl
from scipy.optimize import minimize

ROOT = r"D:\港硕授课与课堂内容\STAT6207_group7_finalproject"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features as F

EXT = os.path.join(ROOT, "main", "match_work", "extracted")
SRC_JD = os.path.join(ROOT, "dataset_from_blackboard", "JD_examples")
SRC_CV = os.path.join(ROOT, "dataset_from_blackboard", "CV_examples")
PAIRS = os.path.join(ROOT, "dataset_from_blackboard", "llm_labelled_pairs", "JD1-50_配对总表.xlsx")
OUT = os.path.dirname(os.path.abspath(__file__))

# 人工先验（brief 第 6 节分层，归一化到和为 1）
# 顺序：skill_must, skill_nice, years_fit, seniority_fit, location,
#       language, domain, education, tfidf, skill_jaccard, semantic
PRIOR = np.array([0.26, 0.07, 0.15, 0.11, 0.03, 0.02, 0.09, 0.07, 0.05, 0.00, 0.15])


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_all():
    jds, cvs = {}, {}
    for f in os.listdir(os.path.join(EXT, "JD")):
        if f.endswith(".json"):
            jds[f[:-5]] = load_json(os.path.join(EXT, "JD", f))
    for f in os.listdir(os.path.join(EXT, "CV")):
        if f.endswith(".json"):
            ref = f[:-5]
            raw = open(os.path.join(SRC_CV, ref + ".txt"), encoding="utf-8").read()
            cvs[ref] = F.prepare_cv(load_json(os.path.join(EXT, "CV", f)), raw)
    return jds, cvs


def load_pairs():
    """读配对表：H 列=配对CV，L 列=等级；排除「兜底」"""
    wb = openpyxl.load_workbook(PAIRS, read_only=True, data_only=True)
    ws = wb["配对总表"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    pairs, levels = [], {}
    for r in rows:
        jid, cref, lv = r[0], r[7], r[11]
        if not cref or cref == "—":
            continue
        if lv == "兜底":
            continue
        pairs.append((f"JD-{int(jid):02d}", str(cref)))
        levels[f"JD-{int(jid):02d}"] = lv
    return pairs, levels


def build_dataset(jds, cvs, pairs):
    """返回 [(X, pos_idx, jd_id)]，X 是 池×10"""
    cv_list = list(cvs.values())
    refs = [c["cv_ref"] for c in cv_list]
    pools = []
    for jid, cref in pairs:
        jd = jds.get(jid)
        if not jd:
            print(f"  跳过 {jid}：无抽取结果")
            continue
        jd_text = open(os.path.join(SRC_JD, jid + ".txt"), encoding="utf-8").read()
        feats = F.build_pool_features(jd, jd_text, cv_list, jd_key=jid)
        X = np.array([feats[r] for r in refs], dtype=float)
        if cref not in refs:
            print(f"  跳过 {jid}：正例 {cref} 不在池中")
            continue
        pools.append((X, refs.index(cref), jid))
    return pools


def listwise_loss(w, pools, lam=0.05):
    total, grad = 0.0, np.zeros_like(w)
    for X, p, _ in pools:
        s = X @ w
        s = s - s.max()
        e = np.exp(s)
        prob = e / e.sum()
        total += -np.log(prob[p] + 1e-12)
        d = prob.copy()
        d[p] -= 1.0
        grad += X.T @ d
    n = len(pools)
    return total / n + lam * np.sum(w ** 2), grad / n + 2 * lam * w


def mrr_at(w, pools, k=None):
    vals = []
    for X, p, _ in pools:
        s = X @ w
        order = np.argsort(-s)
        if k:
            order = order[:k]
        rank = int(np.where(order == p)[0][0]) + 1 if p in order else 10 ** 6
        vals.append(1.0 / rank)
    return float(np.mean(vals)), vals


def hit_at(w, pools, k=5):
    m, _ = mrr_at(w, pools, k)
    return float(np.mean([1.0 if v > 1.0 / (k + 1) else 0.0 for v in mrr_at(w, pools, k)[1]]))


def train(pools, lam=0.05, seed=0):
    rng = np.random.default_rng(seed)
    w0 = PRIOR.copy()
    res = minimize(lambda w: listwise_loss(w, pools, lam), w0, method="L-BFGS-B",
                   jac=True, bounds=[(0.0, None)] * len(w0),
                   options={"maxiter": 500, "ftol": 1e-10})
    return res.x, res.fun, res.success


def main():
    jds, cvs = load_all()
    pairs, levels = load_pairs()
    print(f"JD {len(jds)} 份 | CV {len(cvs)} 份 | 配对 {len(pairs)} 组")

    pools = build_dataset(jds, cvs, pairs)
    print(f"可用训练查询：{len(pools)} 个\n")

    strong = [(X, p, j) for X, p, j in pools if levels.get(j) == "强"]
    print(f"其中「强」匹配：{len(strong)} 组\n")

    print("=== 训练（全部 44 组）===")
    w_all, loss_all, ok_all = train(pools, lam=0.05)
    mrr_all, _ = mrr_at(w_all, pools)
    print(f"  loss={loss_all:.4f} 收敛={ok_all}  训练集 MRR={mrr_all:.3f}")

    print("\n=== 训练（只用 21 组「强」匹配）===")
    w_strong, loss_s, ok_s = train(strong, lam=0.05)
    mrr_s, _ = mrr_at(w_strong, strong)
    print(f"  loss={loss_s:.4f} 收敛={ok_s}  训练集 MRR={mrr_s:.3f}")

    print("\n=== 5 折交叉验证（按查询分折，lambda=0.05）===")
    idx = np.arange(len(pools))
    rng = np.random.default_rng(42)
    rng.shuffle(idx)
    folds = np.array_split(idx, 5)
    fold_mrr_learn, fold_mrr_prior = [], []
    for i in range(5):
        te = [pools[j] for j in folds[i]]
        tr = [pools[j] for j in np.concatenate([folds[k] for k in range(5) if k != i])]
        w, _, _ = train(tr, lam=0.05, seed=i)
        fold_mrr_learn.append(mrr_at(w, te)[0])
        fold_mrr_prior.append(mrr_at(PRIOR, te)[0])
    print(f"  学出权重 平均 MRR = {np.mean(fold_mrr_learn):.3f} ± {np.std(fold_mrr_learn):.3f}")
    print(f"  人工先验 平均 MRR = {np.mean(fold_mrr_prior):.3f} ± {np.std(fold_mrr_prior):.3f}")

    print("\n=== 权重对比 ===")
    print(f"  {'特征':<16}{'人工先验':>10}{'学出(44)':>12}{'学出(21强)':>13}")
    for i, name in enumerate(F.FEATURE_NAMES):
        print(f"  {name:<16}{PRIOR[i]:>10.3f}{w_all[i]:>12.3f}{w_strong[i]:>13.3f}")

    out = {
        "feature_names": F.FEATURE_NAMES,
        "prior": PRIOR.round(4).tolist(),
        "learned_all44": w_all.round(4).tolist(),
        "learned_strong21": w_strong.round(4).tolist(),
        "meta": {
            "n_queries": len(pools),
            "n_strong": len(strong),
            "pool_size": len(cvs),
            "lambda": 0.05,
            "train_mrr_all44": round(mrr_all, 4),
            "cv5_mrr_learned": round(float(np.mean(fold_mrr_learn)), 4),
            "cv5_mrr_prior": round(float(np.mean(fold_mrr_prior)), 4),
            "note": "训练标签来自 LLM 标注；测试集 P01-P30 未参与训练",
        },
    }
    with open(os.path.join(OUT, "weights.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n权重已保存：{os.path.join(OUT, 'weights.json')}")


if __name__ == "__main__":
    main()
