# 05. 部署、安全与运维要点

## 1. 环境分层建议

### 1.1 生产环境（推荐）

1. 数据库：MySQL（通过 `DATABASE_URL` 配置）。
2. 队列：Redis（`JOB_QUEUE_BACKEND=redis`）。
3. 特点：更适合并发、可恢复与长期运行。

### 1.2 开发环境（兼容）

1. 数据库：SQLite（`DATABASE_URL` 为空时回退）。
2. 队列：memory。
3. 特点：单机快速调试、零外部依赖。

## 2. 关键配置项

配置入口：`backend/.env.example`

必须关注：

1. `DATABASE_URL`
2. `JOB_QUEUE_BACKEND`
3. `REDIS_URL`
4. `AUTH_USERNAME`
5. `AUTH_PASSWORD_HASH`
6. `JWT_SECRET_KEY`
7. `TUNING_MIN_TOTAL_SAMPLES`
8. `TUNING_MIN_CLASS_SAMPLES`
9. `TUNING_RECENT_DAYS`

## 3. 启动流程

1. 安装依赖：`./backend/scripts/bootstrap_py311.sh`
2. 执行迁移：`./.py311/bin/alembic -c backend/alembic.ini upgrade head`
3. 启动后端：`./.py311/bin/uvicorn backend.main:app --reload`
4. 启动前端：`cd frontend && npm run dev`

## 4. 安全设计

### 4.1 鉴权与登录保护

1. JWT 鉴权保护业务接口。
2. 登录限流防爆破（429 场景）。
3. 密码支持 PBKDF2，并兼容历史 SHA256。

### 4.2 错误与信息脱敏

1. 默认不透传内部异常细节。
2. `runtime-info` 接口不返回明文密码，只给配置状态。

### 4.3 文件与路径安全

1. 报告下载限制在报告根目录内。
2. 删除历史时仅清理受控路径文件。

## 5. 可观测与稳定性

1. 任务状态与阶段事件可查询。
2. 调参任务单并发保护，避免冲突。
3. 应用启动会检查 schema 漂移并输出告警日志。

## 6. 测试策略

### 6.1 后端

建议至少执行：

1. `./.py311/bin/python -m pytest backend/tests -q`

覆盖重点：

1. 鉴权与限流。
2. 分析任务与报告下载。
3. 历史删除与路径兼容。
4. 反馈与调参 API。
5. 系统信息脱敏。

### 6.2 前端

建议执行：

1. `cd frontend && npm run test:unit`
2. `cd frontend && npm run build`
3. 可选：`cd frontend && npm run test:e2e`

## 7. 运维排障指引

1. 登录失败：先检查用户名、密码哈希、JWT 密钥。
2. 调参不可运行：先看 precheck 的 `blocking_reasons`。
3. 报告无法读取：检查报告路径与文件是否存在。
4. Redis 启动异常：检查 `REDIS_URL` 与网络连通性。
5. 迁移报错：检查数据库连接和 Alembic 版本状态。

