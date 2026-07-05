# Risk-HiMATE 改造实施说明

## 1. 目标

把当前仓库中的 `HiMATE-main` 从“机器翻译错误评估框架”改造成“科创企业特有风险识别智能体（Risk-HiMATE）”原型系统，并保留 HiMATE 的核心方法论：

1. 风险子领域专职 Agent 并行判断
2. 反思与修正降低遗漏和误判
3. 独立核验减少系统性幻觉
4. 最终加权汇总形成结构化风险报告

这次改造不是简单改 prompt，而是把任务对象、数据结构、输出协议、状态记录、评分逻辑、历史趋势全部替换为风险分析场景。

---

## 2. 先看当前仓库：HiMATE 真实结构

当前仓库核心是一个串行脚本式流水线，主入口在：

- `HiMATE-main/code/pipeline.py`

它的真实阶段是：

1. `s1_subtype_evaluation`
2. `s2_self_reflection_correction`
3. `s3_self_reflection_verification`
4. `s4_collaborative_discussion`
5. `score_computation.py`

它的特点：

1. 每次只跑一个 error subtype
2. 输入是 `source.txt` + `hyp.txt`
3. 输出以 JSON 日志拼接为主
4. 阈值、轮次、计分高度绑定 MT 场景
5. 不是 LangChain/LangGraph，而是手工组织 prompt + OpenAI 调用

因此，本项目的正确改法不是“在原目录里硬替换词汇”，而是：

1. 保留 HiMATE 的方法结构
2. 重建领域模型和数据协议
3. 把 orchestration 升级成更适合风险识别的模块化架构
4. 尽量兼容现有仓库，允许分阶段迁移

---

## 3. 改造原则

### 3.1 保留的东西

保留 HiMATE 的四个核心思想：

1. 专职 Agent 分工
2. 自我反思
3. 独立核验
4. 加权整合

### 3.2 必须重写的东西

以下内容建议全部重写，不要复用原始逻辑：

1. `source/hyp` 输入协议
2. MQM taxonomy
3. prompt 模板
4. stage 间 JSON schema
5. collaborative discussion 的轮次细节
6. score computation 逻辑
7. 阈值与置信度逻辑

### 3.3 建议的工程策略

不要一上来把 `HiMATE-main/code/*` 全删掉。更稳妥的是：

1. 保留 `HiMATE-main` 作为论文复现参考
2. 新建一个风险版实现目录，例如 `risk_himate/`
3. 第一阶段先做“本地单文档风险识别原型”
4. 第二阶段再接企业名称采集、外部 API、历史趋势、RAG

---

## 4. 新系统目标架构

建议新建如下目录：

```text
risk_himate/
├── app/
│   ├── agents/
│   │   ├── base.py
│   │   ├── triage_agent.py
│   │   ├── algorithm_agent.py
│   │   ├── data_compliance_agent.py
│   │   ├── ethics_agent.py
│   │   ├── ip_agent.py
│   │   ├── geopolitics_agent.py
│   │   ├── reflection_agent.py
│   │   ├── revision_agent.py
│   │   ├── verifier_agent.py
│   │   └── report_agent.py
│   ├── core/
│   │   ├── taxonomy.py
│   │   ├── schemas.py
│   │   ├── scoring.py
│   │   ├── trends.py
│   │   ├── chunking.py
│   │   ├── evidence.py
│   │   └── config.py
│   ├── data_sources/
│   │   ├── base.py
│   │   ├── document_loader.py
│   │   ├── company_profile_collector.py
│   │   ├── news_search.py
│   │   └── ip_lookup.py
│   ├── rag/
│   │   ├── recommendation_store.py
│   │   └── seed_recommendations.json
│   ├── storage/
│   │   ├── history_store.py
│   │   └── sqlite_store.py
│   ├── workflows/
│   │   ├── pipeline.py
│   │   └── state_graph.py
│   ├── llm/
│   │   ├── client.py
│   │   └── prompts/
│   │       ├── triage.md
│   │       ├── algorithm.md
│   │       ├── data_compliance.md
│   │       ├── ethics.md
│   │       ├── ip.md
│   │       ├── geopolitics.md
│   │       ├── reflection.md
│   │       ├── revision.md
│   │       ├── verifier.md
│   │       └── report.md
│   └── main.py
├── tests/
│   ├── test_chunking.py
│   ├── test_triage.py
│   ├── test_parallel_agents.py
│   ├── test_reflection_cycle.py
│   ├── test_scoring.py
│   └── fixtures/
│       └── sample_company_doc.txt
├── outputs/
├── docs/
│   └── taxonomy.md
├── requirements.txt
└── README.md
```

