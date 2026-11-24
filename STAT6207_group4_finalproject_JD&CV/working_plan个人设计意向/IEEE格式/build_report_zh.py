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
OUT = r"D:\港硕授课与课堂内容\STAT6207_group7_finalproject\working_plan个人设计意向\IEEE格式\AI候选人匹配_报告_中文版.docx"
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
_t = doc.add_paragraph(style="paper title")
_t.add_run("面向技术岗位的 AI 候选人匹配")
_t2 = doc.add_paragraph(style="paper subtitle")
_t2.add_run("本地大模型标签抽取与排序学习")

author([
    "He Zhixuan, Zhang Jiaqian, Li Shenghe, Ke Shengqi",
    "第 4 组",
    "香港中文大学 统计学系",
    "中国香港",
])

abstract(
    "Second Talent 是一家人才服务公司，目前由顾问逐份阅读简历来整理候选名单。本文报告一个替代该环节的原型："
    "每份岗位描述与简历先由本机部署的大语言模型转换为固定字段记录，岗位 19 项、简历 14 项，并附带一个 768 维向量；"
    "线性排序模型在 11 个特征上打分，返回前五名，每人附一句由计算值拼成的理由。由于课程数据不含任何匹配标注，"
    "监督信号另行构造：由外部模型为每份岗位描述选出一名最匹配的候选人并分级，剔除 6 组兜底后保留 44 组。"
    "在未参与训练的 30 组真实录用配对上，正确简历进入前五的比例为 60.0%，排名第一为 33.3%，随机排序仅为 3.8%。"
    "系统在技能描述充分的技术岗位上表现稳定，在描述笼统的岗位上明显退化。"
)

keywords("候选人匹配；排序学习；大语言模型；信息抽取；招聘")

doc.add_section(WD_SECTION.CONTINUOUS)
set_cols(doc.sections[0], 1)
set_cols(doc.sections[-1], 2)

h1("引言")
para(
    "Second Talent 通过招聘、借调与名义雇主三种方式为客户输送人才，公司正在搭建 HRIS 系统，其中一个功能是"
    "候选人匹配：客户描述一个岗位，系统推荐合适的候选人档案。公司承接的岗位中 70% 至 80% 属于技术类，"
    "覆盖 AI、前端、后端与全栈，因此本项目把范围限定在技术岗。", first=True)
para(
    "目前的流程完全依靠人工。顾问拿到一份岗位描述后，需要逐份翻阅库中的简历，比对技能、年限、职级与地点，"
    "才能整理出可供客户挑选的名单。这一步的成本随库的规模增长，而它本身不产生判断，只是判断前的准备工作。"
    "本文的目标因此写得很窄：输入一份岗位描述，返回按匹配度排序的前五名候选人，每人附一句事实性理由，"
    "使顾问面对的是五份简历而不是整个库。")
para(
    "三个难点决定了系统的设计。其一，岗位描述与简历都是非结构化文本，且格式互不相同，转换层因此是系统的组成部分，"
    "而不是预处理细节。其二，课程数据中不存在任何匹配标注，监督信号必须自行构造，并且要交代来路。"
    "其三，输出必须可解释，因为顾问无法为一个不能拆解的排序负责。")
para(
    "本文的贡献有三点：设计并在本地运行了带证据校验的字段抽取，使字段宁可为空也不被猜测；在 44 组构造配对上"
    "用 listwise 目标训练了一个 11 维的线性排序模型，使未标注简历不进入负类；在 30 组真实录用上完成评测，"
    "并把失败按类型归因，而非用一个平均值掩盖。相关工作见排序学习 [1]、[2]，以预训练语言模型表征语义相似度 "
    "[3]、[4]，以及工业界的职位推荐实践 [5]。")
h2("范围说明")
para(
    "业务说明排除了销售岗。系统并不对非技术候选人做硬性过滤：岗位大类只以较低权重进入打分，"
    "技术与非技术的区分主要由技能重合承担。")

h1("数据处理")
h2("数据来源")
para(
    "课程提供三份数据，见表 I。第一份是 100 份脱敏简历 PDF；第二份是公司 ATS 导出的表格，含 50 份岗位描述与 "
    "100 条候选人记录，两张表之间没有任何关联；第三份是 30 份 PDF，每份含一段岗位描述和该岗位实际录用者的简历，"
    "作为测试集，全程不进入训练。", first=True)
