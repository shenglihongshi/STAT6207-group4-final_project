# 通用输入目录 / General input

把任意招聘数据放到这里，然后运行 `start_general.bat`（或 `python run_general.py`）。

## 目录

```text
data/input/
├─ jds/                 # 一份文件 = 一个职位描述
│  ├─ Data Engineer.pdf
│  └─ Product Manager.txt
├─ cvs/                 # 一份文件 = 一份简历
│  ├─ candidate_a.pdf
│  └─ candidate_b.docx
└─ ground_truth.csv     # 可选：有标签时才计算 Recall
```

支持格式：`.pdf`、`.txt`、`.md`、`.docx`。

## 可选 Ground Truth

只有在你想计算 Recall@10 时才需要。CSV 表头二选一：

```csv
jd_id,cv_id
JD_Data_Engineer,CV_candidate_a
JD_Product_Manager,CV_candidate_b
```

或使用文件名：

```csv
jd_file,cv_file
Data Engineer.pdf,candidate_a.pdf
Product Manager.txt,candidate_b.docx
```

`jd_id`/`cv_id` 是系统自动生成的：JD 为 `JD_<文件名>`，CV 为 `CV_<文件名>`，文件名中的空格和特殊字符会被替换为下划线。

## 输出

```text
outputs/general/rankings.csv    # 每个 JD 的 Top-10（长表）
outputs/general/rankings.md     # 每个 JD 的 Top-10（可读表格）
outputs/general/metrics.json    # 仅在有 ground_truth.csv 时生成
```