---

## 5. 领域映射：HiMATE 到 Risk-HiMATE

### 5.1 概念映射

| HiMATE 原概念 | Risk-HiMATE 对应 |
|---|---|
| MQM error type | 风险类别 taxonomy |
| subtype evaluator | 风险专职 Agent |
| translation segment | 文本块 / 企业证据片段 |
| source + hyp | 原始材料 + 结构化上下文 |
| severity | 风险严重程度 |
| self-reflection | 漏判/错分/严重度反思 |
| collaborative discussion | 独立质检核验 |
| score computation | 风险总分与趋势计算 |

### 5.2 风险 taxonomy

一级类：

1. 算法安全风险
2. 数据合规风险
3. 科技伦理风险
4. 知识产权风险
5. 地缘博弈风险

每个一级类再包含子类。建议在 `taxonomy.py` 中定义为静态常量，并附带：

1. 中文名
2. 英文 code
3. 子类列表
4. 对应法规/政策依据
5. 默认评分权重

---

## 6. 数据模型设计

这一部分最重要，Codex 应优先先把 schema 立住。

建议全部使用 Pydantic 模型。

### 6.1 输入对象

```python
class AnalysisInput(BaseModel):
    input_type: Literal["document", "company_name"]
    company_name: str | None = None
    raw_text: str | None = None
    metadata: dict = Field(default_factory=dict)
```

### 6.2 文本块

```python
class TextChunk(BaseModel):
    chunk_id: str
    text: str
    source_type: str
    source_name: str | None = None
    page: int | None = None
    paragraph_index: int | None = None
```

### 6.3 初评结果

```python
class TriageResult(BaseModel):
    chunk_id: str
    text: str
    candidate_risk_types: list[str]
    relevance_score: float
    rationale: str
```

### 6.4 专职 Agent 输出

```python
class RiskFinding(BaseModel):
    finding_id: str
    category: str
    subtype: str
    exists: bool
    severity: Literal["low", "medium", "high"]
    confidence: float
    evidence: str
    evidence_chunk_ids: list[str]
    rationale: str
    legal_basis: list[str] = Field(default_factory=list)
```

### 6.5 反思输出

```python
class ReflectionIssue(BaseModel):
    issue_type: Literal["missing_risk", "misclassified", "severity_issue"]
    category: str | None = None
    related_finding_id: str | None = None
    description: str
    suggested_fix: str
    confidence: float


class ReflectionResult(BaseModel):
    issues: list[ReflectionIssue]
    overall_confidence: float
    summary: str
```

### 6.6 核验输出

```python
class VerificationResult(BaseModel):
    verdict: Literal["accept", "partial_accept", "revert_to_original"]
    confidence: float
    accepted_finding_ids: list[str]
    rejected_finding_ids: list[str]
    needs_human_review: bool
    notes: str
```

### 6.7 最终报告

```python
class RiskReport(BaseModel):
    company: str
    timestamp: str
    overall_risk_level: Literal["low", "medium", "high"]
    overall_score: float
    confidence: float
    risk_details: list[dict]
    trend: str | None = None
    trend_delta: float | None = None
    top3_risks: list[dict]
    human_review_items: list[dict]
```

---

## 7. 五阶段 Pipeline 设计

### 7.0 阶段 0：初评

目标不是给出最终风险结论，而是做“召回优先”的筛选。

输入：

1. 文档全文或企业采集后的拼接文本
2. 文本切块结果

任务：

1. 判断每个 chunk 是否与风险相关
2. 给出候选风险类别
3. 过滤低相关 chunk

建议实现：

1. 先做规则 + LLM 混合方案
2. 规则层负责关键词召回
3. LLM 负责多标签分类和解释

原因：

1. 这样更稳
2. 后续可替换成蒸馏小模型
3. 有利于 Step 5 的轻量化部署

### 7.1 阶段 1：五个专职 Agent 并行评估

