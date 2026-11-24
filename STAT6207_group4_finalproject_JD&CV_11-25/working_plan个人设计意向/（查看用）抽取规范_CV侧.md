# CV 抽取规范（供本地 LLM 使用）

版本 v2 ｜ 2026-11-22 ｜ 用途：把任意格式的候选人简历（PDF / DOCX / TXT）解析为固定标签

---

## 0. 最重要的前提：不假设任何版式

简历由每个求职者自己排版，**没有任何固定结构**。同一条信息可能出现的位置包括但不限于：页眉、姓名下方、正文首段、侧栏、表格单元格、时间轴节点、段落中间；也可能完全缺失。

因此：

1. **所有字段都在全文范围内按语义特征定位**，不按行号、不按页、不按固定段落。
2. 下文出现的 `Skills`、`Work experience`、`Education` 等**只是常见锚点**。找不到这些标题时，必须按内容特征（如"一整串技术名词"、"职位+公司+时间区间"）继续搜，**不得因为缺少某个标题就返回 `null`**。
3. 判定某一字段时，用"**它是什么**"来判断，而不是"**它在哪里**"。

### 0.1 输入形态与常见噪声

你收到的**不是**原生 PDF / Word 文件，而是程序解析后的纯文本：`.txt` 直接读、`.pdf` 取文本层（扫描件走 OCR）、`.docx` 取段落。因此文本里会带这些噪声，抽取时必须容忍：

| 噪声 | 常见样子 | 处理方式 |
|---|---|---|
| 重复页眉页脚 | `CV-042 · page 2`、`Anonymised candidate profile · personal information removed` | 忽略，不当作内容 |
| 分页断句 | 一句话被切成两页 | 视为同一句，合并理解 |
| 换行切词 | `Kuber-` 换行 `netes` | 合并为一个词 |
| 表格错位 | 职位、公司、日期分处不同列或不同行 | 按语义归组，不依赖对齐 |
| OCR 错字 | `0` 与 `O`、`l` 与 `1`、`rn` 与 `m` | 按上下文纠正明显错字 |
| 列表符号丢失 | `•`、`-` 变成空格 | 不影响语义判断 |
| 中英混排 | `Python開發`、`後端工程師` | 按语义识别，不因语言混合而丢弃 |

**格式不影响规则**：同一份简历无论是 PDF、Word 还是纯文本，抽取规则完全一致。遇到解析质量差的文本，宁可把字段写 `null`，也不要猜。

### 0.2 文件命名与编号

- 文件名即编号：`CV-001.pdf`、`CV-001.docx`、`CV-001.txt` 都对应 `CV-001`。
- 编号由程序注入，**你不抽取**（见 2.1）。
- 用户上传的任意命名文件由程序分配临时编号（`CV-U001`），同样与你无关。

---

## 1. 角色与输出约定

你是简历解析器。输入是一份简历全文，输出**一个 JSON 对象**。

- 只输出 JSON，不要解释、不要前后缀、不要代码块标记。
- 所有键必须存在，缺值写 `null`（数组类字段缺值写 `[]`）。
- 不猜测、不补全、不根据常识推断。
- 每个字段附 `evidence`：从原文**逐字复制**的片段；找不到对应句子则该字段为 `null`。

输出骨架：

```json
{
  "cv_ref": null,
  "current_title": null,
  "current_company": null,
  "country": null,
  "languages": [],
  "skills": [],
  "work_history": [],
  "education": null,
  "latest_degree": null,
  "highest_degree": null,
  "domain": "other",
  "years_experience": null,
  "relevant_years": null,
  "seniority": null,
  "evidence": {}
}
```

---

## 2. 字段抽取规则

### 2.1 `cv_ref`（string）
- **是什么**：这份简历的编号。
- **谁来产生**：**由程序从文件名注入，模型不负责抽取**。文件名 `CV-042.txt` → `"CV-042"`。
- **模型的动作**：一律输出 `null`，由后处理填回。
- **为什么**：编号是文件系统的元数据，不是简历内容；让模型去正文里找编号，既容易找错（可能抓到岗位编号、日期），也会在真实上传文件里直接失败。
- **例外**：若文件名不符合 `CV-数字` 规则（用户上传的任意命名文件），程序生成新编号（如 `CV-U001`），同样不由模型判断。

### 2.2 `current_title`（string）
- **是什么**：候选人**当前或最近一份工作**的职位头衔。
- **怎么认出**：一段描述"此人在做什么岗位"的短语，通常与"迄今为止"的任职时间同处一段（`Present`、`Current`、`Now`、`至今`），或紧邻姓名出现。形式多为「（职级词）+ 职能词」，如 `Senior Backend Engineer`、`Data Analyst`、`Marketing Manager`。
- **排除**：
  - 应聘意向岗位（`Hired for:`、`Applied for:`、`Target position:`、`Objective:` 之后的内容）
  - 教育专业名（`Computer Science`）
  - 公司名、部门名
