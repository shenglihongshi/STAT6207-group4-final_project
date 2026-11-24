"""Generate two separate reports: Chinese-only and English-only PDFs.

The report text is authored in Python templates; the local LLM is *not* used
to write prose. Values come from metrics.json / per_query.csv / error_analysis.
HTML is printed to PDF with Microsoft Edge headless.
"""
from __future__ import annotations

import base64
import csv
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MET = ROOT / "outputs" / "metrics"
RET = ROOT / "outputs" / "retrieval"
CLU = ROOT / "outputs" / "clusters"
REP = ROOT / "report"
FIG = REP / "figures"
REP.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

ROLE_TITLES = {}
_jd_path = ROOT / "data" / "processed" / "jd_10.jsonl"
if _jd_path.exists():
    for _line in _jd_path.open(encoding="utf-8"):
        _o = json.loads(_line)
        ROLE_TITLES[_o["doc_id"]] = _o.get("role_title", "")

TITLE_OVERRIDES = {
    "JD_P03": "GTM Marketing Manager / Lead",
    "JD_P05": "Product Manager — WMS & Warehouse Integrations",
    "JD_P10": "Regional Lead Designer UI/UX",
}

METHOD_LABELS = {
    "zh": {
        "tfidf_cosine": "TF-IDF 余弦",
        "keyword_overlap_cos": "关键词重叠",
        "bm25": "BM25",
        "ae_supervised_in_sample": "AE + 监督（in-sample）",
        "ae_supervised_lopo": "AE + 监督（LOPO）",
    },
    "en": {
        "tfidf_cosine": "TF-IDF cosine",
        "keyword_overlap_cos": "Keyword overlap",
        "bm25": "BM25",
        "ae_supervised_in_sample": "AE + supervised (in-sample)",
        "ae_supervised_lopo": "AE + supervised (LOPO)",
    },
}


def role_of(row: dict) -> str:
    jd_id = row.get("jd_id", "")
    if jd_id in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[jd_id]
    return row.get("role_title") or ROLE_TITLES.get(jd_id, "")


def load():
    metrics = json.loads((MET / "metrics.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((RET / "per_query.csv").open(encoding="utf-8")))
    err = json.loads((MET / "error_analysis.json").read_text(encoding="utf-8"))
    clusters = json.loads((CLU / "keyword_clusters.json").read_text(encoding="utf-8"))
    return metrics, rows, err, clusters


def fig_to_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def make_figures(metrics, rows, clusters, lang: str):
    zh = lang == "zh"
    if zh:
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
    else:
        plt.rcParams["font.sans-serif"] = ["Segoe UI", "Arial", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

    labels = METHOD_LABELS[lang]
    names = [k for k in labels if k in metrics]
    vals = [metrics[k]["recall@10"] for k in names]
    fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=180)
    colors = ["#9DB4C0"] * len(names)
    for i, n in enumerate(names):
        if n == "ae_supervised_lopo":
            colors[i] = "#0E7C86"
    ax.barh([labels[n] for n in names], vals, color=colors, height=0.55)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Recall@10")
    ax.set_title("各方法 Recall@10（越高越好）" if zh else "Recall@10 by method (higher is better)")
    for i, v in enumerate(vals):
        ax.text(v + 0.01, i, f"{v:.2f}", va="center", fontsize=8)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    p1 = FIG / f"fig_recall10_{lang}.png"
    fig.savefig(p1, bbox_inches="tight")
    plt.close(fig)

    lopo = sorted([r for r in rows if r["method"] == "ae_supervised_lopo"], key=lambda r: r["pair_id"])
    fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=180)
    if lopo:
        ranks = [int(r["rank"]) for r in lopo]
        labels_x = [r["pair_id"] for r in lopo]
        cols = ["#0E7C86" if x <= 10 else "#C96A2B" for x in ranks]
        ax.bar(labels_x, ranks, color=cols, width=0.6)
        ax.axhline(10, color="#333", linestyle="--", linewidth=1)
        ax.invert_yaxis()
        ax.set_ylabel("hired CV 排名（越低越好）" if zh else "Rank of hired CV (lower is better)")
        ax.set_title("LOPO：留出 hired CV 的排名" if zh else "LOPO: rank of the held-out hired CV")
        for i, v in enumerate(ranks):
            ax.text(i, v + 2, str(v), ha="center", fontsize=8)
    fig.tight_layout()
    p2 = FIG / f"fig_lopo_ranks_{lang}.png"
    fig.savefig(p2, bbox_inches="tight")
    plt.close(fig)

    top = clusters[:12]
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=180)
    ax.barh([c["canonical"] for c in top][::-1], [c["doc_freq"] for c in top][::-1], color="#0E7C86")
    ax.set_xlabel("文档频率" if zh else "Document frequency")
    ax.set_title("最大的关键词聚类" if zh else "Largest keyword clusters")
    fig.tight_layout()
    p3 = FIG / f"fig_clusters_{lang}.png"
    fig.savefig(p3, bbox_inches="tight")
    plt.close(fig)
    return p1, p2, p3