每个 Agent 只看与自己类别相关的候选 chunks。

每个 Agent 的 prompt 都应包含：

1. 自己负责的风险定义
2. 子类定义
3. 严重度标准
4. 允许输出“不存在风险”
5. 必须引用证据 chunk
6. 必须返回 JSON

建议每个 Agent 输出多个 finding，而不是只有一个布尔值，因为企业文档里同类风险可能不止一个。

### 7.2 阶段 2：反思

这个 Agent 不做一线识别，而做“横向审稿”。

它需要检查：

1. taxonomy 是否有遗漏
2. category/subtype 是否错分
3. severity 是否不一致
4. 某些 evidence 是否不足

建议它针对 finding 列表逐条点评，而不是只输出总评。

### 7.3 阶段 3：修正

修正不是自由重写，而是必须“基于反思意见做最小必要改动”。

建议修正规则：

1. 保留原始 findings 的 `finding_id`
2. 新增项生成新 `finding_id`
3. 对被修正项记录 `revision_reason`
4. 输出修正前后 diff 摘要

### 7.4 阶段 4：核验

这里不要照抄 HiMATE 的多轮对话机制。对风险识别场景，更适合一个独立 QA/审核 Agent 直接做仲裁。

它需要看：

1. 原始 findings
2. 反思结果
3. 修正后 findings
4. 原文证据

最后给出：

1. 接受修正
2. 部分接受
3. 回退原结果

低置信度时直接标记人工复核。

### 7.5 阶段 5：整合输出

整合逻辑应包含：

1. 根据 verdict 选择最终 findings
2. 把 severity 转成分值
3. 按风险类别权重聚合
4. 结合置信度做修正
5. 生成建议
6. 读取历史记录计算趋势

---

## 8. 与当前 HiMATE 代码的对应改造建议

### 8.1 不建议继续沿用的实现方式

当前 `HiMATE-main/code/pipeline.py` 的问题：

1. 一次只处理一个 subtype
2. 路径、文件名、轮次高度写死
3. 依赖 `source.txt/hyp.txt`
4. 过程日志结构不适合风险多发现输出

所以不建议在这个文件上继续叠补丁。

### 8.2 可以借鉴的内容

可以借鉴：

1. 分阶段处理思想
2. prompt 目录管理方式
3. 调用模型与日志记录分层

### 8.3 推荐迁移方式

1. 把原始 `HiMATE-main` 当论文参考实现保留
2. 在新目录 `risk_himate/` 中重建
3. 第一步先写同步版 pipeline
4. 第二步再用 LangGraph 重构成状态图

原因是：先跑通业务闭环，再追求图式编排，风险更小。

---

## 9. LangChain / LangGraph 落地建议

### 9.1 最小可行版本

先用“可测试的普通 Python service + LLM client”完成业务逻辑，不必第一天就深度依赖 LangChain。

推荐：

1. `Pydantic` 负责 schema
2. `langchain_core` 负责 prompt template 与结构化输出
3. `LangGraph` 只负责阶段编排

### 9.2 Graph 节点建议

```text
load_input
  -> normalize_input
  -> chunk_text
  -> triage
  -> parallel_domain_agents
  -> reflect
  -> revise
  -> verify
  -> score_and_recommend
  -> persist_history
  -> emit_report
```

### 9.3 状态对象

建议定义统一 `PipelineState`：

```python
class PipelineState(TypedDict, total=False):
    analysis_input: AnalysisInput
    chunks: list[TextChunk]
    triage_results: list[TriageResult]
    domain_findings: dict[str, list[RiskFinding]]
    reflection_result: ReflectionResult
    revised_findings: dict[str, list[RiskFinding]]
    verification_result: VerificationResult
    final_findings: list[RiskFinding]
    report: RiskReport
```

---

## 10. 评分与置信度设计

不要沿用 HiMATE 原来的 MT penalty 逻辑。

建议新逻辑：

### 10.1 severity 分值

1. `low = 30`
2. `medium = 60`
3. `high = 90`

### 10.2 category 权重

初版可先配静态权重：

1. 算法安全：1.0
2. 数据合规：1.2
3. 科技伦理：0.9
4. 知识产权：1.0
5. 地缘博弈：0.8

### 10.3 confidence 修正

