# -*- coding: utf-8 -*-
"""本地 Web 服务：上传 JD → 抽取 → 匹配 → Top-5。

启动：python app.py
访问：http://127.0.0.1:5000
"""
import json
import os
import re
import sys
import threading
import traceback
from datetime import datetime

from flask import Flask, jsonify, render_template, request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import db
import labeler
import pipeline

UPLOAD_DIR = os.path.join(HERE, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
db.ensure_layout()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

print("正在加载简历库与权重…")
MATCHER = pipeline.Matcher()
print(f"就绪：{len(MATCHER.cvs)} 份简历")

# 打标任务的进度状态（单线程，一次只跑一个）
LABEL_STATE = {"running": False, "kind": None, "phase": {"action": "idle"},
               "done": 0, "total": 0, "fails": [], "message": None}


# 错误文案只在这里定义中文；前端按 error_key 换成英文。
# 接口同时返回 error（中文），兼容不看 error_key 的调用方。
ERR_ZH = {
    "kind_invalid": "类型必须是 jd 或 cv",
    "group_empty": "组名不能为空",
    "group_charset": '组名不能包含 \\ / : * ? " < > |',
    "no_files": "没有收到文件",
    "label_running": "已有打标任务在运行",
    "nothing_pending": "没有需要打标的文件",
    "llm_off_label": "本地模型未启动，请先在 LM Studio 点 Start Server",
    "llm_off_match": ("本地模型服务未启动。请在 LM Studio 里点 Start Server（端口 1235）后重试；"
                      "也可以改用下方的示例岗位，那条路径不需要模型。"),
    "jd_not_found": "找不到 {name}",
    "parse_fail": "文件解析失败：{err}",
    "no_text": "没有拿到任何文本",
    "text_too_short": "文本太短，看不出是岗位描述",
    "extract_fail": "抽取或匹配失败：{err}",
    "no_file": "没有拿到文件",
    "bad_format": "只支持 .txt / .md / .pdf / .docx",
    "parse_fail_short": "解析失败：{err}",
    "no_text_pdf": "文件里没有可提取的文字（可能是扫描件或纯图片 PDF）",
    "file_not_found": "找不到该文件",
    "kind_unknown": "未知类型",
    "file_missing": "文件不存在：{name}",
    "open_unsupported": "当前系统不支持直接打开",
    "open_fail": "打不开：{err}",
    "cv_not_found": "找不到该简历",
}


def fail(key, status=400, **args):
    zh = ERR_ZH.get(key, key)
    try:
        zh = zh.format(**args) if args else zh
    except (KeyError, IndexError):
        pass
    return jsonify({"ok": False, "error": zh, "error_key": key,
                    "error_args": args}), status


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({
        "llm": pipeline.llm_alive(),
        "library_size": len(MATCHER.cvs),
        "weights": "learned_all44",
    })


@app.route("/api/examples")
def examples():
    """库里已打标的 JD（不需要模型即可检索）"""
    out = []
    for ref, info in db.index("jd").items():
        with open(info["label"], encoding="utf-8") as fh:
            o = json.load(fh)
        out.append({
            "id": ref,
            "position": o.get("position"),
            "family": o.get("role_family"),
            "country": o.get("country"),
            "group": info["group"],
        })
    out.sort(key=lambda x: x["id"])
    return jsonify(out[:60])


@app.route("/api/library")
def library():
    """库状态：各组数量、待打标数"""
    rows = db.summary()
    detail = {}
    for kind in ("jd", "cv"):
        detail[kind] = []
        for g in db.groups(kind):
            raws = db.raw_files(kind, g)
            labs = db.label_files(kind, g)
            pend = [p for p in db.pending(kind) if p[0] == g]
            detail[kind].append({
                "group": g,
                "raw": len(raws),
                "labelled": len(labs),
                "pending": len(pend),
            })
    return jsonify({"summary": rows, "detail": detail,
                    "label_state": LABEL_STATE})


@app.route("/api/groups")
def api_groups():
    return jsonify({"jd": db.groups("jd"), "cv": db.groups("cv")})


@app.route("/api/group", methods=["POST"])
def create_group():
    body = request.get_json(force=True) or {}
    kind = body.get("kind", "cv")
    group = (body.get("group") or "").strip()
    if kind not in db.KINDS:
        return fail("kind_invalid")
    if not group:
        return fail("group_empty")
    if re.search(r'[\\/:*?"<>|]', group):
        return fail("group_charset")
    db.ensure_group(kind, group)
    return jsonify({"ok": True, "groups": db.groups(kind)})


@app.route("/api/upload", methods=["POST"])
def upload():
    """批量上传到指定库的指定组"""
    kind = request.form.get("kind", "cv")
    group = (request.form.get("group") or db.DEFAULT_GROUP).strip() or db.DEFAULT_GROUP
    if kind not in db.KINDS:
        return fail("kind_invalid")
    files = request.files.getlist("files")
    if not files:
        return fail("no_files")
    payload = [(f.filename, f.read()) for f in files if f and f.filename]
    saved, skipped = labeler.save_uploads(kind, group, payload)
    return jsonify({"ok": True, "saved": saved, "skipped": skipped,
                    "group": group, "kind": kind, "count": len(saved)})


@app.route("/api/label", methods=["POST"])
def start_label():
    """对缺标签的文件批量打标（后台跑，接口立即返回）"""
    body = request.get_json(force=True) or {}
    kind = body.get("kind", "cv")
    if kind not in db.KINDS:
        return fail("kind_invalid")
    if LABEL_STATE["running"]:
        return fail("label_running", 409)

    todo = db.pending(kind)
    if not todo:
        return fail("nothing_pending")
    if not pipeline.llm_alive():
        return fail("llm_off_label", 503)

    LABEL_STATE.update({"running": True, "kind": kind,
                        "phase": {"action": "prepare"},
                        "done": 0, "total": len(todo), "fails": [], "message": None})

    def worker():
        def progress(ev):
            # ev 是 dict：{"action": "extract"|"embed", "i":1, "n":30, "file": "..."}
            if isinstance(ev, dict):
                LABEL_STATE["done"] = max(0, int(ev.get("i", 1)) - 1)
                LABEL_STATE["phase"] = ev
            else:                                   # 兼容旧字符串
                m = re.match(r"\[(\d+)/(\d+)\]", str(ev))
                if m:
                    LABEL_STATE["done"] = int(m.group(1)) - 1
                LABEL_STATE["phase"] = {"action": "text", "text": str(ev)}

        try:
            ok, fails = labeler.label_pending(kind, progress=progress)
            LABEL_STATE["message"] = {"code": "done", "ok": ok, "fail": len(fails)}
            LABEL_STATE["fails"] = [{"file": f, "error": e} for f, e in fails]
            # 打标后重建候选池
            global MATCHER
            MATCHER = pipeline.Matcher()
        except Exception as e:
            traceback.print_exc()
            LABEL_STATE["message"] = {"code": "error", "msg": str(e)}
        finally:
            LABEL_STATE["running"] = False
            LABEL_STATE["done"] = LABEL_STATE["total"]

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"ok": True, "total": len(todo)})


