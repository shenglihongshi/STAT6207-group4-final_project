# HW4 6207 使用手册 / User Manual

**关键词驱动的 CV–JD 匹配 / Keyword-Based CV–JD Matching**

- 版本 / Version: 1.0
- 日期 / Date: 2026-11-07
- 运行环境 / Platform: Windows + Python + LM Studio + Microsoft Edge

---

## 0. 这个项目是什么 / What this project is

本项目包含两种使用方式：

1. **复现实验模式（benchmark）**：使用 `data/raw/` 中固定的 10 组 JD + hired CV，以及 100 份匿名 CV，复现报告中的 Recall@10、MRR、错误分析，并生成中文/英文两份报告。
2. **通用匹配模式（general）**：把任意 JD 和 CV 分别放入 `data/input/jds/` 和 `data/input/cvs/`，运行后得到每个 JD 的 Top-10 CV 检索列表。

This project has two modes:

1. **Benchmark reproduction**: use the fixed 10 JD + hired-CV pairs and 100 anonymised CVs in `data/raw/` to reproduce Recall@10, MRR, error analysis, and the two reports.
2. **General matching**: put arbitrary JDs and CVs in `data/input/jds/` and `data/input/cvs/`, then get a top-10 CV list for every JD.

它不是编译好的 `.exe`，而是 Python 流水线 + `.bat` 启动器。  
It is not a compiled `.exe`; it is a Python pipeline with `.bat` launchers.

---

## 1. 项目结构 / Project structure

```text
HW4_6207/
├─ start.bat                 # benchmark 快速模式：复用缓存，重新生成报告
├─ start_full.bat            # benchmark 完整模式：从 data/raw 重新跑
├─ start_general.bat         # 通用模式：读取 data/input
├─ run_pipeline.py           # benchmark 主程序
├─ run_general.py            # 通用模式主程序
├─ config.json               # 模型、随机种子、AE 参数
├─ requirements.txt          # Python 依赖
├─ 使用手册_User_Manual.md   # 本文件
├─ data/
│  ├─ raw/                   # benchmark 原始数据
│  │  ├─ cvs_100/            # 100 份匿名 CV PDF
│  │  └─ jd_cv_pairs/        # 10 份 JD + hired CV 合体 PDF
│  ├─ processed/             # benchmark 解析结果 + ground_truth.json
│  ├─ input/                 # 通用模式输入
│  │  ├─ jds/                # 一份文件 = 一个 JD
│  │  └─ cvs/                # 一份文件 = 一份 CV
│  └─ general/               # 通用模式解析结果
├─ src/                      # 所有 Python 脚本
├─ outputs/
│  ├─ keywords/              # benchmark 关键词 JSONL
│  ├─ clusters/              # 词表、聚类、TF-IDF 矩阵
│  ├─ models/                # AE 权重、向量
│  ├─ retrieval/             # benchmark 每个 JD 的 Top-10
│  ├─ metrics/               # 指标、错误分析
│  └─ general/               # 通用模式 rankings.csv / rankings.md
└─ report/
   ├─ HW4_6207_Report_CN.pdf
   ├─ HW4_6207_Report_EN.pdf
   ├─ report_zh.html
   └─ report_en.html
```

---

## 2. 环境准备 / Environment setup

### 2.1 Python / Python packages

建议 Python 3.10+；本项目在 Python 3.14 上测试通过。  
Python 3.10+ is recommended; this project was tested on Python 3.14.

在项目根目录运行 / Run in the project root:

```powershell
cd D:\softs_usual\opencode_windows\stat6207_final_groupproject\HW4_6207
pip install -r requirements.txt
```

主要依赖 / Main packages:

```text
numpy
scikit-learn
torch
matplotlib
pymupdf
python-docx
```

### 2.2 LM Studio 和本地模型 / LM Studio and local models

本项目使用 **LM Studio 的本地 OpenAI-compatible API**，地址：

```text
http://127.0.0.1:1234/v1
```

需要两个模型 / Two models are required:

