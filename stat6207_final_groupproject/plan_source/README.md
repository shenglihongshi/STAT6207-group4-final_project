# 单页计划书 · 源文件

本目录保存单页计划书的可编辑 HTML 源文件，A4 单页 PDF 已输出到项目根目录：

- `../AI_CV_Matching_OnePage_Plan_CN.pdf`（中文版）
- `../AI_CV_Matching_OnePage_Plan_EN.pdf`（英文版）

## 修改组名 / 成员

在 HTML 中搜索以下占位符并替换：

- 中文版：`小组：____________`、`成员：____________________`
- 英文版：`Team: ____________`、`Members: ____________________`

## 重新导出 PDF（Windows + Edge）

```powershell
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$html = (Resolve-Path ".\one_page_plan_cn.html").Path
$url = "file:///" + ($html -replace '\\','/')
& $edge --headless --disable-gpu --no-pdf-header-footer `
  --print-to-pdf="..\AI_CV_Matching_OnePage_Plan_CN.pdf" $url
```

英文版把文件名换成 `one_page_plan_en.html` 即可。

## 数据口径

- `Manatal Examples – JD & CV (anonymised).xlsx`：50 份 JD 文本 + 100 条结构化 CV 摘要；这 100 条摘要与 `Anonymised-CVs-100` 中的 100 份 PDF 按 `Ref`（CV-001…CV-100）一一对应。表内没有匹配标签。
- 技术岗子集：23 份技术 JD、46 份技术 CV。
- `JD + Hired CV examples`：10 份 PDF，每份包含 1 份 JD 和 1 份 hired CV，是 **10 组“完美匹配”范例**，作为 known-good 测试（给定 JD，hired CV 是否进 Top-1/Top-5），不参与调参。
- 计划书按“10 组 hired known-good + 另标 50 组技术岗正例 + 50 组 hard negatives”设计；技术岗正例与负例共 100 对。

## 注意

- 版式按 A4 单页设计；改动文字后请检查是否仍为 1 页。
- PDF 中的 **70% / nDCG@5 0.75 / 盲评一致率 80%** 是建议目标值，提交前请与老师或招聘团队确认，确认后可在文中改为最终值。
