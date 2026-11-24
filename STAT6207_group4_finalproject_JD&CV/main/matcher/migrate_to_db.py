# -*- coding: utf-8 -*-
"""把现有 150 份数据复制进新库，并把 embedding 向量写进标签 JSON。

- 原始文件：CV_examples/*.txt → main/db/raw_cv/默认组/*_CV.txt
- 标签文件：extracted/CV/*.json → main/db/label_cv/默认组/*_CV_with_label.json（附 768 维向量）
- 原目录一律不动（复制，不移动）
"""
import json
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import db as D

ROOT = D.ROOT
SRC_JD_TXT = os.path.join(ROOT, "dataset_from_blackboard", "JD_examples")
SRC_CV_TXT = os.path.join(ROOT, "dataset_from_blackboard", "CV_examples")
EXT = os.path.join(ROOT, "main", "match_work", "extracted")
NPZ = os.path.join(HERE, "embeddings.npz")


def load_vecs():
    """返回 {'JD-01': 归一化向量, 'CV-001': ...}"""
    if not os.path.exists(NPZ):
        return {}
    d = np.load(NPZ, allow_pickle=True)
    out = {}
    for prefix in ("JD", "CV"):
        for ref, v in zip(d[prefix + "_refs"], d[prefix + "_vecs"]):
            v = np.asarray(v, dtype="float32")
            n = float(np.linalg.norm(v))
            out[str(ref)] = (v / n) if n else v
    return out


def main():
    D.ensure_layout()
    vecs = load_vecs()
    print(f"向量缓存：{len(vecs)} 条\n")

    plan = [
        ("jd", SRC_JD_TXT, "JD"),
        ("cv", SRC_CV_TXT, "CV"),
    ]
    stat = {}
    for kind, src_dir, label in plan:
        raw_dst = os.path.join(D.raw_root(kind), D.DEFAULT_GROUP)
        lab_dst = os.path.join(D.label_root(kind), D.DEFAULT_GROUP)
        os.makedirs(raw_dst, exist_ok=True)
        os.makedirs(lab_dst, exist_ok=True)

        raw_n = lab_n = vec_n = 0
        for f in sorted(os.listdir(src_dir)):
            if not f.endswith(".txt"):
                continue
            ref = os.path.splitext(f)[0]                      # CV-001 / JD-01
            # 1. 原始文件
            raw_name = f"{ref}{D.SUFFIX[kind]}.txt"
            shutil.copy2(os.path.join(src_dir, f), os.path.join(raw_dst, raw_name))
            raw_n += 1

            # 2. 标签文件
            src_label = os.path.join(EXT, label, ref + ".json")
            if not os.path.exists(src_label):
                print(f"  ! {ref} 缺标签，跳过")
                continue
            obj = json.load(open(src_label, encoding="utf-8"))
            v = vecs.get(ref)
            if v is not None:
                obj["embedding"] = [round(float(x), 6) for x in v]
                obj["_meta"] = dict(obj.get("_meta") or {})
                obj["_meta"]["embedding_model"] = "nomic-embed-text-v1.5"
                obj["_meta"]["embedding_norm"] = "l2"
                vec_n += 1
            dst_label = os.path.join(lab_dst, D.label_name_of(raw_name))
            with open(dst_label, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, ensure_ascii=False, indent=2)
            lab_n += 1

        stat[label] = (raw_n, lab_n, vec_n)
        print(f"{label}: 原始 {raw_n} 份、标签 {lab_n} 份、带向量 {vec_n} 份")

    print()
    for r in D.summary():
        print(f"{r['kind']}: 组={r['groups']} | 原始 {r['raw']} | 已打标 {r['labelled']} | 待打标 {r['pending']}")


if __name__ == "__main__":
    main()
