# PEA Agent

PEA Agent 是一个面向邮件、URL 和附件的安全分析控制台。

当前系统由 3 部分组成：

1. 主后端：邮件分析、URL 风险分析、历史与报告
2. 前端控制台：邮件上传、URL 风险、历史、静态沙箱、规则管理
3. 独立附件静态沙箱：`attachment_sandbox_service`

## 核心能力

1. 邮件 `.eml` 上传分析
2. 独立 URL 风险分析
3. VirusTotal URL 信誉查询
4. URL 传统模型评分
5. LLM 内容复核
6. 附件静态沙箱分析
7. 历史记录、反馈审计、规则管理
8. Markdown 报告输出

## 结果复用

系统会优先复用已有记录，避免重复分析：

1. 邮件分析：按 `fingerprint` 命中历史邮件结果
2. URL 分析：按归一化 URL 命中 `url_analyses`
3. VT 查询：按归一化 URL 命中 `vt_url_cache`
4. 附件分析：按样本 `SHA256` 命中静态沙箱缓存

## 目录结构

```text
backend/                     主后端
frontend/                    Vue 3 控制台
attachment_sandbox_service/  独立附件静态沙箱
docs/                        项目文档与毕设材料说明
output/jupyter-notebook/     URL 模型 notebook 与图表
```

## 快速启动

### 1. 启动 MySQL 和 Redis

```bash
docker compose up -d mysql redis
```

### 2. 启动主后端

```bash
cp backend/.env.example backend/.env
./.py311/bin/alembic -c backend/alembic.ini upgrade head
./.py311/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8010
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### 4. 启动附件静态沙箱

```bash
cd attachment_sandbox_service
docker compose up -d postgres redis api worker
```

## 主要页面

1. `/app/upload` 邮件上传分析
2. `/app/url-risk` URL 风险分析
3. `/app/history` 邮件分析历史
4. `/app/static-sandbox` 静态沙箱上传扫描
5. `/app/static-rules` 静态沙箱规则管理

## 文档入口

如果你要用于毕设或答辩，直接从这里开始：

1. [docs/README.md](./docs/README.md)
2. [docs/08_thesis_submission_package.md](./docs/08_thesis_submission_package.md)

## URL 模型论文材料

配套 notebook：

1. `output/jupyter-notebook/url-model-training-walkthrough.ipynb`

已导出图表：

1. `dataset-label-distribution.png`
2. `model-metric-comparison.png`
3. `roc-curves.png`
4. `best-model-confusion-matrix.png`
5. `feature-weight-bar-charts.png`
6. `ngram-wordclouds.png`

说明：

1. notebook 已预执行
2. 每个 code cell 前都带讲解
3. 每张关键图后都带图表解读

## 当前实现边界

1. 系统只保留 URL 传统模型，不再保留正文模型
2. 外部情报只保留 VT URL reputation
3. VT URL 明确高危时，决策层会直接短路为恶意