@app.route("/api/label_status")
def label_status():
    return jsonify(LABEL_STATE)


@app.route("/api/match-id", methods=["POST"])
def match_by_id():
    body = request.get_json(force=True) or {}
    jd_id = body.get("jd_id")
    top = int(body.get("top", 5))
    try:
        jd, results = MATCHER.match_by_id(jd_id, top=top)
        info = db.index("jd").get(jd_id)
        raw = pipeline.read_raw(info["raw"]) if info else ""
        return jsonify({"ok": True, "jd": summarize_jd(jd), "results": results,
                        "mode": "existing", "jd_id": jd_id, "jd_raw": raw[:20000]})
    except FileNotFoundError:
        return fail("jd_not_found", 404, name=jd_id)
    except Exception as e:
        traceback.print_exc()
        return fail("extract_fail", 500, err=str(e))


@app.route("/api/match", methods=["POST"])
def match_upload():
    top = int(request.form.get("top", 5))
    text = (request.form.get("text") or "").strip()
    upload_name = request.form.get("upload_name") or None

    # 情况一：前端已经预览过，文件已落在 uploads/ 里，直接复用，不重复上传
    if upload_name:
        safe = os.path.basename(upload_name)
        path = os.path.join(UPLOAD_DIR, safe)
        if os.path.exists(path):
            orig = safe.split("_", 2)[-1]
            try:
                with open(path, "rb") as fh:
                    text = pipeline.read_upload(orig, fh.read()).strip()
                upload_name = safe
            except Exception as e:
                return fail("parse_fail", err=str(e))
        else:
            upload_name = None

    # 情况二：没走预览，直接带文件提交
    if not upload_name and "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        orig = os.path.basename(f.filename)
        safe = f"{datetime.now():%Y%m%d_%H%M%S}_{orig}"
        save_path = os.path.join(UPLOAD_DIR, safe)
        f.save(save_path)                       # 原样保存，保留 PDF/docx 格式
        upload_name = safe
        try:
            with open(save_path, "rb") as fh:
                text = pipeline.read_upload(orig, fh.read()).strip()
        except Exception as e:
            return fail("parse_fail", err=str(e))

    if not text:
        return fail("no_text")
    if len(text) < 50:
        return fail("text_too_short")

    if not pipeline.llm_alive():
        return fail("llm_off_match", 503)

    try:
        jd, killed = pipeline.extract_jd(text)
        try:
            vec = pipeline.embed_text(pipeline.jd_text_for_embed(jd, text))
        except Exception as e:
            print("embedding 失败，语义维退化为中性值：", e)
            vec = None
        results = MATCHER.match(jd, text, jd_vec=vec, top=top)
        return jsonify({"ok": True, "jd": summarize_jd(jd), "results": results,
                        "rejected": killed, "mode": "upload",
                        "chars": len(text), "upload_name": upload_name,
                        "jd_raw": text[:20000]})
    except Exception as e:
        traceback.print_exc()
        return fail("extract_fail", 500, err=str(e))