def metric_table(metrics, lang: str) -> str:
    labels = METHOD_LABELS[lang]
    names = [k for k in labels if k in metrics]
    if lang == "zh":
        head = ("<tr><th>方法</th><th>Recall@10</th><th>Recall@5</th>"
                "<th>MRR@10</th><th>平均排名</th><th>95% CI（R@10）</th></tr>")
    else:
        head = ("<tr><th>Method</th><th>Recall@10</th><th>Recall@5</th>"
                "<th>MRR@10</th><th>Mean rank</th><th>95% CI (R@10)</th></tr>")
    body = []
    for k in names:
        m = metrics[k]
        body.append(
            f"<tr><td>{labels[k]}</td><td>{m['recall@10']:.3f}</td>"
            f"<td>{m['recall@5']:.3f}</td><td>{m['mrr@10']:.3f}</td>"
            f"<td>{m['mean_rank']:.1f}</td>"
            f"<td>[{m['ci95_recall@10'][0]:.3f}, {m['ci95_recall@10'][1]:.3f}]</td></tr>"
        )
    return f"<table class='data'>{head}{''.join(body)}</table>"


def per_query_table(rows, lang: str) -> str:
    lopo = sorted([r for r in rows if r["method"] == "ae_supervised_lopo"], key=lambda r: r["pair_id"])
    if lang == "zh":
        head = ("<tr><th>JD / 职位</th><th>Hired CV</th><th>排名</th>"
                "<th>命中@10</th><th>Top-1 返回</th></tr>")
    else:
        head = ("<tr><th>JD / role</th><th>Hired CV</th><th>Rank</th>"
                "<th>Hit@10</th><th>Top-1 returned</th></tr>")
    body = []
    for r in lopo:
        top1 = r["top10"].split("|")[0] if r["top10"] else ""
        cls = "hit" if int(r["recall@10"]) else "miss"
        body.append(
            f"<tr class='{cls}'><td><b>{r['pair_id']}</b><br>"
            f"<span class='small'>{role_of(r)}</span></td>"
            f"<td>{r['cv_id']}</td><td>{r['rank']}</td>"
            f"<td>{'✓' if int(r['recall@10']) else '✗'}</td><td>{top1}</td></tr>"
        )
    return f"<table class='data'>{head}{''.join(body)}</table>"


def top10_table(rows, lang: str) -> str:
    lopo = sorted([r for r in rows if r["method"] == "ae_supervised_lopo"], key=lambda r: r["pair_id"])
    if lang == "zh":
        head = ("<tr><th>JD / 职位</th><th>Hired CV 排名</th>"
                "<th>Top-10 CV（1 → 10）</th></tr>")
    else:
        head = ("<tr><th>JD / role</th><th>Hired CV rank</th>"
                "<th>Top-10 CVs (1 → 10)</th></tr>")
    body = []
    for r in lopo:
        top = r["top10"].split("|")
        cells = []
        for i, cv in enumerate(top, 1):
            if cv == r["cv_id"]:
                cells.append(f"<b>{i}. {cv} ✓</b>")
            else:
                cells.append(f"{i}. {cv}")
        body.append(
            f"<tr><td><b>{r['pair_id']}</b><br>"
            f"<span class='small'>{role_of(r)}</span></td>"
            f"<td>{r['rank']}</td><td>{' · '.join(cells)}</td></tr>"
        )
    return f"<table class='data'>{head}{''.join(body)}</table>"


def error_table(err, lang: str) -> str:
    if lang == "zh":
        head = ("<tr><th>JD / 职位</th><th>排名</th><th>Top-1</th>"
                "<th>JD∩positive</th><th>positive 缺失关键词</th></tr>")
    else:
        head = ("<tr><th>JD / role</th><th>Rank</th><th>Top-1</th>"
                "<th>JD∩positive</th><th>Missing from positive</th></tr>")
    body = []
    for e in err:
        if e["hit@10"]:
            continue
        body.append(
            f"<tr><td><b>{e['pair_id']}</b><br>"
            f"<span class='small'>{role_of(e)}</span></td>"
            f"<td>{e['rank']}</td><td>{e['top1']}</td>"
            f"<td>{', '.join(e['overlap_jd_positive'][:6])}</td>"
            f"<td>{', '.join(e['missing_from_positive'][:6])}</td></tr>"
        )
    if not body:
        body.append("<tr><td colspan='5'>No misses.</td></tr>")
    return f"<table class='data'>{head}{''.join(body)}</table>"


