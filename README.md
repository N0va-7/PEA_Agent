# 钓鱼邮件智能检测系统

基于 LangGraph 构建的智能邮件安全分析系统，集成机器学习模型、威胁情报API和大语言模型，实现多维度钓鱼邮件检测。

## 项目概览

本系统采用 **LangGraph 状态机编排**，通过条件路由实现灵活的分析流程。系统会根据邮件特征（是否包含附件、正文、URL）动态调整分析路径，最终生成综合安全报告。

### 核心特性

- 🎯 **智能路由**: 基于邮件内容动态选择分析路径
- 🔍 **多维检测**: 附件沙箱分析 + URL信誉检测 + 正文内容分析
- 🤖 **AI驱动**: 使用LLM提取URL并生成专业安全报告
- 📊 **实时可视化**: Streamlit Web界面实时展示分析过程
- 🧠 **智能决策**: 动态权重融合多个检测信号

## 系统架构

### Agent工作流 (LangGraph State Machine)

```
                    ┌─────────────────┐
                    │  parse_eml_file │  解析.eml文件
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  extract_urls   │  LLM提取URL
                    └────────┬────────┘
                             │
                    ┌────────▼────────────────────────┐
                    │   条件路由 (route_after_parse)  │
                    └──┬──────────┬──────────────┬────┘
                       │          │              │
            有附件?    │          │ 有正文?      │ 都没有?
                       │          │              │
            ┌──────────▼─┐    ┌───▼──────┐      │
            │ attachment │    │   body   │      │
            │ _reputation│    │_reputation│      │
            └──────┬─────┘    └────┬─────┘      │
                   │               │             │
           恶意? ┌─▼──┐   有URL? ┌─▼──┐         │
                 │skip│           │ url│         │
                 └─┬──┘           │_rep│         │
                   │              └──┬─┘         │
                   │                 │           │
                   └────────┬────────┴───────────┘
                            │
                   ┌────────▼────────┐
                   │ analyze_email   │  综合决策
                   │     _data       │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │   llm_report    │  生成报告
                   └────────┬────────┘
                            │
                          [END]
```

### 条件路由逻辑

系统的智能路由在 `agent/edges/edges.py` 中实现：

1. **parse_eml 后**:
   - 有附件 → 附件分析
   - 无附件但有正文 → 正文分析
   - 都没有 → 直接决策

2. **attachment 分析后**:
   - 恶意 → 直接决策（短路优化）
   - 安全且有正文 → 正文分析
   - 安全且无正文 → 直接决策

3. **body 分析后**:
   - 有URL → URL分析
   - 无URL → 直接决策

4. **url 分析后**:
   - 总是进入综合决策

## 技术栈

### 核心框架
- **LangGraph**: 状态机编排引擎
- **LangChain**: LLM集成框架
- **Streamlit**: Web可视化界面

### 机器学习
- **scikit-learn**: 模型训练与推理
- **joblib**: 模型序列化

### 外部服务
- **ThreatBook API**: 微步在线沙箱分析
- **OpenAI-compatible API**: LLM服务（支持任何兼容接口）

## 快速开始

### 1. 环境配置

```bash
# 复制环境变量模板
cp agent/.env.example agent/.env
```

编辑 `agent/.env` 文件，配置必需的API密钥：

```bash
# LLM配置 (支持OpenAI兼容的API)
LLM_API_KEY="your-api-key"
LLM_BASE_URL="https://api.siliconflow.cn/v1"
LLM_MODEL_ID="Qwen/Qwen3-32B"

# 微步在线API (用于附件沙箱分析)
THREATBOOK_API_KEY="your-threatbook-key"
```

### 2. 安装依赖

```bash
pip install langgraph langchain langchain-openai streamlit scikit-learn joblib python-dotenv requests
```

### 3. 运行方式

#### 方式一：命令行测试

```bash
cd agent
python main.py
```

此方式会分析 `./test/test.eml` 文件，并在终端输出详细的执行日志。

#### 方式二：Web界面 (推荐)

```bash
cd agent
streamlit run app.py
```

访问 `http://localhost:8501`，通过可视化界面上传邮件并实时查看分析过程。

## 项目结构

