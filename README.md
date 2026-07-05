# Risk-HiMATE

Risk-HiMATE 是一个面向科创企业场景的多智能体风险识别原型系统。它将 HiMATE 在机器翻译评测中的“多 Agent 分工 + 反思修正 + 独立核验 + 汇总评分”方法，迁移到了企业风险分析任务中。

这个仓库的目标不是复现通用大模型问答，而是构建一个更像“审阅流程”的系统：先从文档里筛出风险相关证据，再由不同领域 Agent 分别判断，之后经过反思、修正、核验，最后输出结构化风险报告。

## 1. 项目背景

原始参考框架 `HiMATE-main/` 主要用于机器翻译质量评估。它的核心思想不是“单次直接打分”，而是：

1. 先按错误子类型拆分任务
2. 让专职 Agent 分别分析
3. 通过 self-reflection 发现遗漏和误判
4. 通过 collaborative verification 控制系统性幻觉
5. 最后统一汇总结果

Risk-HiMATE 保留了这套结构，但把任务对象改成了科创企业风险识别：

- MQM 错误类型 -> 企业风险 taxonomy
- 翻译片段 -> 企业文档文本块 / 采集证据
- 错误严重度 -> 风险严重度
- 评分汇总 -> 风险等级与结构化报告

## 2. 当前实现了什么

当前原型已经具备一个完整可跑通的端到端流程，支持：

- 文档文本输入
- 企业名称输入
- 本地规则模式、真实 LLM 模式、自动降级模式
- 五类风险的专职 Agent 分析
- reflection / revision / verifier 三阶段闭环
- 结构化 JSON 报告生成
- 历史记录存储与趋势接口
- 本地 PDF 抽取文本后送入 pipeline
- 本地 LM Studio / OpenAI-compatible 接口推理

## 3. 风险 taxonomy

系统当前聚焦五大类风险：

1. `算法安全风险`
   子类包括：算法歧视、算法黑箱、算法滥用
2. `数据合规风险`
   子类包括：数据采集合规、数据存储安全、跨境数据传输、隐私保护
3. `科技伦理风险`
   子类包括：透明度不足、公平性问题、人工干预机制缺失
4. `知识产权风险`
   子类包括：专利侵权、技术泄露、软著/商标风险
5. `地缘博弈风险`
   子类包括：出海合规壁垒、技术封锁风险、数据主权风险

taxonomy 定义在 [risk_himate/app/core/taxonomy.py](/Users/belle/projects/挑战杯/risk_himate/app/core/taxonomy.py)。

## 4. 系统工作流

当前 pipeline 在 [risk_himate/app/workflows/pipeline.py](/Users/belle/projects/挑战杯/risk_himate/app/workflows/pipeline.py)，核心阶段如下：

1. `阶段0 初评`
   `TriageAgent` 负责把原始文本切成 chunk，并筛出“可能与风险相关”的证据块，给出候选风险标签。
2. `阶段1 专职 Agent`
   五个领域 Agent 分别对各自类别做判断，输出 `RiskFinding`。
3. `阶段2 反思`
   `ReflectionAgent` 检查有没有漏掉风险、错分子类、严重度是否不合理。
4. `阶段3 修正`
   `RevisionAgent` 根据反思结果补全或修改 findings。
5. `阶段4 核验`
   `VerifierAgent` 判断修正是否真的解决了问题，避免修正引入新错误。
6. `阶段5 报告整合`
   汇总最终 findings，计算总分、总等级、建议、Top3 风险和趋势字段。

## 5. 输入与输出

### 输入

系统支持两类输入：

1. `document`
   直接给定企业文档文本、公告、合同条款、研发说明等内容。
2. `company_name`
   给企业名称，让 collector 去拼装资料，再统一送入 pipeline。

核心输入 schema 在 [risk_himate/app/core/schemas.py](/Users/belle/projects/挑战杯/risk_himate/app/core/schemas.py)：

```python
class AnalysisInput(BaseModel):
    input_type: Literal["document", "company_name"]
    company_name: str | None = None
    raw_text: str | None = None
    metadata: dict = Field(default_factory=dict)
```

### 输出

