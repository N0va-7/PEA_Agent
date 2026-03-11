# 策略评估节点拆分说明

## 背景

当前邮件分析主链路已经从“模型分数融合”转向“LLM First + 可解释规则决策”。在这条链路里，黑白名单策略属于独立的运营规则，不适合继续直接堆在 `decision_engine_v2` 里。

如果决策节点同时负责：

- 读取系统配置
- 解析发件人地址
- 匹配黑白名单
- 生成策略命中轨迹
- 汇总 URL / 正文 / 附件结果

那么它会很快变成一个难维护的“大节点”，后续每增加一种策略都要继续把状态读取、匹配逻辑和最终裁决混在一起。

## 目标

把“策略读取与匹配”从最终决策中拆出去，形成独立节点：

- `policy_evaluation`

这样可以让职责更清晰：

- `llm_content_review` 只负责正文安全复核
- `policy_evaluation` 只负责策略命中计算
- `decision_engine_v2` 只负责汇总与最终裁决

## 当前工作流

当前主流程调整为：

```text
parse_eml_file
  -> extract_urls
  -> analyze_attachment_reputation
  -> analyze_url_reputation
  -> llm_content_review
  -> policy_evaluation
  -> decision_engine_v2
  -> render_report
  -> persist_analysis
```

其中有一个特例：

- 如果附件已经被沙箱明确判为 `malicious`，流程会直接从 `analyze_attachment_reputation` 跳到 `policy_evaluation`，然后进入最终决策。
- 这样仍然保留了策略命中信息和统一的最终输出结构，但避免为一个已确定的强恶意附件再额外跑正文复核。

## `policy_evaluation` 节点职责

节点文件：

- `backend/workflow/nodes/policy_evaluation.py`

输入：

- `sender`

读取配置：

- `sender_whitelist`
- `sender_blacklist`
- `domain_blacklist`

输出：

- `sender_address`
- `sender_domain`
- `sender_whitelist`
- `sender_blacklist`
- `domain_blacklist`
- `policy_trace`

其中：

- `sender_address` 是标准化后的完整发件人地址，例如 `alerts@example.com`
- `sender_domain` 是发件人地址中的域名，例如 `example.com`
- `policy_trace` 会记录命中的策略，供最终决策和报告层直接复用

## 当前支持的策略

### 1. 精确发件人白名单

配置键：

- `sender_whitelist`

规则：

- 只按完整发件人邮箱精确匹配
- 例如 `alerts@example.com`

用途：

- 只在没有强恶意信号时，帮助把低风险误报从 `suspicious` 降级为 `benign`

限制：

- 白名单不能覆盖附件恶意
- 白名单不能覆盖正文强证据恶意
- 白名单不能覆盖高风险 URL + 可疑正文的组合结论

### 2. 精确发件人黑名单

配置键：

- `sender_blacklist`

规则：

- 按完整发件人邮箱精确匹配

用途：

- 命中后直接按恶意邮件处理

### 3. 发件域黑名单

配置键：

- `domain_blacklist`

规则：

- 按发件人域名匹配
- 支持父域命中，例如黑名单中有 `evil.test`，则 `sub.evil.test` 也视为命中

用途：

- 适合已经明确确认的仿冒域、钓鱼域
- 命中后直接按恶意邮件处理

## `decision_engine_v2` 的新职责边界

拆分后，`decision_engine_v2` 不再负责：

- 查数据库读取策略
- 解析发件人地址
- 自己做黑白名单匹配

它只消费：

- `url_analysis`
- `llm_content_review`
- `attachment_analysis`
- `policy_evaluation`

然后完成最终裁决：

- 发件人黑名单命中 -> `malicious`
- 发件域黑名单命中 -> `malicious`
- 附件 `malicious` -> `malicious`
- `URL >= 0.75` 且 正文 `suspicious` -> `malicious`
- 正文 `malicious` 且证据强 -> `malicious`
- 其余视情况落到 `suspicious` 或 `benign`
- 精确发件人白名单只允许对低风险 `suspicious` 做降级

## 这样拆分后的收益

### 1. 决策节点更稳定

最终决策只保留“裁决逻辑”，不再混入配置读取和策略匹配细节。

### 2. 策略更容易扩展

后续如果增加：

- URL 域名黑名单
- Reply-To 异常策略
- 历史反馈聚合策略

都可以继续收敛在 `policy_evaluation` 里，而不是继续膨胀 `decision_engine_v2`。

### 3. 报告和前端更容易复用

`policy_trace` 已经在一个节点里结构化产出，历史详情、报告、审计日志都可以直接消费，不需要各层重复推断。

## 当前范围之外

这次拆分有意不做以下能力：

- SPF / DKIM / DMARC 校验
- Return-Path / Reply-To 的强身份判断
- 自动学习型策略优化

原因是这些能力会显著增加复杂度，而且当前目标是先把主链路做成“清晰、稳定、可解释”的版本。

## 下一步建议

如果后续继续整理架构，优先级建议如下：

1. 已落地最小事件表 `policy_events`，用于记录策略更新与命中。
2. 下一步可以继续补备注原因和批量变更说明，避免只有“谁在什么时候改过”。
3. 在 `parse_eml` 阶段补标准化身份字段，为更严格的邮件身份判断做准备。
