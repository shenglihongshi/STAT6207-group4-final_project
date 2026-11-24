# -*- coding: utf-8 -*-
"""特征计算：把 (JD, CV) 这一对压成 10 维向量。

10 维的顺序固定，训练与评测必须一致：
  0 skill_must    必备技能加权重合率
  1 skill_nice    加分技能重合率
  2 years_fit     年限达标度
  3 seniority_fit 资历层级匹配
  4 location      地点相容（远程岗位恒为 1）
  5 language      语言覆盖率（任一侧未知 → 0.5，不计入惩罚）
  6 domain        行业匹配
  7 education     学历达标
  8 tfidf         整篇词面相似
  9 skill_jaccard 技能集合 Jaccard
"""
import os
import re
from datetime import date

FEATURE_NAMES = [
    "skill_must", "skill_nice", "years_fit", "seniority_fit", "location",
    "language", "domain", "education", "tfidf", "skill_jaccard", "semantic",
]

# ---------------------------------------------------------------- embedding

_EMB = None


def load_embeddings():
    """加载缓存的向量（embed.py 产出）。没有则返回 None，语义维退化为 0.5"""
    global _EMB
    if _EMB is not None:
        return _EMB
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings.npz")
    if not os.path.exists(path):
        _EMB = {}
        return _EMB
    import numpy as np
    d = np.load(path, allow_pickle=True)
    _EMB = {}
    for k in ("JD", "CV"):
        refs, vecs = d[k + "_refs"], d[k + "_vecs"]
        norm = np.linalg.norm(vecs, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        _EMB[k] = {r: (v / n).astype("float32") for r, v, n in zip(refs, vecs, norm)}
    return _EMB


def semantic_sim(jd_key, cv_ref):
    """余弦相似度。先查训练集 JD，再查测试集 P-JD；都没有 → None"""
    emb = load_embeddings()
    if not emb:
        return None
    jv = emb.get("JD", {}).get(jd_key)
    if jv is None:
        jv = emb.get("P-JD", {}).get(jd_key)
    cv = emb.get("CV", {}).get(cv_ref)
    if cv is None:
        cv = emb.get("P-CV", {}).get(cv_ref)
    if jv is None or cv is None:
        return None
    return float((jv * cv).sum())

# ---------------------------------------------------------------- 技能归一

SKILL_ALIAS = {
    "k8s": "kubernetes", "gcp": "google cloud", "postgres": "postgresql",
    "react.js": "react", "reactjs": "react", "node.js": "nodejs", "node": "nodejs",
    "next.js": "nextjs", "vue.js": "vue", "ci/cd": "cicd", "cicd": "cicd",
    ".net": "dotnet", "dotnet core": "dotnet", "ts": "typescript", "js": "javascript",
    "ml": "machine learning", "dl": "deep learning", "nlp": "natural language processing",
    "cv": "computer vision", "llm": "large language model", "llms": "large language model",
    "aws": "amazon web services", "azure": "microsoft azure",
    "es": "elasticsearch", "ms sql": "sql server", "mssql": "sql server",
    "rest": "rest api", "restful": "rest api", "rest apis": "rest api",
    "powerbi": "power bi", "tableau": "tableau",
}


def norm_skill(s):
    s = str(s).lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(?<=[a-z])\d+(\.\d+)?$", "", s)      # python3 -> python
    return SKILL_ALIAS.get(s, s)


def skill_set(items):
    if not items:
        return set()
    return {norm_skill(x) for x in items if str(x).strip()}


def weighted_overlap(need, have):
    """need 中有多少被 have 覆盖。need 为空 → None（不参与）"""
    need = skill_set(need)
    if not need:
        return None
    have = skill_set(have)
    return len(need & have) / len(need)


def jaccard(a, b):
    a, b = skill_set(a), skill_set(b)
    if not a or not b:
        return None
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------- 派生字段

def parse_ym(s):
    if not s:
        return None
    s = str(s).strip().lower()
    if s in ("present", "current", "now", "至今"):
        return date.today()
    m = re.match(r"(\d{4})-(\d{1,2})", s)
    if m:
        return date(int(m.group(1)), min(max(int(m.group(2)), 1), 12), 1)
    m = re.match(r"(\d{4})", s)
    if m:
        return date(int(m.group(1)), 1, 1)
    return None


def years_from_history(hist):
    """按区间累加，去重叠（区间并集）"""
    spans = []
    for job in hist or []:
        a, b = parse_ym(job.get("start")), parse_ym(job.get("end"))
        if a and b and b >= a:
            spans.append((a, b))
    if not spans:
        return None
    spans.sort()
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    days = sum((b - a).days for a, b in merged)
    return round(days / 365.25, 1)


LEVEL = {"junior": 1, "mid": 2, "senior": 3, "lead": 4}


def infer_seniority(title, hist=None):
    t = (title or "").lower()
    if re.search(r"\b(cto|cio|chief|head of|vp|vice president|director)\b", t):
        return "lead"
    if re.search(r"\b(lead|principal|staff|manager)\b", t):
        return "lead"
    if re.search(r"\b(senior|sr)\b", t):
        return "senior"
    if re.search(r"\b(junior|jr|intern|trainee|graduate|associate|entry)\b", t):
        return "junior"
    if t:
        return "mid"
    return None


def seniority_fit(jd_sen, cv_sen):
    if not jd_sen or not cv_sen:
        return None
    a, b = LEVEL.get(jd_sen), LEVEL.get(cv_sen)
    if not a or not b:
        return None
    return max(0.0, 1 - abs(a - b) / 3)


DEG_LEVEL = {"high_school": 1, "diploma": 2, "bachelor": 3, "master": 4, "phd": 5}


def education_fit(jd_edu, cv_deg):
    if not jd_edu or not cv_deg:
        return None
    a, b = DEG_LEVEL.get(jd_edu), DEG_LEVEL.get(cv_deg)
    if not a or not b:
        return None
    return 1.0 if b >= a else 0.5


# ---------------------------------------------------------------- 逐项特征

DOMAIN_NEIGHBOR = {
    ("software", "data-ai"), ("software", "fintech"), ("software", "ecommerce"),
    ("fintech", "ecommerce"), ("manufacturing", "logistics"), ("retail", "ecommerce"),
    ("marketing", "retail"), ("consulting", "software"),
}


def domain_match(a, b):
    if not a or not b:
        return None
    if a == b:
        return 1.0
    if (a, b) in DOMAIN_NEIGHBOR or (b, a) in DOMAIN_NEIGHBOR:
        return 0.5
    return 0.0


def location_compat(jd, cv):
    """国家相同 = 1；JD 允许远程 = 1；任一未知 = None；明确不同 = 0"""
    if jd.get("remote_allowed") is True:
        return 1.0
    jc, cc = jd.get("country"), cv.get("country")
    if not jc or not cc:
        return None
    return 1.0 if str(jc).strip().lower() == str(cc).strip().lower() else 0.0


def language_compat(jd, cv):
    need = jd.get("languages")
    have = cv.get("languages")
    if not need:
        return None
    need_set = {str(x.get("lang", x)).lower() for x in need} if isinstance(need, list) else set()
    if not need_set:
        return None
    if not have:
        return 0.5                      # 候选人没写 ≠ 不会
    have_set = {str(x.get("lang", x)).lower() for x in have} if isinstance(have, list) else set()
    if not have_set:
        return 0.5
    return len(need_set & have_set) / len(need_set)


def years_fit(jd_min, cv_years):
    if jd_min is None or cv_years is None:
        return None
    if cv_years >= jd_min:
        return 1.0
    gap = jd_min - cv_years
    if gap <= 1:
        return 0.8
    if gap <= 3:
        return 0.4
    return 0.0


# ---------------------------------------------------------------- 组装

def _v(x, default=0.5):
    """缺失统一填中性值 0.5，避免把「不知道」当成「不合格」"""
    return default if x is None else float(x)


def build_pool_features(jd, jd_text, cvs, jd_key=None, jd_vec=None):
    """给一个 JD 和一组候选 CV，产出 {cv_ref: 10 维向量}。

    TF-IDF 在池内统一拟合，保证同一 query 内可比。
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    jd_skills_must = jd.get("must_have_skills")
    jd_skills_nice = jd.get("nice_to_have_skills")
    jd_domain = jd.get("domain")
    jd_edu = jd.get("education_required")
    jd_sen = jd.get("seniority")
    jd_min = jd.get("min_years")

    texts = [jd_text or ""] + [c.get("_text", "") or "" for c in cvs]
    try:
        vec = TfidfVectorizer(max_features=4000, stop_words="english",
                              ngram_range=(1, 1), sublinear_tf=True)
        mat = vec.fit_transform(texts)
        sims = (mat[0] @ mat[1:].T).toarray()[0]
    except Exception:
        sims = [0.0] * len(cvs)

    out = {}
    if jd_key is None and jd.get("jd_id") is not None:
        jd_key = f"JD-{jd['jd_id']:02d}" if isinstance(jd["jd_id"], int) else str(jd["jd_id"])
    import numpy as _np
    emb_cv = (load_embeddings().get("CV", {}) if jd_vec is not None else {})
    for cv, sim in zip(cvs, sims):
        # 优先用标签文件里自带的向量（新库），没有再回退到 npz 缓存（旧路径）
        cv_emb = cv.get("embedding")
        if jd_vec is not None and cv_emb is not None:
            v = _np.asarray(cv_emb, dtype="float32")
            n = float(_np.linalg.norm(v))
            sem = float((jd_vec * (v / n if n else v)).sum())
        elif jd_vec is not None:
            cvv = emb_cv.get(cv["cv_ref"])
            sem = float((jd_vec * cvv).sum()) if cvv is not None else None
        else:
            sem = semantic_sim(jd_key, cv["cv_ref"]) if jd_key else None
        vec = [
            _v(weighted_overlap(jd_skills_must, cv.get("skills"))),
            _v(weighted_overlap(jd_skills_nice, cv.get("skills"))),
            _v(years_fit(jd_min, cv.get("_years"))),
            _v(seniority_fit(jd_sen, cv.get("_seniority"))),
            _v(location_compat(jd, cv)),
            _v(language_compat(jd, cv)),
            _v(domain_match(jd_domain, cv.get("domain"))),
            _v(education_fit(jd_edu, cv.get("highest_degree"))),
            float(sim),
            _v(jaccard(jd_skills_must, cv.get("skills"))),
            _v(sem, 0.5),
        ]
        out[cv["cv_ref"]] = vec
    return out


def prepare_cv(cv, raw_text=None):
    """补上程序派生字段：总工龄、职级、原文（供 TF-IDF）"""
    cv = dict(cv)
    cv["_years"] = years_from_history(cv.get("work_history"))
    cv["_seniority"] = infer_seniority(cv.get("current_title"), cv.get("work_history"))
    cv["_text"] = raw_text if raw_text is not None else (
        " ".join([str(cv.get("current_title") or ""),
                  str(cv.get("current_company") or ""),
                  " ".join(map(str, cv.get("skills") or []))]))
    return cv
