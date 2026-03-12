# 07. 部署与运行说明

## 1. 运行组件

系统分为 3 部分：

1. 主后端：FastAPI
2. 前端：Vue 3 + Vite
3. 附件静态沙箱：独立 FastAPI 服务

基础设施：

1. MySQL
2. Redis
3. 附件静态沙箱自己的 PostgreSQL + Redis

## 2. 基础设施启动

主系统基础设施：

```bash
docker compose up -d mysql redis
```

附件静态沙箱：

```bash
cd attachment_sandbox_service
docker compose up -d postgres redis api worker
```

## 3. 主后端启动

```bash
cp backend/.env.example backend/.env
./.py311/bin/alembic -c backend/alembic.ini upgrade head
./.py311/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8010
```

## 4. 前端启动

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

## 5. 关键环境变量

主系统需要重点配置：

1. `DATABASE_URL`
2. `REDIS_URL`
3. `JWT_SECRET_KEY`
4. `AUTH_USERNAME`
5. `AUTH_PASSWORD_HASH`
6. `VT_ENABLED`
7. `VT_API_KEY`
8. `ATTACHMENT_SANDBOX_BASE_URL`

## 6. 健康检查

主后端：

```bash
curl http://127.0.0.1:8010/healthz
```

静态沙箱：

```bash
curl http://127.0.0.1:8000/healthz
```

前端首页：

```bash
curl -I http://127.0.0.1:5173
```

## 7. 常见故障

### 7.1 VT 不返回结果

排查：

1. `VT_API_KEY` 是否配置
2. Public API 配额是否耗尽
3. 是否命中了缓存降级路径

### 7.2 静态沙箱页面报跨域

优先确认：

1. `8000` 上跑的是当前仓库的 `attachment_sandbox_service`
2. 不是旧目录中的历史进程
3. `allow_origins` 已包含 `5173`

### 7.3 历史记录为空

检查：

1. MySQL 迁移是否执行完成
2. URL 或邮件是否只是命中缓存但未刷新前端
3. 独立静态沙箱和主后端是否连接到不同数据库