pipeline 的完整输出分成两层：

```json
{
  "report": { ...正式报告... },
  "debug": { ...中间过程... }
}
```

- `report` 是给前端、演示、交付看的正式结果
- `debug` 用来检查阶段性行为，方便调试 Agent 和 prompt

如果使用 `--report-only`，CLI 只输出 `report` 对象。

## 6. 目录结构说明

```text
.
├── README.md
├── RISK_HIMATE_IMPLEMENTATION_SPEC.md
├── requirements.txt
├── HiMATE-main/
├── risk_himate/
│   ├── README.md
│   ├── 1207403259.pdf
│   ├── app/
│   │   ├── agents/
│   │   ├── core/
│   │   ├── data_sources/
│   │   ├── llm/
│   │   ├── rag/
│   │   ├── storage/
│   │   └── workflows/
│   └── output/
└── tests/
```

主要模块职责：

- `risk_himate/app/agents/`
  风险分析主体。包含 triage、五类专职 Agent、reflection、revision、verifier。
- `risk_himate/app/core/`
  放 schema、taxonomy、chunking、评分和报告生成逻辑。
- `risk_himate/app/llm/`
  放 OpenAI-compatible client 和 prompt 模板。
- `risk_himate/app/data_sources/`
  放本地 company profile、外部 API collector。
- `risk_himate/app/storage/`
  放 JSON / SQLite 历史存储逻辑。
- `risk_himate/app/rag/`
  放建议库与建议检索逻辑。
- `tests/`
  覆盖 CLI、chunking、pipeline、reflection cycle、history store、LLM adapter 等测试。

## 7. 运行方式

### 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

当前 `requirements.txt` 很轻，核心依赖只有 `pydantic`。如果要本地解析 PDF，可在本地虚拟环境中额外安装 `pypdf`。

### 基本文本分析

```bash
python3 -m risk_himate.app.main \
  --input-type document \
  --company "测试企业" \
  --text "公司计划将用户行为数据存储在境外云平台，并用于智能推荐，尚未明确披露用户授权机制。" \
  --llm-mode auto
```

### 使用本地 Qwen / LM Studio

```bash
LLM_BASE_URL=http://127.0.0.1:1234/v1 \
LLM_API_KEY=lm-studio \
LLM_MODEL=qwen2.5-7b-instruct-mlx \
python3 -m risk_himate.app.main \
  --input-type document \
  --company "测试企业" \
  --text "本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。" \
  --llm-mode llm
```

### 保存报告到文件

```bash
python3 -m risk_himate.app.main \
  --input-type document \
  --company "测试企业" \
  --text "这里放分析文本" \
  --llm-mode auto \
  --report-only \
  --output risk_himate/output/my_report.json
```

参数说明：

- `--llm-mode rule`
  强制规则模式
- `--llm-mode llm`
  强制使用 LLM
- `--llm-mode auto`
  先尝试 LLM，失败再降级到规则模式
- `--output`
  把结果保存为 JSON 文件
- `--report-only`
  只保存正式报告，不输出 `debug`

## 8. PDF 分析方式

当前还没有一等公民的 `--pdf` 参数，所以 PDF 的使用方式是：

1. 先把 PDF 文本抽出来
2. 再把全文作为 `--text` 送入 pipeline

例如：

```bash
TEXT=$( .venv_pdf/bin/python - <<'PY'
from pypdf import PdfReader
reader = PdfReader("risk_himate/1207403259.pdf")
print("\n".join((page.extract_text() or "") for page in reader.pages))
PY
)

LLM_BASE_URL=http://127.0.0.1:1234/v1 \
LLM_API_KEY=lm-studio \
LLM_MODEL=qwen2.5-7b-instruct-mlx \
python3 -m risk_himate.app.main \
  --input-type document \
  --company "皇氏集团股份有限公司" \
  --text "$TEXT" \
  --llm-mode llm \
  --report-only \
  --output risk_himate/output/pdf_report.json
```

## 9. 一份结果该怎么看

正式报告里最关键的是：

- `overall_risk_level`
  总风险等级
- `overall_score`
  综合风险分数
