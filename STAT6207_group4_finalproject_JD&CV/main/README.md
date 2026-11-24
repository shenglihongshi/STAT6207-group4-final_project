# main/ — 程序资产目录

这里是**会跑的东西**。凡是程序、提示词、配置，都放 `main/` 下；
给人看的分析文档留在 `working_plan/`，数据留在 `dataset_from_blackboard/`。

## 目录职责

| 路径 | 放什么 | 谁维护 |
|---|---|---|
| `main/LLM_program/` | 阶段三：本地 LLM 抽取程序 | 代码 |
|　`抽取规范_JD侧.md` | JD 抽取提示词（**权威版本**） | 手写 |
|　`抽取规范_CV侧.md` | CV 抽取提示词（**权威版本**） | 手写 |
| `main/match_work/` | 抽取与匹配的中间产物（可随时重跑生成） | 程序自动 |
| `working_plan/` | 设计文档、计划书解读、测算过程 | 手写，不进程序 |
| `dataset_from_blackboard/` | 老师下发数据 + 我们标注的配对表 | **只读**，程序不得改写 |

## 一条硬规矩：规范只有一份权威副本

`抽取规范_*.md` 在 `working_plan/` 也有一份，那是**文档存档**，供人阅读。
**程序只读 `main/LLM_program/` 下的这一份。** 以后要改规范，改这里，别改存档那份——
两份内容不一致时，以本目录为准。

## 阶段三的输入输出约定

```
输入：dataset_from_blackboard/JD_examples/JD-01.txt
                CV_examples/CV-001.txt
      ↓  本地 LLM（LM Studio）+ 抽取规范
输出：main/match_work/extracted/JD/JD-01.json      ← 50 份
                extracted/CV/CV-001.json           ← 100 份
```

**JD 与 CV 必须分目录存放**，不要混在 `extracted/` 根下：两者的字段结构不同
（JD 19 键 / CV 14 键），混在一起既无法批量校验，也容易在匹配器里读错类型。

- 文件名即编号：`CV-042.pdf` / `CV-042.txt` / `CV-042.docx` 都对应 `CV-042`。
- 编号由程序注入，不由模型抽取。
- 每份文档抽一次即可，结果缓存成同名 `.json`；重跑时若已存在则跳过（`--force` 可覆盖）。

## 运行环境（实测记录）

| 项 | 值 |
|---|---|
| 本地推理引擎 | LM Studio（`H:\LM Studio\Bionic\Bionic.exe`） |
| 接口 | OpenAI 兼容，**`http://127.0.0.1:1235/v1`**（配置写的是 1234，实际 1234 被占用后自动顺延到 1235，以 `netstat` 实测为准） |
| 模型 id | `qwen/qwen3.5-9b`（主用）、`qwen2.5-coder-14b-instruct`（对照）、`deepseek/deepseek-r1-0528-qwen3-8b` |
| 附带 embedding | `text-embedding-nomic-embed-text-v1.5`（可用于语义相似度那一维） |
| 可用模型 | `Qwen2.5-Coder-14B-Instruct-Q4_K_M`（8.37 GB，主用）、`DeepSeek-R1-0528-Qwen3-8B-Q4_K_M`（4.68 GB，对照） |
| 模型目录 | `H:\LM Studio\models` |
| GPU | RTX 5080 Laptop，16 GB，驱动 616.92 |

**两条必须知道的坑：**

1. **访问本机端口要绕代理。** 系统设了 `HTTP_PROXY=http://127.0.0.1:52641`，直接请求 `127.0.0.1:1234` 会返回
   502 Bad Gateway。所有请求必须显式禁用代理：
   ```python
   opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
   ```
2. **服务要先启动。** LM Studio 的 HTTP server 不是常驻的，需要打开 Bionic 后点 Start Server（实测端口 1235）；
   命令行 `lms server start` 在 GUI 未运行时只会输出「Waking up LM Studio service...」然后停在原地。
