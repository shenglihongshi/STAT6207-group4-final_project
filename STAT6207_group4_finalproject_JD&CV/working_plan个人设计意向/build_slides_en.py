# -*- coding: utf-8 -*-
"""从中文 PPT 生成英文版 PPT：复制后逐形状替换文本，保留版式。"""
import copy
import shutil
import os
from pptx import Presentation

SRC = r"D:\港硕授课与课堂内容\STAT6207_group7_finalproject\working_plan个人设计意向\AI候选人匹配_汇报PPT.pptx"
DST = r"D:\港硕授课与课堂内容\STAT6207_group7_finalproject\working_plan个人设计意向\AI_Candidate_Matching_Slides_EN.pptx"

shutil.copy2(SRC, DST)

FOOT = "Second Talent · AI Candidate Matching"

# 幻灯片序号 -> {形状名: 文本}；文本为 str 单段，list 多段
T = {
    1: {
        "TextBox 3": "AI Candidate Matching",
        "TextBox 4": "From one job description to the top five profiles",
        "TextBox 6": ["STAT6207 Final Project · Second Talent",
                      "Members: ________   ·   December 2026"],
    },
    2: {"TextBox 2": "Chapter I", "TextBox 3": "Background and Objectives"},
    3: {
        "TextBox 1": "I · Background and Objectives",
        "TextBox 2": "Where the system enters the consultant's workflow",
        "TextBox 4": FOOT,
        "TextBox 7": "Today: a job description arrives and the consultant reads every profile in turn, comparing skills, years, location and language",
        "TextBox 9": "The larger the pool, the slower this step; it produces no judgement, only the material for one",
        "TextBox 11": "Goal: one job description in, five ranked profiles out, each with one short reason built from the computed scores",
        "TextBox 13": "Scope: 70-80% of the firm's roles are technical, so the project focuses on technical hiring",
        "TextBox 15": "It is a first-pass tool: a hundred profiles become five, and the consultant decides.",
    },
    4: {"TextBox 2": "Chapter II", "TextBox 3": "Data Analysis and Processing"},
    5: {
        "TextBox 1": "II · Data Analysis and Processing",
        "TextBox 2": "Three data sources and what each supplies",
        "TextBox 4": FOOT,
        "TextBox 7": "Anonymised-CVs-100",
        "TextBox 8": "100 anonymised resume PDFs",
        "TextBox 9": "Source of resume text",
        "TextBox 11": "Manatal Examples",
        "TextBox 12": "50 jobs + 100 candidates (field tables)",
        "TextBox 13": "Job text and ID mapping",
        "TextBox 15": "JD-and-Hired-CV-(30)",
        "TextBox 16": "30 real hire pairs (job + hired resume)",
        "TextBox 17": "Test set and ground truth",
        "TextBox 18": "In all three sources the jobs and the resumes are never linked — that is the problem the next pages address.",
    },
    6: {
        "TextBox 1": "II · Data Analysis and Processing",
        "TextBox 2": "Four preprocessing steps and their outputs",
        "TextBox 4": FOOT,
        "TextBox 8": "Job side",
        "TextBox 9": "Take the job description body, prefix a header of key fields",
        "TextBox 10": "50 files",
        "TextBox 13": "Resume side",
        "TextBox 14": "Extract the PDF body, drop the header, keep the table IDs",
        "TextBox 15": "100 files",
        "TextBox 18": "Pairing",
        "TextBox 19": "An external model picks the best match per job; six fallbacks dropped",
        "TextBox 20": "44 pairs",
        "TextBox 23": "Test split",
        "TextBox 24": "Split each PDF at the marker into a job part and a resume part",
        "TextBox 25": "30 + 30",
        "TextBox 26": "Output: 50 job texts, 100 resume texts, 44 training pairs and 30 verification pairs.",
    },
    7: {"TextBox 2": "Chapter III", "TextBox 3": "How the Matcher Is Trained"},
    8: {
        "TextBox 1": "III · How the Matcher Is Trained",
        "TextBox 2": "Training pipeline: labels first, then weights",
        "TextBox 4": FOOT,
        "TextBox 7": "Labels: 150 documents are read by the local Qwen3.5-9B into 19 job fields and 14 resume fields, each with a 768-dim vector",
        "TextBox 9": "Samples: 44 queries, each one job + 100 candidates + one known correct answer",
        "TextBox 11": "Objective: adjust 11 weights so the correct answer scores highest inside its own pool",
        "TextBox 13": "Output: 11 numbers, converged in 3 seconds, stored in one small file",
        "TextBox 15": ["Why not a classifier: apart from the answer, the other 99 profiles carry no label.",
                       "Labelling them zero would assert a mismatch nobody verified."],
    },
    9: {
        "TextBox 1": "III · How the Matcher Is Trained",
        "TextBox 2": "Fields taken on each side and how they are paired",
        "TextBox 4": FOOT,
        "TextBox 7": "JD side · 12 fields used in matching",
        "TextBox 8": ["Position, role family, country, city,",
                      "remote permission, contract type, salary band,",
                      "minimum years, seniority, must-have skills,",
                      "nice-to-have skills, education requirement"],
        "TextBox 10": "CV side · 7 fields used in matching",
        "TextBox 11": ["Current title, current company, country,",
                       "skill list, work history,",
                       "highest degree, industry"],
        "TextBox 12": "Only five pairs are compared directly: skills, years, seniority, education, country. The rest feed the result card and the reason.",
    },
    10: {
        "TextBox 1": "III · How the Matcher Is Trained",
        "TextBox 2": "Weight tiers and the single hard filter",
        "TextBox 4": FOOT,
        "TextBox 7": "High",
        "TextBox 8": "Must-have skill hit rate, relevant years",
        "TextBox 9": "largely decides the top five",
        "TextBox 11": "Medium",
        "TextBox 12": "Seniority agreement, semantic closeness",
        "TextBox 13": "separates candidates of similar ability",
        "TextBox 15": "Low",
        "TextBox 16": "Nice-to-have skills, education, country, skill breadth",
        "TextBox 17": "matters when scores are close",
        "TextBox 19": "No score",
        "TextBox 20": "Language (7 of 100 resumes), industry (two values cover 60%)",
        "TextBox 21": "not comparable",
        "TextBox 23": "Hard filter: conflicting countries with no remote option excludes the candidate. Every other dimension only moves the score.",
    },
    11: {"TextBox 2": "Chapter IV", "TextBox 3": "How the System Works"},
    12: {
        "TextBox 1": "IV · How the System Works",
        "TextBox 2": "Two stages: extraction, then ranking",
        "TextBox 4": FOOT,
        "TextBox 7": ["Documents", "PDF / Word / TXT"],
        "TextBox 10": ["Local model", "extracts fields"],
        "TextBox 13": ["Label store", "fields + vector"],
        "TextBox 16": ["Scoring", "11 dimensions"],
        "TextBox 19": ["Ranking", "top five + reason"],
        "TextBox 20": "The model only turns documents into fields; the eleven weights do the judging.",
        "TextBox 21": ["The first three boxes are built once: extract, store labels, fit weights.",
                       "The last two run on every query: score this one job, then rank."],
    },
    13: {
        "TextBox 1": "IV · How the System Works",
        "TextBox 2": "Operating flow, result layout and library growth",
        "TextBox 4": FOOT,
        "TextBox 7": "Open the page",
        "TextBox 10": "Upload or paste a JD",
        "TextBox 13": "Choose top-K",
        "TextBox 16": "Run match",
        "TextBox 19": "Read results",
        "TextBox 21": "Each result: reference, title, company, country, years, score, plus one factual reason",
        "TextBox 23": "Expand the 11 features, or open the original resume file (PDF / Word, original layout)",
        "TextBox 25": "New resumes: upload, then label once to join the pool; unlabelled ones stay invisible",
        "TextBox 26": "Reasons are assembled from computed numbers, never generated freely by a model.",
    },
    14: {
        "TextBox 1": "IV · How the System Works",
        "TextBox 2": "Screenshot of a live run",
        "TextBox 30": "All 130 indexed resumes are already labelled and searchable.",
        "TextBox 32": "Upload one job description (here P04 Data Engineer, 3,444 characters) and ask for the top five.",
        "TextBox 34": "Matching returns in about ten seconds; the first profile scores 2.83.",
        "TextBox 36": "The reason is computed: 5 of 7 must-have skills, 7.5 years against 3 required, same country.",
        "TextBox 38": "Each result expands into 11 features, or opens the original file.",
        "TextBox 39": FOOT,
    },
    15: {"TextBox 2": "Chapter V", "TextBox 3": "Experimental Results"},
    16: {
        "TextBox 1": "V · Experimental Results",
        "TextBox 2": "Retrieval quality on 30 real hires",
        "TextBox 4": FOOT,
        "TextBox 7": "ranked first (10/30)",
        "TextBox 9": "in the top five (18/30)",
        "TextBox 10": "4th",
        "TextBox 11": "median rank",
        "TextBox 13": "Pool of 130: 100 indexed plus the 30 answers. In six cases out of ten the right person is in the top five.",
        "TextBox 14": ["In business terms: 130 profiles read by hand become five profiles confirmed.",
                       "Technical roles hold up: DevOps, AI engineering and tech lead all rank in the top three."],
    },
    17: {
        "TextBox 1": "V · Experimental Results",
        "TextBox 2": "Where it fails, and why",
        "TextBox 4": FOOT,
        "TextBox 7": "Product manager",
        "TextBox 8": "Cross-functional; no comparable profile",
        "TextBox 9": "rank 120",
        "TextBox 11": "UI/UX designer",
        "TextBox 12": "Sparse skills; semantic and text only",
        "TextBox 13": "rank 67",
        "TextBox 15": "HR manager",
        "TextBox 16": "Vague description; low discrimination",
        "TextBox 17": "rank 28",
        "TextBox 18": "Causes",
        "TextBox 20": "Main cause: too little training data — a few dozen pairs for eleven weights, and no comparable profile in the pool",
        "TextBox 22": "Then: coarse fields and a purely additive score — skills are flat, weights do not vary by role",
    },
    18: {"TextBox 2": "Chapter VI", "TextBox 3": "Business Value"},
    19: {
        "TextBox 1": "VI · Business Value",
        "TextBox 2": "Business value: core contribution and added strengths",
        "TextBox 4": FOOT,
        "TextBox 7": "Reproducible",
        "TextBox 8": "Matching becomes a repeatable process; disagreements resolve on a dimension",
        "TextBox 10": "Novel",
        "TextBox 11": "A local LLM turns any JD or CV format into computable labels",
        "TextBox 13": "Scalable",
        "TextBox 14": "A resume is indexed once; the pool grows, the query cost does not",
        "TextBox 16": "Private",
        "TextBox 17": "Runs locally, works offline, data never leaves the network",
        "TextBox 18": ["Stakeholders: the consultant gets a list sooner; no candidate is dropped for formatting;",
                       "company data stays inside; the system ranks and never decides who is hired."],
    },
    20: {"TextBox 2": "Chapter VII", "TextBox 3": "Conclusion"},
    21: {
        "TextBox 1": "VII · Conclusion",
        "TextBox 2": "Conclusion and next steps",
        "TextBox 4": FOOT,
        "TextBox 7": "A complete path now works: it reads documents, scores them, and explains itself",
        "TextBox 9": "Usable for first-pass screening on technical roles; vague roles still need a human",
        "TextBox 11": "The limit is annotation scale, not model capacity — add data before adding model",
    },
    22: {
        "TextBox 1": "VII · Conclusion",
        "TextBox 2": "Improvement and outlook",
        "TextBox 4": FOOT,
        "TextBox 7": "Enlarge the training set",
        "TextBox 9": "Refine the field design",
        "TextBox 11": "Try a stronger ranking model",
    },
    23: {"TextBox 2": "Thank you"},
}


