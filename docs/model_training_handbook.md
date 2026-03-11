# 模型训练手册（URL-only）

## 1. 当前还保留什么

当前仓库只保留 URL 模型训练链路。

1. 训练数据：`ml/training/email_url/phishing_site_urls.csv`
2. 线上模型产物：`ml/artifacts/phishing_url.pkl`
3. 教学 notebook：`output/jupyter-notebook/url-model-training-walkthrough.ipynb`
4. 图表导出目录：`output/jupyter-notebook/url-model-figures/`
5. 离线调参脚本：`ml/training/tune_fusion_threshold.py`

正文模型、正文训练数据和 URL 重训脚本已经移除，不再是当前系统的一部分。

## 2. 现在怎么理解这个模型

当前仓库不再提供独立的 URL 重训脚本，保留的是：

1. 现有线上产物 `phishing_url.pkl`
2. 一份可直接运行的教学 notebook，用来展示训练过程、参数选择和基线对比

推荐阅读入口：

1. `output/jupyter-notebook/url-model-training-walkthrough.ipynb`

它会展示：

1. 当前线上模型的管线结构
2. 训练集标签分布
3. 字符级 TF-IDF 的设计原因
4. `LogisticRegression / SGDClassifier / MultinomialNB` 的对比
5. ROC、混淆矩阵、高权重特征条形图和词云
6. 为什么最后保留当前方案

并且：

1. notebook 已预执行，打开就能看到结果
2. 每个 code cell 前都有讲解
3. 每张关键图后都有图表解读

## 3. 训练管线

当前保留的 URL 模型思路为：

1. 特征：URL 字符级 `TF-IDF`
2. 分类器：`LogisticRegression`
3. 优点：对 URL 里的子串、混淆、路径模式比较敏感
4. 部署优势：产物轻、推理快、容易复现

## 4. `tune_fusion_threshold.py` 还在做什么

它保留为离线实验工具，用来对已有分数做权重和阈值网格搜索。

注意：

1. 它不依赖正文模型文件。
2. 其中的 `text_prob` 可以理解为“内容侧分数”，例如 LLM 内容复核分数。
3. 它不会自动更新线上主链，只是输出一个 JSON 供离线比较。

## 5. 常用命令

### 5.1 打开训练讲解 notebook

```bash
jupyter lab /Users/qwx/dev/code/PEA_Agent/output/jupyter-notebook/url-model-training-walkthrough.ipynb
```

### 5.2 直接取图表素材

图表会写到：

```text
/Users/qwx/dev/code/PEA_Agent/output/jupyter-notebook/url-model-figures/
```

当前包含：

1. `dataset-label-distribution.png`
2. `model-metric-comparison.png`
3. `roc-curves.png`
4. `best-model-confusion-matrix.png`
5. `feature-weight-bar-charts.png`
6. `ngram-wordclouds.png`

### 5.3 离线做分数融合实验

```bash
/Users/qwx/dev/code/PEA_Agent/.py311/bin/python /Users/qwx/dev/code/PEA_Agent/ml/training/tune_fusion_threshold.py \
  --csv /path/to/labeled_url_and_content_scores.csv \
  --fpr-target 0.03 \
  --output-json /tmp/fusion_tuning.json
```
