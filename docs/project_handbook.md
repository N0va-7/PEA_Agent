# PEA Agent 技术主文档

这份文档只回答一个目标：
把项目现在“真实在跑什么、怎么跑、怎么调”的事实讲清楚。

## 1. 一分钟结论

1. 主流程：`上传邮件 -> 异步任务 -> 多节点分析 -> 融合判定 -> 中文报告 -> 人工反馈 -> 手动调参激活`。
2. 线上判定不是只靠 LLM，LLM 主要负责把结果写成结构化中文报告。
3. 模型层分两块：
   - 基础模型：正文概率、URL 概率。
   - 融合策略：按权重和阈值做最终判定。
4. 人工反馈不会自动触发模型重训；它用于融合调参数据集。
5. 系统支持 MySQL/SQLite 与 Redis/memory 两套运行方式。

## 2. 你最关心的三个问题

### 2.1 `retrain_models.py` 到底有没有在线上自动跑？

没有。

- 后端路由和工作流没有调用它。
- 它是手动离线脚本，用于重训并导出新的 `.pkl`。

### 2.2 当前“打标后会触发什么”？

打标后会更新 `email_analyses` 的反馈字段，并写一条审计事件。

只有你在前端点击“运行调参”时，才会：

1. 读取已打标样本。
2. 生成 `url_prob,text_prob,label` 数据。
3. 网格搜索融合参数。
4. 产出一个调参版本。

### 2.3 当前线上基础模型是哪套算法？

按当前仓库中的产物文件实际加载结果：

1. `phishing_body.pkl`：`TfidfVectorizer + RandomForestClassifier`
2. `phishing_url.pkl`：`CountVectorizer + LogisticRegression`

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
4. 决策节点：`/Users/qwx/dev/code/PEA_Agent/backend/workflow/nodes/analysis.py`
5. 报告节点：`/Users/qwx/dev/code/PEA_Agent/backend/workflow/nodes/llm_report.py`
6. 分析与反馈 API：`/Users/qwx/dev/code/PEA_Agent/backend/api/routes/analyses.py`
7. 调参 API：`/Users/qwx/dev/code/PEA_Agent/backend/api/routes/tuning.py`
8. 系统运行信息 API：`/Users/qwx/dev/code/PEA_Agent/backend/api/routes/system.py`

## 5. 建议阅读顺序

1. 先读 `00` 和 `01`，知道边界和架构。
2. 再读 `02` 和 `03`，理解判定与调参。
3. 最后读 `04` 和 `05`，掌握数据、接口、部署。
