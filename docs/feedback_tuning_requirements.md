# 反馈调参与处理需求（实现前冻结草案）

关联主文档：
- `docs/project_handbook.md`
- `docs/handbook/03_model_training_and_feedback_tuning.md`

## 1. 背景与首要问题
当前系统的核心问题不是模型复杂度，而是缺少真实线上反馈闭环，导致无法可靠评估误报/漏报，也无法基于真实分布持续调优融合参数。

## 2. 目标
1. 建立可审计的人工反馈标注流程。
2. 基于反馈数据自动产出邮件级调参集（`url_prob,text_prob,label`）。
3. 一键运行融合调参并生成可加载的参数文件。
4. 支持参数版本化、回滚、灰度启用。

## 3. 成功指标（验收口径）
1. 反馈覆盖率：上线后 7 天内，新增分析结果中至少 30% 有人工反馈。
2. 调参可复现：同一输入数据与参数范围，输出结果一致。
3. 发布可回滚：可在 1 分钟内回退到前一版融合参数。
4. 可观测：每次调参与发布均有记录（时间、操作者、数据范围、指标）。

## 4. 范围
## In Scope
1. 后端数据模型新增反馈字段。
2. 反馈录入与查询 API。
3. 反馈数据导出为调参 CSV。
4. 融合调参任务触发、结果落盘、版本化管理。
5. 前端历史页增加“标注反馈”与“参数版本查看/启用”。

## Out of Scope（本阶段不做）
1. 重新训练正文/URL基础模型。
2. LLM 微调或更换主模型架构。
3. URL 提取策略改造。

## 5. 角色与流程
1. 分析员：在历史记录中标注每封邮件真实结果（恶意/正常）。
2. 管理员：触发调参任务，审核指标后启用新参数。
3. 系统：生成 `fusion_tuning_*.json`，并更新当前生效参数指针。

## 6. 功能需求
## FR-1 反馈标注
1. 每条 `email_analyses` 支持一次最新反馈（可覆盖旧反馈并保留审计记录）。
2. 反馈字段至少包含：
- `review_label`：`malicious` | `benign`
- `review_note`：可选文本
- `reviewed_by`：用户名
- `reviewed_at`：UTC 时间
3. 标注接口必须鉴权，仅登录用户可写。

## FR-2 反馈审计
1. 新建 `analysis_feedback_events` 表，记录每次修改历史，不丢审计。
2. 审计字段：`analysis_id`、旧值、新值、操作者、时间。

## FR-3 调参数据集导出
1. 按时间范围导出有反馈的数据为 CSV。
2. 输出列固定：`url_prob,text_prob,label`。
3. `url_prob` 来源：`url_analysis.max_possibility`。
4. `text_prob` 来源：`body_analysis.phishing_probability`。
5. `label` 映射：`malicious -> 1`, `benign -> 0`。
6. 数据校验：缺任一概率或标签则跳过并计数。

## FR-4 融合调参任务
1. 调参仅支持“用户手动触发”，禁止自动定时或自动触发。
2. 支持通过 API 触发调参任务，参数包括：`fpr_target`、阈值搜索范围、权重步长。
3. 增加运行门槛校验，未达到门槛直接拒绝执行并返回原因：
- 最小总样本数：默认 `>= 500`（可配置）
- 正/负类最小样本数：默认各 `>= 100`（可配置）
- 最近反馈更新时间窗口：默认 `7` 天内至少有新增反馈（可配置）
4. 任务触发前返回“预检查结果”（样本量、类分布、是否达标），前端需二次确认后才真正运行。
5. 任务执行后输出：
- `ml/artifacts/fusion_tuning_<timestamp>.json`
- `ml/artifacts/fusion_tuning_latest.json`（可选，按“启用”动作覆盖）
6. 任务结果入库：样本量、最优参数、Top-K 候选、触发人、时间。

## FR-5 参数版本管理
1. 新建 `fusion_tuning_runs` 表记录每次运行结果。
2. 支持“设为生效版本”动作。
3. 决策节点始终读取“生效版本”，而非固定文件名。
4. 支持回滚至任意历史版本。

## FR-6 前端交互
1. 历史详情页增加反馈标注区。
2. 增加调参管理页：
- 发起调参
- 查看运行历史与关键指标
- 一键启用/回滚

## 7. 非功能需求
1. 安全：所有写操作需 JWT 鉴权。
2. 并发：同一时间仅允许一个调参任务运行。
3. 性能：10 万条反馈样本调参在 2 分钟内完成（目标值）。
4. 稳定性：调参失败不得影响当前线上参数读取。
5. 防误触：运行门槛不达标时必须 fail-fast，不得“降级继续跑”。

## 8. 数据模型变更（初稿）
1. `email_analyses` 新增列：
- `review_label`（nullable）
- `review_note`（nullable）
- `reviewed_by`（nullable）
- `reviewed_at`（nullable）
2. 新表 `analysis_feedback_events`。
3. 新表 `fusion_tuning_runs`。
4. 新表 `system_config` 或等价配置表，用于存当前生效 `fusion_tuning_run_id`。

## 9. API 草案
1. `POST /api/v1/analyses/{analysis_id}/feedback`
2. `GET /api/v1/analyses/{analysis_id}/feedback-history`
3. `POST /api/v1/tuning/fusion/run`
4. `GET /api/v1/tuning/fusion/runs`
5. `POST /api/v1/tuning/fusion/runs/{run_id}/activate`
6. `POST /api/v1/tuning/fusion/precheck`（返回样本量与门槛校验结果）

## 10. 验收测试清单
1. 可成功提交反馈并在列表中看到最新反馈。
2. 修改反馈后审计表新增一条事件。
3. 导出 CSV 列与格式满足调参脚本输入要求。
4. 调参完成后可查看最优参数与候选列表。
5. 启用新版本后，后端决策读取到新参数并可回滚。
6. 样本量或类分布不达标时，调参接口拒绝执行且提示具体缺口。

## 11. 待你确认的决策点
1. `review_label` 是否只保留二值（`malicious/benign`），还是允许 `suspicious`。
2. 谁可以“启用参数版本”：仅管理员，还是所有登录用户。
3. 是否需要调参任务审批流（运行后需二次确认才能启用）。
4. 调参默认目标：`FPR <= 0.03` 是否继续沿用。
5. 运行门槛默认值是否采用：总样本 `500`、单类 `100`、近 `7` 天有新增反馈。
