# 02. 工作流与决策引擎

## 1. 节点链路

工作流定义在 `backend/workflow/graph.py`。

标准路径：

1. `fingerprint_email`
2. `check_existing_analysis`
3. `parse_eml_file`
4. `extract_urls`
5. `analyze_attachment_reputation`
6. `analyze_body_reputation`
7. `analyze_url_reputation`
8. `analyze_email_data`
9. `llm_report`
10. `persist_analysis`

## 2. 关键分支规则

1. 命中缓存：直接结束，返回历史结果。
2. 没正文：不跑正文模型。
3. 没 URL：不跑 URL 模型。
4. 附件先行：如果附件判恶意，可直接定恶意。

## 3. 最终判定逻辑

逻辑在 `backend/workflow/nodes/analysis.py`。

判定优先级：

1. 附件恶意 -> 直接恶意。
2. 无正文 -> 判正常（`score=0`）。
3. 正文+URL 都有 -> 走融合分数与融合阈值。
4. 只有正文 -> 用正文阈值判断。

## 4. 动态融合公式

```text
c_u = |p_url - 0.5| + 0.5
c_t = |p_text - 0.5| + 0.5
w_u = (w_url_base * c_u) / (w_url_base * c_u + w_text_base * c_t)
w_t = 1 - w_u
score = w_u * p_url + w_t * p_text
```

直白解释：

1. `p_url` 和 `p_text` 越远离 0.5，说明信号越“有把握”。
2. 更有把握的那一路会被临时加权更多。

## 5. 参数从哪里来

读取顺序：

1. 数据库激活版本（`system_config.active_fusion_tuning_run_id`）。
2. `ml/artifacts` 下最新 `fusion_tuning*.json`。
3. 代码默认值。

说明：

- 如果有 `retrain_report_*.json`，只会提供阈值提示，不会覆盖基础模型。

## 6. 报告为什么更稳定

`llm_report.py` 采用“两段式”：

1. 先让 LLM 输出结构化 JSON（摘要、风险级别、证据、建议）。
2. 再由后端固定模板渲染 Markdown。

即使 LLM 异常，也会用默认中文文案填充，所以报告结构不会乱。

## 7. 一个数值例子

假设：

1. `p_url=0.90`
2. `p_text=0.60`
3. `w_url_base=0.40`
4. `w_text_base=0.60`

则：

1. `c_u=0.90`
2. `c_t=0.60`
3. `w_u=(0.4*0.9)/(0.4*0.9+0.6*0.6)=0.5`
4. `w_t=0.5`
5. `score=0.5*0.9+0.5*0.6=0.75`

如果融合阈值是 `0.79`，这封邮件最终不会被判恶意。
