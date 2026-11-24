# STAT6207 Group 4 — 期末项目

为 **Second Talent** 实现的 AI 候选人匹配原型：输入一份岗位描述，返回按匹配度排序的**前五份简历**，每份附一句由计算值拼成的事实性理由。

不是"AI 帮你选人"，而是把顾问从"翻一百份简历"降到"看五份并确认"。

---

## 仓库内容

| 路径 | 内容 |
|---|---|
| `STAT6207_group4_finalproject_JD&CV_11-25/` | 期末项目本体：代码、数据、报告、PPT |
| `stat6207_assignment4/` | Assignment 4 存档（与期末项目无关） |

期末项目内部结构：

```
STAT6207_group4_finalproject_JD&CV_11-25/
├── main/                       ← 程序
│   ├── LLM_program/            ← 本地 LLM 标签抽取
│   ├── matcher/                ← 特征、训练、评测、网页服务
│   ├── db/                     ← 130 份已打标简历 + 50 份 JD
│   ├── experiment_results/     ← 实验证据（逐条排名、六组基线）
│   ├── appendix/               ← 提示词、权重、特征计算源码
│   └── 启动系统.bat            ← 双击这个
├── dataset_from_blackboard/    ← 老师下发的原始数据
├── working_plan个人设计意向/      ← 报告、PPT、设计文档
└── requirements.txt
```

---

## 快速开始

### 1. 装 Python

Python **3.10 或更高**。Windows 安装时务必勾选 **Add python.exe to PATH**。

### 2. 装依赖

在仓库根目录执行：

```bat
pip install -r "STAT6207_group4_finalproject_JD&CV_11-25/requirements.txt"
```

> 注意路径里的 `&`：**在命令行里必须加双引号**，否则 cmd 会把它当成命令分隔符。

### 3. 启动

用资源管理器进入 `STAT6207_group4_finalproject_JD&CV_11-25\main\`，**双击 `启动系统.bat`**。

浏览器会自动打开 <http://127.0.0.1:5000>。黑色命令行窗口不要关，关掉即停止服务。

启动脚本会自己找 Python（先试 `python`，再试 `py -3`），找不到或缺包时会直接告诉你该敲哪一行命令。

---

## 没有本地大模型，还能用吗？

**能。** 首页左侧的「示例岗位」是预抽取好的标签，点一下就能看到前五名，**全程不调用任何模型**，也不联网。

只有「上传一份新的岗位描述」这条路径需要本地 LLM。需要时装：

1. 安装 [LM Studio](https://lmstudio.ai/)，加载 `qwen/qwen3.5-9b`（Q4_K_M）
2. 在 LM Studio 里点 **Start Server**，记下端口（默认 1234，被占用会顺延到 1235）
3. 本项目默认请求 `127.0.0.1:1235`；端口不同时设环境变量 `LLM_ENDPOINT`

---

## 只看结果、不跑代码

| 想要 | 去哪 |
|---|---|
| 报告（中 / 英，IEEE 双栏，各 3 页） | `working_plan个人设计意向/报告与展示/` |
| 汇报 PPT（中 / 英） | 同上 `PPT/` |
| 30 组测试的逐条排名与失败分析 | `main/experiment_results/实验记录.md` |
| 六组基线的完整指标 | `main/experiment_results/eval_result.json` |

## 主要数字

在 **30 组真实录用配对**、**130 人候选池**上，答案落入前五的比例 **60.0%**，排第一 **33.3%**，随机排序仅 **3.8%**。

```
学出权重 : R@1 0.333  R@5 0.600  R@10 0.667  MRR 0.439
人工先验 : R@1 0.200  R@5 0.433  R@10 0.500  MRR 0.307
纯 TF-IDF: R@1 0.200  R@5 0.800  R@10 0.800  MRR 0.434
```

复现（纯 CPU，约 8 秒，不需要模型）：

```bat
cd "STAT6207_group4_finalproject_JD&CV_11-25\main\matcher"
python eval.py
```

> 包内已包含训练好的权重与打标结果，**不需要重训**。

---

## 已知限制

- 测试集只有 30 组，单个样本即影响 3.3 个百分点，所有指标置信区间较宽。
- 技能词稀疏的岗位（设计、内容、泛化管理岗）明显退化，是主要失败来源。
- 课程数据中不存在人工匹配标注；训练用的 44 组配对由 LLM 标注构造，测试集 P01–P30 全程未进入训练。
