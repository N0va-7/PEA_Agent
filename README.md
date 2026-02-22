# PEA Agent

PEA Agent 是一个面向企业场景的钓鱼邮件分析系统，支持“检测 + 报告 + 人工反馈 + 手动调参”闭环。

## 快速开始

1. 安装后端依赖

```bash
./backend/scripts/bootstrap_py311.sh
```

2. 准备配置

```bash
cp backend/.env.example backend/.env
```

3. 启动后端

```bash
./.py311/bin/alembic -c backend/alembic.ini upgrade head
./.py311/bin/uvicorn backend.main:app --reload
```

4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

## 文档入口

1. 完整项目技术手册：`docs/project_technical_manual.md`
2. 模型训练方法：`docs/model_training_handbook.md`
3. 反馈调参需求与约束：`docs/feedback_tuning_requirements.md`
4. 毕设写作辅助文档：`docs/thesis_bootstrap_for_aiagent.md`

## 项目清理说明

当前仓库已清理与主流程无关的历史内容，仅保留“可运行 + 可训练 + 可调参”主线：

1. 已移除旧版归档目录 `legacy/agent_archive`。
2. 已移除未被代码引用的旧训练产物：
   - `ml/training/email_text/model/phishing_text_model.pkl`
   - `ml/training/email_url/model/phishing_url.pkl`
   - `ml/training/email_url/predict_app.py`
3. 已移除无业务价值的缓存/索引文件（如 `.DS_Store`）。
4. 已移除历史调参样本快照 CSV，调参数据改为按反馈动态生成。

当前线上实际依赖的模型与参数产物位于：

1. `ml/artifacts/phishing_body.pkl`
2. `ml/artifacts/phishing_url.pkl`
3. `ml/artifacts/fusion_tuning*.json`（可选，用于融合参数覆盖）

## 测试命令

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
