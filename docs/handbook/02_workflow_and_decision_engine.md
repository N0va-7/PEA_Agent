# 02. 工作流与决策引擎实现要点

## 1. 工作流节点链路

工作流在 `backend/workflow/graph.py` 定义，核心节点顺序：

1. `fingerprint_email`：生成邮件指纹。
2. `check_existing_analysis`：缓存命中检查。
3. `parse_eml_file`：解析头部、正文、附件。
4. `extract_urls`：提取正文 URL。
5. `analyze_attachment_reputation`：附件威胁判定。
6. `analyze_body_reputation`：正文模型概率预测。
7. `analyze_url_reputation`：URL 模型概率预测。
8. `analyze_email_data`：融合决策。
9. `llm_report`：报告生成。
10. `persist_analysis`：写库与落盘报告。

## 2. 条件路由规则

在 `backend/workflow/edges.py` 中定义关键分支：

1. 缓存命中则直接结束。
2. 有附件先做附件分析。
3. 有正文才做正文模型。
4. 有 URL 才做 URL 模型。
5. 最终都汇聚到融合决策节点。

## 3. 最终判定逻辑（核心）

决策节点在 `backend/workflow/nodes/analysis.py`，规则优先级：

1. 附件判定为恶意时，直接恶意。
2. 无正文时，默认正常（分数 0）。
3. 有正文且有 URL，执行融合评分并与融合阈值比较。
4. 仅正文时，使用正文阈值判定。

## 4. 动态置信融合公式

当正文与 URL 同时存在时，融合评分：

```text
c_u = |p_url - 0.5| + 0.5
c_t = |p_text - 0.5| + 0.5
w_u = (w_url_base * c_u) / (w_url_base * c_u + w_text_base * c_t)
w_t = 1 - w_u
score = w_u * p_url + w_t * p_text
```

设计意图：

1. 让置信更高的信号在单封邮件中权重更高。
2. 降低单一弱信号导致的误判。

## 5. 参数来源优先级

决策参数并非写死，读取优先级：

1. 当前激活调参版本（数据库 `system_config` 指向 `fusion_tuning_runs`）。
2. `ml/artifacts/fusion_tuning*.json` 最新文件。
3. 代码默认参数（兜底）。

## 6. 报告生成机制

报告节点在 `backend/workflow/nodes/llm_report.py`，策略是“结构稳定优先”：

1. 优先请求 LLM 返回结构化 JSON 字段。
2. 按固定中文模板渲染 Markdown。
3. 若 LLM 异常或返回不符合预期，自动回退默认中文文案。

## 7. 任务进度可观测机制

`backend/services/analysis_service.py` 会记录节点级进度事件：

1. 阶段开始。
2. 阶段完成。
3. 任务成功/失败/缓存命中。

这保证前端可展示完整执行进度，不是黑盒等待。