```text
qwen2.5-coder-14b-instruct              # 关键词抽取
text-embedding-nomic-embed-text-v1.5   # 关键词向量化 / clustering
```

检查模型 / Check models:

```powershell
lms ls
```

启动服务并加载模型 / Start the server and load models:

```powershell
lms server start
lms load qwen2.5-coder-14b-instruct --gpu max --context-length 8192 --identifier qwen2.5-coder-14b-instruct
lms load text-embedding-nomic-embed-text-v1.5 --gpu max --identifier nomic-embed
```

检查 API / Check the API:

```powershell
Invoke-RestMethod http://127.0.0.1:1234/v1/models
```

如果返回模型列表，说明服务正常。  
If it returns the model list, the server is ready.

**显存说明 / GPU note**：Qwen2.5-Coder-14B 以 4-bit 量化加载约 9 GB，建议 16 GB 显存；显存不足会自动变慢或失败。  
Qwen2.5-Coder-14B at 4-bit uses about 9 GB; 16 GB VRAM is recommended. With less VRAM it may be slower or fail.

### 2.3 Microsoft Edge

报告使用 **Microsoft Edge headless** 打印 HTML 为 PDF。  
Reports are printed from HTML to PDF with **Microsoft Edge headless**.

默认路径 / Default path:

```text
C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
```

如果 Edge 安装在其他位置，请修改 `src/make_report.py` 中的 `edge` 路径。  
If Edge is installed elsewhere, edit the `edge` path in `src/make_report.py`.

---

## 3. 第一次运行前检查 / Preflight checks

```powershell
cd HW4_6207
python -c "import torch, sklearn, pymupdf, matplotlib, docx; print('python deps OK')"
lms ps
```

确认 `data/raw/cvs_100` 有 100 份 PDF，`data/raw/jd_cv_pairs` 有 10 份 PDF。  
Confirm that `data/raw/cvs_100` contains 100 PDFs and `data/raw/jd_cv_pairs` contains 10 PDFs.

---

## 4. 模式 A：复现实验 / Benchmark reproduction

### 4.1 数据 / Data

```text
data/raw/cvs_100/          # 100 份匿名 CV PDF
data/raw/jd_cv_pairs/      # 10 份 PDF；每份前半是 JD，后半是 CV OF THE HIRED CANDIDATE
```

- 10 份 PDF 的 JD 是 query。
- 每份 PDF 后半的 CV 是该 JD 的唯一 known positive。
- 候选池 = 100 份匿名 CV + 10 份 hired CV = **110 份 CV**。
- `CV OF THE HIRED CANDIDATE` 是 benchmark PDF 里的分页标记，不是通用输入格式要求。

### 4.2 完整复现 / Full reproduction

双击 / Double-click:

```text
start_full.bat
```

或命令行 / Or:

```powershell
python run_pipeline.py --full
```

它会依次执行：

```text
1. parse_data.py      解析 10 份 JD+CV PDF 和 100 份 CV PDF
2. extract_keywords.py 本地 Qwen 抽 120 份文档的关键词
3. cluster_keywords.py Nomic embedding + 聚类 + TF-IDF 矩阵
4. train_eval.py      AE 训练 + LOPO 评估 + 基线
5. error_analysis.py  错误分析
6. make_report.py     生成中文/英文两份 PDF
```

预计时间 / Expected time: **20–40 分钟**（取决于 GPU 和模型加载）。  
20–40 minutes depending on GPU and model load.

### 4.3 快速重出报告 / Quick report regeneration

如果 `outputs/` 里的缓存还在，只需要重新生成报告：

```text
start.bat
```

或 / Or:

```powershell
python run_pipeline.py
```

预计时间 / Expected time: **几秒到几十秒**。它不会重新调用 LLM，也不会重新训练 AE。

### 4.4 预期结果 / Expected results