make_table(
    "三份数据源及其在流程中的作用",
    ["来源", "内容", "用途"],
    [
        ["Anonymised-CVs-100", "100 份简历 PDF", "简历正文"],
        ["Manatal 导出表", "50 岗位 + 100 简历", "岗位正文与编号"],
        ["JD-and-Hired-CV", "30 组岗位 + 录用者简历", "测试集"],
    ],
    [3.3, 2.8, 2.5],
    "I",
)
h2("数据观察")
para(
    "三点观察决定了处理方式。表格只有字段、没有简历正文，因此简历文本只能取自 PDF；岗位表自带岗位描述全文列，"
    "因此岗位文本可以整理自表格；两张表只是并列摆放，训练所需的配对关系并不存在，必须另行构造。")
h2("预处理")
para(
    "四步处理，均不改变任何原文措辞。岗位文档由描述正文加一个关键字段抬头重排而成，得 50 份；简历文本取自 PDF "
    "并去掉脱敏页眉，沿用原编号，得 100 份；配对由外部模型 DeepSeek-V4.1-Flash 完成，为每份岗位从 100 人中选出"
    "最匹配的一份，其中 6 组因库内确实没有合适人选被剔除，保留 44 组；30 份测试 PDF 按录用者简历前的分界标记切开，"
    "并验证切开后两部分拼接与原文逐字符一致。")
h2("结构化抽取")
para(
    "每份文档由 Qwen3.5-9B 转换为固定 schema，模型由 LM Studio 在本机以 HTTP 接口提供服务，文档不出本机。"
    "岗位侧输出 19 个字段，包括岗位名称、岗位大类、国家、城市、是否允许远程、合同类型、薪资区间、最低年限、"
    "职级、必备技能、加分技能与学历要求；简历侧输出 14 个字段，包括当前职位、公司、国家、技能、工作经历、"
    "教育背景与行业。每个字段附一段从原文逐字复制的证据，程序回原文检索该片段，检索不到就把字段置空，"
    "提示层的约束由此变成可执行的检查。")
para(
    "两条约定影响下游。空值表示未知，不表示否定：没写国家不等于地点冲突，没写技能不等于没有技能。"
    "枚举字段限定在白名单内。150 份文档抽取一次约需 45 分钟。")
para(
    "字段覆盖率并不均衡，而这不均衡直接限制了模型。岗位侧，岗位名称与合同类型在 50 份中全部可抽，"
    "必备技能 92%，国家 86%，职级 80%，薪资区间 62%；简历侧，当前职位、公司与技能在 100 份中全部可抽，"
    "工作经历 97%，但语言一项仅 7%。这正是语言维度最终权重为零的原因：字段存在于 schema，却不存在于数据。")

h1("匹配模型")
h2("特征")
para(
    "对一对（q, c），计算 11 个特征并统一折算到 0 至 1：必备技能命中率、加分技能命中率、两侧技能集合的 Jaccard、"
    "年限达标程度、职级匹配程度、国家相容性、语言相容性、行业一致性、学历达标程度、全文 TF-IDF 余弦相似度、"
    "两侧向量的余弦相似度。信息缺失时取中性值而非零。", first=True)
h2("打分与训练")
para("打分对特征是线性的，模型本体就是权重向量：")
eq([("score(q, c) = ", "i"), ("w", "i"), ("T", "sup"), ("\u03c6(q, c)", "i")], "1")
para(
    "训练时，每组配对视为一次检索：一个岗位描述、100 份候选、其中一份是已知的正确答案。权重通过最大化 "
    "listwise softmax 似然求得，L2 正则取 0.05，优化器为 L-BFGS：")
eq([("max", "i"), ("w", "i+sub"), ("\u2009\u03a3", "i"), ("j", "sub"),
    (" log [ exp(", "i"), ("s(q", "i"), ("j", "sub"), (", c", "i"), ("j", "sub"), ("+", "sup"),
    (") ) / \u03a3", "i"), ("k\u2208Pj", "sub"), (" exp(", "i"), ("s(q", "i"), ("j", "sub"),
    (", c", "i"), ("k", "sub"), (") ]", "i")], "2")
para(
    "式中 φ 为 11 维特征向量，w 为权重向量，s 为由式 (1) 定义的打分函数，c 上标加号表示已知的正确答案，"
    "P 为该查询的候选池。选择排序目标而非二分类，是数据决定的：除一份正确答案外，每个查询其余 99 份都没有标注，"
    "既不知道合适，也不知道不合适，把它们标为零等于断言一个没有人验证过的否定。在式 (2) 中，它们只出现在分母，"
    "作为竞争者，因此目标从未声称某份未标注简历不匹配。拟合约需 3 秒。")
h2("学出的权重")
para(
    "拟合结果由必备技能（1.14）、语义相似（0.83）、职级（0.78）与全文相似（0.70）主导，其后是地点（0.45）、"
    "学历（0.26）、技能覆盖（0.26）、加分技能（0.20）与年限（0.16）。语言与行业为零。行业为零是数据效应："
    "100 份简历中 77 份填了行业，但两个取值即占约六成，特征近似常数，没有梯度可学。")