- **多条候选时的取舍**：取时间上最新（`present` 或最近结束）的那一段的职位名。
- **缺失**：`null`

### 2.3 `current_company`（string）
- **是什么**：与 `current_title` 对应的雇主。
- **怎么认出**：与职位名同段或紧邻的组织名。常见线索：紧跟职位名之后（`Title at Company` / `Title · Company`）、带公司后缀（`Ltd`、`Pte`、`Inc`、`GmbH`、`Group`、`Technologies`、`Solutions`）、或位于时间区间同一段内。
- **排除**：客户名、学校名、前雇主。
- **规则**：`Freelance`、`Independent`、`Family Business`、`Confidential Company` 照原样保留。
- **示例**：`Garanti BBVA (via VBT Software)` 整体保留，不要拆成两家。
- **缺失**：`null`

### 2.4 `country`（string）
- **是什么**：候选人**当前居住或工作**的国家。
- **怎么认出**：任何明确表示所在地的国家名，可能出现在：姓名下方、职位/公司同一行、`Based in …`、`Location: …`、地址块末尾、页脚。
- **必须映射**：出现城市名时映射到国家——`HCMC`/`Ho Chi Minh`/`Hanoi`→`Vietnam`；`Jakarta`/`Bandung`→`Indonesia`；`Manila`/`Makati`/`Cebu`→`Philippines`；`Kuala Lumpur`/`Selangor`/`Shah Alam`/`Johor`→`Malaysia`；`Taipei`/`Hsinchu`→`Taiwan`；`Hong Kong`→`Hong Kong`；`Dubai`/`Abu Dhabi`/`Sharjah`→`United Arab Emirates`；`Singapore`→`Singapore`。
- **排除（关键）**：大学所在国、过往任职国、公司注册地——这些都不是"当前所在地"。只有当国家与当前任职同一段、或明确标注 `current`／`based in` 时才采用。
- **禁止**：从电话区号、语言、姓名推断。
- **缺失**：`null`

### 2.5 `languages`（array）
- **是什么**：候选人掌握的自然语言。
- **怎么认出**：① 任何列举语言能力的表述（`Languages: English, Mandarin`、`Fluent in Cantonese`、`Native Vietnamese`）；② 技能区里出现的自然语言名。
- **排除（关键）**：编程语言不是这个字段的内容（`Python`、`Java`、`Go` 属于 `skills`，不属于 `languages`）。
- **规则**：每项 `{"lang": string, "level": string}`；`level` 只允许 `native`、`fluent`、`professional`、`basic`、`unknown`，原文未写等级填 `unknown`。
- **禁止**：因为简历用英文写就推断"会英语"。
- **缺失**：`[]`

### 2.6 `skills`（array of string）
- **是什么**：候选人掌握的技术、工具、平台、方法论。
- **怎么认出**：① 连续罗列技术名词的区域（常有 `Skills`、`Technologies`、`Tech Stack`、`Expertise` 等标题，也可能没有标题、只是逗号分隔的一长串）；② 职责描述中出现的具体技术名词。
- **规则**：
  1. 全部转小写；
  2. 别名归一：`k8s`→`kubernetes`、`gcp`→`google cloud`、`postgres`→`postgresql`、`react.js`→`react`、`node.js`→`nodejs`、`next.js`→`nextjs`、`ci/cd`→`cicd`、`.net`→`dotnet`、`vue.js`→`vue`、`ts`→`typescript`；
  3. 去版本号：`python3`→`python`、`java8`→`java`；
  4. 去重，最多 60 项；
  5. 只收技术/工具类，排除软技能（communication、teamwork、leadership）、自然语言名（归 `languages`）、公司名、学历词。
- **示例**：`Python, Golang, PHP, MySQL, Postgres, Docker, Kubernetes, Gcp, Kafka` → `["python","golang","php","mysql","postgresql","docker","kubernetes","google cloud","kafka"]`
- **缺失**：`[]`

### 2.7 `work_history`（array of object）
- **是什么**：按时间倒序的完整工作经历。
- **怎么认出**：任何同时具备三要素的内容块——**职位名 + 组织名 + 时间区间**。排版可能是段落、表格、时间轴，也可能三要素分散在不同行。
- **规则**：
  - `start` / `end` 统一 `YYYY-MM`；`Present`/`Current`/`Now`/`至今` 写 `"present"`；
  - 只有年份时写 `YYYY-01`，并置 `"date_precision": "year"`；
  - `description` 取该段职责原文，超过 300 字符截断；
  - 最多保留最近 6 段；
  - 不得混入教育经历、项目经历（若与任职分开列且无雇主）。
- **示例**：
```json
{"title":"Backend developer","company":"Sea - Shopee","start":"2019-10","end":"present",
 "is_current":true,"date_precision":"month","description":"Devops using GCP, kubernetes and Helm..."}
```
- **缺失**：`[]`

