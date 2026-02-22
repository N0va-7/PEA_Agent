# 模型训练原理手册（PEA Agent）

## 1. 你当前方案是否合理

是合理的。  
你现在采用“URL 模型 + 正文模型”双模型并行，是邮件钓鱼检测里常见且实用的设计。问题一般不在架构，而在以下三点：

- 训练集和线上分布不一致（尤其 URL 数据老旧时，误报会高）。
- 概率分数没有校准，导致 0.8 未必真是“80%风险”。
- 融合权重与阈值没有在验证集系统搜索。

## 2. 训练目标怎么定义

先明确业务优先级：你现在主要痛点是“误报高”，所以目标应是：

1. 在验证集上约束误报率 `FPR <= 目标值`（例如 3%）。
2. 在满足 FPR 约束的候选中，最大化召回率 `Recall`。

如果只追求 Recall，系统会把大量正常邮件打成恶意；  
如果只追求 Precision，系统会漏掉真实钓鱼邮件。  
所以要做“约束优化”，而不是单指标优化。

## 3. 训练与评估流程（标准）

1. 按分层抽样切分：`train/val/test = 70/15/15`。
2. 分别重训正文和 URL 模型。
3. 当前版本使用 `log_loss` 模型直接输出概率；如需更强可解释性，可在下一版加入 sigmoid/isotonic 校准。
4. 在 `val` 上搜索阈值（优先满足 FPR 约束）。
5. 仅在 `test` 上做一次最终报告，避免数据泄漏。

说明：
- `train`：学习参数。
- `val`：调阈值/调权重。
- `test`：只用于最终验收，不能参与调参。

## 4. 指标原理（最重要）

二分类混淆矩阵：

- `TP`：恶意邮件判恶意
- `FP`：正常邮件误判恶意
- `FN`：恶意邮件漏判正常
- `TN`：正常邮件判正常

核心指标：

- `Precision = TP / (TP + FP)`：告警里有多少是真的
- `Recall = TP / (TP + FN)`：真实攻击抓住了多少
- `FPR = FP / (FP + TN)`：正常邮件被误伤比例
- `F1 = 2PR / (P + R)`：Precision 与 Recall 的平衡

你现在要解决的是误报，优先盯 `FPR`。

## 5. 线上融合公式原理

后端当前综合分：

```text
score = w_u * p_url + w_t * p_text
```

其中 `w_u/w_t` 不是固定值，而是带置信度动态缩放：

```text
c_u = |p_url - 0.5| + 0.5
c_t = |p_text - 0.5| + 0.5
w_u = (w_u_base * c_u) / (w_u_base * c_u + w_t_base * c_t)
w_t = 1 - w_u
```

含义：谁离 0.5 更远（更“有把握”），谁权重会被放大。

## 6. 如何找到“最合适点”

最合适点 = `(w_url_base, threshold)`，其中 `w_text_base = 1 - w_url_base`。

做法：

1. 准备“邮件级标注集”CSV，至少包含：
   - `url_prob`
   - `text_prob`
   - `label`（是否恶意）
2. 网格搜索：
   - `w_url_base`：`0.0~1.0`，步长 0.05
   - `threshold`：`0.50~0.95`，步长 0.01
3. 先筛 `FPR <= 目标值`，再选 Recall 最高。

这就是“最合适点”的工程定义。

## 7. 项目内一键命令

### 7.1 重训正文 + URL 模型

```bash
/Users/qwx/dev/code/PEA_Agent/.py311/bin/python /Users/qwx/dev/code/PEA_Agent/ml/training/retrain_models.py
```

输出：
- `/Users/qwx/dev/code/PEA_Agent/ml/artifacts/phishing_body.pkl`
- `/Users/qwx/dev/code/PEA_Agent/ml/artifacts/phishing_url.pkl`
- `ml/artifacts/retrain_report_*.json`

说明：
- 线上推理只读取 `ml/artifacts/` 下产物。
- `ml/training/**/model/*.pkl` 旧副本已从主仓库移除，避免与线上模型混淆。

### 7.2 搜索融合最优权重/阈值

```bash
/Users/qwx/dev/code/PEA_Agent/.py311/bin/python /Users/qwx/dev/code/PEA_Agent/ml/training/tune_fusion_threshold.py \
  --csv /path/to/labeled_email_level_scores.csv \
  --fpr-target 0.03 \
  --output-json /tmp/fusion_tuning.json
```

## 8. 常见误区

- 用 test 集反复调阈值：会高估真实效果。
- 只看 Accuracy：在不平衡数据上误导性很强。
- 训练集很旧但不更新：会导致线上误报/漏报显著上升。

## 9. 推荐迭代节奏

1. 每 2~4 周增量补充线上真实样本。
2. 每次重训必须产出同一格式报告（便于横向比较）。
3. 线上阈值调整必须有离线验证记录，避免拍脑袋改参。
