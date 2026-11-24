# -*- coding: utf-8 -*-
"""把 30 份混装 PDF 按页切成「只有 JD」和「只有 CV」两份。

规则：
- 分界标记 `CV OF THE HIRED CANDIDATE` 所在页及之后 = 简历
- 该页之前 = 岗位描述
- 纯页面复制，不改文字、不去页眉、不重排版
"""
import os

import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # 项目根，由本文件位置反推（本文件在 dataset_from_blackboard 下两层）
SRC = os.path.join(ROOT, "dataset_from_blackboard", "JD-and-Hired-CV-(30)-examples")
OUT_JD = os.path.join(SRC, "JD-30-real-examples")
OUT_CV = os.path.join(SRC, "CV-30-real-examples")
MARK = "CV OF THE HIRED CANDIDATE"


def split_one(src_path, jd_path, cv_path):
    doc = pymupdf.open(src_path)
    hit = None
    for i in range(doc.page_count):
        if MARK in doc[i].get_text():
            hit = i
            break
    if hit is None:
        doc.close()
        return None, "未找到分界标记"
    if hit == 0:
        doc.close()
        return None, "标记在第 1 页，JD 部分为空"

    # JD：第 0 页 .. hit-1 页
    jd = pymupdf.open()
    jd.insert_pdf(doc, from_page=0, to_page=hit - 1)
    jd.save(jd_path)
    jd.close()

    # CV：第 hit 页 .. 末页
    cv = pymupdf.open()
    cv.insert_pdf(doc, from_page=hit, to_page=doc.page_count - 1)
    cv.save(cv_path)
    cv.close()

    n = (hit, doc.page_count - hit)
    doc.close()
    return n, None


def main():
    os.makedirs(OUT_JD, exist_ok=True)
    os.makedirs(OUT_CV, exist_ok=True)

    files = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".pdf"))
    print(f"源文件 {len(files)} 份\n")
    print(f"{'文件':<52}{'JD页':>5}{'CV页':>5}  状态")
    print("-" * 74)

    ok = fail = 0
    for f in files:
        stem = os.path.splitext(f)[0]
        jd_path = os.path.join(OUT_JD, stem + "_only_JD.pdf")
        cv_path = os.path.join(OUT_CV, stem + "_only_CV.pdf")
        pages, err = split_one(os.path.join(SRC, f), jd_path, cv_path)
        if err:
            print(f"{f[:50]:<52}{'-':>5}{'-':>5}  ✗ {err}")
            fail += 1
        else:
            print(f"{f[:50]:<52}{pages[0]:>5}{pages[1]:>5}  ✓")
            ok += 1

    print("-" * 74)
    print(f"成功 {ok} 份，失败 {fail} 份")
    print(f"\n输出目录：\n  {OUT_JD}\n  {OUT_CV}")


if __name__ == "__main__":
    main()
