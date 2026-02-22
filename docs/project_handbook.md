# PEA Agent 项目讲解主文档

## 1. 文档定位

本主文档用于统一讲清 PEA Agent 的技术实现。  
阅读目标是让读者快速回答这五个问题：

1. 项目解决什么问题，核心能力是什么。
2. 系统架构如何组织，哪些模块负责什么。
3. 模型除了基础训练，后续调参到底做了什么。
4. 数据与接口如何落地，如何支撑可追溯运营。
5. 生产环境为何建议 MySQL + Redis，以及如何稳定运行。

## 2. 当前项目结论（先看这个）

1. 当前项目主流程是：`EML上传 -> 异步分析 -> 融合判定 -> 中文报告 -> 人工反馈 -> 手动调参激活`。
2. 当前线上模型不是“持续微调大模型”，而是：
   - 正文模型与 URL 模型做固定推理。
   - 融合层参数（权重与阈值）通过反馈数据进行受控调优。
3. 当前部署建议是：
   - 生产：`MySQL + Redis`
   - 开发兼容：`SQLite + memory queue`

## 3. 阅读地图（主文档关联）

1. 项目总览与范围：`docs/handbook/00_overview_and_scope.md`
2. 系统架构与骨架：`docs/handbook/01_system_architecture.md`
3. 工作流与决策引擎：`docs/handbook/02_workflow_and_decision_engine.md`
4. 模型训练与反馈调参：`docs/handbook/03_model_training_and_feedback_tuning.md`
5. 数据模型与 API：`docs/handbook/04_data_schema_and_api_contract.md`
6. 部署、安全与运维：`docs/handbook/05_deployment_security_observability.md`

## 4. 关键源码定位

1. 启动与依赖装配：`backend/main.py`
2. 全局配置：`backend/infra/config.py`
3. 任务执行器：`backend/services/job_runner.py`
4. 业务编排服务：`backend/services/analysis_service.py`
5. 工作流图：`backend/workflow/graph.py`
6. 决策节点：`backend/workflow/nodes/analysis.py`
7. 报告节点：`backend/workflow/nodes/llm_report.py`
8. 调参 API：`backend/api/routes/tuning.py`
9. 反馈 API：`backend/api/routes/analyses.py`

## 5. 推荐阅读顺序

1. 先读 `00` 与 `01`，明确系统边界和架构分层。
2. 再读 `02` 与 `03`，理解“判定如何产生”和“参数如何更新”。
3. 最后读 `04` 与 `05`，掌握接口、表结构、部署与运维落地点。