h2("推理")
para(
    "查询时只加载权重文件，不再训练。来料岗位描述被抽成 19 个字段、算出向量，随后与库内每份简历逐一比对 11 个特征，"
    "130 名候选人排序不足一秒。主要开销在抽取，单张消费级显卡上每份岗位 10 至 15 秒。理由是拼装的，例如"
    "必备技能命中 7 项中的 5 项并列出技能名、7.5 年经验对应 3 年要求、国家相同，没有任何一句由模型自由生成。")

h1("实验结果")
h2("评测协议")
para(
    "每个测试岗位面对 130 人的候选池：库内 100 份简历加 30 份录用者简历，答案在池内。指标为前 1、前 5、前 10 命中率"
    "与平均倒数排名。随机排序进入前五的概率为 3.8%，作为参照下界。", first=True)
h2("主要结果")
make_table(
    "30 组真实录用上的检索质量（候选池 130 人）",
    ["方案", "前 1", "前 5", "前 10", "MRR"],
    [
        ["仅 TF-IDF", "0.200", "0.800", "0.800", "0.434"],
        ["仅语义向量", "0.000", "0.000", "0.000", "0.009"],
        ["仅技能重合", "0.067", "0.300", "0.433", "0.167"],
        ["人工权重", "0.200", "0.433", "0.500", "0.307"],
        ["学出权重（44 组）", "0.333", "0.600", "0.667", "0.439"],
        ["学出权重（21 组强）", "0.233", "0.467", "0.633", "0.366"],
    ],
    [3.1, 1.3, 1.3, 1.35, 1.35],
    "II",
)
para(
    "线上配置在 30 个查询中有 10 个把答案排在第一、18 个排进前五，中位排名为第 4。学出权重的前五命中与排名第一"
    "两项均高于人工权重，说明构造的监督确实携带信号。两组对照的表现值得注意：全文相似取得最高的前五命中，"
    "却难以转化为第一名，它是召回手段而非排序手段；语义相似单独使用时几乎失效，因为招聘语料中的文档相似度"
    "挤在 0.64 至 0.69 的窄带内，标准差仅 0.04 至 0.06，它只在组合中起作用。")
figure(FIG, 7.0,
       "界面截图：一份岗位描述与库内候选人匹配后的结果。选中的简历以 2.83 分排在首位，其理由由计算特征拼装而成。")
h2("失败分析")
para(
    "30 个查询中有 12 个未能进入前五，归为三类。跨职能岗位失败，因为池中没有可比对象：产品经理查询把答案排到第 120 名。"
    "技能词汇稀疏的岗位失败，因为只剩最弱的特征可用：UI/UX 设计师查询的岗位名与录用者现职几乎逐字相同，仍排在第 67 名。"
    "描述笼统的管理岗因同样原因失败。")
h2("局限")
para(
    "监督与容量的比例偏紧：44 个查询确定 11 个参数，五折交叉验证中学出权重为 0.252，人工权重为 0.290，"
    "优势只在留出数据上出现，且方差较大。30 个测试样本意味着单个案例即可移动 3.3 个百分点。此外评测以批处理方式"
    "使用预先抽好的标签，隔离了抽取质量；端到端路径只在个别查询上验证过，未做系统扫描。")

h1("商业价值")
para(
    "价值主张窄而可测。顾问过去需要读完整个库才能给出名单，系统返回五份排好序的简历，十次中有六次合适的人就在其中。"
    "节省的部分是读 130 份与确认 5 份之间的差额，且它随库的规模放大，而不是随工作量放大。", first=True)
para(
    "三个属性支撑这一判断。流程可复现：参与判断的维度及其相对分量以文件形式保存，可查、可改，顾问之间的分歧"
    "因此落到具体维度上。成本可扩展：一份简历只入库计算一次，之后每次查询只处理来料岗位描述。部署在本地："
    "两个模型都在本机运行，个人信息不出内网；外部模型只在开发阶段用于构造配对标签。")
para(
    "对不同相关方的影响各不相同。顾问从阅读转为确认；客户更快拿到名单，岗位空缺时间缩短；候选人不会因排版差异"
    "在解析环节被丢弃，也不会因信息缺失被倒扣；公司保留最终决定权，系统只负责排序与解释，不决定录用。")

h1("结论")
para(
    "只用本地组件，就可以把一份岗位描述变成五人的排序名单：语言模型负责抽取，向量模型负责语义相似，"
    "线性排序模型在 44 组构造配对上训练完成。在真实录用上取得 60.0% 的前五命中，并可逐维解释。"
    "当前瓶颈是标注规模而不是排序容量，因此下一步是三件事：增加配对标注、细化技能表示以区分深度与接触、"
    "引入当前加性形式无法表达的特征交互。", first=True)