| 方法 / Method | Recall@10 | Recall@5 | MRR@10 | 平均排名 / Mean rank |
|---|---:|---:|---:|---:|
| TF-IDF cosine | 0.800 | 0.600 | 0.440 | 10.6 |
| Keyword overlap | 0.700 | 0.500 | 0.472 | 12.0 |
| BM25 | 0.800 | 0.700 | 0.471 | 10.0 |
| AE + supervised (in-sample) | 1.000 | 1.000 | 1.000 | 1.0 |
| **AE + supervised (LOPO, primary)** | **0.800** | 0.400 | 0.320 | 9.3 |

Bottleneck 消融 / ablation（LOPO Recall@10）：

```text
16 → 0.200    32 → 0.800    64 → 0.600
```

主评估是 leave-one-pair-out：每折留出 1 组 GT，用其余 9 组 + 100 份匿名 CV 训练，再检索留出的 JD。  
The primary protocol is leave-one-pair-out: each fold holds out one GT pair, trains on the other 9 + 100 unlabelled CVs, then retrieves the held-out JD.

### 4.5 输出文件 / Outputs

```text
report/HW4_6207_Report_CN.pdf      # 中文报告
report/HW4_6207_Report_EN.pdf      # 英文报告
outputs/metrics/metrics.json       # 所有方法的指标
outputs/metrics/error_analysis.md  # 错误分析
outputs/retrieval/per_query.csv    # 每个 JD 的 Top-10
outputs/keywords/all_keywords.jsonl# LLM 关键词
outputs/clusters/                  # 词表、聚类、矩阵
outputs/models/                    # AE 权重、向量
```

---

## 5. 模式 B：通用匹配 / General matching

### 5.1 放数据 / Put your data

```text
data/input/
├─ jds/          # 一份文件 = 一个 JD
│  ├─ Data Engineer.pdf
│  └─ Product Manager.txt
└─ cvs/          # 一份文件 = 一份 CV
   ├─ candidate_a.pdf
   └─ candidate_b.docx
```

支持格式 / Supported formats:

```text
.pdf  .txt  .md  .docx
```

**不需要** `CV OF THE HIRED CANDIDATE` 标记；JD 和 CV 已经在不同文件夹里。  
The marker is **not** required; JDs and CVs are already separated by folder.

### 5.2 运行 / Run

双击 / Double-click:

```text
start_general.bat
```

或 / Or:

```powershell
python run_general.py
```

它会执行：

```text
1. 解析 data/input/jds 和 data/input/cvs
2. 本地 Qwen 抽关键词
3. Nomic 聚类 + TF-IDF 矩阵
4. 训练 AE
5. 对每个 JD 检索 Top-10 CV
6. 输出 rankings.csv / rankings.md
```

### 5.3 输出 / Outputs

```text
outputs/general/rankings.csv   # 长表：jd_id, jd_title, rank, cv_id, cv_title, score, shared_keywords
outputs/general/rankings.md    # 每个 JD 的可读 Top-10 表格
outputs/general/metrics.json   # 仅当提供 ground_truth.csv 时生成
```

`rankings.md` 示例 / Example:

```text
## Data Engineer

| Rank | CV | Score | Shared keywords |
|---:|---|---:|---|
| 1 | CV-001 | 0.87 | python, sql, spark |
| 2 | CV-003 | 0.81 | python, etl |
```

### 5.4 可选 Ground Truth / Optional ground truth

只有想计算 Recall@10 时才需要。  
Only needed if you want Recall@10.

```text
data/input/ground_truth.csv
```

格式 / Format:

```csv
jd_id,cv_id
JD_Data_Engineer,CV_candidate_a
```

或使用文件名 / Or use filenames:

```csv
jd_file,cv_file
Data Engineer.pdf,candidate_a.pdf
```

系统会把文件名转成：

```text
JD_<文件名>  /  CV_<文件名>
```

空格和特殊字符会替换为下划线。  
Spaces and special characters are replaced with underscores.

### 5.5 通用模式的限制 / General-mode limitations

- 每次运行都会重建索引、重新训练 AE；适合几百份文档，不适合超大规模。
- 没有 OCR：扫描版 PDF 提取不到文字，需要先 OCR。
- 没有“只加一份新 JD、直接查已有索引”的轻量模式；目前是全量重建。
- 没有 Ground Truth 时只出检索列表，不计算 Recall。

