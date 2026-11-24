# -*- coding: utf-8 -*-
"""库结构：四个库的路径与文件操作。

    main/db/
    ├── raw_jd/<组>/<原名>_JD.<ext>              原始 JD
    ├── raw_cv/<组>/<原名>_CV.<ext>              原始 CV
    ├── label_jd/<组>/<原名>_JD_with_label.json   JD 标签（含向量）
    └── label_cv/<组>/<原名>_CV_with_label.json   CV 标签（含向量）

约定：
- 组 = 子文件夹，只为物理归类，检索时不区分
- 文件名全局唯一：重名时序号加在后缀之后（resume_CV_2.pdf）
- 标签文件里带 768 维向量，不再依赖外部缓存表
"""
import os
import re

ROOT = r"D:\港硕授课与课堂内容\STAT6207_group7_finalproject"
DB = os.path.join(ROOT, "main", "db")

RAW_JD = os.path.join(DB, "raw_jd")
RAW_CV = os.path.join(DB, "raw_cv")
LABEL_JD = os.path.join(DB, "label_jd")
LABEL_CV = os.path.join(DB, "label_cv")

DEFAULT_GROUP = "默认组"
KINDS = ("jd", "cv")
SUFFIX = {"jd": "_JD", "cv": "_CV"}
LABEL_SUFFIX = "_with_label.json"

RAW_EXT_OK = {".pdf", ".docx", ".doc", ".txt", ".md"}


def raw_root(kind):
    return RAW_JD if kind == "jd" else RAW_CV


def label_root(kind):
    return LABEL_JD if kind == "jd" else LABEL_CV


def ensure_layout():
    for kind in KINDS:
        for root in (raw_root(kind), label_root(kind)):
            os.makedirs(os.path.join(root, DEFAULT_GROUP), exist_ok=True)


# ---------------------------------------------------------------- 组

def groups(kind):
    """列出该库下所有组（文件夹名）"""
    root = raw_root(kind)
    if not os.path.isdir(root):
        return [DEFAULT_GROUP]
    out = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    if DEFAULT_GROUP not in out:
        out.insert(0, DEFAULT_GROUP)
    return sorted(out, key=lambda x: (x != DEFAULT_GROUP, x))


def ensure_group(kind, group):
    for root in (raw_root(kind), label_root(kind)):
        os.makedirs(os.path.join(root, group), exist_ok=True)


# ---------------------------------------------------------------- 命名

def strip_suffix(stem, kind):
    """去掉已有的 _JD/_CV 后缀，避免重复叠加"""
    s = SUFFIX[kind]
    return stem[: -len(s)] if stem.endswith(s) else stem


def unique_raw_name(kind, base_stem, ext):
    """生成全局唯一的原始文件名：{stem}{suffix}.{ext}，重名则 {stem}{suffix}_2.{ext}"""
    stem = strip_suffix(base_stem, kind)
    suf = SUFFIX[kind]
    used = set()
    for g in groups(kind):
        d = os.path.join(raw_root(kind), g)
        if os.path.isdir(d):
            used |= {f.lower() for f in os.listdir(d)}
    cand = f"{stem}{suf}{ext}"
    n = 2
    while cand.lower() in used:
        cand = f"{stem}{suf}_{n}{ext}"
        n += 1
    return cand


def label_name_of(raw_name):
    """xxx_CV.pdf → xxx_CV_with_label.json"""
    return os.path.splitext(raw_name)[0] + LABEL_SUFFIX


def raw_name_of(label_name):
    """xxx_CV_with_label.json → xxx_CV（无扩展名）"""
    if label_name.endswith(LABEL_SUFFIX):
        return label_name[: -len(LABEL_SUFFIX)]
    return label_name


def ref_of(raw_or_label_name, kind):
    """文件主名 → 引用名（去掉 _with_label.json 与类型后缀）
    worker01_CV_with_label.json → worker01
    worker01_CV.pdf            → worker01
    """
    base = raw_name_of(raw_or_label_name)
    return strip_suffix(base, kind)


# ---------------------------------------------------------------- 枚举

def raw_files(kind, group=None):
    """返回 [(group, filename, fullpath)]"""
    out = []
    gs = [group] if group else groups(kind)
    for g in gs:
        d = os.path.join(raw_root(kind), g)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if os.path.isfile(p) and os.path.splitext(f)[1].lower() in RAW_EXT_OK:
                out.append((g, f, p))
    return out


def label_files(kind, group=None):
    out = []
    gs = [group] if group else groups(kind)
    for g in gs:
        d = os.path.join(label_root(kind), g)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(LABEL_SUFFIX):
                out.append((g, f, os.path.join(d, f)))
    return out


def pending(kind):
    """列出「有原始文件但缺标签」的项：[(group, raw_name, label_target_name)]"""
    out = []
    for g in groups(kind):
        have = set()
        d = os.path.join(label_root(kind), g)
        if os.path.isdir(d):
            have = {f for f in os.listdir(d) if f.endswith(LABEL_SUFFIX)}
        for gg, f, _ in raw_files(kind, g):
            ln = label_name_of(f)
            if ln not in have:
                out.append((gg, f, ln))
    return out


def orphans(kind):
    """列出「有标签但没有原始文件」的项"""
    out = []
    for g in groups(kind):
        raws = set()
        d = os.path.join(raw_root(kind), g)
        if os.path.isdir(d):
            raws = {f for f in os.listdir(d)}
        for g2, f, _ in label_files(kind, g):
            if raw_name_of(f) not in {os.path.splitext(r)[0] for r in raws}:
                out.append((g2, f))
    return out


def raw_path_of(kind, group, ref):
    """按引用名找原始文件路径：('cv','默认组','CV-001') → .../CV-001_CV.txt"""
    d = os.path.join(raw_root(kind), group)
    if not os.path.isdir(d):
        return None
    want = f"{ref}{SUFFIX[kind]}"
    for f in os.listdir(d):
        if os.path.splitext(f)[0] == want:
            return os.path.join(d, f)
    return None


def label_path_of(kind, group, ref):
    """按引用名找标签文件路径"""
    d = os.path.join(label_root(kind), group)
    if not os.path.isdir(d):
        return None
    want = f"{ref}{SUFFIX[kind]}{LABEL_SUFFIX}"
    p = os.path.join(d, want)
    return p if os.path.exists(p) else None


def index(kind, group=None):
    """返回 {ref: {'group':g, 'label':path, 'raw':path}}"""
    out = {}
    for g, f, lp in label_files(kind, group):
        ref = ref_of(f, kind)
        out[ref] = {
            "group": g,
            "label": lp,
            "raw": raw_path_of(kind, g, ref),
        }
    return out


# ---------------------------------------------------------------- 状态

def summary():
    rows = []
    for kind, label in (("jd", "JD"), ("cv", "CV")):
        raw = raw_files(kind)
        lab = label_files(kind)
        pend = pending(kind)
        rows.append({
            "kind": label,
            "groups": groups(kind),
            "raw": len(raw),
            "labelled": len(lab),
            "pending": len(pend),
        })
    return rows


if __name__ == "__main__":
    ensure_layout()
    for r in summary():
        print(f"{r['kind']}: 组={r['groups']} | 原始 {r['raw']} 份 | 已打标 {r['labelled']} 份 | 待打标 {r['pending']} 份")
