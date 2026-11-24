# -*- coding: utf-8 -*-
"""抽取测试集（P01-P30 的 JD 与录用者 CV），复用 extract.py 的逻辑，只改路径"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根，由本文件位置反推
sys.path.insert(0, os.path.join(ROOT, "main", "LLM_program"))
import extract as E

TEST = os.path.join(ROOT, "main", "matcher", "testset")
# 重定向路径：读测试集，写测试集目录，避免污染训练数据
E.SRC_JD = os.path.join(TEST, "JD")
E.SRC_CV = os.path.join(TEST, "CV")
E.OUT_JD = os.path.join(TEST, "extracted", "JD")
E.OUT_CV = os.path.join(TEST, "extracted", "CV")
os.makedirs(E.OUT_JD, exist_ok=True)
os.makedirs(E.OUT_CV, exist_ok=True)

jobs = [("jd", f[:-4]) for f in sorted(os.listdir(E.SRC_JD)) if f.endswith(".txt")]
jobs += [("cv", f[:-4]) for f in sorted(os.listdir(E.SRC_CV)) if f.endswith(".txt")]

print(f"共 {len(jobs)} 份待抽取")
ok = fail = skip = 0
for i, (kind, stem) in enumerate(jobs, 1):
    status, dt, info = E.extract_one(kind, stem)
    if status == "ok":
        ok += 1
        print(f"[{i}/{len(jobs)}] {stem} ({kind}) OK {dt:5.1f}s  {info}", flush=True)
    elif status == "skip":
        skip += 1
    else:
        fail += 1
        print(f"[{i}/{len(jobs)}] {stem} ({kind}) FAIL {dt:5.1f}s  {info}", flush=True)

print(f"\n完成：ok={ok} skip={skip} fail={fail}")