### 2.8 `education`（string）
- **是什么**：教育背景全文。
- **怎么认出**：同时具备**学位或专业 + 院校（+ 年份）**的内容块。
- **规则**：原样拼接所有条目，用 `；` 分隔；不翻译、不改写。
- **注意**：约两成简历**没有**这一块，此时 `null`，不得视为"学历不合格"。
- **示例**：`Bachelor's Degree — UNIVERSITY OF INFORMATION TECHNOLOGY, HCMC (2017)`
- **缺失**：`null`

### 2.9 `latest_degree`（string）
- **是什么**：最高或最新的一条学历，提炼为「专业 — 院校」。
- **怎么认出**：从 `education` 的条目里，取年份最新（或学位等级最高）的一条；有的简历会单独写一行 `Latest: 专业 — 院校`。
- **规则**：格式 `专业 — 院校`；原文无专业信息写 `unknown — 院校`。
- **示例**：`Software Engineering — University of Information Technology, Vietnam National University, HCMC`
- **缺失**：`null`

### 2.10 `highest_degree`（enum）
- **是什么**：学位等级。
- **怎么认出**：教育相关文本中的学位词。
- **规则**：只能取 `high_school`、`diploma`、`bachelor`、`master`、`phd` 之一：
  - `bachelor`：Bachelor、B.Tech、B.E.、BSc、BA、本科、学士
  - `master`：Master、M.Tech、MSc、MBA、硕士
  - `phd`：PhD、Doctorate、博士
  - `diploma`：Diploma、Associate、大专、专科
  - `high_school`：High School、Secondary、高中
  - 多条取最高
- **禁止**：默认填 `bachelor`。
- **缺失**：`null`

### 2.11 `domain`（enum）
- **是什么**：候选人所在行业的**公司业务**，与岗位职能无关。
- **怎么认出**：从雇主名称与工作描述中的业务词判断（服务对象、产品类型、行业术语）。
- **规则**：只能取一个值：`software`、`data-ai`、`fintech`、`ecommerce`、`healthcare`、`manufacturing`、`retail`、`marketing`、`logistics`、`education`、`energy`、`consulting`、`other`。
  - 银行/保险/券商/支付/加密 → `fintech`
  - 电商平台（Shopee、Lazada、Zalora）→ `ecommerce`
  - 半导体设备/汽车零部件/钢铁/机械 → `manufacturing`
  - IT 外包/软件产品/互联网 → `software`
  - 广告公司/媒体代理 → `marketing`
- **示例**：`Uber` → `"software"`；`BP` → `"energy"`；`Goldman Sachs` → `"fintech"`
- **缺失**：`"other"`

---

## 3. 由程序计算、模型不要填的 3 个字段

以下三个字段一律输出 `null`：

| 字段 | 原因 | 程序算法 |
|---|---|---|
| `years_experience` | 日期算术，模型易错 | 累加 `work_history` 各段月数，减去重叠 |
| `relevant_years` | 需与具体 JD 比对，单份简历无从判断 | 只累加与 JD 同岗位大类、或与必备技能有交集的经历段 |
| `seniority` | 需跨字段综合，title 通胀严重 | 优先看是否带团队（`led a team of N`、`managed N people`）→ lead；否则按 title 关键词（intern/junior→junior；senior/sr→senior；lead/principal/staff/head/chief/director→lead）；其余→mid |

---

## 4. 全局禁止事项

1. **不许按位置找**：没有"页眉第三行"这回事。任何字段都按语义在全文搜索。
2. **不许因缺段落判空**：没有 `Skills` 标题不代表没有技能，可能写在职责描述里。
3. **不许推断**：没写国家不得从大学推；没写语言不得从简历语言推。
4. **不许补全**：技能只收原文出现过的词。
5. **不许编造 evidence**：必须逐字来自原文，找不到就置 `null`。
6. **不许自造枚举值**：`highest_degree`、`domain`、`level` 只能取白名单值。
7. **不许输出散文**：只返回 JSON。
8. **不许把 JD 当 CV**：若输入文档同时含 JD 与简历，只处理 `CV OF THE HIRED CANDIDATE` 之后的部分。

---

## 5. 自检清单

- [ ] 所有 15 个键都存在
- [ ] 每个字段是靠"内容特征"识别出来的，不是靠位置
- [ ] 分页断裂、换行切词、表格错位没有导致漏抽
- [ ] 页眉页脚与页码没有被当作正文内容
- [ ] `work_history` 倒序、日期格式 `YYYY-MM` 或 `present`
- [ ] `skills` 全小写、去重、无软技能、无自然语言名
- [ ] `highest_degree` 在五个枚举值内
- [ ] `domain` 在十三个枚举值内
- [ ] 三个派生字段均为 `null`
- [ ] 每个非 `null` 字段都有 `evidence`
