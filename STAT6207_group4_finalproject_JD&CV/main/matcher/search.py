# -*- coding: utf-8 -*-
"""检索器：给一份 JD，从简历库里挑出 Top-N，并逐条给出理由。

用法：
    python search.py JD-01              # 用编号检索
    python search.py --file path.txt    # 用一份新 JD 的文本检索（需要本地模型先抽取）
    python search.py JD-01 --top 10
"""
import argparse
import json
import os
import sys

import numpy as np

ROOT = r"D:\港硕授课与课堂内容\STAT6207_group7_finalproject"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features as F

EXT = os.path.join(ROOT, "main", "match_work", "extracted")
SRC_JD = os.path.join(ROOT, "dataset_from_blackboard", "JD_examples")
SRC_CV = os.path.join(ROOT, "dataset_from_blackboard", "CV_examples")
HERE = os.path.dirname(os.path.abspath(__file__))

# 中文名，供理由生成使用
CN = {
    "skill_must": "必备技能", "skill_nice": "加分技能", "years_fit": "年限",
    "seniority_fit": "资历", "location": "地点", "language": "语言",
    "domain": "行业", "education": "学历", "tfidf": "文本相似", "skill_jaccard": "技能覆盖",
    "semantic": "语义相似",
}


def load_weights(which="learned_all44"):
    with open(os.path.join(HERE, "weights.json"), encoding="utf-8") as f:
        d = json.load(f)
    names = d["feature_names"]
    return names, np.array(d[which], dtype=float)


def load_library():
    cvs = {}
    for f in sorted(os.listdir(os.path.join(EXT, "CV"))):
        if not f.endswith(".json"):
            continue
        ref = f[:-5]
        raw = open(os.path.join(SRC_CV, ref + ".txt"), encoding="utf-8").read()
        cvs[ref] = F.prepare_cv(json.load(open(os.path.join(EXT, "CV", f), encoding="utf-8")), raw)
    return cvs


def make_reason(jd, cv, vec, names, w):
    """理由只写事实：命中的技能、年限、地点。不写形容词。"""
    jm = F.skill_set(jd.get("must_have_skills"))
    cs = F.skill_set(cv.get("skills"))
    hit = sorted(jm & cs)
    miss = sorted(jm - cs)
    bits = []
    if jm:
        bits.append(f"必备技能命中 {len(hit)}/{len(jm)}" + (f"（{', '.join(hit[:5])}）" if hit else ""))
        if miss and len(miss) <= 3:
            bits.append(f"缺 {', '.join(miss)}")
    yrs = cv.get("_years")
    if yrs is not None:
        if jd.get("min_years"):
            bits.append(f"{yrs:g} 年经验（要求 {jd['min_years']} 年）")
        else:
            bits.append(f"{yrs:g} 年经验")
    jc, cc = jd.get("country"), cv.get("country")
    if jc and cc:
        bits.append("同国" if str(jc).lower() == str(cc).lower() else f"异地（{cc}）")
    return "；".join(bits)


def search(jd, jd_text, cvs, names, w, top=5):
    feats = F.build_pool_features(jd, jd_text, list(cvs.values()))
    scored = []
    for ref, vec in feats.items():
        scored.append((float(np.dot(w, vec)), ref, vec))
    scored.sort(reverse=True)
    return scored[:top], scored


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jd_id", nargs="?")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--weights", default="learned_all44")
    ap.add_argument("--show-all", action="store_true", help="同时打印每项特征分数")
    args = ap.parse_args()

    if not args.jd_id:
        print("用法：python search.py JD-01 [--top 5]")
        return

    jd = json.load(open(os.path.join(EXT, "JD", args.jd_id + ".json"), encoding="utf-8"))
    jd_text = open(os.path.join(SRC_JD, args.jd_id + ".txt"), encoding="utf-8").read()
    cvs = load_library()
    names, w = load_weights(args.weights)

    print(f"查询：{args.jd_id} | {jd.get('position')} | {jd.get('role_family')} | "
          f"{jd.get('country')} | 年限 {jd.get('min_years')} | 候选 {len(cvs)} 人")
    if jd.get("must_have_skills"):
        print(f"必备技能：{', '.join(jd['must_have_skills'][:8])}")
    print()

    top, allscored = search(jd, jd_text, cvs, names, w, args.top)
    for i, (score, ref, vec) in enumerate(top, 1):
        cv = cvs[ref]
        print(f"{i}. {ref}  {score:.3f}  {cv.get('current_title')} @ {cv.get('current_company')} "
              f"({cv.get('country')})")
        print(f"   {make_reason(jd, cv, vec, names, w)}")
        if args.show_all:
            parts = [f"{CN.get(n, n)}={v:.2f}" for n, v in zip(names, vec)]
            print("   " + "  ".join(parts))
        print()


if __name__ == "__main__":
    main()
