# 05. 部署、安全、可观测

## 1. 运行模式

### 1.1 生产常用

1. 数据库：MySQL（`DATABASE_URL`）
2. 队列：Redis（`JOB_QUEUE_BACKEND=redis`）

### 1.2 当前默认开发方式

1. 数据库：MySQL
2. 队列：Redis

## 2. 必填配置项

来自 `backend/infra/config.py` 与 `.env.example`：

1. `AUTH_USERNAME`
2. `AUTH_PASSWORD_HASH`
3. `JWT_SECRET_KEY`
4. `DATABASE_URL`（生产必须填）
5. `JOB_QUEUE_BACKEND`
6. `REDIS_URL`（当 backend=redis 时必须填）

## 3. 调参门槛配置

1. `TUNING_MIN_TOTAL_SAMPLES`（默认 500）
2. `TUNING_MIN_CLASS_SAMPLES`（默认 100）
3. `TUNING_RECENT_DAYS`（默认 7）

## 4. 启动步骤

```bash
./backend/scripts/bootstrap_py311.sh
docker compose up -d mysql redis
cp backend/.env.example backend/.env
./.py311/bin/alembic -c backend/alembic.ini upgrade head
./.py311/bin/uvicorn backend.main:app --reload

cd frontend
npm install
npm run dev
```

## 5. MySQL + Redis 示例

```env
DATABASE_URL=mysql+pymysql://root:root@127.0.0.1:3306/pea_agent?charset=utf8mb4
JOB_QUEUE_BACKEND=redis
REDIS_URL=redis://127.0.0.1:6379/0
```

对应基础设施可直接用根目录 `docker-compose.yml` 启动：

```bash
docker compose up -d mysql redis
```

## 6. 安全点

1. 认证：JWT。
2. 登录限流：连续失败会 429。
3. 错误脱敏：默认不返回内部异常细节。
4. 报告路径安全：报告下载与删除都限制在报告目录内。
5. 系统信息脱敏：前端只看到密码“已配置/未配置”。

## 7. 可观测点

1. 每个任务有阶段级 `progress_events`。
2. 调参 run 有完整状态与指标记录。
3. 启动时会检查 Alembic 版本漂移并写日志。

## 8. 常见排查

1. 登录失败：检查 `AUTH_*` 和 `JWT_SECRET_KEY`。
2. 调参不可运行：看 precheck 的 `blocking_reasons`。
3. 报告下载失败：检查 `report_path` 是否存在且在报告根目录内。
4. Redis 报错：检查 `REDIS_URL` 和网络连通。
5. 迁移失败：检查数据库连接和 Alembic 版本。
