# 03. 数据库设计与复用策略

## 1. 主数据库

主系统使用 MySQL，核心表定义在 `backend/models/tables.py`。

### 1.1 `email_analyses`

存储每封邮件的完整分析结果，关键字段包括：

1. 基本信息：`message_id`、`fingerprint`、`sender`、`recipient`、`subject`
2. 分析结果：`parsed_email`、`url_extraction`、`url_reputation`、`url_analysis`
3. 高层结果：`content_review`、`attachment_analysis`、`decision`
4. 报告信息：`report_markdown`、`report_path`
5. 审核信息：`review_label`、`review_note`

### 1.2 `analysis_jobs`

用于异步任务状态管理：

1. `status`
2. `current_stage`
3. `analysis_id`
4. `progress_events`

### 1.3 `analysis_feedback_events`

用于记录人工复核审计历史。

### 1.4 `vt_url_cache`

用于缓存 VT URL 查询结果，减少重复请求和配额消耗。

### 1.5 `url_analyses`

用于存储独立 URL 风险分析结果，支持按归一化 URL 复用。

## 2. 附件静态沙箱数据库

附件静态沙箱使用独立 PostgreSQL 和 Redis。

它维护的核心概念包括：

1. 样本对象：按 `sha256` 标识
2. 分析任务：按 `job_id` 跟踪
3. 分析结果：包含 `verdict`、`risk_score`、`reasons`
4. 规则版本：用于判断缓存结果是否仍然有效

## 3. 复用策略

### 3.1 邮件分析复用

邮件主链会先计算 `fingerprint`。

若 `email_analyses` 中已存在相同指纹，系统直接返回历史结果，不再重新执行整条工作流。

### 3.2 URL 分析复用

独立 URL 分析会先完成 URL 归一化和哈希计算。

若 `url_analyses` 中已有相同 `url_hash`，则：

1. 返回历史结果
2. 增加 `request_count`
3. 标记为缓存命中

### 3.3 VT 查询复用

VT 查询先命中 `vt_url_cache`。

缓存策略包括：

1. 成功结果缓存
2. `404` 结果缓存
3. `429/5xx` 不覆盖旧成功缓存
4. Public API 模式下按节流间隔控制请求

### 3.4 附件样本复用

附件静态沙箱按样本 `sha256` 复用分析结果。

若样本内容不变且规则版本未变化，则不会重新跑一遍静态分析。

## 4. 论文可展示的数据设计亮点

1. 主分析与附件分析分库解耦。
2. URL 和附件都做了结果复用，降低重复分析成本。
3. 分析结果使用 JSON 结构化存储，适合前端展示和后续扩展。