def ablation_table(lang: str) -> str:
    rows = []
    for tag, dim in [("b16", 16), ("b32", 32), ("b64", 64)]:
        p = MET / f"metrics_{tag}.json"
        if not p.exists():
            continue
        m = json.loads(p.read_text(encoding="utf-8")).get("ae_supervised_lopo")
        if not m:
            continue
        rows.append(
            f"<tr><td>{dim}</td><td>{m['recall@10']:.3f}</td>"
            f"<td>{m['recall@5']:.3f}</td><td>{m['mrr@10']:.3f}</td>"
            f"<td>{m['mean_rank']:.1f}</td></tr>"
        )
    if lang == "zh":
        head = ("<tr><th>Bottleneck 维度</th><th>LOPO Recall@10</th>"
                "<th>Recall@5</th><th>MRR@10</th><th>平均排名</th></tr>")
    else:
        head = ("<tr><th>Bottleneck dim</th><th>LOPO Recall@10</th>"
                "<th>Recall@5</th><th>MRR@10</th><th>Mean rank</th></tr>")
    return f"<table class='data'>{head}{''.join(rows)}</table>"


CSS = """
@page { size: A4; margin: 17mm 16mm 22mm; }
* { box-sizing: border-box; }
body { font-family: "Microsoft YaHei","Segoe UI",Arial,sans-serif; color:#1b2a3a;
       font-size:9.8pt; line-height:1.62; }
h1 { font-size:22pt; margin:0 0 3mm; color:#0C2340; }
h2 { font-size:14pt; color:#0C2340; margin:8mm 0 3mm; border-bottom:1.2px solid #DCE4EC;
     padding-bottom:2mm; page-break-after:avoid; }
h3 { font-size:11pt; color:#0E7C86; margin:5mm 0 2mm; page-break-after:avoid; }
p { margin:0 0 2.5mm; text-align:justify; }
.cover { min-height:245mm; display:flex; flex-direction:column; justify-content:center;
         background:linear-gradient(135deg,#0C2340 0%,#123A5A 62%,#0E5A66 100%);
         color:#fff; padding:22mm; border-radius:2mm; }
.cover .kicker { letter-spacing:2px; color:#8FD3D8; font-size:9pt; font-weight:700; }
.cover h1 { color:#fff; font-size:30pt; line-height:1.15; margin-top:5mm; }
.cover .sub { font-size:13pt; color:#DCEBED; margin-top:3mm; }
.cover .meta { margin-top:18mm; font-size:10pt; color:#C9DDE2; line-height:1.8; }
.tag { display:inline-block; border:1px solid #8FD3D8; color:#B9E4E7;
       border-radius:10mm; padding:1mm 3mm; font-size:8.5pt; margin-right:2mm; }
.note { background:#F4F7FA; border-left:3px solid #0E7C86; padding:3mm 4mm; margin:3mm 0;
        font-size:9pt; }
.warn { background:#FBF0E6; border-left:3px solid #C96A2B; padding:3mm 4mm; margin:3mm 0; }
table.data { width:100%; border-collapse:collapse; font-size:8.2pt; margin:3mm 0 4mm;
             page-break-inside:avoid; }
table.data th { background:#0C2340; color:#fff; padding:1.6mm 1.4mm; text-align:left; font-weight:600; }
table.data td { padding:1.3mm 1.4mm; border-bottom:1px solid #E1E8EE; vertical-align:top; }
table.data tr.hit td { background:#EDF7F6; }
table.data tr.miss td { background:#FBF0E6; }
.fig { width:100%; margin:3mm 0 5mm; page-break-inside:avoid; }
.fig img { width:100%; }
.cap { font-size:8.2pt; color:#5B6B7F; text-align:center; margin-top:1mm; }
.small { font-size:8.4pt; color:#5B6B7F; }
.pagebreak { page-break-before:always; }
code { background:#F1F5F8; padding:0.3mm 1mm; border-radius:1mm; font-size:8.5pt; }
ul { margin:0 0 3mm 5mm; padding:0; }
li { margin-bottom:1.4mm; }
pre { white-space:pre-wrap; background:#F4F7FA; padding:3mm; font-size:8pt; }
"""


