# 04. 数据模型与 API 契约

## 1. 数据模型设计

核心表定义在 `backend/models/tables.py`。

### 1.1 email_analyses（分析主表）

存储每封邮件的：

1. 基础信息：发件人、主题、收件人、消息ID、指纹。
2. 分析结果：URL/正文/附件/最终判定 JSON。
3. 报告信息：报告文本与报告路径。
4. 反馈最新态：`review_label/review_note/reviewed_by/reviewed_at`。

### 1.2 analysis_jobs（任务表）

存储：

1. 异步任务状态（queued/running/succeeded/failed/cached）。
2. 当前阶段、错误信息。
3. 进度事件列表。

### 1.3 analysis_feedback_events（反馈审计表）

存储每次反馈变更的前后值与操作者时间，保证可审计。

### 1.4 fusion_tuning_runs（调参运行表）

存储每次调参的：

1. 输入参数与样本统计。
2. 运行状态与错误。
3. 最优参数、Top-K 候选、结果文件路径。
4. 是否激活及激活时间。

### 1.5 system_config（系统配置表）

用于记录当前激活的调参版本指针，例如 `active_fusion_tuning_run_id`。

## 2. API 分组与契约

基础路由前缀：`/api/v1`

### 2.1 认证

1. `POST /auth/login`
2. 输入：用户名与密码。
3. 输出：JWT token 与过期时间。

### 2.2 分析任务

1. `POST /analyses`：上传 `.eml`，返回 `job_id`。
2. `GET /jobs/{job_id}`：查询任务状态与阶段进度。
3. `GET /analyses`：按主题、发件人、时间分页检索。
4. `GET /analyses/{analysis_id}`：读取分析详情。
5. `DELETE /analyses/{analysis_id}`：删除单条记录。
6. `DELETE /analyses`：清空历史记录。

### 2.3 报告与反馈

1. `GET /reports/{analysis_id}`：下载报告。
2. `POST /analyses/{analysis_id}/feedback`：提交反馈。
3. `GET /analyses/{analysis_id}/feedback-history`：读取反馈审计轨迹。

### 2.4 调参与版本

1. `POST /tuning/fusion/precheck`：运行前门槛检查。
2. `POST /tuning/fusion/run`：手动运行调参。
3. `GET /tuning/fusion/runs`：查看历史运行记录。
4. `POST /tuning/fusion/runs/{run_id}/activate`：激活版本。

### 2.5 系统信息

1. `GET /system/runtime-info`：返回数据库与队列信息（脱敏展示）。

## 3. 错误码与前端映射

前端错误映射定义在 `frontend/src/api.js`，典型错误码：

1. `invalid_credentials`
2. `too_many_login_attempts`
3. `analysis_not_found`
4. `report_not_found`
5. `precheck_failed`
6. `tuning_already_running`
7. `tuning_run_not_succeeded`

这保证用户界面错误提示可读，不直接暴露内部异常栈。