h5("致谢")
para(
    "开发阶段使用 DeepSeek-V4.1-Flash 构造配对标签并协助文字起草，其输出经人工复核后使用。交付系统中运行的模型为"
    "本机的 Qwen3.5-9B 与 nomic-embed，均不联网调用。感谢课程提供的脱敏数据与指导。", first=True)

h5("参考文献")
refs = [
    "T.-Y. Liu, \u201cLearning to rank for information retrieval,\u201d Found. Trends Inf. Retr., vol. 3, no. 3, pp. 225-331, 2009.",
    "Z. Cao, T. Qin, T.-Y. Liu, M.-F. Tsai, and H. Li, \u201cLearning to rank: from pairwise approach to listwise approach,\u201d in Proc. ICML, 2007, pp. 129-136.",
    "J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, \u201cBERT: pre-training of deep bidirectional transformers for language understanding,\u201d in Proc. NAACL-HLT, 2019, pp. 4171-4186.",
    "N. Reimers and I. Gurevych, \u201cSentence-BERT: sentence embeddings using Siamese BERT-networks,\u201d in Proc. EMNLP-IJCNLP, 2019, pp. 3982-3992.",
    "K. Kenthapadi, B. Le, and G. Venkataraman, \u201cPersonalized job recommendation system at LinkedIn: practical challenges and lessons learned,\u201d in Proc. RecSys, 2017, pp. 346-347.",
]
for r in refs:
    p = doc.add_paragraph(style="references")
    p.add_run(r)

# 中文字体：正文宋体、西文 Times New Roman
styles_el = doc.styles.element
rpr_def = styles_el.find(qn("w:docDefaults")).find(qn("w:rPrDefault"))
rPr = rpr_def.find(qn("w:rPr"))
if rPr is None:
    rPr = rpr_def.makeelement(qn("w:rPr"), {})
    rpr_def.append(rPr)
rFonts = rPr.find(qn("w:rFonts"))
if rFonts is None:
    rFonts = rPr.makeelement(qn("w:rFonts"), {})
    rPr.append(rFonts)
rFonts.set(qn("w:ascii"), "Times New Roman")
rFonts.set(qn("w:hAnsi"), "Times New Roman")
rFonts.set(qn("w:eastAsia"), "宋体")



# ---- 表格：固定布局 + 收窄单元格边距 ----
from docx.oxml import OxmlElement
for tbl in doc.tables:
    tblPr = tbl._tbl.tblPr
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblPr.append(lay)
    mar = OxmlElement("w:tblCellMar")
    for side in ("left", "right"):
        el = OxmlElement("w:" + side); el.set(qn("w:w"), "45"); el.set(qn("w:type"), "dxa"); mar.append(el)
    tblPr.append(mar)
    for j, col in enumerate(tbl.columns):
        w = tbl.rows[0].cells[j].width
        if w is not None:
            col.width = w

# ---- 中文排版修正：标题加粗放大，摘要/关键词标签换中文 ----
for pa in doc.paragraphs:
    if pa.style.name == "Heading 1":
        for r in pa.runs:
            r.font.bold = True
            r.font.size = Pt(11)
            r.font.small_caps = False
    elif pa.style.name == "Heading 2":
        for r in pa.runs:
            r.font.bold = True
            r.font.italic = False
    elif pa.style.name in ("Abstract", "Keywords"):
        if pa.runs:
            t = pa.runs[0].text
            t = t.replace("Abstract—", "摘要—").replace("Keywords—", "关键词—")
            pa.runs[0].text = t

# ---- 中文字体统一：模板 paper title / paper subtitle / references 自带 eastAsia="MS Mincho"（日文明朝体），
#      会让标题汉字与正文宋体字形不一致；此处统一为宋体，并把标题从 24pt 收到 18pt 加粗 ----
def _unify_font(style_name, size=None, bold=None, italic=None):
    st = doc.styles[style_name]
    rpr = st.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    rf.set(qn("w:eastAsia"), "宋体")
    rf.set(qn("w:ascii"), "Times New Roman")
    rf.set(qn("w:hAnsi"), "Times New Roman")
    if size is not None:
        st.font.size = Pt(size)
    if bold is not None:
        st.font.bold = bold
    if italic is not None:
        st.font.italic = italic


_unify_font("paper title", size=18, bold=True)
_unify_font("paper subtitle", size=13, bold=False)


doc.save(OUT)
print("已生成", OUT, os.path.getsize(OUT), "B")
