# PEA Agent

PEA Agent 是一个邮件与链接安全分析控制台。

当前仓库已经重构成两层：

1. `backend/agent_tools`
   统一工具层，负责邮件解析、URL 提取、VT URL 信誉、URL 模型分析、正文复核、附件沙箱、决策和报告生成。
2. `backend/workflow`
   Agent 编排层，负责串起工具、命中缓存、持久化结果。

同时提供三类前端分析入口：

1. 邮件上传分析
2. 独立 URL 风险分析
3. 独立静态沙箱扫描

## 当前能力

- 邮件 `.eml` 上传分析
- VirusTotal URL 信誉查询
- URL 模型风险评分
- 正文内容复核
- 附件静态沙箱接入 `Eml_Agent`
- 最终决策与 Markdown 报告输出
- 历史记录、人工反馈、规则管理
- 独立 URL 检查台

## 缓存与复用

系统默认会复用已分析记录，避免重复消耗外部配额和重复扫描：

- 邮件分析：按 `message_id / fingerprint` 命中历史记录
- URL 检查：按归一化 URL 命中 `url_analyses`
- VT URL 查询：按归一化 URL 命中 `vt_url_cache`
- 附件静态沙箱：按样本 `SHA256` 命中 `Eml_Agent` 缓存

## 目录

```text
backend/
  agent_tools/          核心分析工具
  api/                  FastAPI 路由
  models/               SQLAlchemy 表结构
  repositories/         持久化访问层
  schemas/              API schema
  services/             工作流与任务服务
  workflow/             Agent workflow 编排
  alembic/              数据库迁移

frontend/
  src/views/            控制台页面
  src/api.js            前端 API 客户端

Eml_Agent/
  独立静态附件沙箱
```

## 技术栈

- Backend: FastAPI, SQLAlchemy, Alembic
- Frontend: Vue 3, Vite
- Database: MySQL
- Queue/Cache: Redis
- External intel: VirusTotal URL API
- Attachment sandbox: 独立 `Eml_Agent`

## 快速启动

### 1. 基础设施

```bash
docker compose up -d mysql redis
```

默认地址：

- MySQL: `127.0.0.1:3306`
- Redis: `127.0.0.1:6379`

### 2. 后端

```bash
cp backend/.env.example backend/.env
./.py311/bin/alembic -c backend/alembic.ini upgrade head
./.py311/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8010 --reload
```

### 3. 前端

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### 4. 静态沙箱

按 `Eml_Agent/README.md` 启动独立服务，默认使用：

- `http://127.0.0.1:8000`

## 关键环境变量

`backend/.env` 至少需要这些配置：

```env
DATABASE_URL=mysql+pymysql://root:root@127.0.0.1:3306/pea_agent?charset=utf8mb4
REDIS_URL=redis://127.0.0.1:6379/0
JOB_QUEUE_BACKEND=redis

JWT_SECRET_KEY=replace-me
AUTH_USERNAME=admin
AUTH_PASSWORD_HASH=...

VT_ENABLED=true
VT_API_KEY=...
VT_BASE_URL=https://www.virustotal.com/api/v3
VT_PUBLIC_MODE=true
VT_CACHE_TTL_HOURS=24
VT_MIN_INTERVAL_SECONDS=15
VT_DAILY_BUDGET=500

ATTACHMENT_SANDBOX_BASE_URL=http://127.0.0.1:8000
```

## 主要页面

- `/app/upload` 邮件上传分析
- `/app/url-risk` URL 风险分析
- `/app/history` 邮件分析历史
- `/app/static-sandbox` 静态沙箱上传扫描
- `/app/static-rules` 静态沙箱规则管理

## 主要接口

- `POST /api/v1/analyses` 创建邮件分析任务
- `GET /api/v1/jobs/{job_id}` 查看任务进度
- `GET /api/v1/analyses/{analysis_id}` 查看邮件分析详情
- `POST /api/v1/url-checks` 创建独立 URL 风险分析
- `GET /api/v1/url-checks` 查看 URL 历史
- `GET /api/v1/url-checks/{id}` 查看 URL 详情

## 测试

后端：

```bash
./.py311/bin/pytest backend/tests -q
```

前端：

```bash
cd frontend
npm run build
```

## 说明

- `VT URL` 明确高危时，决策层会直接短路为恶意
- URL 页面只开放前端入口，不在前端暴露 VT API Key
- 当前仓库仍保留部分旧工作流节点与历史文档，未全部清理；已经脱离主链的前端遗留页面已删除
