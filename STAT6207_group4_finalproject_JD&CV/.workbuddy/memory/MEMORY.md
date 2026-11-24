# STAT6207 Group 7 期末项目 · 长期约定

## 数据角色（用户 2026-11-21 明确口径，最高优先级）
1. `Manatal Examples – JD & CV (anonymised).xlsx`
   - `JD Examples`：50 条 JD（Position / Role family / Country / Remote / Contract type / Salary / Job description 全文）
   - `CV Examples`：100 条结构化简历（Ref / Current title / Current company / Country / Role family / Skills / Work history / Education / Latest degree）
   - **两者之间没有任何匹配标签或匹配关系**。
2. `dataset_from_blackboard/JD-and-Hired-CV-(30)-examples`（P01–P30）
   - 每份 PDF：前段 JD，后段 `CV OF THE HIRED CANDIDATE`（其中 "Hired for" = 应聘岗位，"当前 title" = 候选人现职）。
   - 声明：**人工业务确认「优质匹配」标准模范录用 → 基准测试集**。
   - **绝对不能在模型训练阶段进入训练，只能用于验证 / 评测 / 误差分析。**

## 由此确定的硬约束
- 训练阶段可用标签数 = 0（30 组全部锁定为测试集）。
- 因此方法主线必须是「无监督 / 规则权重打分 / 表征相似度」，不能声称用有监督方式从标注配对中学出权重——除非用人工规则构造弱标签，并在报告里如实披露。
- 评测要用 leave-one-out 候选池：100 份无标签 CV + 其余 29 份 hired CV（≈129 份），否则 Recall 恒为 0。

## 重要事实：老师原话只锁 10 组（待确认）
- `项目要求与老师的提示QA.txt` 原文只说 "The 10 examples are appropriate as the benchmark… the 10 positives must never enter training"。
- 实测 `zips/JD   Hired CV examples.zip` = P01–P10 共 **10** 份；`JD-and-Hired-CV-20-more-examples.zip` = P11–P30 共 **20** 份。
- 即「30 组全锁」是用户自己加严的口径。是否放宽需向老师确认（草稿问句见 `数据策略与标注方案_2026-11-21.md` §8.3）。


## 业务要求（Second Talent brief）
- 这份 PDF 是**学生任务书**（"Student briefing: the project and your role"），三件事是派活：① 准备数据 ② 写匹配指南（抽什么+权重）③ 搭 baseline + 一套测试。
- **把"约 50 组优质匹配配对"当作产出，不是输入**：起始表 "with no match labels yet" + 工具写明 "embeddings and Google Sheets for labelling" → brief 要的是标注流程（LLM 抽取/脱敏 → embedding 缩候选 → 人工表格确认），不是找现成带标签数据集。市面上确实不存在此类公开库。
- 输入 JD → 输出 Top-5 排序 + 每条一句推荐理由，验收标准是「资深招聘顾问认可」（人的判断，需人工盲评 + Recall 双轨检验）。
- 五步流程：读 JD 做要求清单 → 读 CV 抽同构信息 → 硬筛（地点/时区/远程/notice period/语言）→ 加权打分 → 排序出 Top-5。
- 权重分层：最高＝硬技能重合 + 相关经验年限；高＝资历层级 + 薪资预算；中＝行业背景 / 稳定性 / 学历。
- 公司 70–80% 岗位为技术类，项目聚焦技术岗；Sales roles 明确 out of scope。

## 课程交付（详见 项目要求与老师的提示QA.txt）
- 必须交 Python 代码 + 数据；不接受只交 prompt / skill。
- 报告：IEEE 模板，≤4 页 A4，2026-12-12 截止。
- 展示：2026-12-05，10 分钟 + 5 分钟 Q&A；露脸 + PPT；全员出镜。

## 已排除的误读
- `期末作业建议.png`（autoencoder / 聚类 / recall@10 那条）= **Assignment 4 的建议**，不是期末项目要求。期末路线开放，只需保证有基线对比。

## 字段 Schema（用户 2026-11-21 定调）
- **Manatal 的标签格式是本项目最有价值的资产**：它定义了「看什么」，与「什么算好」（配对）正交；没有字段定义，配对再多也学不出东西。用户逐字列了 JD 14 字段与 CV 9 字段。
- 但 Schema 有两处硬缺口：
  1. **JD 侧完全没有技能字段**（技能只存在于 job_description 正文）→ 必须扩展 `must_have_skills` / `nice_to_have_skills` / `min_years` / `seniority`。
  2. **CV 侧没有 city / remote / notice_period / languages / expected_salary** → brief 的五个硬筛条件里只有地点（国家级）可用，通知期两侧皆无、remote 只能单向判断。
- 由此定：`notice_period` 硬筛放弃并在报告说明；remote 只判 PASS/UNKNOWN 不判 FAIL；城市级匹配降级到国家级。
- 详细字段表与硬筛对照矩阵见 `匹配字段Schema_v1.md`。
- 合成数据集（uhfew）的定位：只用其 `keywords/experience_years/result` 学权重，**不用其 cv 文本**（中位数仅 262 字符，真实简历 1,092–6,190）。

## 协作方式（用户 2026-11-21 强烈要求，优先级高于一切技巧）
- **必须先拿到明确指令「开始工作」才允许动手**：写文件、跑命令、装依赖、生成方案文档，一律等指令。用户明确厌恶「讨论结束后擅自开工」，2026-11-21 当晚连续两次因此发火。
- 讨论阶段只说话：可以分析、提问、指出问题，但不产出任何文件、不执行任何命令。
- **先把「项目是什么」讲清楚，再谈实现；不要一上来写代码。** 用户明确反感「还没理解项目就开工，最后交出一个自己都不知道怎么运行的产物」。
- **不要拿评分细则当设计依据。** 评分是老师事后打分用的，不是设计规格；反复讨论「这块值多少分」会被视为没抓住重点。
- 交付物必须**用户自己能跑起来**；形态（命令行/本地网页/桌面程序）与运行方式要在动手前定死。
- 用户单干（组内合作视为沟通成本，不做分工），进度压力全在他一人。
- 不要用「清单平铺」回答复杂问题：必须给出判断（什么是核心、什么是枝节），而不是把所有条目都当成同等重要。
