# 04. 接口与前端模块设计

## 1. 主后端接口

主后端 API 前缀为 `/api/v1`。

### 1.1 认证接口

1. `POST /auth/login`

### 1.2 邮件分析接口

1. `POST /analyses`
2. `GET /jobs/{job_id}`
3. `GET /analyses`
4. `GET /analyses/{analysis_id}`
5. `DELETE /analyses/{analysis_id}`
6. `DELETE /analyses`
7. `POST /analyses/{analysis_id}/feedback`

### 1.3 URL 风险接口

1. `POST /url-checks`
2. `GET /url-checks`
3. `GET /url-checks/{analysis_id}`

### 1.4 报告与系统接口

1. `GET /reports/{analysis_id}`
2. `GET /system/runtime-info`

## 2. 附件静态沙箱接口

附件静态沙箱独立运行在 `http://127.0.0.1:8000`，核心接口包括：

1. `POST /analysis/jobs`
2. `GET /analysis/jobs`
3. `GET /analysis/jobs/{job_id}`
4. `GET /rules`
5. `GET /rules/{rule_path}`
6. `POST /rules`
7. `PUT /rules/{rule_path}`
8. `DELETE /rules/{rule_path}`

## 3. 前端模块

### 3.1 邮件上传页

功能：

1. 选择 `.eml` 文件
2. 发起异步分析任务
3. 展示阶段进度
4. 跳转详情结果

### 3.2 历史记录页

功能：

1. 筛选分析记录
2. 查看详情
3. 查看决策原因和报告
4. 删除历史

### 3.3 URL 风险页

功能：

1. 单条或批量输入 URL
2. 发起分析
3. 复用已分析 URL 结果
4. 展示 VT 与模型双侧输出

### 3.4 静态沙箱页

功能：

1. 上传附件样本
2. 查看近期静态沙箱历史
3. 查看风险分和裁决

### 3.5 规则管理页

功能：

1. 查看规则版本
2. 浏览规则列表
3. 查看和编辑本地规则

## 4. 页面设计思路

当前前端采用控制台式结构：

1. 左侧为导航区
2. 中间为操作台或列表区
3. 右侧为详情或状态区

这样做的好处是：

1. 上传、查看、解释三个动作可以并列存在
2. 适合展示安全分析结果而不是普通表单
3. 更适合论文截图和答辩演示
