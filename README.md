# PEA Agent (Vue + FastAPI)

PEA Agent 现已重构为前后端分离架构：
- 前端：Vue 3 + Vite
- 后端：FastAPI + SQLAlchemy + Alembic
- 工作流：邮件分析图（保留原子图决策逻辑）

## 1. 目录结构（当前）

```text
PEA_Agent/
├── backend/                 # FastAPI 服务、工作流、仓储、迁移、测试
├── frontend/                # Vue 前端
├── runtime/                 # 运行期数据（不入库）
│   ├── db/
│   ├── reports/
│   └── uploads/
├── ml/                      # 模型与训练数据
│   ├── artifacts/           # 线上推理使用的 .pkl
│   └── training/            # 训练数据与 notebook
├── legacy/
│   └── agent_archive/       # 旧 Streamlit/Agent 归档（不再作为主运行路径）
└── docs/
```

## 2. 后端环境变量

先复制：

```bash
cp backend/.env.example backend/.env
```

`backend/.env` 关键项：

```env
# Storage
DATABASE_URL=""
SQLITE_DB_PATH="/Users/qwx/dev/code/PEA_Agent/runtime/db/analysis.db"
REPORT_OUTPUT_DIR="/Users/qwx/dev/code/PEA_Agent/runtime/reports"
UPLOAD_DIR="/Users/qwx/dev/code/PEA_Agent/runtime/uploads"
MODEL_DIR="/Users/qwx/dev/code/PEA_Agent/ml/artifacts"
UPLOAD_RETENTION_HOURS="72"

# Auth / JWT
AUTH_USERNAME="admin"
AUTH_PASSWORD_HASH="<sha256(password) or pbkdf2_sha256$...>"
JWT_SECRET_KEY="<strong-random-secret>"
JWT_ALGORITHM="HS256"
JWT_EXPIRE_HOURS="8"
LOGIN_RATE_MAX_ATTEMPTS="10"
LOGIN_RATE_WINDOW_SECONDS="300"
EXPOSE_INTERNAL_ERROR_DETAILS="false"

# LLM
LLM_API_KEY=""
LLM_BASE_URL="https://api.openai.com/v1"
LLM_MODEL_ID="gpt-4o-mini"

# Threat Intel
THREATBOOK_API_KEY=""

# CORS
CORS_ALLOW_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"

# Queue (optional redis persistence)
JOB_QUEUE_BACKEND="memory"
REDIS_URL="redis://127.0.0.1:6379/0"
REDIS_QUEUE_NAME="pea:jobs"
```

## 3. 启动方式（唯一推荐）

### 3.1 启动后端

```bash
# 可选：准备 py3.11 环境
./backend/scripts/bootstrap_py311.sh

# 启动服务
/Users/qwx/dev/code/PEA_Agent/.py311/bin/uvicorn backend.main:app --reload
```

迁移数据库（可选，首次建议执行）：

```bash
/Users/qwx/dev/code/PEA_Agent/.py311/bin/alembic -c backend/alembic.ini upgrade head
```

如需切换 MySQL（示例）：

```env
DATABASE_URL="mysql+pymysql://user:pass@127.0.0.1:3306/pea_agent?charset=utf8mb4"
```

如需启用 Redis 持久化队列（示例）：

```env
JOB_QUEUE_BACKEND="redis"
REDIS_URL="redis://127.0.0.1:6379/0"
REDIS_QUEUE_NAME="pea:jobs"
```

### 3.2 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：`http://127.0.0.1:5173`

## 4. 测试

### 4.1 后端测试

```bash
/Users/qwx/dev/code/PEA_Agent/.py311/bin/python -m pytest backend/tests -q
```

### 4.2 前端测试

```bash
cd frontend
npm run test:unit
npm run build
# 如需 E2E
npm run test:e2e
```

## 5. API 概览

- `POST /api/v1/auth/login`
- `POST /api/v1/analyses`（入队）
- `GET /api/v1/jobs/{job_id}`（轮询任务状态）
- `GET /api/v1/analyses`
- `GET /api/v1/analyses/{analysis_id}`
- `GET /api/v1/reports/{analysis_id}`

## 6. 模型重训（可复现）

一键重训正文/URL模型并覆盖线上推理产物：

```bash
/Users/qwx/dev/code/PEA_Agent/.py311/bin/python /Users/qwx/dev/code/PEA_Agent/ml/training/retrain_models.py
```

重训后会输出：
- `ml/artifacts/phishing_body.pkl`
- `ml/artifacts/phishing_url.pkl`
- `ml/artifacts/retrain_report_*.json`

若要搜索最优融合权重与阈值（需邮件级标注集）：

```bash
/Users/qwx/dev/code/PEA_Agent/.py311/bin/python /Users/qwx/dev/code/PEA_Agent/ml/training/tune_fusion_threshold.py \
  --csv /path/to/labeled_email_level_scores.csv \
  --fpr-target 0.03 \
  --output-json /tmp/fusion_tuning.json
```

原理说明见：`docs/model_training_handbook.md`

## 7. 运行时产物说明

- 数据库：`runtime/db/analysis.db`
- 报告文件：`runtime/reports/report_{analysis_id}_{YYYYMMDD_HHMMSS}.md`
- 上传文件：`runtime/uploads/`

以上目录只保留 `.gitkeep`，业务运行文件不会提交到 Git。

## 8. 旧版本说明

`legacy/agent_archive` 保留旧版 Streamlit/Agent 代码仅作对照，不再作为主流程的一部分。
