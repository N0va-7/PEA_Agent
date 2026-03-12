# 05. 模型与实验材料说明

## 1. 当前保留的算法能力

当前系统只保留 1 个传统模型：

1. URL 风险模型：`ml/artifacts/phishing_url.pkl`

正文模型已经从仓库中移除，不再参与当前主流程。

## 2. 当前风险信号来源

邮件或 URL 的最终结论由以下信号共同形成：

1. VirusTotal URL reputation
2. URL 传统模型评分
3. LLM 内容复核分数
4. 附件静态沙箱结果

## 3. URL 模型方案

当前 URL 模型的核心思路：

1. 特征：字符级 `TF-IDF`
2. 分类器：`LogisticRegression`
3. 优点：对域名拼写变体、路径片段、脚本后缀和钓鱼关键词更敏感

保留它的原因：

1. 推理轻量
2. 部署简单
3. 结果可解释
4. 与 VT 信誉组合后表现稳定

## 4. Notebook 与图表材料

论文配套 notebook：

`output/jupyter-notebook/url-model-training-walkthrough.ipynb`

该 notebook 已预执行，包含：

1. 数据集标签分布
2. 现有模型结构说明
3. `LogisticRegression / SGDClassifier / MultinomialNB` 对比
4. ROC 曲线
5. 混淆矩阵
6. 高权重特征条形图
7. 辅助词云图

## 5. 已导出的论文图

图文件目录：

`output/jupyter-notebook/url-model-figures/`

当前可直接使用：

1. `dataset-label-distribution.png`
2. `model-metric-comparison.png`
3. `roc-curves.png`
4. `best-model-confusion-matrix.png`
5. `feature-weight-bar-charts.png`
6. `ngram-wordclouds.png`

## 6. 论文中建议怎么写

### 6.1 算法部分

建议写成：

1. 先用 VT 提供外部情报
2. 再用 URL 模型补充模式识别能力
3. 再由内容复核和附件分析补足上下文
4. 最后由决策引擎统一裁决

### 6.2 实验部分

建议重点展示：

1. 数据集分布
2. 模型对比
3. ROC 曲线
4. 混淆矩阵
5. 高权重特征条形图

词云图建议作为辅助图，不建议当核心结论图。
