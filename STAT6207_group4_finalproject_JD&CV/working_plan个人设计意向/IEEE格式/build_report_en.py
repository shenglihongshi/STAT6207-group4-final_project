# -*- coding: utf-8 -*-
"""生成 IEEE 格式英文报告（4 页以内）。"""
import os
import docx
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

TPL = r"D:\港硕授课与课堂内容\STAT6207_group7_finalproject\working_plan个人设计意向\IEEE格式\_template_transitional.docx"
OUT = r"D:\港硕授课与课堂内容\STAT6207_group7_finalproject\working_plan个人设计意向\IEEE格式\AI_Candidate_Matching_Report_EN.docx"
FIG = r"C:\Users\admin\.workbuddy\clipboard-images\clipboard-2026-11-24T19-02-44-141Z-cbfd4156.png"

doc = docx.Document(TPL)
body = doc.element.body

# ---------- 清空正文，保留 sectPr ----------
for child in list(body):
    if child.tag == qn("w:sectPr"):
        continue
    body.remove(child)


def P(style="Body Text"):
    return doc.add_paragraph(style=style)


def add_text(p, text, bold=False, italic=False):
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    return r


def title(text):
    p = doc.add_paragraph(style="paper title")
    p.add_run(text)


def author(lines):
    for i, t in enumerate(lines):
        p = doc.add_paragraph(style="Author")
        p.add_run(t)
        p.paragraph_format.space_before = Pt(0 if i else 14)
        p.paragraph_format.space_after = Pt(0)


def abstract(text):
    p = doc.add_paragraph(style="Abstract")
    p.add_run("Abstract\u2014" + text)


def keywords(text):
    p = doc.add_paragraph(style="Keywords")
    p.add_run("Keywords\u2014" + text)


def h1(text):
    p = doc.add_paragraph(style="Heading 1")
    r = p.add_run(text)
    r.font.small_caps = True
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def h5(text):
    p = doc.add_paragraph(style="Heading 5")
    r = p.add_run(text)
    r.font.small_caps = True
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def h2(text):
    p = doc.add_paragraph(style="Heading 2")
    r = p.add_run(text)
    r.italic = True


def para(text, first=False):
    p = doc.add_paragraph(style="Body Text")
    p.add_run(text)
    if first:
        p.paragraph_format.first_line_indent = Cm(0)
    return p


def eq(tokens, num):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(5)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for txt, kind in tokens:
        r = p.add_run(txt)
        r.font.size = Pt(10)
        if "i" in kind:
            r.italic = True
        if "sub" in kind:
            r.font.subscript = True
        if "sup" in kind:
            r.font.superscript = True
    r2 = p.add_run("        (" + num + ")")
    r2.font.size = Pt(10)


def set_cols(section, num, space_cm=0.62):
    sectPr = section._sectPr
    cols = sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sectPr.append(cols)
    cols.set(qn("w:num"), str(num))
    cols.set(qn("w:space"), str(int(space_cm * 567)))
    cols.set(qn("w:equalWidth"), "1")


