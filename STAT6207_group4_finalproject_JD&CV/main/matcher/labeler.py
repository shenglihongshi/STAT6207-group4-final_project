# -*- coding: utf-8 -*-
"""给「有原始文件但缺标签」的项批量打标。

两阶段执行，避免每份都在两个模型间来回切换：
  阶段一：全部抽取（Qwen 常驻）
  阶段二：全部算向量（nomic-embed 常驻）
  阶段三：统一写盘
"""
import json
import os
import sys
from datetime import datetime

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "LLM_program"))

import db
import embed as EMB
import extract as E
import pipeline


def label_pending(kind, group=None, progress=None):
    """返回 (成功数, 失败列表)"""
    todo = db.pending(kind)
    if group:
        todo = [t for t in todo if t[0] == group]
    if not todo:
        return 0, []

    total = len(todo)
    results, fails = [], []

    # 阶段一：抽取
    for i, (g, raw_name, label_name) in enumerate(todo, 1):
        raw_path = os.path.join(db.raw_root(kind), g, raw_name)
        if progress:
            progress({"action": "extract", "i": i, "n": total, "file": raw_name})
        try:
            text = pipeline.read_raw(raw_path)
            if len(text.strip()) < 30:
                raise ValueError("文件里没有足够文字")
            system = E.load_prompt(kind)
            reply = E.call_llm(system, text)
            obj = E.parse_json(reply)
            obj, killed = E.verify_evidence(obj, text)
            obj = E.fix_enums(obj)
            ref = db.ref_of(raw_name, kind)
            obj["cv_ref" if kind == "cv" else "jd_id"] = ref
            obj["_meta"] = {
                "source": raw_name,
                "group": g,
                "model": E.MODEL,
                "extracted_at": datetime.now().isoformat(timespec="seconds"),
                "evidence_rejected": killed,
            }
            results.append({"g": g, "label_name": label_name, "obj": obj, "text": text})
        except Exception as e:
            fails.append((raw_name, f"{type(e).__name__}: {e}"))

    # 阶段二：向量
    for i, r in enumerate(results, 1):
        if progress:
            progress({"action": "embed", "i": i, "n": len(results),
                      "file": r["label_name"]})
        try:
            obj, text = r["obj"], r["text"]
            if kind == "jd":
                t = EMB.jd_text(obj, text)
            else:
                t = EMB.cv_text(obj, text)
            v = pipeline.embed_text(t)
            obj["embedding"] = [round(float(x), 6) for x in v]
            obj["_meta"]["embedding_model"] = EMB.MODEL
            obj["_meta"]["embedding_norm"] = "l2"
        except Exception as e:
            fails.append((r["label_name"], f"向量失败 {type(e).__name__}: {e}"))

    # 阶段三：写盘
    for r in results:
        dst = os.path.join(db.label_root(kind), r["g"], r["label_name"])
        with open(dst, "w", encoding="utf-8") as fh:
            json.dump(r["obj"], fh, ensure_ascii=False, indent=2)

    return len(results), fails


def save_uploads(kind, group, files):
    """把上传的文件存进原始库。files = [(filename, bytes)]"""
    db.ensure_group(kind, group)
    saved, skipped = [], []
    for name, blob in files:
        base, ext = os.path.splitext(os.path.basename(name))
        ext = ext.lower()
        if ext not in db.RAW_EXT_OK:
            skipped.append((name, f"不支持的格式 {ext}"))
            continue
        target = db.unique_raw_name(kind, base, ext)
        path = os.path.join(db.raw_root(kind), group, target)
        with open(path, "wb") as fh:
            fh.write(blob)
        saved.append(target)
    return saved, skipped
