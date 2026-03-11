# PEA Agent 技术主文档

这份文档只回答一个目标：
把项目现在“真实在跑什么、怎么跑、怎么调”的事实讲清楚。

## 1. 一分钟结论

1. 主流程：`上传邮件 -> 异步任务 -> URL 信誉 + URL 模型 + 内容复核 + 附件沙箱 -> 决策 -> 报告`。
2. 当前外部情报只保留 VirusTotal URL reputation。
3. 当前唯一保留的传统模型是 URL 模型；正文模型已经移除。
4. 附件样本和 URL 结果都支持数据库复用，不命中时才重新分析。
5. 仓库提供一份已预执行的 URL 模型讲解 notebook，可直接导出论文图表。
6. 当前默认运行栈是 MySQL + Redis。

## 2. 你最关心的三个问题

### 2.1 URL 模型会在线自动重训吗？

没有。

- 后端路由和工作流不会自动重训 URL 模型。
- 当前仓库保留现成的 `phishing_url.pkl` 产物和一份训练讲解 notebook。

### 2.2 当前“打标后会触发什么”？

打标后会更新 `email_analyses` 的反馈字段，并写一条审计事件。

只有你在前端点击“运行调参”时，才会：

1. 读取已打标样本。
2. 生成 `url_prob,text_prob,label` 数据。
3. 网格搜索融合参数。
4. 产出一个调参版本。

### 2.3 当前线上基础模型是哪套算法？

按当前仓库中的保留产物：

1. `phishing_url.pkl`：URL 字符级向量化 + 线性分类器

正文模型已经不再保留，也不再参与当前主流程。

### 2.4 如果要写论文，图表从哪里来？

直接看：

1. `output/jupyter-notebook/url-model-training-walkthrough.ipynb`
2. `output/jupyter-notebook/url-model-figures/`

当前 notebook 已经内嵌并导出这些图：

1. 标签分布图
2. 模型指标对比图
3. ROC 曲线
4. 混淆矩阵
5. 高权重特征条形图
6. 词云图（辅助图）

## 3. 文档地图

1. `/Users/qwx/dev/code/PEA_Agent/docs/handbook/00_overview_and_scope.md`
2. `/Users/qwx/dev/code/PEA_Agent/docs/handbook/01_system_architecture.md`
3. `/Users/qwx/dev/code/PEA_Agent/docs/handbook/02_workflow_and_decision_engine.md`
4. `/Users/qwx/dev/code/PEA_Agent/docs/handbook/03_model_training_and_feedback_tuning.md`
5. `/Users/qwx/dev/code/PEA_Agent/docs/handbook/04_data_schema_and_api_contract.md`
6. `/Users/qwx/dev/code/PEA_Agent/docs/handbook/05_deployment_security_observability.md`
7. `/Users/qwx/dev/code/PEA_Agent/docs/model_training_handbook.md`
8. `/Users/qwx/dev/code/PEA_Agent/docs/feedback_tuning_requirements.md`

## 4. 关键源码入口

1. 启动与依赖注入：`/Users/qwx/dev/code/PEA_Agent/backend/main.py`
2. 配置加载：`/Users/qwx/dev/code/PEA_Agent/backend/infra/config.py`
3. 工作流图：`/Users/qwx/dev/code/PEA_Agent/backend/workflow/graph.py`
4. 决策工具：`/Users/qwx/dev/code/PEA_Agent/backend/agent_tools/decision_engine.py`
5. 报告工具：`/Users/qwx/dev/code/PEA_Agent/backend/agent_tools/report_renderer.py`
6. 分析与反馈 API：`/Users/qwx/dev/code/PEA_Agent/backend/api/routes/analyses.py`
7. URL 风险 API：`/Users/qwx/dev/code/PEA_Agent/backend/api/routes/url_checks.py`
8. 系统运行信息 API：`/Users/qwx/dev/code/PEA_Agent/backend/api/routes/system.py`

## 5. 建议阅读顺序

1. 先读 `00` 和 `01`，知道边界和架构。
2. 再读 `02` 和 `03`，理解判定与调参。
3. 最后读 `04` 和 `05`，掌握数据、接口、部署。
