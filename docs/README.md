# PEA Agent 文档索引

这套文档按“毕设可提交材料”重组，只保留当前实现仍然有效的内容。

建议阅读顺序：

1. [01_system_overview.md](./01_system_overview.md)
2. [02_architecture_and_workflow.md](./02_architecture_and_workflow.md)
3. [03_database_and_reuse_strategy.md](./03_database_and_reuse_strategy.md)
4. [04_api_and_frontend_modules.md](./04_api_and_frontend_modules.md)
5. [05_model_and_experiment_guide.md](./05_model_and_experiment_guide.md)
6. [06_test_and_acceptance.md](./06_test_and_acceptance.md)
7. [07_deployment_and_operations.md](./07_deployment_and_operations.md)
8. [08_thesis_submission_package.md](./08_thesis_submission_package.md)

配套材料：

1. URL 模型 notebook：
   `output/jupyter-notebook/url-model-training-walkthrough.ipynb`
2. 论文图表导出目录：
   `output/jupyter-notebook/url-model-figures/`
3. 独立附件静态沙箱服务说明：
   `attachment_sandbox_service/README.md`

当前文档边界：

1. 当前系统只保留 URL 传统模型，不再保留正文模型。
2. 外部情报只保留 VirusTotal URL reputation。
3. 附件分析由独立服务 `attachment_sandbox_service` 提供。