`final_item_score = severity_score * category_weight * (0.7 + 0.3 * confidence)`

### 10.4 overall score

建议 0-100，最后裁剪到上限 100。

### 10.5 风险等级

1. `0-39: low`
2. `40-69: medium`
3. `70-100: high`

---

## 11. RAG 建议库设计

初版不要做复杂向量检索，先做一个本地建议库即可。

建议库按：

1. category
2. subtype
3. severity

组织成 JSON。

示例：

```json
{
  "category": "数据合规风险",
  "subtype": "跨境数据传输",
  "severity": "high",
  "suggestion": "建议建立数据出境分级评估、标准合同备案与敏感字段脱敏机制。"
}
```

后续再切换到 FAISS / Chroma。

---

## 12. 历史记录与趋势

趋势计算建议单独做，不要塞进主评分函数。

存储结构：

1. `company`
2. `timestamp`
3. `overall_score`
4. `category_scores`
5. `top_risks`

趋势逻辑：

1. 取最近两次有效记录
2. `delta = current - previous`
3. `delta >= 8 -> 上升`
4. `delta <= -8 -> 下降`
5. 其余为稳定

---

## 13. 测试策略

至少做三类测试：

### 13.1 纯逻辑单元测试

1. chunk 切分
2. scoring
3. trend 计算
4. schema 校验

### 13.2 agent 输出契约测试

用 mock LLM 输出验证：

1. triage 输出是否符合 schema
2. domain agent 是否返回 evidence
3. reflection/revision/verification 是否能串起来

### 13.3 端到端样例测试

给一份企业文档样例，验证：

1. 能跑完整流程
2. 能产出标准 JSON
3. 能正确标记人工复核项

---

## 14. 分步实施计划

## Step 1：基础 pipeline 骨架

目标：

1. 建立新目录 `risk_himate/`
2. 定义 schema
3. 实现输入归一化、chunking、阶段 0 初评
4. 实现五个专职 Agent 的统一基类
5. 实现阶段 1 并行评估
6. 增加一个 CLI 入口
7. 增加最小测试

完成标准：

1. 输入一段企业文本
2. 能输出五类 Agent 的结构化结果
3. 不要求外部 API
4. 不要求历史趋势

## Step 2：反思-修正-核验循环

目标：

1. 实现 reflection agent
2. 实现 revision agent
3. 实现 verifier agent
4. 实现最终 findings 仲裁逻辑

完成标准：

1. 同一份输入可同时得到原始 findings、修正 findings、最终 findings
2. 低置信度条目被标记人工复核

## Step 3：整合输出

目标：

1. 实现评分器
2. 实现建议生成
3. 实现标准 JSON 报告
4. 实现 Markdown 报告导出

完成标准：

1. JSON 字段稳定
2. Markdown 可读
3. overall score / level / confidence 可用

## Step 4：外部数据接入

目标：

1. 支持企业名称输入
2. 外接工商、司法、知识产权、新闻数据源
3. 统一转成标准 chunks

完成标准：

1. `input_type=company_name` 时可自动拉取数据
2. 数据失败时能优雅降级

## Step 5：轻量模型蒸馏

目标：

1. 使用主 pipeline 结果产生伪标签
2. 针对阶段 0 初评进行 LoRA 微调
3. 在快速分类场景替换大模型

完成标准：

1. triage 成本下降
2. 召回率不明显恶化

---

## 15. 直接给 Codex 的实施要求

下面这段可以直接作为 Codex 的主任务说明。

### 主任务 Prompt

