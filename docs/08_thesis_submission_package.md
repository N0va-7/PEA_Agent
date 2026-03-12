# 08. 毕设提交材料清单

## 1. 必交材料

建议最少准备以下 8 项：

1. 论文正文
2. 系统说明书
3. 数据库设计说明
4. 测试报告
5. 部署与运行说明
6. 项目源码
7. 系统运行截图
8. 算法实验图表

## 2. 本仓库对应材料来源

### 2.1 论文“系统概述”章节

使用：

1. `docs/01_system_overview.md`
2. `README.md`

### 2.2 论文“系统设计”章节

使用：

1. `docs/02_architecture_and_workflow.md`
2. `docs/04_api_and_frontend_modules.md`

### 2.3 论文“数据库设计”章节

使用：

1. `docs/03_database_and_reuse_strategy.md`
2. `backend/models/tables.py`

### 2.4 论文“算法与实验”章节

使用：

1. `docs/05_model_and_experiment_guide.md`
2. `output/jupyter-notebook/url-model-training-walkthrough.ipynb`
3. `output/jupyter-notebook/url-model-figures/`

### 2.5 论文“测试与验证”章节

使用：

1. `docs/06_test_and_acceptance.md`
2. 前后端运行截图
3. 典型样本分析结果截图

### 2.6 论文“系统部署”章节

使用：

1. `docs/07_deployment_and_operations.md`

## 3. 论文截图建议

建议至少准备这 6 张：

1. 邮件上传与任务阶段截图
2. 历史记录详情截图
3. URL 风险分析截图
4. 静态沙箱扫描截图
5. 规则管理截图
6. 系统整体控制台截图

## 4. 图表建议

推荐优先放这些图：

1. `dataset-label-distribution.png`
2. `model-metric-comparison.png`
3. `roc-curves.png`
4. `best-model-confusion-matrix.png`
5. `feature-weight-bar-charts.png`

`ngram-wordclouds.png` 适合作为辅助图，不建议单独承担核心结论。

## 5. 答辩时建议强调的点

1. 不是只做单点 URL 判断，而是多信号联合决策。
2. VT 和静态沙箱都做了历史复用，降低重复分析成本。
3. 前端控制台支持邮件、URL 和附件 3 种入口。
4. 输出不仅有分数，还有决策依据和结构化报告。