```
phishing/
├── agent/                      # Agent主目录
│   ├── state/
│   │   └── state.py           # 状态定义 (EmailAnalysisState)
│   ├── nodes/                 # 工作流节点
│   │   ├── parse_eml.py       # 解析.eml文件
│   │   ├── extract_urls.py    # LLM提取URL
│   │   ├── attachment_reputation.py  # 附件威胁分析
│   │   ├── body_reputation.py # 正文钓鱼检测
│   │   ├── url_reputation.py  # URL信誉检测
│   │   ├── analysis.py        # 综合决策逻辑
│   │   ├── llm_report.py      # 生成安全报告
│   │   └── sanitize.py        # 数据类型清理
│   ├── edges/
│   │   └── edges.py           # 条件路由函数
│   ├── models/
│   │   ├── ollama_llm.py      # LLM实例化
│   │   ├── phishing_url.pkl   # URL分类模型
│   │   └── phishing_body.pkl  # 正文分类模型
│   ├── uploads/               # 附件临时存储
│   ├── reports/               # 生成的分析报告
│   ├── main.py                # 工作流定义入口
│   ├── app.py                 # Streamlit Web应用
│   └── .env.example           # 环境变量模板
└── training/                  # 模型训练 (独立模块)
```

## 核心组件详解

### 1. 状态管理 (`state/state.py`)

使用 TypedDict 定义整个工作流的共享状态：

```python
class EmailAnalysisState(TypedDict):
    # 输入
    raw_eml_content: Optional[bytes]

    # 解析结果
    sender: str
    recipient: str
    subject: str
    body: str
    urls: List[str]
    attachments: List[Dict[str, Any]]

    # 分析结果
    url_analysis: Optional[Dict[str, Any]]
    body_analysis: Optional[Dict[str, Any]]
    attachment_analysis: Optional[Dict[str, Any]]

    # 最终输出
    final_decision: Optional[Dict[str, Any]]
    llm_report: Optional[str]

    # 执行追踪
    execution_trace: List[str]
```

### 2. 工作流节点设计

每个节点都是一个纯函数，遵循统一接口：

```python
def node_function(state: EmailAnalysisState) -> Dict[str, Any]:
    # 1. 从状态中读取所需数据
    # 2. 执行分析逻辑
    # 3. 返回部分状态更新 (partial update)
    return {
        "field_to_update": new_value,
        "execution_trace": state["execution_trace"] + ["node_name"]
    }
```

#### 关键节点说明

**parse_eml_file** (`nodes/parse_eml.py`)
- 解析EML文件格式
- 提取发件人、收件人、主题、正文
- 保存附件到 `./uploads/` 目录
- 返回基础元数据

**extract_urls** (`nodes/extract_urls.py`)
- 使用LLM智能提取正文中的URL
- 处理HTML链接（提取href属性）
- 自动去重和清理（移除http/https前缀）
- 避免误提取示例URL

**attachment_reputation** (`nodes/attachment_reputation.py`)
- 调用ThreatBook API上传附件
- 等待沙箱分析完成
- 解析威胁等级：malicious/suspicious/clean/unknown
- 将 malicious/suspicious 标记为 bad

**body_reputation** (`nodes/body_reputation.py`)
- 加载Random Forest模型 (`phishing_body.pkl`)
- 对正文进行TF-IDF特征提取
- 返回钓鱼概率和正常概率
- 特殊逻辑：无URL时提高阈值（降低误报）

**url_reputation** (`nodes/url_reputation.py`)
- 加载Logistic Regression模型 (`phishing_url.pkl`)
- 对每个URL提取特征并预测
- 计算最大恶意概率（取所有URL中最危险的）

**analysis** (`nodes/analysis.py`)
- 综合所有分析结果
- 动态权重计算（基于置信度）
- 分层决策逻辑：
  1. 附件恶意 → 直接判定为恶意
  2. URL + 正文都存在 → 加权融合
  3. 仅有单一信号 → 使用更高阈值

**llm_report** (`nodes/llm_report.py`)
- 使用LLM生成中文安全报告
- 结构化Markdown输出
- 包含：基本信息、判定结果、威胁详情、安全建议
- 保存到 `./reports/email_report.md`

### 3. 条件路由 (`edges/edges.py`)

LangGraph的核心能力 - 根据状态动态决定下一步：

```python
def route_after_parse_eml(state: EmailAnalysisState) -> str:
    if state["attachments"]:
        return "analyze_attachment_reputation"
    elif state["body"]:
        return "analyze_body_reputation"
    else:
        return "analyze_email_data"
```

### 4. 综合决策算法 (`analysis.py`)

系统使用动态权重融合多个信号：

