# HW4 6207 — Keyword-Based CV–JD Matching

> **中文/English 使用手册：`使用手册_User_Manual.md`**
>
> 环境准备、两种运行模式、输出文件、常见问题都在手册里。
> For setup, the two run modes, outputs and troubleshooting, see the manual.

This project builds a keyword-based retrieval pipeline for CV–JD matching:

1. A **local LLM** (LM Studio, `qwen2.5-coder-14b-instruct`) extracts keywords from natural-language JDs and CVs.
2. Keywords are normalised and clustered with a **non-LLM** pipeline (alias rules + local Nomic embeddings + agglomerative clustering).
3. A **PyTorch autoencoder** encodes the document–keyword matrix.
4. For each of the 10 ground-truth JDs, the system retrieves the **top-10 CVs** from a pool of 110 CVs.
5. Retrieval is evaluated with **Recall@10** (primary), Recall@5, MRR@10 and mean rank.
6. Error analysis and **two separate PDF reports (Chinese and English)** are produced.

## Data (no Excel)

- `data/raw/cvs_100/`: 100 anonymised CV PDFs (`CV-001` … `CV-100`).
- `data/raw/jd_cv_pairs/`: 10 PDFs (`P01` … `P10`); each contains a JD followed by
  `CV OF THE HIRED CANDIDATE`. The JD is the query and the hired CV is the
  positive candidate.
- `data/processed/ground_truth.json`: 10 `(jd_id, cv_id)` pairs.
- Candidate pool: **100 anonymised CVs + 10 hired CVs = 110 CVs**.
- The Manatal Excel file is **not used** in this task.

## How to start / 启动方式

There is no compiled `.exe`; the project is a Python pipeline with three one-click wrappers:

- **`start.bat`** — quick start for the benchmark. Reuses the cached keyword/cluster/metrics files and regenerates the reports in a few seconds.
- **`start_full.bat`** — full benchmark run from `data/raw`. Starts LM Studio, loads Qwen + Nomic, re-extracts 120 documents, retrains the AE, evaluates, and regenerates the reports. Expect 20–40 minutes.
- **`start_general.bat`** — general mode for new data. Reads `data/input/jds` and `data/input/cvs`, builds an index, and writes `outputs/general/rankings.csv` + `rankings.md`.

Or from a terminal:

```powershell
python run_pipeline.py            # quick
python run_pipeline.py --full     # from raw PDFs
python run_pipeline.py --skip-report
```

Full mode requires LM Studio to be reachable at `http://127.0.0.1:1234/v1` with:

- `qwen2.5-coder-14b-instruct`
- `nomic-embed`

## General mode (drop-in CVs and JDs)

This is the mode for using the tool on **new, arbitrary** documents.

1. Put files here (one file = one JD, one file = one CV):
   ```text
   data/input/jds/*.pdf|*.txt|*.md|*.docx
   data/input/cvs/*.pdf|*.txt|*.md|*.docx
   ```
2. Optional: add `data/input/ground_truth.csv` (`jd_id,cv_id`) to compute Recall@10.
3. Run:
   ```text
   start_general.bat
   ```
   or:
   ```powershell
   python run_general.py
   ```

Outputs:

```text
outputs/general/rankings.csv   # long table: jd_id, rank, cv_id, score, shared keywords
outputs/general/rankings.md    # readable top-10 tables
outputs/general/metrics.json   # only if ground_truth.csv exists
```

The general mode does **not** require `CV OF THE HIRED CANDIDATE`; it reads each JD/CV file independently. The old benchmark mode (`start_full.bat`) is kept for reproducing the 10-pair experiment.

## Pipeline

```powershell
# 1. parse PDFs
python src/parse_data.py

# 2. local LLM keyword extraction (resume-safe)
python src/extract_keywords.py --out all_keywords.jsonl --workers 4
# if interrupted, resume:
python src/extract_keywords.py --out all_keywords.jsonl --workers 4 --resume

# 3. keyword normalisation / clustering / document-term matrix
python src/cluster_keywords.py

# 4. baselines + AE retrieval (leave-one-pair-out primary)
python src/train_eval.py --mode all --epochs 100 --bottleneck 32

# 5. validate keyword extraction
python src/validate_keywords.py

# 6. two reports: Chinese + English
python src/make_report.py
```