def set_lines(tf, lines):
    """按行写入，复用已有段落的格式；段落不足则复制末段。"""
    if isinstance(lines, str):
        lines = [lines]
    paras = tf.paragraphs
    while len(tf.paragraphs) < len(lines):
        last = tf.paragraphs[-1]._p
        last.addnext(copy.deepcopy(last))
    while len(tf.paragraphs) > len(lines):
        extra = tf.paragraphs[-1]._p
        extra.getparent().remove(extra)
    for pa, line in zip(tf.paragraphs, lines):
        runs = pa.runs
        if not runs:
            pa.add_run(line)
            continue
        runs[0].text = line
        for r in runs[1:]:
            r._r.getparent().remove(r._r)


prs = Presentation(DST)
fail = []
for idx, mapping in T.items():
    slide = prs.slides[idx - 1]
    shapes = {sh.name: sh for sh in slide.shapes if sh.has_text_frame}
    for name, text in mapping.items():
        sh = shapes.get(name)
        if sh is None:
            fail.append((idx, name, "shape missing"))
            continue
        set_lines(sh.text_frame, text)

# 第 19 页「核心贡献」保留双 run 结构
s19 = prs.slides[18]
for sh in s19.shapes:
    if sh.name == "TextBox 20":
        pa = sh.text_frame.paragraphs[0]
        if len(pa.runs) >= 2:
            pa.runs[0].text = "Core contribution: "
            pa.runs[1].text = ("replaces manual shortlisting — one job description in, five ranked "
                              "profiles out, and the consultant reads only those five.")
            for r in pa.runs[2:]:
                r._r.getparent().remove(r._r)
        else:
            fail.append((19, "TextBox 20", "runs<2"))

# 全篇页脚统一
for slide in prs.slides:
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip() == "Second Talent · AI 候选人匹配":
            set_lines(sh.text_frame, FOOT)


# ---- 修版：p17 卡片副标题加宽、原因两行改 13pt ----
from pptx.util import Inches, Pt
s17 = prs.slides[16]
for sh in s17.shapes:
    if sh.name in ("TextBox 8", "TextBox 12", "TextBox 16"):
        sh.width = Inches(6.40)
    if sh.name in ("TextBox 20", "TextBox 22"):
        for pa in sh.text_frame.paragraphs:
            for r in pa.runs:
                r.font.size = Pt(13)

prs.save(DST)

print("生成", DST, os.path.getsize(DST), "B")
print("异常:", fail if fail else "无")
