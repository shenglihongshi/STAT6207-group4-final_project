# -*- coding: utf-8 -*-
"""端到端流程：任意格式 JD → 本地 LLM 抽标签 → 11 维特征 → 排序 → Top-N。

命令行与 Web 共用这一层，避免两边逻辑分叉。
"""
import json
import os
import sys
import urllib.request

import numpy as np

ROOT = r"D:\港硕授课与课堂内容\STAT6207_group7_finalproject"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "main", "LLM_program"))

import extract as E
import features as F
import db
import embed as EMB          # jd_text / cv_text 的拼接口径在这里，不要写成 E.jd_text

EXT = os.path.join(ROOT, "main", "match_work", "extracted")
SRC_CV = os.path.join(ROOT, "dataset_from_blackboard", "CV_examples")
EMB_URL = "http://127.0.0.1:1235/v1/embeddings"
EMB_MODEL = "text-embedding-nomic-embed-text-v1.5"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# ---------------------------------------------------------------- 文本解析

def read_upload(filename, blob):
    """把上传的二进制变成纯文本。支持 txt/md/pdf/docx"""
    name = (filename or "").lower()
    if name.endswith((".txt", ".md", ".csv")):
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                return blob.decode(enc)
            except UnicodeDecodeError:
                continue
        return blob.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        import io

        import pymupdf
        doc = pymupdf.open(stream=blob, filetype="pdf")
        return "\n".join(p.get_text() for p in doc)
    if name.endswith(".docx"):
        import io

        import docx
        d = docx.Document(io.BytesIO(blob))
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts += [c.text for c in row.cells]
        return "\n".join(parts)
    # 兜底：当文本读
    return blob.decode("utf-8", errors="ignore")


# ---------------------------------------------------------------- 抽取

def llm_alive():
    try:
        with OPENER.open("http://127.0.0.1:1235/v1/models", timeout=4) as r:
            d = json.loads(r.read().decode())
        return any("qwen" in m.get("id", "").lower() for m in d.get("data", []))
    except Exception:
        return False


def extract_jd(text):
    """把 JD 文本抽成结构化字段。返回 (dict, 被作废字段列表)"""
    system = E.load_prompt("jd")
    reply = E.call_llm(system, text)
    obj = E.parse_json(reply)
    obj, killed = E.verify_evidence(obj, text)
    obj = E.fix_enums(obj)
    obj.pop("jd_id", None)          # 新 JD 没有编号
    return obj, killed


def embed_text(text):
    """现算一份 JD 的向量（不写入缓存，避免污染训练集）"""
    req = urllib.request.Request(
        EMB_URL,
        data=json.dumps({"model": EMB_MODEL, "input": [text]}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with OPENER.open(req, timeout=60) as r:
        d = json.loads(r.read().decode())
    v = np.array(d["data"][0]["embedding"], dtype="float32")
    n = np.linalg.norm(v)
    return v / n if n else v


def jd_text_for_embed(obj, raw):
    return EMB.jd_text(obj, raw)


# ---------------------------------------------------------------- 匹配

def read_raw(path):
    """读原始文件成文本（txt/pdf/docx 都走同一个解析器）"""
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        blob = f.read()
    return read_upload(os.path.basename(path), blob)


class Matcher:
    """候选池来自「标签 CV 库」，向量直接读标签文件里自带的 768 维。"""

    def __init__(self, weights_key="learned_all44", group=None):
        self.group = group
        self.cvs = self._load_cvs(group)
        with open(os.path.join(HERE, "weights.json"), encoding="utf-8") as fh:
            wj = json.load(fh)
        self.names = wj["feature_names"]
        self.w = np.array(wj[weights_key], dtype=float)

    def _load_cvs(self, group):
        out = []
        for ref, info in db.index("cv", group).items():
            with open(info["label"], encoding="utf-8") as fh:
                o = json.load(fh)
            o["cv_ref"] = ref
            o["_group"] = info["group"]
            out.append(F.prepare_cv(o, read_raw(info["raw"])))
        return out

    def match(self, jd, jd_raw, jd_vec=None, top=5):
        feats = F.build_pool_features(jd, jd_raw, self.cvs, jd_key=None, jd_vec=jd_vec)
        rows = []
        for cv in self.cvs:
            ref = cv["cv_ref"]
            vec = feats[ref]
            rows.append((float(np.dot(self.w, vec)), ref, cv, vec))
        rows.sort(key=lambda x: -x[0])

        out = []
        for i, (score, ref, cv, vec) in enumerate(rows[:top], 1):
            out.append({
                "rank": i,
                "cv_ref": ref,
                "group": cv.get("_group"),
                "score": round(score, 3),
                "title": cv.get("current_title"),
                "company": cv.get("current_company"),
                "country": cv.get("country"),
                "years": cv.get("_years"),
                "seniority": cv.get("_seniority"),
                "skills_top": (cv.get("skills") or [])[:10],
                "reason": reason(jd, cv),
                "reason_facts": reason_facts(jd, cv),
                "features": {n: round(float(v), 3) for n, v in zip(self.names, vec)},
            })
        return out

    def match_by_id(self, jd_ref, top=5):
        """用库里已打标的 JD（读标签文件自带的向量，不重算）"""
        info = db.index("jd", self.group).get(jd_ref)
        if not info:
            raise FileNotFoundError(jd_ref)
        with open(info["label"], encoding="utf-8") as fh:
            jd = json.load(fh)
        raw = read_raw(info["raw"])
        vec = np.asarray(jd["embedding"], dtype="float32") if jd.get("embedding") else None
        return jd, self.match(jd, raw, jd_vec=vec, top=top)


def reason(jd, cv):
    """理由只陈述事实：命中技能、年限、地点、学历"""
    jm = F.skill_set(jd.get("must_have_skills"))
    cs = F.skill_set(cv.get("skills"))
    hit = sorted(jm & cs)
    bits = []
    if jm:
        bits.append(f"必备技能命中 {len(hit)}/{len(jm)}")
        if hit:
            bits.append("（" + "、".join(hit[:4]) + "）")
    yrs = cv.get("_years")
    if yrs is not None:
        req = jd.get("min_years")
        bits.append(f"{yrs:g} 年经验" + (f"（要求 {req} 年）" if req else ""))
    jc, cc = jd.get("country"), cv.get("country")
    if jc and cc:
        bits.append("同国" if str(jc).lower() == str(cc).lower() else f"异地（{cc}）")
    if cv.get("seniority_display") or cv.get("_seniority"):
        bits.append(f"职级 {cv.get('_seniority')}")
    return "".join(bits[:2]) + ("；" + "；".join(bits[2:]) if len(bits) > 2 else "")


def reason_facts(jd, cv):
    """理由的结构化版本：前端按当前语言自己拼句子，避免中英混杂。"""
    facts = []
    jm = F.skill_set(jd.get("must_have_skills"))
    cs = F.skill_set(cv.get("skills"))
    if jm:
        hit = sorted(jm & cs)
        facts.append({"k": "skill", "hit": len(hit), "total": len(jm),
                      "names": hit[:4]})
    yrs = cv.get("_years")
    if yrs is not None:
        facts.append({"k": "years", "y": float(yrs), "req": jd.get("min_years")})
    jc, cc = jd.get("country"), cv.get("country")
    if jc and cc:
        same = str(jc).lower() == str(cc).lower()
        facts.append({"k": "loc", "same": same, "cv": None if same else cc})
    sen = cv.get("_seniority")
    if cv.get("seniority_display") or sen:
        facts.append({"k": "sen", "v": sen})
    return facts