## Evaluation protocol

- **Primary:** leave-one-pair-out (10 folds). Each fold trains on 9 GT pairs + the
  100 unlabelled CVs, then evaluates the held-out JD against the 110-CV pool.
- **Upper bound:** train on all 10 pairs and evaluate the same 10 (`in_sample`).
- **Baselines:** TF-IDF cosine, keyword-overlap cosine, BM25.
- **Metrics:** Recall@10, Recall@5, MRR@10, mean rank, Wilson 95% CI.

## Directory layout

```text
HW4_6207/
├─ data/raw/                 # benchmark PDFs (10 pairs + 100 CVs)
├─ data/processed/           # benchmark parsed JSONL + ground truth
├─ data/input/               # GENERAL MODE drop-in folders
│  ├─ jds/                   # one JD per file
│  └─ cvs/                   # one CV per file
├─ data/general/             # general-mode parsed documents
├─ src/                      # pipeline scripts
├─ outputs/keywords/         # benchmark LLM keyword profiles
├─ outputs/clusters/         # benchmark vocabulary/clusters
├─ outputs/models/           # benchmark AE weights / embeddings
├─ outputs/retrieval/        # benchmark per-query rankings
├─ outputs/metrics/          # benchmark metrics + error analysis
├─ outputs/general/          # general-mode rankings.csv / rankings.md
├─ report/                   # two PDFs: CN and EN + HTML/figures
├─ 使用手册_User_Manual.md   # Chinese/English usage manual
└─ README.md
```

## Results (seed 42, bottleneck 32)

| Method | Recall@10 | Recall@5 | MRR@10 | Mean rank |
|---|---:|---:|---:|---:|
| TF-IDF cosine | 0.800 | 0.600 | 0.440 | 10.6 |
| Keyword overlap | 0.700 | 0.500 | 0.472 | 12.0 |
| BM25 | 0.800 | 0.700 | 0.471 | 10.0 |
| AE + supervised (in-sample) | 1.000 | 1.000 | 1.000 | 1.0 |
| **AE + supervised (LOPO, primary)** | **0.800** | 0.400 | 0.320 | 9.3 |

Bottleneck ablation (LOPO Recall@10): **16 → 0.200**, **32 → 0.800**, **64 → 0.600**.
The AE matches the TF-IDF/BM25 Recall@10 but has lower MRR; in-sample 1.000 vs LOPO 0.800 shows strong optimism from only 10 GT pairs. See `outputs/metrics/error_analysis.md` and the final report.

- Final reports (separate languages): `report/HW4_6207_Report_CN.pdf`, `report/HW4_6207_Report_EN.pdf`
- Keyword profiles: 120 docs, 24.5 keywords/doc on average (12–46)
- Keyword clusters: 1,552 canonical terms from 1,938 normalised variants
- Random baseline Recall@10 ≈ 10/110 = 0.091

## How the PDF reports are generated

The local LLM is used **only** for keyword extraction. It does not write the report.

1. `src/make_report.py` contains two hand-authored templates: one Chinese, one English.
2. Numbers are injected from `outputs/metrics/metrics.json`, `per_query.csv` and `error_analysis.json`.
3. Figures are rendered with matplotlib (Chinese and English versions separately).
4. Each template is written as an HTML/CSS file and printed to PDF with **Microsoft Edge headless** (`--print-to-pdf`).

So the pipeline is: local LLM → structured keywords → Python/numpy/sklearn/PyTorch metrics → HTML template → Edge PDF.

## Notes

- Keyword extraction is prompt-based; the local LLM is **not fine-tuned**.
- The AE is trained from scratch; the supervised retrieval loss uses the 10 GT pairs.
- Since only 10 labelled pairs exist, LOPO is the honest estimate; in-sample is an upper bound.
- The report clearly separates measured facts from proposed improvements.