```text
请基于当前仓库中的 HiMATE 论文实现，重构出一个新的中文项目：Risk-HiMATE（科创企业特有风险识别智能体）。

要求：
1. 不要直接在 HiMATE-main/code/pipeline.py 上打补丁实现全部逻辑；保留原始 HiMATE 目录作为参考。
2. 新建独立目录 risk_himate/，用 Python 实现新的风险识别框架。
3. 参考 HiMATE 的方法结构，但任务域替换为科创企业风险识别。
4. 使用 LangChain / LangGraph 友好的模块化结构，但优先保证代码可运行、可测试。
5. 默认主模型配置为 Qwen2.5-14B-Instruct，保留后续替换模型的接口。
6. 所有阶段之间使用清晰的 Pydantic schema，不要用松散 dict 乱传。
7. 输出必须是结构化 JSON 报告，并保留 Markdown 报告导出能力。
8. 先完成 Step 1，再补 Step 2，不要一次性把所有高级能力硬塞进去。

风险 taxonomy：
- 算法安全风险：算法歧视、算法黑箱、算法滥用
- 数据合规风险：数据采集合规、数据存储安全、跨境数据传输、隐私保护
- 科技伦理风险：透明度不足、公平性问题、人工干预机制缺失
- 知识产权风险：专利侵权、技术泄露、软著/商标风险
- 地缘博弈风险：出海合规壁垒、技术封锁风险、数据主权风险

五阶段流程：
阶段0：初评筛选文本块并做候选风险分类
阶段1：五个专职 Agent 并行评估
阶段2：反思，检查遗漏/错分/严重度问题
阶段3：修正，基于反思结果修复 findings
阶段4：核验，独立 QA agent 判断是否接受修正
阶段5：整合输出，计算总分、趋势、建议、人工复核项

请优先完成 Step 1：
1. 新建项目目录结构
2. 定义核心 schema
3. 实现 chunking
4. 实现 triage agent
5. 实现五个领域 agent 的基类和最小可运行版本
6. 实现 pipeline 主入口
7. 添加最小测试

请先阅读当前仓库结构，再实施，不要假设现有代码已经适合直接复用。
```

---

## 16. Step 1 专用 Prompt

如果只让 Codex 先做第一步，直接发这段：

```text
请在当前仓库中实现 Risk-HiMATE 的 Step 1 基础骨架，参考 HiMATE 的方法，但不要直接修改原始 HiMATE-main 代码结构来硬适配。

具体要求：

1. 新建独立目录 `risk_himate/`，不要破坏 `HiMATE-main/`。
2. 用 Python 实现一个最小可运行的企业风险识别 pipeline。
3. 先不要接外部 API，不要做历史趋势，不要做 LoRA。
4. 先支持“文档文本输入”这一种输入模式。

请完成以下内容：

- 定义核心 Pydantic schema：
  - AnalysisInput
  - TextChunk
  - TriageResult
  - RiskFinding
  - RiskReport 的最小版本

- 定义五类风险 taxonomy 常量：
  - 算法安全风险
  - 数据合规风险
  - 科技伦理风险
  - 知识产权风险
  - 地缘博弈风险

- 实现文本处理：
  - 将输入长文本切分为 chunk
  - 保留 chunk_id 和原文内容

- 实现阶段0 TriageAgent：
  - 输入 chunks
  - 输出每个 chunk 的候选风险类别和 relevance_score
  - 先支持 mock / rule-based / LLM adapter 三选一的可替换实现

- 实现阶段1 五个专职 Agent：
  - 统一继承 BaseRiskAgent
  - 每个 Agent 只处理自己负责的风险类
  - 输出结构化 RiskFinding 列表
  - 先做最小可运行版本，允许内部用 stub/mock 结果占位，但接口必须稳定

- 实现 pipeline 主入口：
  - 输入一段企业文档文本
  - 运行 chunking -> triage -> 五类 agent
  - 输出按类别组织的结构化 JSON

- 实现最小测试：
  - 至少覆盖 chunking
  - 至少覆盖 triage 输出 schema
  - 至少覆盖 pipeline 能跑通

工程要求：
1. 代码模块化，后续方便接 LangGraph。
2. 不要把 prompt 字符串硬编码在业务逻辑里，预留 prompt 文件或 prompt builder。
3. 不要用散乱 dict 传递阶段状态。
4. 保持中文业务语义命名清晰，但代码标识符用英文。
5. 给出运行方式和测试方式。

完成后请总结：
1. 新增了哪些文件
2. Step 1 当前支持什么
3. 下一步最自然的 Step 2 接口该怎么接
```

---

## 17. 一句判断

如果你的目标是“基于 HiMATE 的思想做一个比赛可展示、可继续扩展的风控智能体”，正确路线是：

1. 保留 HiMATE 作为论文参考
2. 新建 Risk-HiMATE 实现
3. 先做 Step 1 骨架
4. 再逐步补反思、核验、趋势、外部数据

不要直接把 MT 评测代码生硬替换成企业风险识别代码，否则后面会越来越难维护。
