# 反馈调参需求与执行约束

这份文档不是“想法清单”，而是当前实现对应的执行规则。

## 1. 目标

把人工反馈转成可控的融合参数更新流程。

## 2. 触发原则

1. 只能手动触发。
2. 先 Precheck，后 Run。
3. Run 成功后默认不生效。
4. 只有 Activate 才切换线上参数。
5. Run 与 Activate 仅管理员可执行（当前以 `AUTH_USERNAME` 账号为准）。

## 3. 数据来源

来源表：`email_analyses`

抽取字段：

1. `url_analysis.max_possibility` -> `url_prob`
2. `body_analysis.phishing_probability` -> `text_prob`
3. `review_label` -> `label`

映射规则：

1. `malicious -> 1`
2. `benign -> 0`

## 4. 运行前门槛（Precheck）

不满足任一门槛就拒绝运行：

1. `valid_rows >= TUNING_MIN_TOTAL_SAMPLES`
2. `positive_rows >= TUNING_MIN_CLASS_SAMPLES`
3. `negative_rows >= TUNING_MIN_CLASS_SAMPLES`
4. 近 `TUNING_RECENT_DAYS` 内有新增反馈

## 5. 运行逻辑

1. 遍历 `w_url_base` 与 `threshold`。
2. 先筛 `fpr <= fpr_target` 的候选。
3. 在候选里优先 `recall`，再看 `f1`。
4. 输出 `best` 和 `top_k`。

## 6. 版本与生效

1. 每次运行会写一条 `fusion_tuning_runs` 记录。
2. 记录包含：参数、样本统计、结果 JSON 路径、状态。
3. 激活动作会更新 `system_config.active_fusion_tuning_run_id`。
4. 决策节点读取这个指针决定当前生效版本。

## 7. API 流程（前端也是按这个走）

1. `POST /api/v1/tuning/fusion/precheck`
2. `POST /api/v1/tuning/fusion/run`（`confirm=true`）
3. `GET /api/v1/tuning/fusion/runs`
4. `POST /api/v1/tuning/fusion/runs/{run_id}/activate`

## 8. 前端交互约束

1. 必须先看到 Precheck 结果。
2. 用户必须二次确认后才能 Run。
3. 历史页可查看每个 run 的状态和指标。
4. 激活前有确认弹窗。

## 9. 验收清单

1. 可以提交和更新反馈。
2. 反馈审计事件可查。
3. 小样本会被 Precheck 拦截。
4. 调参 run 可成功入库。
5. 激活后新参数能在后续分析中生效。
6. 历史 run 可用于回滚。
