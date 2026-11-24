# -*- coding: utf-8 -*-
"""评测：在 P01-P30 真实配对上算 Recall@K / MRR。

候选池 = 100 份无标签简历 + 其余 29 份录用者简历（leave-one-out），共 129 人。
答案（本人）只在评测时放进池子，不参与任何训练。
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根，由本文件位置反推
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import features as F

EXT = os.path.join(ROOT, "main", "match_work", "extracted")
SRC_CV = os.path.join(ROOT, "dataset_from_blackboard", "CV_examples")
TEST = os.path.join(HERE, "testset")
T_EXT = os.path.join(TEST, "extracted")


def load_train_cvs():
    out = {}
    for f in sorted(os.listdir(os.path.join(EXT, "CV"))):
        if not f.endswith(".json"):
            continue
        ref = f[:-5]
        raw = open(os.path.join(SRC_CV, ref + ".txt"), encoding="utf-8").read()
        out[ref] = F.prepare_cv(json.load(open(os.path.join(EXT, "CV", f), encoding="utf-8")), raw)
    return out


def load_hired_cvs():
    out = {}
    d = os.path.join(T_EXT, "CV")
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        ref = f[:-5]
        src = os.path.join(TEST, "CV", ref + ".txt")
        raw = open(src, encoding="utf-8").read() if os.path.exists(src) else ""
        out[ref] = F.prepare_cv(json.load(open(os.path.join(d, f), encoding="utf-8")), raw)
    return out


def load_test_jds():
    out = {}
    d = os.path.join(T_EXT, "JD")
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        ref = f[:-5]
        src = os.path.join(TEST, "JD", ref + ".txt")
        raw = open(src, encoding="utf-8").read() if os.path.exists(src) else ""
        out[ref] = (json.load(open(os.path.join(d, f), encoding="utf-8")), raw)
    return out


def evaluate(name, w, names, train_cvs, hired_cvs, test_jds):
    ranks, detail = [], []
    # 候选池 = 100 份无标签简历 + 30 份录用者（含答案本人在内）
    pool = list(train_cvs.values()) + list(hired_cvs.values())
    refs = [c["cv_ref"] for c in pool]
    for pid, (jd, raw) in test_jds.items():
        if pid not in hired_cvs:
            continue
        feats = F.build_pool_features(jd, raw, pool, jd_key=pid)
        scores = np.array([float(np.dot(w, feats[r])) for r in refs])
        order = np.argsort(-scores)
        target = refs.index(pid)
        rank = int(list(order).index(target)) + 1
        ranks.append(rank)
        detail.append((pid, rank, refs[order[0]], refs[order[1]] if len(order) > 1 else None))

    ranks = np.array(ranks)
    r1 = float((ranks <= 1).mean())
    r5 = float((ranks <= 5).mean())
    r10 = float((ranks <= 10).mean())
    mrr = float((1.0 / ranks).mean())
    print(f"{name:<22} n={len(ranks):>2}  R@1={r1:.3f}  R@5={r5:.3f}  R@10={r10:.3f}  MRR={mrr:.3f}")
    return {"name": name, "n": len(ranks), "R@1": r1, "R@5": r5, "R@10": r10,
            "MRR": mrr, "ranks": ranks.tolist(), "detail": detail}


def main():
    train_cvs = load_train_cvs()
    hired_cvs = load_hired_cvs()
    test_jds = load_test_jds()
    print(f"训练库 {len(train_cvs)} 份 | 录用者 {len(hired_cvs)} 份 | 测试 JD {len(test_jds)} 份\n")
    if not test_jds or not hired_cvs:
        print("测试集尚未抽取完成")
        return

    wj = json.load(open(os.path.join(HERE, "weights.json"), encoding="utf-8"))
    names = wj["feature_names"]
    prior = np.array(wj["prior"])
    learned = np.array(wj["learned_all44"])
    learned21 = np.array(wj["learned_strong21"])

    def one_hot(idx):
        v = np.zeros(len(names))
        v[idx] = 1.0
        return v

    n_pool = len(train_cvs) + len(hired_cvs)
    print(f"=== 基线对照（{n_pool} 人候选池，答案在池内）===")
    res = []
    res.append(evaluate("随机（理论值≈3.9%）", np.zeros(len(names)), names,
                        train_cvs, hired_cvs, test_jds) if False else None)
    res.append(evaluate("B1 纯 TF-IDF 词面", one_hot(names.index("tfidf")), names,
                        train_cvs, hired_cvs, test_jds))
    res.append(evaluate("B2 纯语义 embedding", one_hot(names.index("semantic")), names,
                        train_cvs, hired_cvs, test_jds))
    res.append(evaluate("B3 纯技能重合", one_hot(names.index("skill_must")), names,
                        train_cvs, hired_cvs, test_jds))
    res.append(evaluate("B4 人工先验权重", prior, names, train_cvs, hired_cvs, test_jds))
    res.append(evaluate("B5 学出权重(44组)", learned, names, train_cvs, hired_cvs, test_jds))
    res.append(evaluate("B6 学出权重(21强)", learned21, names, train_cvs, hired_cvs, test_jds))

    best = max([r for r in res if r], key=lambda x: x["MRR"])
    print(f"\n最佳：{best['name']}  MRR={best['MRR']:.3f}")
    print("\n=== 逐条（学出权重 44 组）===")
    det = [r for r in res if r and r["name"].startswith("B5")][0]["detail"]
    for pid, rank, top1, top2 in det:
        flag = "✓" if rank <= 5 else "✗"
        print(f"  {flag} {pid} 答案排第 {rank:>3}  第一名={top1}")

    with open(os.path.join(HERE, "eval_result.json"), "w", encoding="utf-8") as f:
        json.dump([r for r in res if r], f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存：{os.path.join(HERE, 'eval_result.json')}")


if __name__ == "__main__":
    main()
