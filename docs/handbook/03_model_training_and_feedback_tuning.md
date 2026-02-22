# 03. 模型训练与反馈调参机制

## 1. 基础模型与融合层的职责拆分

项目把“模型预测能力”和“业务判定策略”拆成两层：

1. 基础模型层：
   - 正文模型：输出正文钓鱼概率。
   - URL模型：输出 URL 钓鱼概率。
2. 融合策略层：
   - 根据两类概率做动态权重融合。
   - 使用阈值完成最终恶意判定。

这意味着后续优化不一定要重训基础模型，也可以先优化融合层参数。

## 2. 基础训练流程（离线）

训练脚本：`ml/training/retrain_models.py`

1. 读取正文与 URL 训练数据。
2. 分层切分 train/val/test。
3. 训练支持概率输出的线性分类器。
4. 在验证集按 FPR 目标选阈值。
5. 导出线上产物到 `ml/artifacts/`：
   - `phishing_body.pkl`
   - `phishing_url.pkl`
   - `retrain_report_*.json`

## 3. 在线推理阶段做什么

每封邮件分析时：

1. 读取 `phishing_body.pkl` 预测正文概率。
2. 读取 `phishing_url.pkl` 预测 URL 概率并取最大风险值。
3. 决策节点读取当前生效融合参数并计算最终分数。
4. 根据阈值输出 `is_malicious` 与 `reason`。

## 4. 反馈驱动调参（不是重训）

调参接口：`backend/api/routes/tuning.py`

### 4.1 数据来源

1. 从 `email_analyses` 中筛选已人工标注的样本。
2. 抽取字段：
   - `url_analysis.max_possibility`
   - `body_analysis.phishing_probability`
   - `review_label -> {malicious:1, benign:0}`

### 4.2 Precheck 门槛

必须满足：

1. 总样本量达到 `TUNING_MIN_TOTAL_SAMPLES`。
2. 正负样本分别达到 `TUNING_MIN_CLASS_SAMPLES`。
3. 最近 `TUNING_RECENT_DAYS` 内有新增反馈。

不满足直接拒绝运行，避免少量样本导致参数漂移。

### 4.3 运行逻辑

1. 网格搜索 `w_url_base` 与 `threshold`。
2. 先筛选满足 FPR 目标的候选。
3. 在候选中优先 Recall，再参考 F1。
4. 产出 `best` 与 `top_k` 候选。

### 4.4 激活逻辑

1. 运行成功后并不会自动生效。
2. 只有调用 `activate` 才更新当前生效版本。
3. 决策节点下一次读取时才应用新参数。

## 5. 关键结论

你现在项目“训练后还涉及什么”的准确答案：

1. 涉及融合参数搜索与阈值治理。
2. 涉及反馈样本质量门槛与人工发布控制。
3. 不涉及在线微调大模型。

