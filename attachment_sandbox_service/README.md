# Attachment Analysis Sandbox

静态邮件附件分析服务。

它不负责解析 `eml`，只接收上游传来的附件字节流或对象引用，输出统一的 JSON 结果：

- `allow`
- `quarantine`
- `block`
- `error`

当前实现重点覆盖邮件里常见的附件类型：

- `Office`
- `PDF`
- `Archive`
- `Script`
- `PE / EXE`
- `LNK`

## Current Capabilities

- 附件分析 API：提交附件并查询作业结果
- 真实 YARA 编译链：支持 `.yar` 和 `.yara`
- 静态结构解析：Office / PDF / Archive / Script / PE / LNK
- 规则管理 API：列出、查看、新建、修改、删除规则
- Web demo：同时展示分析结果和规则管理能力
- 异步 worker 架构：API 与分析执行解耦
- 结果缓存：按 `sha256 + analysis_version` 复用

## Architecture

- API: FastAPI
- Queue: Redis in demo, in-memory in tests
- Database: PostgreSQL in demo, SQLite in tests
- Object store: filesystem, SHA-256 dedupe
- Worker: standalone process or embedded worker
- Detection:
  - YARA
  - static parsers
  - policy scoring

主链路代码：

- API: [app/api.py](/Users/qwx/dev/code/PEA_Agent/attachment_sandbox_service/app/api.py)
- Service: [app/service.py](/Users/qwx/dev/code/PEA_Agent/attachment_sandbox_service/app/service.py)
- Static scan engine: [app/static_scan/engine.py](/Users/qwx/dev/code/PEA_Agent/attachment_sandbox_service/app/static_scan/engine.py)
- Policy: [app/policy.py](/Users/qwx/dev/code/PEA_Agent/attachment_sandbox_service/app/policy.py)
- Rule loading: [app/rules.py](/Users/qwx/dev/code/PEA_Agent/attachment_sandbox_service/app/rules.py)
- Rule admin: [app/rule_admin.py](/Users/qwx/dev/code/PEA_Agent/attachment_sandbox_service/app/rule_admin.py)

## Rule Layout

规则目录在 [rules/yara](/Users/qwx/dev/code/PEA_Agent/attachment_sandbox_service/rules/yara)。

分三类：

- `builtin`: 项目内置规则，例如 `00_generic.yar`
- `external`: vendored 外部规则，只读
- `local`: 你自己新增的规则，允许 CRUD

当前外部规则基线：

- `ReversingLabs` 作为高置信恶意家族库
- `Yara-Rules maldocs` 作为 Office / RTF exploit 补充

规则版本和哈希元数据在 [rules/manifest.json](/Users/qwx/dev/code/PEA_Agent/attachment_sandbox_service/rules/manifest.json)。

## Run Locally

安装依赖：

```bash
pip install -r requirements.txt
```

启动本地服务：

```bash
uvicorn app.main:app --reload
```

默认行为：

- SQLite 数据库
- 本地文件对象存储 `.sandbox-data/objects`
- 内嵌 worker

## Run Demo Stack

启动 demo：

```bash
docker compose up -d --build
```

访问：

- Web demo: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Health: [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz)

运行演示提交脚本：

```bash
python3 scripts/demo_submit.py
```

停止：

```bash
docker compose down
```

## API

### Analysis

`POST /analysis/jobs`

- `multipart/form-data`
  - `file`
  - `source_id`
  - optional: `filename`, `declared_mime`, `content_sha256`
- `application/json`
  - `filename`
  - `source_id`
  - optional: `declared_mime`, `content_sha256`
  - one of:
    - `content_base64`
    - `object_ref`

`GET /analysis/jobs/{job_id}`

返回：

- `status`
- `verdict`
- `risk_score`
- `reasons`
- `normalized_type`
- `artifacts`
- `rule_version`
- `sample_sha256`
- `source_id`

### Rule Management

`GET /rules`

- 列出所有规则

`GET /rules/{rule_path}`

- 查看单条规则内容

`POST /rules`

- 新建规则

`PUT /rules/{rule_path}`

- 更新规则

`DELETE /rules/{rule_path}`

- 删除规则

规则管理约束：

- `external/*` 只读，不允许修改
- `local/*` 建议作为自定义规则目录
- 保存或删除规则时会自动重编译
- 编译失败会回滚文件改动

## Example

提交附件：

```bash
curl -X POST http://127.0.0.1:8000/analysis/jobs \
  -F source_id=mail-gateway \
  -F file=@/path/to/sample.pdf
```

列出规则：

```bash
curl http://127.0.0.1:8000/rules
```

新建一条本地规则：

```bash
curl -X POST http://127.0.0.1:8000/rules \
  -H 'content-type: application/json' \
  -d '{
    "path": "local/demo_rule.yar",
    "content": "rule LOCAL_Demo { meta: reason = \"KNOWN_MALWARE_SIGNATURE\" score = 100 source = \"local-yara\" condition: true }"
  }'
```

## Testing

运行测试：

```bash
pytest -q
```

当前测试覆盖：

- 分析 API
- 缓存行为
- YARA 重新编译
- 外部规则命中映射
- Web demo 页面可访问
- 规则 CRUD 与回滚

## Notes

- 当前是静态分析沙箱，不做动态执行
- 结果采用 fail-closed 思路，不确定样本优先 `quarantine`
- 真正生产上线前，仍建议补充白样本回归、鉴权、限流和监控
