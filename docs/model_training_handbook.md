# 模型训练手册（直白版）

## 1. 先回答你的核心疑问

### 1.1 `retrain_models.py` 是干嘛的

它是“离线重训工具”。

它做四件事：

1. 读两份训练数据 CSV（正文、URL）。
2. 训练两套模型并导出 `.pkl`。
3. 在验证集上找阈值。
4. 输出重训报告 `retrain_report_*.json`。

### 1.2 目前项目有自动用到它吗

没有。

- 后端代码没有自动调用这个脚本。
- 只有你手动跑，才会覆盖 `ml/artifacts/*.pkl`。

### 1.3 现在的调参数到底是哪一段在跑

是融合调参：

1. API 收集人工打标样本。
2. 用 `tune_fusion_threshold.py` 的函数做网格搜索。
3. 产出 `fusion_tuning_*.json`。
4. 手动激活后生效。

## 2. 当前基础模型产物（按文件实测）

当前 `ml/artifacts` 里的两个文件是：

1. `phishing_body.pkl`：`TfidfVectorizer + RandomForestClassifier`
2. `phishing_url.pkl`：`CountVectorizer + LogisticRegression`

这和 notebook 内容一致：

1. 正文 notebook 包含 `RandomForestClassifier`、`SVC` 方案。
2. URL notebook 包含 `CountVectorizer + LogisticRegression`、`MultinomialNB` 方案。

## 3. `retrain_models.py` 用了什么技术

它用的是另一套轻量训练管线：

1. 特征：TF-IDF（正文词 n-gram、URL 字符 n-gram）
2. 分类器：`SGDClassifier(loss="log_loss")`
3. 切分：`train/val/test = 70/15/15`
4. 阈值选择：优先满足 `FPR` 目标

## 4. 为什么要有“融合调参”这层

因为你的线上误报/漏报，很多时候是“阈值和权重问题”，不是“基础模型必须重训”。

融合调参的价值：

1. 成本低：不动基础模型。
2. 风险低：有门槛检查，不会小样本乱调。
3. 可回滚：每次调参是一个版本，激活可回退。
4. 易解释：每个参数组合都有指标。

## 5. 为什么用网格搜索，不用更复杂方法

在这个场景里，参数空间很小（权重+阈值），网格搜索反而是最稳妥的：

1. 足够快。
2. 易复现。
3. 易审计。
4. 指标对比清楚。

可以替代，但没必要先上复杂方案：

1. 可替代为贝叶斯优化。
2. 可替代为遗传算法。
3. 可替代为可微优化。

这些更复杂，但收益不一定明显，且解释成本更高。

## 6. 什么时候应该重训基础模型

满足下面条件再做：

1. 反馈数据量够大，融合调参仍不理想。
2. 错误主要来自单模型本身（不是阈值错）。
3. 数据分布明显变化（业务语料、URL模式变了）。

## 7. 常用命令

### 7.1 手动重训（可选）

```bash
/Users/qwx/dev/code/PEA_Agent/.py311/bin/python /Users/qwx/dev/code/PEA_Agent/ml/training/retrain_models.py
```

### 7.2 离线融合调参（脚本方式）

```bash
/Users/qwx/dev/code/PEA_Agent/.py311/bin/python /Users/qwx/dev/code/PEA_Agent/ml/training/tune_fusion_threshold.py \
  --csv /path/to/labeled_email_level_scores.csv \
  --fpr-target 0.03 \
  --output-json /tmp/fusion_tuning.json
```
