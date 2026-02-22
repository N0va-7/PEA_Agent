# PEA Agent

PEA Agent 是一个面向 `.eml` 邮件的钓鱼分析系统。

它做 6 件事：

1. 上传邮件并异步分析。
2. 解析正文、链接、附件。
3. 输出最终恶意/正常判定分数。
4. 生成固定结构的中文 Markdown 报告。
5. 允许人工打标（`malicious` / `benign`）。
6. 基于已打标样本手动运行融合调参，并手动激活新版本。

## 先看这个（避免误解）

1. 当前系统里的“调参”是融合层参数调优，不是自动重训基础模型。
2. `ml/training/retrain_models.py` 是离线重训脚本，不会被后端自动调用。
3. 当前线上推理直接读取 `ml/artifacts/phishing_body.pkl` 与 `ml/artifacts/phishing_url.pkl`。
4. 这两个现有产物实际是：
   - 正文：`TfidfVectorizer + RandomForestClassifier`
   - URL：`CountVectorizer + LogisticRegression`
5. 生产部署推荐 `MySQL + Redis`；开发可用 `SQLite + memory queue`。

## 快速启动

```bash
./backend/scripts/bootstrap_py311.sh
cp backend/.env.example backend/.env
./.py311/bin/alembic -c backend/alembic.ini upgrade head
./.py311/bin/uvicorn backend.main:app --reload

cd frontend
npm install
npm run dev
```

## 文档入口

1. 主文档：`/Users/qwx/dev/code/PEA_Agent/docs/project_handbook.md`
2. 总览与范围：`/Users/qwx/dev/code/PEA_Agent/docs/handbook/00_overview_and_scope.md`
3. 系统架构：`/Users/qwx/dev/code/PEA_Agent/docs/handbook/01_system_architecture.md`
4. 工作流与决策：`/Users/qwx/dev/code/PEA_Agent/docs/handbook/02_workflow_and_decision_engine.md`
5. 模型训练与反馈调参：`/Users/qwx/dev/code/PEA_Agent/docs/handbook/03_model_training_and_feedback_tuning.md`
6. 数据表与 API：`/Users/qwx/dev/code/PEA_Agent/docs/handbook/04_data_schema_and_api_contract.md`
7. 部署、安全、运维：`/Users/qwx/dev/code/PEA_Agent/docs/handbook/05_deployment_security_observability.md`
8. 训练专题：`/Users/qwx/dev/code/PEA_Agent/docs/model_training_handbook.md`
9. 调参需求与执行约束：`/Users/qwx/dev/code/PEA_Agent/docs/feedback_tuning_requirements.md`

## 当前运行依赖的产物

1. `ml/artifacts/phishing_body.pkl`
2. `ml/artifacts/phishing_url.pkl`
3. `ml/artifacts/fusion_tuning*.json`（有激活版本时覆盖默认融合参数）

## 测试

后端：

```bash
./.py311/bin/python -m pytest backend/tests -q
```

前端：

```bash
cd frontend
npm run test:unit
npm run build
```