- `risk_details`
  逐条风险明细
- `top3_risks`
  最值得优先关注的三项风险
- `human_review_items`
  低置信度、建议人工复核的条目

每条 `risk_details` 里最值得看的是：

- `category`
- `subtype`
- `severity`
- `evidence`
- `suggestion`
- `legal_basis`

## 10. 当前工程状态

目前这更像一个“研究型原型系统”，而不是生产级产品。它已经能做的，是：

- 跑通多阶段流程
- 用真实本地 LLM 产出结构化 risk report
- 保存报告到 JSON
- 对企业文本、公告、PDF 提取文本进行演示分析

但还存在一些明确局限：

- `地缘博弈风险` 目前偏容易误报
- `company_name` 外部采集还属于可扩展状态，不是完整商用接入
- PDF 还没有独立 CLI 参数
- 现在的“并行”更多是结构上的多 Agent，而不是高并发调度
- 还没有真正迁移到 LangGraph state graph

## 11. 目前还需要补充和修正的部分

这一节更偏“研发待办说明”，适合告诉协作者、评审或后续接手的人：这个项目现在不是缺一两个小功能，而是有几块关键能力还需要系统性打磨。

### 11.1 Prompt 设计还需要继续收紧

当前系统已经有：

- `triage.md`
- `algorithm.md`
- `data_compliance.md`
- `ethics.md`
- `ip.md`
- `geopolitics.md`
- `reflection.md`
- `revision.md`
- `verifier.md`

这些 prompt 已经是结构化模板，但从工程角度看，仍然需要继续优化：

1. 各 Agent 的“边界感”还不够强  
   例如地缘博弈 Agent 目前容易把“合作不确定性”“战略协议”这类一般商业不确定性误识别成地缘风险。
2. 输出 schema 虽然已有约束，但“判断依据”和“证据引用”的力度还不完全一致  
   有些 finding 的 `rationale` 比较泛，没把“为什么是这个子类、为什么是这个严重度”说透。
3. reflection/revision/verifier 的角色分工还可以更清晰  
   当前 reflection 仍然混合了部分规则判断逻辑，和 LLM 反思的边界没有完全切干净。
4. 对“风险不存在”的约束还可以更严格  
   某些 prompt 仍会出现“为了给结果而给结果”的倾向。

### 11.2 Prompt 设计建议

如果继续优化 prompt，建议按下面几个原则推进：

1. 每个 Agent 必须先声明“自己只负责哪一类风险”
2. 每个 Agent 必须内置该类风险的子类定义和判定标准
3. 严重度必须给出明确规则，不能只靠模型自由发挥
4. 必须要求引用原文证据，而不是只做抽象转述
5. 必须允许输出空数组，避免强行编造风险
6. reflection 必须逐条指出问题，而不是给笼统意见
7. verifier 必须说明“接受 / 部分接受 / 回退”的依据

一个更成熟的 prompt 目标不是“写得长”，而是做到三件事：

- 降低误报
- 提高 JSON 稳定性
- 提高 evidence 和 subtype 的一致性

### 11.3 Triage 逻辑还需要优化召回与精度平衡

当前 `TriageAgent` 的定位是“先尽量召回”，这是合理的，但副作用是：

- 会把一些泛化表述拉进后续分析
- 给后面的 Agent 带来额外噪声
- 可能放大误报，尤其是地缘风险类

后续建议：

1. 提高 triage 的“候选标签解释性”
2. 给 triage 增加更细粒度的触发词或 few-shot 示例
3. 区分“弱相关”与“强相关” chunk
4. 对标题、页脚、公告头部等噪声 chunk 做过滤

### 11.4 地缘博弈风险需要重点修正

这是当前最明显的薄弱点之一。

问题主要在于：

- “国际合作”“合作不确定性”“战略协议”这类词很容易被泛化成地缘风险
- 当前 taxonomy 下的 `出海合规壁垒 / 技术封锁风险 / 数据主权风险` 边界还不够清楚
- 缺少更强的政策、地域、出口管制、海外监管等硬信号约束

建议把地缘风险的 prompt 收紧成：

