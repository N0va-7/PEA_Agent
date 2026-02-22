# 04. 数据表与 API 契约

## 1. 核心数据表

定义在 `backend/models/tables.py`。

### 1.1 `email_analyses`

存每封邮件的完整分析结果：

1. 基本字段：`sender/recipient/subject/message_id/fingerprint`
2. 分析 JSON：`url_analysis/body_analysis/attachment_analysis/final_decision`
3. 报告：`llm_report/report_path`
4. 反馈最新态：`review_label/review_note/reviewed_by/reviewed_at`

### 1.2 `analysis_jobs`

存异步任务状态与进度：

1. `status/current_stage/error`
2. `progress_events`

### 1.3 `analysis_feedback_events`

存反馈审计历史：

1. 修改前标签/备注
2. 修改后标签/备注
3. 操作人和时间

### 1.4 `fusion_tuning_runs`

存每次调参运行：

1. 输入参数与样本统计
2. 运行状态、报错
3. 结果文件路径
4. `best_params` 与 `top_k`
5. 是否激活

### 1.5 `system_config`

存系统级指针，例如：

1. `active_fusion_tuning_run_id`

## 2. API 总览

基础前缀：`/api/v1`

### 2.1 认证

1. `POST /auth/login`

### 2.2 分析任务

1. `POST /analyses` 上传 `.eml`
2. `GET /jobs/{job_id}` 看进度
3. `GET /analyses` 分页检索
4. `GET /analyses/{analysis_id}` 看详情
5. `DELETE /analyses/{analysis_id}` 删单条
6. `DELETE /analyses` 清空历史

### 2.3 报告与反馈

1. `GET /reports/{analysis_id}` 下载报告
2. `POST /analyses/{analysis_id}/feedback` 提交打标
3. `GET /analyses/{analysis_id}/feedback-history` 查审计

### 2.4 调参与版本

1. `POST /tuning/fusion/precheck`
2. `POST /tuning/fusion/run`
3. `GET /tuning/fusion/runs`
4. `POST /tuning/fusion/runs/{run_id}/activate`

### 2.5 系统信息

1. `GET /system/runtime-info`

返回脱敏信息：

1. 数据库驱动、地址、用户名、是否有密码
2. 队列后端、Redis 地址、是否有密码

## 3. 关键输入输出示例

### 3.1 反馈提交请求

```json
{
  "review_label": "malicious",
  "review_note": "仿冒财务通知，链接域名可疑"
}
```

### 3.2 调参预检查响应（示例）

```json
{
  "meets_requirements": false,
  "blocking_reasons": [
    "valid_rows=120 is below min_total=500"
  ],
  "valid_rows": 120,
  "positive_rows": 40,
  "negative_rows": 80
}
```

## 4. 错误码（前端有映射）

典型错误码：

1. `invalid_credentials`
2. `analysis_not_found`
3. `report_not_found`
4. `precheck_failed`
5. `tuning_already_running`
6. `tuning_run_not_succeeded`