---

## 6. 报告是怎么生成的 / How reports are generated

本地 LLM **只做关键词抽取**，不写报告。  
The local LLM is used **only** for keyword extraction; it does not write the report.

```text
metrics.json / per_query.csv / error_analysis.json / keyword_clusters.json
        ↓
src/make_report.py（中文模板 + 英文模板）
        ↓
matplotlib 图表（中文/英文分别生成）
        ↓
HTML + CSS
        ↓
Microsoft Edge headless --print-to-pdf
        ↓
报告 PDF
```

关键点 / Key points:

- 表格、指标、Top-10 明细从结果文件读取。
- 分析文字是模板，不是模型每次重写。
- 报告本地生成，不连接云端大模型。

---

## 7. 复现性 / Reproducibility

- 随机种子 / Seed: **42**
- 主要参数 / Main config: `config.json`
- Benchmark 完整模式会重新抽关键词、重新训练。
- 快速模式复用已有缓存，只重新生成报告。
- 报告生成不需要 LLM。

---

## 8. 常见问题 / Troubleshooting

| 现象 / Symptom | 原因 / Cause | 解决 / Fix |
|---|---|---|
| `LM Studio API is not reachable` | 服务未启动或模型未加载 | `lms server start`；`lms load ...`；检查 `http://127.0.0.1:1234/v1/models` |
| `model not found` | 模型名称不对/未下载 | `lms ls` 确认名称；在 LM Studio 下载 |
| `No module named ...` | Python 依赖缺失 | `pip install -r requirements.txt` |
| `No input documents found` | 通用模式输入目录为空 | 把文件放入 `data/input/jds` 和 `data/input/cvs` |
| `Marker not found` | 把纯 JD 放进了 benchmark 的 `jd_cv_pairs` | 通用模式请用 `data/input/jds`；benchmark 需保留 `CV OF THE HIRED CANDIDATE` 结构 |
| `Keyword extraction failed for ...` | 某份文档 JSON 被截断/解析失败 | 重新运行；通用模式会自动用更小 prompt 重试 |
| PDF 报告没有更新 | 旧 PDF 被预览器占用 | 关闭预览窗口后重跑 `python src/make_report.py` |
| Edge 找不到 | 未安装 Edge 或路径不同 | 安装 Edge，或修改 `make_report.py` 的 `edge` 路径 |
| 运行很慢 | 本地 14B 模型推理慢 | 确认使用 GPU；不要在抽关键词时同时跑其他大任务 |
| 扫描版 PDF 没内容 | 没有文本层 | 先 OCR，再放入输入目录 |

---

## 9. 最短复现步骤 / Minimal reproduction checklist

1. 解压/拿到整个 `HW4_6207` 文件夹。  
   Get the whole `HW4_6207` folder.
2. `pip install -r requirements.txt`。  
   Install Python dependencies.
3. 启动 LM Studio，加载 `qwen2.5-coder-14b-instruct` 和 `nomic-embed`。  
   Start LM Studio and load both models.
4. 双击 `start_full.bat`（benchmark）或 `start_general.bat`（通用模式）。  
   Double-click the appropriate launcher.
5. 等待运行完成，查看：  
   Check:
   - `report/HW4_6207_Report_CN.pdf`
   - `report/HW4_6207_Report_EN.pdf`
   - `outputs/general/rankings.csv`（通用模式）
6. 如果只想重出报告：`start.bat`。  
   To regenerate reports only: `start.bat`.

---

## 10. 已知限制 / Known limitations

- Benchmark 只有 10 组 GT，Recall 的统计置信区间较宽。
- 通用模式每次全量重建索引，适合中小规模数据。
- 不支持扫描版 PDF 的 OCR。
- 还没有单 JD 的增量查询模式。
- 报告中的分析文字是固定模板，换数据后部分数字需要同步更新模板。

English summary: the benchmark has only 10 GT pairs; general mode rebuilds the index each run; scanned PDFs need OCR; there is no incremental single-JD query yet; narrative text in the report is templated and some numbers may need updating when data changes.
