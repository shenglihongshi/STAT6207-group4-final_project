# -*- coding: utf-8 -*-
"""诊断：为什么正例排不上来"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根，由本文件位置反推
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features as F
import train as T

jds, cvs = T.load_all()
pairs, levels = T.load_pairs()
pools = T.build_dataset(jds, cvs, pairs)
w = np.array(json.load(open(os.path.join(T.OUT, "weights.json"), encoding="utf-8"))["learned_all44"])

print("=== 1. 按岗位族看 MRR（学出权重）===")
by_fam = {}
for X, p, jid in pools:
    fam = jds[jid].get("role_family") or "unknown"
    s = X @ w
    rank = int(np.argsort(-s).tolist().index(p)) + 1
    by_fam.setdefault(fam, []).append(rank)
for fam, ranks in sorted(by_fam.items(), key=lambda x: np.mean(x[1])):
    print(f"  {fam:<18} n={len(ranks):>2}  平均排名 {np.mean(ranks):5.1f}  中位 {int(np.median(ranks))}")

print("\n=== 2. 排名最差的 6 个查询 ===")
rows = []
for X, p, jid in pools:
    s = X @ w
    order = np.argsort(-s)
    rank = int(list(order).index(p)) + 1
    rows.append((rank, jid, jds[jid].get("role_family"), jds[jid].get("position"), p))
for rank, jid, fam, pos, p in sorted(rows, reverse=True)[:6]:
    print(f"  {jid} 排第 {rank:>3} | {fam} | {pos}")

print("\n=== 3. 特征分布：有多少维度是「几乎没区分度」的 ===")
print(f"  {'特征':<16}{'均值':>7}{'标准差':>8}{'最小':>7}{'最大':>7}")
for i, name in enumerate(F.FEATURE_NAMES):
    vals = np.concatenate([X[:, i] for X, _, _ in pools])
    print(f"  {name:<16}{vals.mean():>7.3f}{vals.std():>8.3f}{vals.min():>7.2f}{vals.max():>7.2f}")

print("\n=== 4. 技能字段可用性（技术岗 vs 非技术岗）===")
for fam in ["Engineering", "Data & AI", "Sales & BD", "Marketing", "Finance & Legal", "Design & Creative"]:
    js = [jds[j] for j, _ in pairs if jds.get(j, {}).get("role_family") == fam]
    if not js:
        continue
    n_has = sum(1 for j in js if j.get("must_have_skills"))
    avg = np.mean([len(j.get("must_have_skills") or []) for j in js])
    print(f"  {fam:<18} n={len(js):>2}  有必备技能的 {n_has:>2}  平均 {avg:.1f} 项")
