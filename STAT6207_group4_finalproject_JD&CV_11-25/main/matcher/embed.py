# -*- coding: utf-8 -*-
"""用本地 embedding 模型给 JD / CV 算向量并缓存。

文本怎么拼很关键：只放「与岗位相关」的部分，不要把公司介绍、福利塞进去。
"""
import json
import os
import urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根，由本文件位置反推
EXT = os.path.join(ROOT, "main", "match_work", "extracted")
SRC_JD = os.path.join(ROOT, "dataset_from_blackboard", "JD_examples")
SRC_CV = os.path.join(ROOT, "dataset_from_blackboard", "CV_examples")
CACHE = os.path.join(ROOT, "main", "matcher", "embeddings.npz")
TEST = os.path.join(ROOT, "main", "matcher", "testset")

URL = "http://127.0.0.1:1235/v1/embeddings"
MODEL = "text-embedding-nomic-embed-text-v1.5"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def jd_text(o, raw):
    """JD 文本：岗位 + 技能 + 原文前段（职责描述比技能词更能表达岗位性质）"""
    parts = [str(o.get("position") or "")]
    if o.get("role_family"):
        parts.append(str(o["role_family"]))
    parts += [str(x) for x in (o.get("must_have_skills") or [])]
    parts += [str(x) for x in (o.get("nice_to_have_skills") or [])]
    head = " ".join(parts)
    body = (raw or "").replace("\n", " ")[:1500]
    return (head + " || " + body)[:3000]


def cv_text(o, raw):
    """CV 文本：职位 + 公司 + 技能 + 各段经历描述（经历最能说明这人实际做什么）"""
    parts = [str(o.get("current_title") or ""), str(o.get("current_company") or "")]
    parts += [str(x) for x in (o.get("skills") or [])]
    head = " | ".join(p for p in parts if p)
    hist = []
    for job in (o.get("work_history") or [])[:4]:
        if isinstance(job, dict):
            seg = " ".join([str(job.get("title") or ""),
                            str(job.get("company") or ""),
                            str(job.get("description") or "")[:400]])
            if seg.strip():
                hist.append(seg)
    return (head + " || " + " ".join(hist))[:3000]


def embed(texts):
    out = []
    for i in range(0, len(texts), 16):
        batch = texts[i:i + 16]
        req = urllib.request.Request(
            URL,
            data=json.dumps({"model": MODEL, "input": batch}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with OPENER.open(req, timeout=180) as r:
            d = json.loads(r.read().decode())
        out += [x["embedding"] for x in d["data"]]
        print(f"    {min(i+16, len(texts))}/{len(texts)}", flush=True)
    return np.array(out, dtype=np.float32)


def collect(kind, base_ext, base_src):
    items = {}
    for f in sorted(os.listdir(os.path.join(base_ext, kind))):
        if not f.endswith(".json"):
            continue
        ref = f[:-5]
        o = json.load(open(os.path.join(base_ext, kind, f), encoding="utf-8"))
        src = os.path.join(base_src, ref + ".txt")
        raw = open(src, encoding="utf-8").read() if os.path.exists(src) else ""
        items[ref] = (jd_text(o, raw), cv_text(o, raw))[0 if kind == "JD" else 1]
    return items


def main():
    sets = {}
    for kind, ext_base, src in [
        ("JD", EXT, SRC_JD),
        ("CV", EXT, SRC_CV),
        ("P-JD", os.path.join(TEST, "extracted"), os.path.join(TEST, "JD")),
        ("P-CV", os.path.join(TEST, "extracted"), os.path.join(TEST, "CV")),
    ]:
        d = os.path.join(ext_base, "JD" if kind.endswith("JD") else "CV")
        if not os.path.isdir(d):
            print(f"跳过 {kind}：目录不存在 {d}")
            continue
        items = collect("JD" if kind.endswith("JD") else "CV", ext_base, src)
        if not items:
            print(f"跳过 {kind}：无数据")
            continue
        print(f"{kind}: {len(items)} 份，开始嵌入…")
        refs = list(items)
        vecs = embed([items[r] for r in refs])
        sets[kind + "_refs"] = np.array(refs)
        sets[kind + "_vecs"] = vecs
        print(f"  完成，shape={vecs.shape}")

    np.savez_compressed(CACHE, **sets)
    print(f"\n缓存已写入：{CACHE}")
    print("键：", list(sets))


if __name__ == "__main__":
    main()
