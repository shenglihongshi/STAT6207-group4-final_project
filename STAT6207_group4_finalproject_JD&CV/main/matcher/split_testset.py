# -*- coding: utf-8 -*-
"""把 P01-P30 的配对 PDF 切成「JD 文本」与「录用者 CV 文本」两份。

结构：整份 PDF 前面是 JD，从含 `CV OF THE HIRED CANDIDATE` 的那一页起是简历。
切分必须按标记，不能按页码（P01 的简历从第 4 页才开始）。
"""
import os
import re

import pymupdf

ROOT = r"D:\港硕授课与课堂内容\STAT6207_group7_finalproject"
SRC = os.path.join(ROOT, "dataset_from_blackboard", "JD-and-Hired-CV-(30)-examples")
OUT = os.path.join(ROOT, "main", "matcher", "testset")
OUT_JD = os.path.join(OUT, "JD")
OUT_CV = os.path.join(OUT, "CV")

MARK = "CV OF THE HIRED CANDIDATE"


def clean(lines, pid):
    """去掉页眉页脚与孤立页码"""
    keep = []
    for l in lines:
        s = l.strip()
        if not s:
            continue
        if re.match(rf"^{pid}\s*[·\-—]", s):      # P01 · ...
            continue
        if s == pid:
            continue
        if re.fullmatch(r"(page\s*)?\d{1,2}", s, re.I):
            continue
        keep.append(s)
    return keep


os.makedirs(OUT_JD, exist_ok=True)
os.makedirs(OUT_CV, exist_ok=True)

files = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".pdf"))
print(f"共 {len(files)} 份\n")

report = []
for f in files:
    pid = f.split(" ")[0]                      # "P01"
    doc = pymupdf.open(os.path.join(SRC, f))
    pages = [p.get_text() for p in doc]

    cv_start = None
    for i, t in enumerate(pages):
        if MARK in t:
            cv_start = i
            break
    if cv_start is None:
        print(f"  ! {pid} 找不到简历标记，跳过")
        continue

    jd_lines, cv_lines = [], []
    for i, t in enumerate(pages):
        lines = t.split("\n")
        if i < cv_start:
            jd_lines += lines
        elif i == cv_start:
            # 标记之前的残留归 JD，之后归 CV
            k = next((j for j, l in enumerate(lines) if MARK in l), 0)
            jd_lines += lines[:k]
            cv_lines += lines[k:]
        else:
            cv_lines += lines

    jd = "\n".join(clean(jd_lines, pid))
    cv = "\n".join(clean(cv_lines, pid))
    open(os.path.join(OUT_JD, pid + ".txt"), "w", encoding="utf-8").write(jd)
    open(os.path.join(OUT_CV, pid + ".txt"), "w", encoding="utf-8").write(cv)
    report.append((pid, len(jd), len(cv), cv_start + 1))

print(f"{'编号':<6}{'JD字符':>8}{'CV字符':>9}{'CV起始页':>9}")
for pid, a, b, p in report:
    print(f"{pid:<6}{a:>8}{b:>9}{p:>9}")
print(f"\n输出：{OUT_JD}  ({len(report)} 份)")
print(f"      {OUT_CV}  ({len(report)} 份)")