1. 必须出现“海外市场、出口管制、跨境监管、数据主权、制裁、实体清单、境外数据治理”等强信号
2. 不能仅因“合作框架协议存在不确定性”就给出地缘风险
3. 如果只是商业合作风险，应该允许不输出地缘风险

### 11.5 数据合规风险还可以做得更细

当前数据合规 Agent 已经能识别出：

- 人脸识别
- 境外存储
- 未明确告知

但还不够细，后续可以继续强化：

1. 区分“数据采集合规”和“隐私保护”的边界
2. 增加对“敏感个人信息”的专门判断
3. 增加对“用户授权机制”“最小必要原则”“用途透明度”的明确规则
4. 对跨境传输场景增加更严格的高风险判定条件

### 11.6 PDF 输入链路还不够产品化

现在 PDF 方案本质上是：

1. 用 `pypdf` 本地抽文本
2. 把抽出的全文当作 `--text`
3. 再走 document pipeline

这对原型验证没问题，但还不是理想形态。后续需要：

1. 增加 `--pdf` 原生参数
2. 在抽文本阶段保留页码信息
3. 支持扫描件 OCR
4. 支持按页或按段落建立更稳定的 `chunk_id`
5. 让 evidence 可以准确回指 PDF 页码

### 11.7 Company collector 还只是原型级接入

虽然已经有：

- `LocalCompanyDataCollector`
- `ExternalCompanyDataCollector`

但现在的外部采集能力还不算完整商用接入，主要还差：

1. 不同来源字段映射的统一 schema
2. 多源证据去重
3. API 异常、频控、空结果的稳健处理
4. 不同来源证据的可信度建模
5. 采集结果与 LLM prompt 的更紧密融合

### 11.8 评分逻辑仍然是“原型打分”

现在的总分逻辑已经能工作，但仍偏启发式：

- severity -> score 的映射比较简单
- category weight 还是静态权重
- confidence 只做了轻量修正

后续可以继续做：

1. 不同风险类别使用不同权重区间
2. 区分“单条高危风险”和“多条中危风险”的总分策略
3. 增加更稳定的人工规则校准
4. 用真实样本做分数标定

### 11.9 历史趋势还只是接口打通

现在支持 JSON / SQLite history store，也能算 `trend` 和 `trend_delta`，但离“趋势分析”还差不少：

1. 还没有跨时间同类风险对齐
2. 还没有识别“新增风险 / 已缓解风险 / 持续风险”
3. 还没有按风险类别给趋势解释
4. 还没有结合外部舆情或企业事件做趋势说明

### 11.10 LangGraph 还没真正接上

当前系统已经有统一的 `PipelineState`，这是后续迁移到 LangGraph 的很好基础。

但严格来说，现在还只是“LangGraph-ready”，不是“LangGraph-native”。后续如果继续做：

1. 可以把当前串行 `run_state` 映射成 state graph
2. 可以让 triage、domain agents、reflection、revision、verifier 成为明确节点
3. 可以让低置信度分支进入人工复核节点
4. 可以更方便地加 retry、branch、checkpoint

### 11.11 评审展示层还可以更强

现在系统已经能产出 JSON 报告，但如果要更适合比赛、答辩、GitHub 展示，还建议补：

1. 阶段化可视化输出
2. 示例输入 -> 示例输出对照
3. “为什么判成这个风险”的自然语言摘要
4. 前端页面或 notebook demo
5. 一页式架构图

## 12. 测试

运行全部测试：

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

当前测试覆盖了：

- chunking
- triage
- reflection / revision / verifier chain
- reporting
- history store
- CLI 输出
- LLM adapter
- external collector

## 13. 后续建议

如果把它继续往“可展示、可提交、可扩展”的方向推进，最自然的下一步是：

1. 增加 `--pdf` 原生输入支持
2. 把阶段输出改成更直观的 `stage0~stage5` 视图
3. 收紧地缘风险判断，减少误报
4. 把现有 pipeline 接成 LangGraph 的 `PipelineState`
5. 增加前端或 notebook demo

## 14. 参考来源

本项目方法结构参考 HiMATE，但任务目标已经从机器翻译质量评估改造成了科创企业风险识别。
