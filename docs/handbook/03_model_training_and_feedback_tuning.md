# 03. 模型训练与反馈调参

## 1. 三条线要分清

### 1.1 线上推理线（每封邮件都会走）

1. 读取 `phishing_body.pkl` 得正文概率。
2. 读取 `phishing_url.pkl` 得 URL 概率。
3. 用融合参数算最终分数并判定。

### 1.2 离线重训线（手动脚本）

1. 脚本：`ml/training/retrain_models.py`
2. 输入：`Phishing_Email.csv`、`phishing_site_urls.csv`
3. 输出：`phishing_body.pkl`、`phishing_url.pkl`、`retrain_report_*.json`

注意：

- 这条线不会被后端自动触发。

### 1.3 反馈调参线（前端手动触发）

1. 从已打标结果提取 `url_prob,text_prob,label`。
2. 网格搜索 `w_url_base + threshold`。
3. 产出调参版本 JSON。
4. 手动 Activate 后才生效。

## 2. 当前仓库里的基础模型产物是什么

按当前 `ml/artifacts/*.pkl` 实际加载结果：

1. 正文模型：`TfidfVectorizer + RandomForestClassifier`
2. URL 模型：`CountVectorizer + LogisticRegression`

这与 `retrain_models.py` 中实现的 `SGDClassifier(log_loss)` 不同。

结论：

- 你现在在用的是 notebook 产物风格的模型文件。
- `retrain_models.py` 是可选替代训练管线，不是当前默认在线来源。

## 3. 标签重训到底怎么触发

如果你说的是“打标后自动更新线上参数”：

- 不会自动触发。

真实触发条件是：

1. 先打标：`POST /api/v1/analyses/{analysis_id}/feedback`
2. 再 Precheck：`POST /api/v1/tuning/fusion/precheck`
3. 再手动 Run（`confirm=true`）：`POST /api/v1/tuning/fusion/run`
4. 最后 Activate：`POST /api/v1/tuning/fusion/runs/{run_id}/activate`

权限说明：

1. Run 和 Activate 由后端限制为管理员账号执行（当前判断为 `AUTH_USERNAME` 对应用户）。

## 4. 为什么融合调参选“网格搜索 + FPR约束”

因为这个场景目标很明确：

1. 先控制误报（FPR）。
2. 再尽量提高召回（Recall）。

网格搜索的优点：

1. 可解释：每个候选参数都有明确指标。
2. 可复现：同样输入一定得到同样输出。
3. 可审计：便于记录和回滚。

## 5. 一个小例子

假设有三条打标数据：

```csv
url_prob,text_prob,label
0.91,0.72,1
0.15,0.20,0
0.63,0.81,1
```

调参脚本会遍历：

1. `w_url_base` 从 0 到 1（按步长）。
2. `threshold` 从 `th_min` 到 `th_max`（按步长）。

然后筛掉 `fpr > fpr_target` 的组合，只在剩余候选里选最优。

## 6. 什么时候才考虑重训基础模型

满足以下任一情况再考虑：

1. 反馈量足够但融合怎么调都不理想。
2. 误报来源集中在正文特征或 URL 特征本身，而不是阈值。
3. 数据分布明显变化（业务域、语言、攻击模板发生变化）。

否则先做融合调参，成本更低、风险更可控。
