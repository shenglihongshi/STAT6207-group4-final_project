# -*- coding: utf-8 -*-
"""
本地 LLM 抽取器：把 JD / CV 的纯文本，按抽取规范转成结构化 JSON。

用法：
    python extract.py --jd JD-01          # 抽一份 JD（试跑）
    python extract.py --cv CV-042         # 抽一份 CV
    python extract.py --all               # 全部 150 份（已存在则跳过，可断点续跑）
    python extract.py --all --force       # 强制重跑
    python extract.py --all --only fail   # 只重跑上次失败的

设计要点：
- 只依赖标准库，不需要 pip install
- 必须绕过系统代理，否则访问 127.0.0.1 会 502
- 每份文档抽一次，结果缓存成同名 .json；已存在则跳过
- evidence 回原文逐字校验，对不上就把该字段置 null（防编造）
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根，由本文件位置反推
PROMPT_DIR = os.path.join(ROOT, "main", "LLM_program")
SRC_JD = os.path.join(ROOT, "dataset_from_blackboard", "JD_examples")
SRC_CV = os.path.join(ROOT, "dataset_from_blackboard", "CV_examples")
OUT_DIR = os.path.join(ROOT, "main", "match_work", "extracted")
OUT_JD = os.path.join(OUT_DIR, "JD")
OUT_CV = os.path.join(OUT_DIR, "CV")


def out_dir(kind):
    """JD 与 CV 分目录存放，避免混在一起"""
    return OUT_JD if kind == "jd" else OUT_CV
LOG_PATH = os.path.join(ROOT, "main", "match_work", "extract_log.txt")

ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://127.0.0.1:1235/v1/chat/completions")
MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.5-9b")
TIMEOUT = 300

# 程序注入的编号字段，模型输出 null，这里填回真值
ID_FIELDS = {"jd": "jd_id", "cv": "cv_ref"}


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_prompt(kind):
    name = "抽取规范_JD侧.md" if kind == "jd" else "抽取规范_CV侧.md"
    with open(os.path.join(PROMPT_DIR, name), encoding="utf-8") as f:
        return f.read()


def call_llm(system, text, max_tokens=3000):
    """调本地 OpenAI 兼容接口。

    关 thinking 只有 reasoning_effort="none" 有效（实测）：
    chat_template_kwargs 和 /no_think 都不被 LM Studio 透传，模型会只输出思维链、content 为空。
    """
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    variants = [
        dict(base, reasoning_effort="none"),
    ]
    last_err = None
    for i, payload in enumerate(variants):
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with opener.open(req, timeout=TIMEOUT) as r:
                data = json.loads(r.read().decode("utf-8"))
            choice = data["choices"][0]
            msg = choice["message"]
            content = msg.get("content") or ""
            finish = choice.get("finish_reason")
            if finish == "length":
                raise RuntimeError("输出被上下文截断（finish_reason=length），JSON 不完整")
            if not content.strip():
                raise RuntimeError("content 为空（thinking 未关闭？）")
            return content
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            last_err = f"HTTP {e.code}: {body}"
            if i == 0:
                log(f"    ! 请求被拒（{e.code}），换参数重试")
                continue
            raise RuntimeError(last_err)
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            if i == 0:
                continue
            raise RuntimeError(last_err)
    raise RuntimeError(last_err or "unknown")


def _repair_quotes(s):
    """修复字符串值内部的裸双引号（模型抄原文时带进来的，如 "Frequently Bought Together"）。

    做法：逐字符扫描，遇到引号时向后看第一个非空白字符——
    是 , } ] : 就认为它是字符串结束，否则视为值内部的引号，替换成中文引号。
    """
    out, n, i, in_str = [], len(s), 0, False
    while i < n:
        ch = s[i]
        if in_str and ch == "\\":
            out.append(ch)
            if i + 1 < n:
                out.append(s[i + 1])
            i += 2
            continue
        if ch == '"':
            if not in_str:
                in_str = True
                out.append(ch)
            else:
                j = i + 1
                while j < n and s[j] in " \t\r\n":
                    j += 1
                if j < n and s[j] in ",}]:[{":
                    in_str = False
                    out.append(ch)
                else:
                    out.append("“" if out and out[-1] not in " “" else "”")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_json(txt):
    """从模型回复里剥出 JSON 对象。先严格解析，失败再修引号重试。"""
    s = txt.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("回复里没有 JSON 对象：" + txt[:200])
    body = s[i:j + 1]
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        repaired = _repair_quotes(body)
        return json.loads(repaired)


def norm(s):
    return re.sub(r"\s+", "", str(s)).lower()


def _snippet_ok(snippet, raw_n):
    """判断一条 evidence 是否可信。

    - 整段能在原文找到 → 通过
    - 找不到时按换行/分号/竖线切成片段，只要有片段能找到 → 通过
      （模型常把"Position: X"和"Job Title: X"拼在一起，但原文里这两句并不相邻）
    """
    if isinstance(snippet, list):
        items = [s for s in snippet if isinstance(s, str) and s.strip()]
        if not items:
            return True
        hits = sum(1 for s in items if _snippet_ok(s, raw_n))
        return hits >= max(1, len(items) * 0.5)
    s = str(snippet)
    if norm(s) in raw_n:
        return True
    parts = [p for p in re.split(r"[\n;|]+", s) if len(p.strip()) > 3]
    return any(norm(p) in raw_n for p in parts)


# 程序注入的编号字段，不参与 evidence 校验
ID_KEYS = {"jd_id", "cv_ref"}

# 必须逐字来自原文的字段：没有对应 evidence 就置空
STRICT_FIELDS = {
    "position", "country", "city", "salary_min_raw", "salary_max_raw",
    "currency", "salary_frequency", "education", "latest_degree",
    "current_title", "current_company",
}

# 派生/归类字段：允许没有独立 evidence（由其他字段推断而来）
LENIENT_FIELDS = {
    "role_family", "domain", "seniority", "highest_degree", "min_years",
    "contract_type", "remote_allowed", "notice_expectation", "education_required",
    "languages", "skills", "must_have_skills", "nice_to_have_skills", "work_history",
}


def verify_evidence(obj, raw_text):
    """evidence 回校验。

    - 编号字段（jd_id/cv_ref）不校验，由程序注入
    - **整份没有 evidence**：不做校验，保留原值，但在 _meta 里标记，供人工复核
    - 严格字段（位置/薪资/学历原文等）：必须有 evidence，且能在原文定位
    - 其他字段：有 evidence 才校验，没有则保留（它们是从其他字段推断的）
    """
    ev = obj.get("evidence") or {}
    if not isinstance(ev, dict):
        ev = {}
    if not ev:
        obj.setdefault("_meta", {})["evidence_missing"] = True
        return obj, ["(整份无 evidence，未校验)"]

    raw_n = norm(raw_text)
    killed = []
    for field in list(obj.keys()):
        if field.startswith("_") or field == "evidence" or field in ID_KEYS:
            continue
        val = obj.get(field)
        if val in (None, [], ""):
            continue
        snippet = ev.get(field)
        if snippet is None:
            if field in STRICT_FIELDS:
                killed.append(field + "(无evidence)")
                obj[field] = None
            continue
        if not _snippet_ok(snippet, raw_n):
            killed.append(field)
            obj[field] = None
    return obj, killed


# 枚举纠偏：模型偶尔会自造值，映射到白名单
ENUM_FIX = {
    "highest_degree": {
        "associate": "diploma", "associate's": "diploma", "associates": "diploma",
        "bachelors": "bachelor", "bachelor's": "bachelor",
        "masters": "master", "master's": "master", "mba": "master",
        "doctorate": "phd", "doctoral": "phd",
        "highschool": "high_school", "secondary": "high_school",
    },
}


def fix_enums(obj):
    for field, mapping in ENUM_FIX.items():
        v = obj.get(field)
        if isinstance(v, str) and v.lower().strip() in mapping:
            obj[field] = mapping[v.lower().strip()]
    return obj


def extract_one(kind, stem, force=False, max_retry=2):
    src = os.path.join(SRC_JD if kind == "jd" else SRC_CV, stem + ".txt")
    out = os.path.join(out_dir(kind), stem + ".json")
    if os.path.exists(out) and not force:
        return "skip", 0.0, None
    if not os.path.exists(src):
        return "missing", 0.0, None

    with open(src, encoding="utf-8") as f:
        raw = f.read()
    system = load_prompt(kind)

    t0 = time.time()
    last_err = None
    for attempt in range(max_retry + 1):
        try:
            reply = call_llm(system, raw)
            obj = parse_json(reply)
            obj, killed = verify_evidence(obj, raw)
            obj = fix_enums(obj)
            # 编号注入：JD-01 → 1；P01 → "P01"（测试集必须与训练集编号区分开）
            if kind == "jd":
                if stem.upper().startswith("P") and not stem.upper().startswith("JD"):
                    obj["jd_id"] = stem
                else:
                    m = re.search(r"(\d+)", stem)
                    obj["jd_id"] = int(m.group(1)) if m else None
            else:
                obj[ID_FIELDS[kind]] = stem
            obj["_meta"] = {
                "source": os.path.relpath(src, ROOT),
                "model": MODEL,
                "extracted_at": datetime.now().isoformat(timespec="seconds"),
                "evidence_rejected": killed,
            }
            os.makedirs(out_dir(kind), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            dt = time.time() - t0
            n_null = sum(1 for k, v in obj.items() if v is None and k not in ("_meta",))
            return "ok", dt, f"字段 {len(obj)-2} 个，空值 {n_null} 个，evidence 作废 {len(killed)} 个"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < max_retry:
                log(f"    ! {stem} 第 {attempt+1} 次失败：{last_err[:160]}")
                time.sleep(2)
    return "fail", time.time() - t0, last_err


def collect(kind):
    d = SRC_JD if kind == "jd" else SRC_CV
    return sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.lower().endswith(".txt"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jd")
    ap.add_argument("--cv")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", choices=["fail"], help="只重跑缺失或失败的")
    args = ap.parse_args()

    jobs = []
    if args.jd:
        jobs.append(("jd", args.jd))
    if args.cv:
        jobs.append(("cv", args.cv))
    if args.all:
        jobs += [("jd", s) for s in collect("jd")]
        jobs += [("cv", s) for s in collect("cv")]

    if not jobs:
        ap.print_help()
        return 1

    os.makedirs(OUT_JD, exist_ok=True)
    os.makedirs(OUT_CV, exist_ok=True)
    log(f"=== 开始：{len(jobs)} 份 | 模型 {MODEL} | 端点 {ENDPOINT} ===")
    stat = {"ok": 0, "skip": 0, "fail": 0, "missing": 0}
    t_start = time.time()
    for idx, (kind, stem) in enumerate(jobs, 1):
        status, dt, info = extract_one(kind, stem, force=args.force)
        stat[status] = stat.get(status, 0) + 1
        if status == "ok":
            log(f"[{idx}/{len(jobs)}] {stem} OK  {dt:5.1f}s  {info}")
        elif status == "fail":
            log(f"[{idx}/{len(jobs)}] {stem} FAIL  {dt:5.1f}s  {info}")
        elif status == "missing":
            log(f"[{idx}/{len(jobs)}] {stem} 源文件不存在")
    total = time.time() - t_start
    log(f"=== 结束：ok={stat['ok']} skip={stat['skip']} fail={stat['fail']} missing={stat['missing']} | 总耗时 {total/60:.1f} 分钟 ===")
    return 0 if stat["fail"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