@app.route("/api/preview", methods=["POST"])
def preview():
    """选中文件后立刻解析，让用户在跑之前先看到 JD 内容。文件同时落盘，供「打开原文件」使用。"""
    f = request.files.get("file")
    if not f or not f.filename:
        return fail("no_file")
    orig = os.path.basename(f.filename)
    if not re.search(r"\.(txt|md|pdf|docx)$", orig, re.I):
        return fail("bad_format")

    safe = f"{datetime.now():%Y%m%d_%H%M%S}_{orig}"
    path = os.path.join(UPLOAD_DIR, safe)
    f.save(path)
    try:
        with open(path, "rb") as fh:
            text = pipeline.read_upload(orig, fh.read())
    except Exception as e:
        return fail("parse_fail_short", err=str(e))

    text = text.strip()
    if not text:
        return fail("no_text_pdf")
    return jsonify({"ok": True, "name": orig, "upload_name": safe,
                    "chars": len(text), "text": text[:60000]})


@app.route("/api/open", methods=["POST"])
def open_file():
    """用系统默认程序打开原始文件（PDF 用阅读器，docx 用 Word）。"""
    body = request.get_json(force=True) or {}
    kind = body.get("kind")
    name = os.path.basename(body.get("name") or "")

    if kind == "upload":
        path = os.path.join(UPLOAD_DIR, name)
    elif kind in ("cv", "jd"):
        info = db.index(kind).get(name)
        if not info:
            return fail("file_not_found", 404)
        path = info["raw"] or info["label"]
    else:
        return fail("kind_unknown")

    if not path or not os.path.exists(path):
        return fail("file_missing", 404, name=name)

    try:
        if hasattr(os, "startfile"):
            os.startfile(path)
        else:
            return fail("open_unsupported", 501)
        return jsonify({"ok": True, "path": path})
    except Exception as e:
        return fail("open_fail", 500, err=str(e))


@app.route("/api/cv/<ref>")
def cv_detail(ref):
    """返回一份简历的结构化字段与原文，供前端展开查看"""
    import features as F

    info = db.index("cv").get(ref)
    if not info:
        return fail("cv_not_found", 404)
    with open(info["label"], encoding="utf-8") as fh:
        fields = json.load(fh)
    raw = pipeline.read_raw(info["raw"])
    derived = {
        "years": F.years_from_history(fields.get("work_history")),
        "seniority": F.infer_seniority(fields.get("current_title")),
    }
    keep = {k: v for k, v in fields.items()
            if k not in ("evidence", "_meta", "cv_ref", "embedding")}
    return jsonify({"ok": True, "fields": keep, "derived": derived,
                    "group": info["group"], "raw": raw})


def summarize_jd(jd):
    return {
        "position": jd.get("position"),
        "role_family": jd.get("role_family"),
        "country": jd.get("country"),
        "city": jd.get("city"),
        "remote": jd.get("remote_allowed"),
        "min_years": jd.get("min_years"),
        "seniority": jd.get("seniority"),
        "domain": jd.get("domain"),
        "must_have": jd.get("must_have_skills") or [],
        "nice_to_have": jd.get("nice_to_have_skills") or [],
    }


if __name__ == "__main__":
    import threading
    import webbrowser

    URL = "http://127.0.0.1:5000"
    threading.Timer(1.6, lambda: webbrowser.open(URL)).start()
    print(f"\n服务地址：{URL}    （关闭本窗口即停止服务）\n")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