def build_html(lang: str, metrics, rows, err, clusters, p1, p2, p3) -> str:
    zh = lang == "zh"
    lopo = metrics.get("ae_supervised_lopo", {})
    base = metrics.get("tfidf_cosine", {})
    lopo_r = lopo.get("recall@10", float("nan"))
    base_r = base.get("recall@10", float("nan"))
    delta = (lopo_r - base_r) if (lopo and base) else float("nan")
    in_r = metrics.get("ae_supervised_in_sample", {}).get("recall@10", float("nan"))

    if zh:
        cover_title = "关键词驱动的 CV–JD 匹配"
        cover_sub = "本地 LLM 关键词抽取 · 关键词聚类 · 自编码器检索"
        kicker = "STAT6207 · HW4 · 实验报告"
        tags = "<span class='tag'>10 组标准配对</span><span class='tag'>110 份 CV</span><span class='tag'>前 10 检索</span>"
        meta = ("数据：Anonymised-CVs-100 + JD + Hired CV examples<br>"
                "模型：Qwen2.5-Coder-14B-Instruct（LM Studio，本地）<br>"
                "日期：2026-11-07")
        abstract = (
            "本项目研究在职位描述（JD）与简历（CV）均为非结构化自然语言的条件下，"
            "如何用“本地 LLM 关键词抽取 → 关键词合并/聚类 → 自编码器编码 → 向量检索”的流水线完成 CV–JD 匹配。"
            "数据包含 10 份带“实际被雇佣 CV”的标准 JD–CV 对，以及 100 份匿名 CV；候选池共 110 份 CV。"
            "关键词由本地 Qwen2.5-Coder-14B-Instruct 抽取，后续聚类、编码和检索均由非 LLM 程序完成。"
            "主评估采用 leave-one-pair-out（LOPO）：每折用 9 组 GT + 100 份无标签 CV 训练，留出 1 组评估，10 折平均。"
            "主指标为 Recall@10，并报告 Recall@5、MRR@10、平均排名与 Wilson 95% 置信区间。"
        )
        sections = {
            "task": ("1. 任务与数据", "1.1 任务定义", "1.2 数据"),
            "method": ("2. 方法", "2.1 本地 LLM 关键词抽取", "2.2 关键词合并与聚类",
                       "2.3 自编码器", "2.4 检索与评估"),
            "results": ("3. 实验结果",),
            "error": ("4. 错误分析", "4.1 Bottleneck 消融", "4.2 主要观察"),
            "improve": ("5. 改进方案",),
            "limit": ("6. 局限",),
            "appendix": ("附录", "A. LLM prompt（英文原文）", "B. 复现",
                         "C. 每个 JD 的 Top-10 检索结果"),
        }
    else:
        cover_title = "Keyword-Based CV–JD Matching"
        cover_sub = "Local LLM keyword extraction · keyword clustering · autoencoder retrieval"
        kicker = "STAT6207 · HW4 · EXPERIMENT REPORT"
        tags = "<span class='tag'>10 GT pairs</span><span class='tag'>110 CVs</span><span class='tag'>Top-10 retrieval</span>"
        meta = ("Data: Anonymised-CVs-100 + JD + Hired CV examples<br>"
                "Model: Qwen2.5-Coder-14B-Instruct (LM Studio, local)<br>"
                "Date: 2026-11-07")
        abstract = (
            "This project studies CV–JD matching when both job descriptions (JDs) and CVs are unstructured natural language. "
            "The pipeline is: local-LLM keyword extraction → keyword merging/clustering → autoencoder encoding → vector retrieval. "
            "The data contain 10 standard JD–CV pairs with the actual hired CV, plus 100 anonymised CVs, giving a 110-CV candidate pool. "
            "Keywords are extracted by a local Qwen2.5-Coder-14B-Instruct model; clustering, encoding and retrieval are non-LLM programs. "
            "The primary evaluation is leave-one-pair-out (LOPO): each fold trains on 9 GT pairs + 100 unlabelled CVs and evaluates the held-out pair. "
            "The primary metric is Recall@10, with Recall@5, MRR@10, mean rank and Wilson 95% CI."
        )
        sections = {
            "task": ("1. Task and Data", "1.1 Task definition", "1.2 Data"),
            "method": ("2. Method", "2.1 Local-LLM keyword extraction", "2.2 Keyword merging and clustering",
                       "2.3 Autoencoder", "2.4 Retrieval and evaluation"),
            "results": ("3. Results",),
            "error": ("4. Error Analysis", "4.1 Bottleneck ablation", "4.2 Main observations"),
            "improve": ("5. Improvements",),
            "limit": ("6. Limitations",),
            "appendix": ("Appendix", "A. LLM prompt", "B. Reproducibility",
                         "C. Top-10 retrieval per JD"),
        }

    if zh:
        key = (
            f"<div class='note'><b>主要结果：</b>LOPO Recall@10 = <b>{lopo_r:.3f}</b>；"
            f"TF-IDF 基线 = <b>{base_r:.3f}</b>；Δ = <b>{delta:+.3f}</b>；"
            f"全量训练上界（in-sample）= <b>{in_r:.3f}</b>。</div>"
        )
    else:
        key = (
            f"<div class='note'><b>Key result:</b> LOPO Recall@10 = <b>{lopo_r:.3f}</b>; "
            f"TF-IDF baseline = <b>{base_r:.3f}</b>; Δ = <b>{delta:+.3f}</b>; "
            f"in-sample upper bound = <b>{in_r:.3f}</b>.</div>"
        )

    if zh:
        task_p = (
            "<p>给定一份 JD 和一组 CV，系统需要返回与 JD 最匹配的前 10 份 CV。匹配信号只来自自然语言文本中抽取出的关键词，"
            "不使用人工匹配标签作为输入特征；10 组 GT 只用于监督训练和评估。</p>"
            "<h3>1.2 数据</h3><ul>"
            "<li><b>10 份标准 JD</b>：来自 <code>JD + Hired CV examples</code> 每份 PDF 的前半部分；自然语言职位描述。</li>"
            "<li><b>10 份 hired CV</b>：同一 PDF 的 <code>CV OF THE HIRED CANDIDATE</code> 部分；作为每份 JD 的唯一已知正例。</li>"
            "<li><b>100 份匿名 CV</b>：<code>Anonymised-CVs-100</code>；作为无标签候选与无监督训练语料。</li>"
            "<li><b>候选池</b>：100 + 10 = <b>110 份 CV</b>。10 份 hired CV 不在 100 份匿名 CV 中。</li>"
            "<li><b>Excel 未使用</b>：本任务不依赖 Manatal 表的结构化标签。</li></ul>"
        )
        method_p = (
            "<h3>2.1 本地 LLM 关键词抽取</h3>"
            "<p>使用 LM Studio 本地部署的 <b>Qwen2.5-Coder-14B-Instruct</b>，temperature=0，要求模型输出固定 JSON schema。"
            "JD 与 CV 使用同一 schema：<code>role_title</code>、<code>seniority</code>、<code>years_experience</code>、"
            "<code>location</code>、<code>languages</code>、<code>keywords[]</code>；每个关键词包含 <code>term</code>、"
            "<code>category</code>、<code>importance</code>（1–3）。抽取结果写入 JSONL 并缓存，支持断点续跑。"
            "120 份文档平均 24.5 个关键词（范围 12–46）；3 份超长输出用更大 token 预算重试后全部合法。</p>"
            "<h3>2.2 关键词合并与聚类</h3>"
            "<p>先做别名归一化（如 JS→JavaScript、Golang→Go、Postgres→PostgreSQL），再用本地 Nomic embedding 模型"
            "（非生成式 LLM）对关键词向量化，并用 cosine + 层次聚类合并相似词；<code>java</code>、<code>javascript</code>、"
            "<code>sql</code> 等易混词设为保护词，避免误合并。每个 cluster 选择文档频率最高的词作为 canonical term，"
            "最终构建 120 份文档 × 词表的 TF-IDF 矩阵。</p>"
            "<h3>2.3 自编码器</h3>"
            "<p>AE 结构为 <code>V → 512 → 256 → 32 → 256 → 512 → V</code>，使用 GELU、Dropout、AdamW 和 denoising reconstruction。"
            "除重构损失外，在 bottleneck 上加入 supervised contrastive / listwise retrieval loss：每个 JD 的 positive 是它的 hired CV，"
            "其余 109 份 CV 为 negatives。这样 AE 既学习文档表示，也直接从 10 组 GT 学习“匹配”。bottleneck 做了 16/32/64 的消融，32 维最好。</p>"
            "<h3>2.4 检索与评估</h3>"
            "<p>JD 与 CV 均编码为 32 维单位向量，按 cosine similarity 排序，返回 Top-10。主评估为 leave-one-pair-out："
            "每折留出 1 组 GT，用其余 9 组 + 100 份匿名 CV 训练，再在 110 份 CV 中检索；10 折平均。"
            "另报全部 10 组训练的 in-sample 上界，以及 TF-IDF、关键词重叠、BM25 三个无监督基线。</p>"
        )
        results_note = (
            "<div class='note'><b>Recall@10 定义：</b>每个 JD，如果 hired CV 出现在 Top-10 记 1，否则记 0；"
            "对 10 个 query 取平均。每个 query 只有 1 份相关 CV，因此 Recall@10 等于 HitRate@10。</div>"
        )
        error_intro = (
            "<p>下表列出 LOPO 中未命中（rank &gt; 10）的案例。最后一列是 JD 中出现、但 positive CV 未覆盖的关键词，"
            "用于区分“关键词抽取/聚类问题”和“候选人确实缺少 must-have 技能”。</p>"
        )
        observations = (
            "<ul>"
            "<li><b>AE 与基线打平 Recall，但 MRR 更低：</b>LOPO Recall@10 = 0.80，与 TF-IDF / BM25 的 0.80 相同；"
            "但 AE 的 MRR@10 只有 0.32（TF-IDF 0.44），说明它能把正确 CV 找进 Top-10，却经常把相似的干扰 CV 排在更前面。</li>"
            "<li><b>in-sample 严重乐观：</b>全部 10 组训练后同批评估为 1.00，而 LOPO 只有 0.80；10 组 GT 很容易被记住，报告必须以 LOPO 为准。</li>"
            "<li><b>两个 miss：</b>P04（Data Engineer）排第 13（差一点），positive CV 缺少 Azure Synapse、PySpark 等 JD 关键词；"
            "P06（Deployment Strategist）排第 36，JD 是项目/客户/交付，hired CV 是 Data Science 背景，两边关键词几乎零重合，属于抽取/标签口径问题。</li>"
            "<li><b>命中但排名靠后：</b>P02（Sales Manager in Indonesia）第 9、P07（Marketing Manager (HK & SG)）第 9、P09（Tech Lead）第 10；"
            "positive CV 与 JD 的显式关键词重合少，AE 主要靠隐向量把它们拉进 Top-10，但 top-1 常被领域不相关的 CV 占据（如 P08 的 top-1 是视频剪辑 CV）。</li>"
            "<li><b>同义词仍是主要误差源：</b>flavour/flavor、key account management/client relationship management、"
            "B2B sales/international sales 等未完全合并，导致 P02/P07 的 positive 只共享 1 个 JD 关键词。</li></ul>"
        )
        improvements = (
            "<ul>"
            "<li><b>Must-have 加权：</b>把 JD 中 importance=3 的关键词单独作为门槛；缺少关键 must-have 的 CV 降权或直接过滤。</li>"
            "<li><b>混合检索：</b>AE 向量 + BM25 / 关键词重叠的 hybrid score，兼顾语义与精确术语。</li>"
            "<li><b>更好的关键词归一化：</b>扩展技能同义词表，区分 Java/JavaScript、SQL/MySQL、AWS/Azure/GCP 等易混词。</li>"
            "<li><b>更多 GT：</b>10 组标签太少；建议人工补充 30–50 组 JD–CV 相关性判断，或做 pooled 人工评估。</li>"
            "<li><b>类别感知编码：</b>按 skill/tool/domain 分块编码，避免通用职责词压过硬技能。</li></ul>"
        )
        limitations = (
            "<ul>"
            "<li>只有 10 组 GT，Recall 的统计置信区间较宽；10 个 query 的粒度是 0.1。</li>"
            "<li>Recall 只把“实际 hired CV”视为相关；其他潜在好 CV 未标注，因此指标偏保守。</li>"
            "<li>候选池 110 份，规模较小；结论不应直接外推到大规模招聘。</li>"
            "<li>LLM 抽取存在类别漂移和漏抽；本报告未做大规模人工校对。</li></ul>"
        )
        appendix_note = (
            "<p>下表是 LOPO 中每个 GT JD 实际返回的 10 份 CV（按相似度从高到低）。✓ 表示该 JD 的 hired CV；"
            "若 hired CV 不在表内，说明它的排名 &gt; 10（P04 Data Engineer = 13，P06 Deployment Strategist = 36）。</p>"
        )
        repro = ("<p>代码与中间结果位于 <code>HW4_6207/</code>；运行 <code>python src/train_eval.py --mode all</code> 可复现实验。"
                 "随机种子固定为 42。</p>")
        prompt_label = "A. LLM prompt（英文原文）"
    else:
        task_p = (
            "<p>Given a JD and a pool of CVs, the system returns the top-10 best-matching CVs. The matching signal comes only "
            "from keywords extracted from natural-language text; human match labels are never used as input features. "
            "The 10 GT pairs are used only for supervised training and evaluation.</p>"
            "<h3>1.2 Data</h3><ul>"
            "<li><b>10 standard JDs</b>: the first part of each PDF in <code>JD + Hired CV examples</code>; natural-language descriptions.</li>"
            "<li><b>10 hired CVs</b>: the <code>CV OF THE HIRED CANDIDATE</code> part of the same PDFs; one known positive per JD.</li>"
            "<li><b>100 anonymised CVs</b>: <code>Anonymised-CVs-100</code>; unlabelled candidates and unsupervised training data.</li>"
            "<li><b>Candidate pool</b>: 100 + 10 = <b>110 CVs</b>. The 10 hired CVs are not in the 100 anonymised CVs.</li>"
            "<li><b>Excel not used</b>: the Manatal structured tags are not used in this task.</li></ul>"
        )
        method_p = (
            "<h3>2.1 Local-LLM keyword extraction</h3>"
            "<p>We use a locally deployed <b>Qwen2.5-Coder-14B-Instruct</b> via LM Studio at temperature 0, with a fixed JSON schema. "
            "Each keyword has a term, category and importance (1–3). Results are cached as JSONL with resume support. Across 120 documents "
            "the extraction produced 24.5 keywords on average (range 12–46); three very long outputs were retried with a larger token budget "
            "and all became valid.</p>"
            "<h3>2.2 Keyword merging and clustering</h3>"
            "<p>Alias normalisation is followed by local Nomic keyword embeddings (a non-generative model) and cosine agglomerative clustering. "
            "Ambiguous terms such as Java/JavaScript and SQL are protected from merging. Each cluster gets a canonical term, yielding a "
            "120-document × vocabulary TF-IDF matrix.</p>"
            "<h3>2.3 Autoencoder</h3>"
            "<p>The AE is <code>V → 512 → 256 → 32 → 256 → 512 → V</code> with GELU, dropout, AdamW and denoising reconstruction. "
            "A supervised listwise retrieval loss is added on the bottleneck: the hired CV is the positive and the other 109 CVs are negatives. "
            "The AE therefore learns both document representation and matching from the 10 GT pairs. A 16/32/64 bottleneck ablation favoured 32 dimensions.</p>"
            "<h3>2.4 Retrieval and evaluation</h3>"
            "<p>JDs and CVs are encoded into 32-d unit vectors and ranked by cosine similarity. The primary LOPO protocol holds out one GT pair per fold, "
            "trains on the other 9 pairs + 100 unlabelled CVs, and retrieves from the 110-CV pool. We also report an in-sample upper bound and "
            "three unsupervised baselines: TF-IDF, keyword overlap and BM25.</p>"
        )
        results_note = (
            "<div class='note'><b>Recall@10 definition:</b> for each JD, 1 if the hired CV appears in the top 10, else 0; average over 10 queries. "
            "With one relevant CV per query, Recall@10 equals HitRate@10.</div>"
        )
        error_intro = (
            "<p>The table lists LOPO misses (rank &gt; 10). The last column shows JD keywords missing from the positive CV, "
            "separating extraction/clustering errors from genuine must-have gaps.</p>"
        )
        observations = (
            "<ul>"
            "<li><b>AE matches the baselines on Recall, but has lower MRR:</b> LOPO Recall@10 = 0.80, the same as TF-IDF / BM25; "
            "however AE MRR@10 is 0.32 (TF-IDF 0.44), so it often retrieves the right CV but ranks a similar distractor above it.</li>"
            "<li><b>In-sample is strongly optimistic:</b> 1.00 after training on all 10 pairs vs 0.80 under LOPO; 10 pairs are easy to memorise, "
            "so the report uses LOPO as the primary estimate.</li>"
            "<li><b>Two misses:</b> P04 (Data Engineer) at rank 13, a near miss with missing Azure Synapse / PySpark terms; "
            "P06 (Deployment Strategist) at rank 36, with almost zero keyword overlap because the JD is a project/customer/delivery role "
            "while the hired CV is data-science oriented.</li>"
            "<li><b>Hits with low ranks:</b> P02 (Sales Manager in Indonesia) rank 9, P07 (Marketing Manager (HK & SG)) rank 9, "
            "P09 (Tech Lead) rank 10; the positive CV shares few explicit JD keywords and is pulled into the top-10 by the latent vector, "
            "while top-1 is often a domain-irrelevant CV (e.g. P08's top-1 is a video-editing CV).</li>"
            "<li><b>Synonyms remain a major error source:</b> flavour/flavor, key account management/client relationship management, "
            "B2B sales/international sales are not fully merged, so P02/P07 positives share only one JD keyword.</li></ul>"
        )
        improvements = (
            "<ul>"
            "<li><b>Must-have gating:</b> use JD keywords with importance=3 as a hard gate; down-weight or filter CVs missing critical must-haves.</li>"
            "<li><b>Hybrid retrieval:</b> combine AE vectors with BM25 / keyword overlap to balance semantics and exact terminology.</li>"
            "<li><b>Better normalisation:</b> expand the skill synonym table and separate Java/JavaScript, SQL/MySQL, AWS/Azure/GCP.</li>"
            "<li><b>More GT:</b> 10 pairs are too few; add 30–50 human relevance judgments or run a pooled evaluation.</li>"
            "<li><b>Category-aware encoding:</b> encode skill/tool/domain blocks separately so generic responsibility words do not dominate hard skills.</li></ul>"
        )
        limitations = (
            "<ul>"
            "<li>Only 10 GT pairs; the confidence interval is wide and the query granularity is 0.1.</li>"
            "<li>Recall treats only the hired CV as relevant; other potentially good CVs are unlabelled, so the metric is conservative.</li>"
            "<li>The 110-CV pool is small; results should not be extrapolated to large-scale recruiting.</li>"
            "<li>LLM extraction has category drift and misses; no large-scale human audit was performed.</li></ul>"
        )
        appendix_note = (
            "<p>The table lists the actual top-10 CVs returned for each GT JD under LOPO. ✓ marks the hired CV; "
            "if it is absent, its rank is &gt; 10 (P04 Data Engineer = 13, P06 Deployment Strategist = 36).</p>"
        )
        repro = ("<p>All code and intermediate artefacts are under <code>HW4_6207/</code>; run "
                 "<code>python src/train_eval.py --mode all</code>. Random seed is 42.</p>")
        prompt_label = "A. LLM prompt"

    task_title, task_11, task_12 = sections["task"]
    method_title, m21, m22, m23, m24 = sections["method"]
    results_title = sections["results"][0]
    error_title, e41, e42 = sections["error"]
    improve_title = sections["improve"][0]
    limit_title = sections["limit"][0]
    app_title, app_a, app_b, app_c = sections["appendix"]

    body = f"""
<div class="cover">
  <div class="kicker">{kicker}</div>
  <h1>{cover_title}</h1>
  <div class="sub">{cover_sub}</div>
  <div class="meta">{tags}<br>{meta}</div>
</div>

<div class="pagebreak"></div>
<h2>{'摘要' if zh else 'Abstract'}</h2>
<p>{abstract}</p>
{key}

<h2>{task_title}</h2>
<h3>{task_11}</h3>
{task_p.split('<h3>')[0]}
<h3>{task_12}</h3>
{task_p.split('<h3>')[1].split('</h3>', 1)[1] if '<h3>' in task_p else ''}

<h2>{method_title}</h2>
{method_p}

<h2>{results_title}</h2>
{results_note}
{metric_table(metrics, lang)}
<div class="fig"><img src="data:image/png;base64,{fig_to_b64(p1)}"><div class="cap">{'图 1. 各方法 Recall@10。' if zh else 'Figure 1. Recall@10 by method.'}</div></div>
<div class="fig"><img src="data:image/png;base64,{fig_to_b64(p2)}"><div class="cap">{'图 2. LOPO 中 hired CV 的排名（越低越好）。' if zh else 'Figure 2. LOPO rank of the held-out hired CV (lower is better).'}</div></div>
{per_query_table(rows, lang)}
<p class="small">{'完整的每个 JD × Top-10 明细见附录 C。' if zh else 'Full per-JD top-10 lists are in Appendix C.'}</p>

<h2>{error_title}</h2>
{error_intro}
{error_table(err, lang)}
<div class="fig"><img src="data:image/png;base64,{fig_to_b64(p3)}"><div class="cap">{'图 3. 最大的关键词聚类。' if zh else 'Figure 3. Largest keyword clusters.'}</div></div>
<h3>{e41}</h3>
{ablation_table(lang)}
<p class="small">{'16 维欠拟合，64 维在 10 组 GT 上过拟合；32 维的 LOPO Recall@10 最好。' if zh else '16-d underfits, 64-d overfits the 10 pairs; 32-d generalises best.'}</p>
<h3>{e42}</h3>
{observations}

<h2>{improve_title}</h2>
{improvements}

<h2>{limit_title}</h2>
{limitations}

<h2>{app_title}</h2>
<h3>{app_a}</h3>
<pre>Extract 12-25 canonical keywords...
Return JSON: doc_id, doc_type, role_title, seniority,
years_experience, location, languages, keywords[{{term, category, importance}}].
"languages" must contain ONLY human spoken languages.
Programming languages use category "programming_language".</pre>
<h3>{app_b}</h3>
{repro}
<h3>{app_c}</h3>
{appendix_note}
{top10_table(rows, lang)}
"""
    return f"""<!DOCTYPE html>
<html lang="{'zh-CN' if zh else 'en'}"><head><meta charset="utf-8">
<title>{cover_title}</title><style>{CSS}</style></head><body>{body}</body></html>"""


def main():
    metrics, rows, err, clusters = load()
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    for lang, filename in [("zh", "HW4_6207_Report_CN.pdf"), ("en", "HW4_6207_Report_EN.pdf")]:
        p1, p2, p3 = make_figures(metrics, rows, clusters, lang)
        html = build_html(lang, metrics, rows, err, clusters, p1, p2, p3)
        html_path = REP / f"report_{lang}.html"
        html_path.write_text(html, encoding="utf-8")
        pdf_path = REP / filename
        subprocess.run(
            [edge, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()],
            check=False,
        )
        print(f"{lang}: {html_path} -> {pdf_path}")


if __name__ == "__main__":
    main()