```python
# 置信度因子
c_u = abs(url_prob - 0.5) + 0.5   # URL置信度
c_t = abs(text_prob - 0.5) + 0.5  # 正文置信度

# 动态权重 (基础权重 × 置信度)
w_u = (0.6 * c_u) / (0.6 * c_u + 0.4 * c_t)
w_t = 1 - w_u

# 最终得分
final_prob = w_u * url_prob + w_t * text_prob
```

**设计理念**：
- URL检测基础权重更高（0.6 vs 0.4）
- 置信度越高的信号权重越大
- 概率接近0.5时置信度低，远离0.5时置信度高

### 5. LangGraph工作流构建 (`main.py`)

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

# 1. 创建状态图
workflow = StateGraph(EmailAnalysisState)

# 2. 添加节点
workflow.add_node("parse_eml_file", parse_eml_file)
workflow.add_node("extract_urls", extract_urls)
# ... 其他节点

# 3. 添加边（静态路由）
workflow.add_edge(START, "parse_eml_file")
workflow.add_edge("parse_eml_file", "extract_urls")

# 4. 添加条件边（动态路由）
workflow.add_conditional_edges(
    "extract_urls",
    route_after_parse_eml,  # 路由函数
    {
        "analyze_attachment_reputation": "analyze_attachment_reputation",
        "analyze_body_reputation": "analyze_body_reputation",
        "analyze_email_data": "analyze_email_data"
    }
)

# 5. 编译（启用状态持久化）
memory = InMemorySaver()
app = workflow.compile(checkpointer=memory)

# 6. 运行
initial_state = {"raw_eml_content": eml_bytes, ...}
config = {"configurable": {"thread_id": "session-1"}}
async for output in app.astream(initial_state, config=config):
    # 处理每个节点的输出
    pass
```

### 6. Streamlit实时可视化 (`app.py`)

关键特性：
- **异步流式执行**: 使用 `asyncio.run()` 包装LangGraph
- **实时UI更新**: 通过 `st.empty()` 占位符动态刷新
- **分层展示**:
  - 指标卡片：附件威胁度、正文概率、URL概率
  - 执行日志：实时显示Agent思考过程
  - 最终报告：Markdown格式的专业报告

```python
# 创建占位符
metric = st.empty()
log_area = st.empty()
report_container = st.empty()

# 流式更新
async for output in app.astream(initial_state, config):
    for node_name, state_update in output.items():
        # 更新日志
        logs.append(f"✅ 完成节点: {node_name}")
        log_area.code("\n".join(logs))

        # 更新指标
        if node_name == "analyze_url_reputation":
            prob = state_update["url_analysis"]["max_possibility"]
            metric.metric("URL钓鱼概率", f"{prob*100:.1f}%")
```

## 使用示例

### 完整分析流程

```python
import asyncio
from main import create_email_analysis_workflow

async def analyze_email():
    # 1. 创建工作流
    app = create_email_analysis_workflow()

    # 2. 读取邮件
    with open("suspicious_email.eml", "rb") as f:
        eml_content = f.read()

    # 3. 初始化状态
    initial_state = {
        "raw_eml_content": eml_content,
        "sender": "",
        "recipient": "",
        "subject": "",
        "body": "",
        "url_analysis": {},
        "body_analysis": {},
        "attachment_analysis": {},
        "final_decision": {},
        "execution_trace": []
    }

    # 4. 运行分析
    config = {"configurable": {"thread_id": "analysis-1"}}
    async for output in app.astream(initial_state, config=config):
        for node_name, node_output in output.items():
            print(f"节点: {node_name}")
            if node_name == "llm_report":
                print(node_output["llm_report"])

asyncio.run(analyze_email())
```

### 输出示例

**终端日志**:
```
节点: parse_eml_file
发现附件: invoice.pdf
附件数量: 1

节点: extract_urls
→ 提取到 2 个 URL
去重后 URL: ['paypal-verify.com/login', 'bit.ly/xxxxx']

节点: analyze_attachment_reputation
提交附件: invoice.pdf
成功获取报告，解析结果
附件报告: {'threat_level': 'unknown', 'multi_engines': '0/28'}

节点: analyze_body_reputation
正文分析结果: {'phishing_probability': 0.72}

节点: analyze_url_reputation
URL分析结果: {'phishing_probability': 0.89}
最大恶意可能性: 0.89

节点: analyze_email_data
综合评分: 0.83
最终判定: 正文和URL综合评分较高，判定为恶意

节点: llm_report
报告生成完成
```

**生成的报告** (`reports/email_report.md`):
```markdown
## 邮件基本信息
- **主题**: 您的账户需要验证
- **发件人**: support@paypal.com
- **收件人**: victim@example.com