def table_borders(tbl):
    tblPr = tbl._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge, sz in (("top", 8), ("bottom", 8), ("insideH", 4)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:color"), "000000")
        borders.append(el)
    for edge in ("left", "right", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        borders.append(el)
    tblPr.append(borders)


def make_table(caption, header, rows, widths_cm, caption_no):
    cap = doc.add_paragraph(style="table head")
    br = cap.add_run()
    br.add_break()
    r2 = cap.add_run(caption)
    r2.font.small_caps = True
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER

    tbl = doc.add_table(rows=1 + len(rows), cols=len(header))
    tbl.autofit = False
    table_borders(tbl)
    for j, w in enumerate(widths_cm):
        for row in tbl.rows:
            row.cells[j].width = Cm(w)

    def fill(cell, text, bold=False, align=WD_ALIGN_PARAGRAPH.CENTER):
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = align
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(text)
        r.font.size = Pt(9)
        r.font.name = "Times New Roman"
        r.bold = bold

    for j, htxt in enumerate(header):
        fill(tbl.rows[0].cells[j], htxt, bold=True)
    for i, row in enumerate(rows, 1):
        for j, val in enumerate(row):
            fill(tbl.rows[i].cells[j], val, align=WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER)
    return tbl


def figure(path, width_cm, caption):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.add_run().add_picture(path, width=Cm(width_cm))
    cap = doc.add_paragraph(style="figure caption")
    cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
    cap.add_run(caption)


# =============================== 标题区 ===============================
title("AI Candidate Matching for Technical Roles: Local LLM Label Extraction with Learning-to-Rank")

author([
    "He Zhixuan, Zhang Jiaqian, Li Shenghe, Ke Shengqi",
    "Group 4",
    "Department of Statistics, The Chinese University of Hong Kong",
    "Hong Kong SAR, China",
])

abstract(
    "Second Talent, a talent-services firm, screens candidates by hand: a consultant reads every "
    "profile in the pool to assemble a shortlist. This paper reports a prototype that replaces that "
    "step. Each job description and each resume is first converted into a fixed-schema record, "
    "nineteen fields for a job description and fourteen for a resume, by a locally deployed language "
    "model, together with a 768-dimensional embedding. A linear learning-to-rank model then scores "
    "candidates on eleven features and returns the top five with a one-line justification. Since the "
    "provided data contains no match annotations, supervision was constructed: an external model "
    "selected one best candidate per job description and graded the pairing, leaving 44 usable pairs "
    "after six fallback rows were removed. On 30 held-out real hires the correct resume appeared in "
    "the top five in 60.0% of cases, at rank one in 33.3%, against 3.8% for random ordering. "
    "Performance is stable on skill-rich technical roles and degrades on roles with vague descriptions."
)

keywords(
    "candidate matching, learning to rank, large language models, information extraction, recruitment"
)

# =============================== 正文两栏 ===============================
doc.add_section(WD_SECTION.CONTINUOUS)
set_cols(doc.sections[0], 1)
set_cols(doc.sections[-1], 2)

h1("Introduction")
para(
    "Second Talent supplies talent to its clients through recruitment, secondment, and employer of "
    "record arrangements. The firm is building an HRIS platform whose candidate-matching feature is "
    "expected to recommend profiles for a role described by a client. Between 70% and 80% of the "
    "roles the firm handles are technical, covering AI, front-end, back-end, and full-stack "
    "engineering, so the scope of this project is restricted to technical positions.", first=True)
para(
    "The current process is manual. A consultant receives a job description, then reads the pool "
    "profile by profile, comparing skills, seniority, location, and language, before assembling a "
    "shortlist for the client. The cost of this step grows with the size of the pool, and the step "
    "itself produces no judgement: it only prepares the material on which judgement is exercised. "
    "The objective of this work is therefore stated narrowly: given a job description, return the "
    "five most suitable candidates in ranked order, each accompanied by one factual sentence, so "
    "that the consultant reviews five profiles instead of the whole pool.")
para(
    "Three difficulties shape the design. First, both job descriptions and resumes are unstructured "
    "and heterogeneous, so a conversion layer is part of the system rather than a preprocessing "
    "detail. Second, the provided data contains no match annotations, which means supervision has to "
    "be constructed and its provenance disclosed. Third, the output must be explainable, because a "
    "consultant cannot defend a ranking that cannot be decomposed.")
para(
    "The contributions are as follows. A schema-constrained extraction step runs on a local model "
    "and is guarded by verbatim evidence verification, so that a field is left empty rather than "
    "guessed. An eleven-feature linear ranker is trained with a listwise objective on 44 constructed "
    "pairs, which keeps unlabelled candidates out of the negative class. The system is evaluated on "
    "30 real hires against five baselines, and its failures are classified rather than averaged "
    "away. The work relates to learning-to-rank [1], [2], to contextual embeddings used as semantic "
    "similarity features [3], [4], and to industrial job recommendation [5].")
h2("Scope")
para(
    "Sales roles are excluded by the business brief and non-technical candidates are not filtered "
    "out, since the pool is shared. Instead of a hard role filter, role family enters the score with "
    "a small weight, and skill overlap separates technical from non-technical profiles.")

h1("Data Processing")
h2("Sources")
para(
    "Three files were provided, summarised in Table I. The first is a set of 100 anonymised resumes "
    "in PDF. The second is an export from the firm ATS containing 50 job descriptions and 100 "
    "candidate records as fields, with no relation between the two sheets. The third is a set of 30 "
    "PDFs, each holding one job description followed by the resume of the candidate who was actually "
    "hired for it; this set is the test set and never enters training.", first=True)
make_table(
    "Data sources and their role in the pipeline",
    ["Source", "Content", "Role"],
    [
        ["Anonymised-CVs-100", "100 resume PDFs", "Resume text"],
        ["Manatal export", "50 JD + 100 CV, field tables", "JD text, IDs"],
        ["JD-and-Hired-CV", "30 JD + hired resume, combined", "Test set"],
    ],
    [3.4, 3.4, 2.6],
    "I",
)
h2("Observations")
para(
    "Three observations determined the processing. The ATS sheet holds fields but no resume body, "
    "so resume text can only come from the PDFs. The job sheet does contain a full job description "
    "column, so job text can be reorganised from the table. The two sheets are merely placed side by "
    "side, so the pairing required for training does not exist and must be created.")
h2("Preprocessing")
para(
    "Four operations were applied, none of which alters wording. Job documents were rebuilt from the "
    "description text preceded by a header of key fields, giving 50 files. Resume text was extracted "
    "from PDF and stripped of the anonymisation footer, keeping the original identifiers, giving 100 "
    "files. Pairing used an external model, DeepSeek-V4.1-Flash, which selected for each job "
    "description the single best candidate among the 100; six rows that had no adequate candidate "
    "were discarded, leaving 44 pairs. The 30 test PDFs were split at the marker that introduces the "
    "hired resume, and the concatenation of the two parts was verified to be character-identical to "
    "the original file.")
h2("Structured Extraction")
para(
    "Each document is converted into a fixed schema by Qwen3.5-9B, served locally by LM Studio over "
    "an HTTP interface, so that no document leaves the machine. A job description yields nineteen "
    "fields, including position, role family, country, city, remote permission, contract type, salary "
    "band, minimum years, seniority, must-have skills, nice-to-have skills, and education "
    "requirement; a resume yields fourteen, including current title, employer, country, skills, work "
    "history, education, and domain. Every field carries an evidence string copied verbatim from the "
    "source. The program then searches the source for that string and nulls the field when it cannot "
    "be located, which converts a prompt-level instruction into an enforceable check.")
para(
    "Two conventions matter downstream. An empty field means unknown, never negative, so a missing "
    "country does not imply a location mismatch and a missing skill list does not imply an "
    "unskilled candidate. Enumerated fields are restricted to a whitelist. Extraction runs once over "
    "150 documents in about 45 minutes.")
para(
    "Coverage is uneven across fields, and the unevenness constrains the model. On the job side, "
    "position and contract type are present in all 50 documents, must-have skills in 92%, country in "
    "86%, seniority in 80%, and a salary band in 62%. On the resume side, current title, employer, and "
    "skill list are complete in all 100 profiles and work history in 97%, but a language section "
    "appears in only 7%. The last figure is the reason language carries zero weight in the fitted "
    "model: the field exists in the schema but not in the data.")

h1("Matching Model")
h2("Features")
para(
    "For a pair (q, c) of job description and resume, eleven features are computed, each normalised "
    "to the unit interval: must-have skill overlap, nice-to-have overlap, Jaccard overlap of the two "
    "skill sets, years of experience against the requirement, seniority agreement, country "
    "compatibility, language compatibility, industry agreement, education attainment, TF-IDF cosine "
    "similarity of the raw texts, and cosine similarity of the two embeddings. Missing information "
    "yields a neutral value rather than zero.", first=True)
h2("Scoring and Training")
para(
    "The score is linear in the features and the model is the weight vector itself:")
eq([("score(q, c) = ", "i"), ("w", "i"), ("T", "sup"), ("\u03c6(q, c)", "i")], "1")
para(
    "Training treats each pair as a retrieval query: one job description, a pool of 100 candidates, "
    "and the known correct candidate. Weights are fitted by maximising the listwise softmax "
    "likelihood, with L2 regularisation at 0.05 and L-BFGS as optimiser:")
eq([("max", "i"), ("w", "i+sub"), ("\u2009\u03a3", "i"), ("j", "sub"), (" log [ exp(", "i"), ("s(q", "i"), ("j", "sub"), (", c", "i"), ("j", "sub"), ("+", "sup"), (") ) / \u03a3", "i"), ("k\u2208Pj", "sub"), (" exp(", "i"), ("s(q", "i"), ("j", "sub"), (", c", "i"), ("k", "sub"), (") ]", "i")], "2")
para(
    "The choice of a ranking objective rather than binary classification follows from the data. "
    "Apart from the one correct candidate, the remaining 99 profiles per query carry no annotation: "
    "they are neither known to fit nor known to be unsuitable. Labelling them zero would assert a "
    "negative that nobody verified. In (2) they appear only in the denominator, as competitors, so "
    "the objective never claims that an unlabelled candidate is a bad match. Fitting takes about "
    "three seconds.")
h2("Learned Weights")
para(
    "The fitted weights are dominated by must-have skills (1.14), semantic similarity (0.83), "
    "seniority (0.78), and textual similarity (0.70), followed by location (0.45), education (0.26), "
    "skill-set coverage (0.26), nice-to-have skills (0.20), and years of experience (0.16). Language "
    "and industry receive zero. For industry this is a data effect: 77 of 100 resumes specify a "
    "domain, but two values account for about 60% of them, so the feature is nearly constant and "
    "carries no gradient.")
h2("Inference")
para(
    "At query time the weights are loaded from a small file and no training occurs. The incoming job "
    "description is extracted into the nineteen fields, its embedding is computed, and eleven "
    "features are evaluated against every indexed resume; ranking 130 candidates takes well under a "
    "second. The dominant cost is extraction, 10 to 15 seconds per job description on a single "
    "consumer GPU. Justifications are assembled from the computed values, for example must-have "
    "skills 5 of 7 with the matching names, 7.5 years against a 3-year requirement, and same "
    "country, so that no sentence is generated freely by a model.")

h1("Experimental Results")
h2("Protocol")
para(
    "Each test job description is issued against a pool of 130 profiles: the 100 indexed resumes plus "
    "the 30 hired resumes, with the answer inside the pool. Metrics are Recall at 1, 5, and 10, and "
    "mean reciprocal rank. Random ordering places the answer in the top five 3.8% of the time, which "
    "is the reference floor.", first=True)
h2("Main Results")
make_table(
    "Retrieval quality on 30 held-out hires (pool of 130)",
    ["Method", "R@1", "R@5", "R@10", "MRR"],
    [
        ["TF-IDF only", "0.200", "0.800", "0.800", "0.434"],
        ["Embedding only", "0.000", "0.000", "0.000", "0.009"],
        ["Skill overlap only", "0.067", "0.300", "0.433", "0.167"],
        ["Manual weights", "0.200", "0.433", "0.500", "0.307"],
        ["Learned, 44 pairs", "0.333", "0.600", "0.667", "0.439"],
        ["Learned, 21 strong", "0.233", "0.467", "0.633", "0.366"],
    ],
    [3.6, 1.4, 1.4, 1.5, 1.5],
    "II",
)
para(
    "The deployed configuration answers the first rank in 10 of 30 cases and the top five in 18, "
    "with a median rank of 4. Learned weights outperform manual weights on both measures, which is "
    "the evidence that the constructed supervision carries signal. Two baselines behave "
    "instructively. Textual similarity attains the highest recall at five but converts it poorly into "
    "rank one, so it is a recall device rather than a ranker. Embedding similarity alone is close to "
    "useless, because all documents in a recruitment corpus sit in a narrow similarity band: mean "
    "0.64 to 0.69 with a standard deviation of 0.04 to 0.06. Semantic similarity therefore "
    "contributes only in combination.")
figure(FIG, 7.0,
       "Interface after a job description is matched against the indexed pool. "
       "The selected profile ranks first at 2.83, with the factual justification assembled from the "
       "computed features.")
h2("Failure Analysis")
para(
    "Twelve of the 30 queries miss the top five. Three patterns account for them. Cross-functional "
    "roles fail because the pool contains no comparable profile: a product manager query places the "
    "answer at rank 120. Roles whose descriptions are sparse in skill vocabulary fail because only "
    "the weakest features remain: a UI/UX designer query, whose title almost matches the hired "
    "candidate title word for word, still ranks 67. Managerial roles with generic descriptions fail "
    "for the same reason.")
h2("Limitations")
para(
    "The ratio of supervision to capacity is thin: 44 queries inform eleven parameters, and in "
    "five-fold cross-validation the learned weights score 0.252 against 0.290 for manual weights, so "
    "the advantage appears only on held-out data and carries variance. Thirty test cases mean that a "
    "single case moves recall by 3.3 percentage points. Finally, evaluation is run as a batch over "
    "pre-extracted labels, which isolates the ranking model from extraction quality; the end-to-end "
    "path was checked on individual queries but not swept.")

h1("Business Value")
para(
    "The value proposition is narrow and measurable. A consultant previously read the whole pool to "
    "produce a shortlist; the system returns five ranked profiles, and in six cases out of ten the "
    "suitable candidate is among them. The saving is the difference between reading 130 profiles and "
    "confirming five, and it grows with the pool rather than with the workload.", first=True)
para(
    "Three properties support the claim. The process is reproducible, because the dimensions that "
    "enter a decision and their relative weights are stored as an artefact that can be inspected and "
    "revised, so a disagreement between consultants becomes a discussion about a specific dimension. "
    "The cost structure scales, because a resume is indexed once and every later query processes "
    "only the incoming job description. The deployment is local, because both models run on the "
    "machine, so personal data does not leave the network; an external model was used only during "
    "development, to construct pairing labels.")
para(
    "The effect on stakeholders differs by party. The consultant moves from reading to confirming. "
    "The client receives a shortlist sooner, which shortens the vacancy. The candidate is not "
    "discarded for formatting reasons, since parsing normalises presentation differences, and is not "
    "penalised for missing information, since unknown fields are skipped rather than treated as "
    "failures. The firm keeps the decision with a human: the system ranks and explains, but does not "
    "decide who is hired.")

h1("Conclusion")
para(
    "A job description can be turned into a ranked shortlist of five profiles using only local "
    "components: a language model for extraction, an embedding model for semantic similarity, and a "
    "linear ranker trained on 44 constructed pairs. The result is 60.0% recall at five on real "
    "hires, with per-dimension explanations. The binding constraint is the size of the annotation "
    "set, not the capacity of the ranker; the next steps are therefore more labelled pairs, a finer "
    "skill representation that distinguishes depth from exposure, and interactions between features "
    "that the current additive form cannot express.", first=True)

h5("Acknowledgment")
para(
    "DeepSeek-V4.1-Flash was used during development to construct the pairing labels and to assist "
    "with drafting; its output was reviewed before use. The models that run in the delivered system, "
    "Qwen3.5-9B for extraction and nomic-embed for semantic vectors, are executed locally and are "
    "not called over the network. The authors thank the course staff for the anonymised data.", first=True)

h5("References")
refs = [
    "T.-Y. Liu, \u201cLearning to rank for information retrieval,\u201d Found. Trends Inf. Retr., vol. 3, no. 3, pp. 225\u2013331, 2009.",
    "Z. Cao, T. Qin, T.-Y. Liu, M.-F. Tsai, and H. Li, \u201cLearning to rank: from pairwise approach to listwise approach,\u201d in Proc. ICML, 2007, pp. 129\u2013136.",
    "J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, \u201cBERT: pre-training of deep bidirectional transformers for language understanding,\u201d in Proc. NAACL-HLT, 2019, pp. 4171\u20134186.",
    "N. Reimers and I. Gurevych, \u201cSentence-BERT: sentence embeddings using Siamese BERT-networks,\u201d in Proc. EMNLP-IJCNLP, 2019, pp. 3982\u20133992.",
    "K. Kenthapadi, B. Le, and G. Venkataraman, \u201cPersonalized job recommendation system at LinkedIn: practical challenges and lessons learned,\u201d in Proc. RecSys, 2017, pp. 346\u2013347.",
]
for i, r in enumerate(refs, 1):
    p = doc.add_paragraph(style="references")
    p.add_run(r)

doc.save(OUT)
print("已生成", OUT, os.path.getsize(OUT), "B")
