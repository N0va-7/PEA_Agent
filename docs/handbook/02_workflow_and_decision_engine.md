# 02. 工作流与决策引擎

## 1. 节点链路

工作流定义在 `backend/workflow/graph.py`。

标准路径：

1. `fingerprint_email`
2. `check_existing_analysis`
3. `email_parser`
4. `url_extractor`
5. `url_reputation_vt`
6. `url_model_analysis`
7. `attachment_sandbox`
8. `content_review`
9. `decision_engine`
10. `report_renderer`
11. `persist_analysis`

## 2. 关键分支规则

1. 命中缓存：直接结束，返回历史结果。
2. URL 去重后优先查 VT 缓存和数据库复用。
3. 附件分析复用独立静态沙箱已有样本结果。
4. VT URL 高危或附件恶意时，可直接触发恶意短路。

## 3. 最终判定逻辑

逻辑在 `backend/agent_tools/decision_engine.py`。

判定优先级：

1. 附件恶意 -> 直接恶意。
2. VT URL 明确高危 -> 直接恶意。
3. 内容复核强恶意证据 -> 恶意或高优先级可疑。
4. 其他情况按 URL 模型、内容分和附件分综合判定。

## 4. 评分输入

当前决策层主要读取四类输入：

1. `vt_score`
2. `url_model_score`
3. `content_score`
4. `attachment_score`

决策层会优先处理短路规则，再给出最终 `score / verdict / reasons / decision_trace`。

## 5. 报告为什么更稳定

`llm_report.py` 采用“两段式”：

1. 先让 LLM 输出结构化 JSON（摘要、风险级别、证据、建议）。
2. 再由后端固定模板渲染 Markdown。

即使 LLM 异常，也会用默认中文文案填充，所以报告结构不会乱。

## 6. 一个直白例子

假设：

1. 某 URL 被 VT 标为高危。
2. 附件为空。
3. 内容复核只有一般社工迹象。

则最终仍会直接判恶意，因为 VT 高危 URL 命中了短路规则。