## 综合判定结果
- **是否恶意**: 是
- **置信度**: 高
- **判定依据**: URL信誉检测发现高风险钓鱼链接，正文包含诱导性话术

## 威胁详情分析
### 正文分析
- 钓鱼概率: 72%
- 风险描述: 包含诱导点击链接的紧急性话术

### 链接分析
- 检测链接: paypal-verify.com/login, bit.ly/xxxxx
- 风险等级: 恶意
- 分析说明: 第一个URL为已知钓鱼域名，短链接指向可疑站点

### 附件分析
- 附件名称: invoice.pdf
- 威胁等级: 未知
- 检测结果: 0/28 引擎报警，沙箱未发现明显异常

## 安全建议
- 请勿点击邮件中的任何链接
- 删除此邮件并标记为钓鱼邮件
- 如已点击链接，建议立即修改账户密码并启用双因素认证
```

## 关键设计模式

### 1. 纯函数节点

所有节点都是无副作用的纯函数（除了I/O操作），确保：
- 可测试性
- 可重放性（配合checkpointer）
- 状态可追溯

### 2. 部分状态更新

节点只返回需要修改的字段，LangGraph自动合并：

```python
# 节点只返回变化的字段
return {
    "url_analysis": {...},
    "execution_trace": state["execution_trace"] + ["url_reputation"]
}
# LangGraph自动合并到完整状态
```

### 3. 短路优化

发现明确恶意信号时立即决策，避免不必要的计算：

```python
if attachment_is_malicious:
    return "analyze_email_data"  # 跳过后续分析
```

### 4. 动态权重

根据模型置信度动态调整各信号的权重，而非固定加权。

### 5. 懒加载模型

模型在节点函数内加载，而非模块级别：

```python
def analyze_url_reputation(state):
    # 在函数内加载，避免序列化问题
    phish_model = open('./models/phishing_url.pkl', 'rb')
    model = joblib.load(phish_model)
    ...
```

## 常见问题

### Q: 为什么使用LangGraph而不是普通的if-else?

A: LangGraph提供：
1. **状态持久化**: 支持中断恢复、人机协作
2. **可视化**: 可生成工作流图便于理解
3. **流式输出**: 实时获取每个节点的结果
4. **并行执行**: 未来可轻松实现节点并行（如同时分析URL和正文）

### Q: execution_trace的作用是什么?

A: 用于追踪工作流的实际执行路径，便于调试和审计：
```python
['parse_eml', 'extract_urls', 'analyze_attachment_reputation',
 'analyze_body_reputation', 'analyze_url_reputation', 'analyze_email_data', 'llm_report']
```

### Q: 如何自定义决策逻辑?

A: 修改 `agent/nodes/analysis.py` 中的权重和阈值：
```python
# 调整基础权重
w_u_base = 0.7  # 提高URL权重
w_t_base = 0.3  # 降低正文权重

# 调整阈值
if phishing_score > 0.6:  # 原来是0.5
    final_decision["is_malicious"] = True
```

### Q: 如何添加新的检测维度?

1. 在 `state.py` 中添加新字段
2. 在 `nodes/` 中创建新节点
3. 在 `main.py` 中注册节点并添加边
4. 在 `edges.py` 中更新路由逻辑（如需要）
5. 在 `analysis.py` 中整合新信号

### Q: 模型如何更新?

1. 重新训练模型（在 `training/` 目录）
2. 使用 `pickle.dump()` 或 `joblib.dump()` 保存
3. 复制到 `agent/models/` 目录
4. 节点会自动加载新模型

## 扩展建议

### 1. 增加SMTP/DKIM验证
在 `parse_eml.py` 中添加邮件头真实性验证。

### 2. 实现节点并行
修改工作流，同时执行独立的分析节点：
```python
workflow.add_edge("extract_urls", "analyze_attachment_reputation")
workflow.add_edge("extract_urls", "analyze_body_reputation")
workflow.add_edge("extract_urls", "analyze_url_reputation")
```

### 3. 添加人机协作
使用LangGraph的中断机制，在高置信度时自动处理，低置信度时请求人工审核。

### 4. 集成更多威胁情报
- VirusTotal API
- URLScan.io
- Google Safe Browsing

### 5. 实现反馈学习
收集误报/漏报案例，定期重训练模型。

## 许可证

本项目仅供学习研究使用。

## 贡献

欢迎提交Issue和Pull Request！

---

**技术支持**: 如有问题请查看 `CLAUDE.md` 文件获取更多技术细节。
