# Risk-HiMATE Package

这个目录是项目的可运行主体实现。你可以把它理解为“真正执行企业风险分析”的应用层，顶层仓库里的 `HiMATE-main/` 则更多是论文参考和方法来源。

当前这一版已经是 **LangGraph-native** 架构：系统内部不是单纯按手写顺序调用阶段，而是按状态图节点组织工作流。

如果你想先看项目全貌，请先读根目录 [README.md](/Users/belle/projects/挑战杯/README.md)。

## 1. 这个目录里有什么

```text
risk_himate/
├── README.md
├── 1207403259.pdf
├── app/
│   ├── agents/
│   ├── core/
│   ├── data_sources/
│   ├── llm/
│   ├── rag/
│   ├── storage/
│   └── workflows/
└── output/
```

### `app/agents/`

负责执行多阶段分析：

- `triage_agent.py`
  初评，筛选风险相关 chunk
- `domain_agents.py`
  五类风险专职 Agent
- `reflection_agent.py`
  反思是否漏判、错分、误判严重度
- `revision_agent.py`
  根据反思结果修正 findings
- `verifier_agent.py`
  对修正后的结果做最终核验

### `app/core/`

放系统的基础定义：

- `schemas.py`
  全部 Pydantic schema
- `taxonomy.py`
  风险分类体系
- `chunking.py`
  文本切块逻辑
- `analysis.py`
  打分和聚合辅助函数
- `confidence.py`
  独立置信度评估层，负责连续置信度分与二元红线 gate
- `reporting.py`
  报告生成逻辑

### `app/llm/`

放 LLM 调用相关逻辑：

- `client.py`
  OpenAI-compatible 接口适配器
- `prompts/`
  各阶段 prompt 模板

### `app/workflows/`

- `pipeline.py`
  当前的核心调度入口，对外保持稳定 API
- `state_graph.py`
  当前真正的 LangGraph-native 工作流定义，负责节点、边和分支组织

### `app/data_sources/`

负责把不同来源的数据整理成统一输入：

- 本地 company profile
- mock 数据
- 外部 API collector 预留

### `output/`

用于保存导出的报告 JSON。这个目录默认保留，但导出的具体结果文件已被 `.gitignore` 忽略。

## 2. 主入口

CLI 主入口在：

[main.py](/Users/belle/projects/挑战杯/risk_himate/app/main.py)

它内部会调用 `RiskHiMATEPipeline`，再由 `RiskHiMATEPipeline` 调用 LangGraph-native 工作流。

查看帮助：

```bash
python3 -m risk_himate.app.main --help
```

## 3. 常见运行方式

### 文本直接分析

```bash
python3 -m risk_himate.app.main \
  --input-type document \
  --company "测试企业" \
  --text "贵公司计划向海外客户提供智能推荐服务，并将用户行为数据传输至境外云平台。" \
  --llm-mode auto
```

### 使用本地 LLM

如果你已经把 `langgraph` 装在 Conda 里的 Python，而不是系统或 Homebrew 的 `python3`，建议显式使用对应解释器。我们本地已验证可运行的是：

```bash
LLM_BASE_URL=http://127.0.0.1:1234/v1 \
LLM_API_KEY=lm-studio \
LLM_MODEL=qwen2.5-7b-instruct-mlx \
/Users/belle/miniconda3/bin/python3 -m risk_himate.app.main \
  --input-type document \
  --company "测试企业" \
  --text "本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。" \
  --llm-mode llm
```

如果你的终端里 `python3` 指向的是其他解释器，例如 `/opt/homebrew/opt/python@3.14/bin/python3.14`，而 `langgraph` 又安装在 Conda 解释器里，就可能出现：

- `debug.workflow_backend` 退回 `sequential_fallback`
- 明明安装了依赖，但 CLI 表现像“没装 LangGraph”

最稳妥的做法是：

1. 先用 `python3 -c "import sys; print(sys.executable)"` 看当前解释器路径
2. 再确认 `langgraph` 装在哪个 Python 里
3. 运行时显式使用那个解释器

### 导出正式报告

```bash
python3 -m risk_himate.app.main \
  --input-type document \
  --company "测试企业" \
  --text "这里放分析文本" \
  --llm-mode auto \
  --report-only \
  --output risk_himate/output/my_report.json
```

## 4. 输出结构

默认输出是：

```json
{
  "report": { ... },
  "debug": { ... }
}
```

其中：

- `report`
  正式报告，适合前端展示和交付
- `debug`
  中间过程，适合调 prompt、看阶段行为

如果加上 `--report-only`，只输出 `report`。

`debug` 里还会带一个额外字段：

- `workflow_backend`

用来说明当前到底是：

- `langgraph`
  真实 `StateGraph` 在执行
- `sequential_fallback`
  当前环境没有安装 `langgraph` 时使用的兼容后备执行器

也就是说，从代码组织上它已经是 LangGraph-native；只是为了保证仓库在未安装依赖时也能运行，保留了一个执行层的后备模式。

### 一次真实验证过的结果

下面这条命令已经在本地用 LM Studio 真模型跑通，并确认：

- `debug.workflow_backend = "langgraph"`
- 能正常返回 `report` 和 `debug`
- 数据合规高风险能够被识别出来

验证命令：

```bash
LLM_BASE_URL=http://127.0.0.1:1234/v1 \
LLM_API_KEY=lm-studio \
LLM_MODEL=qwen2.5-7b-instruct-mlx \
/Users/belle/miniconda3/bin/python3 -m risk_himate.app.main \
  --input-type document \
  --company "测试企业" \
  --text "本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。" \
  --llm-mode llm
```

## 5. 独立置信度层

当前实现里，`confidence` 不是由 `Verifier` 单独主观判断出来的，而是先经过一个独立的置信度评估模块：

- 位置：
  [confidence.py](/Users/belle/projects/挑战杯/risk_himate/app/core/confidence.py)
- 状态字段：
  [schemas.py](/Users/belle/projects/挑战杯/risk_himate/app/core/schemas.py) 中的 `ConfidenceResult`、`GateFlags`、`PipelineState.confidence_result`

这一层的设计参考了 TrustLLM 一类可信 AI 评估框架，但没有直接照搬其原始指标，而是重组为更适合多智能体风险识别任务的三类连续指标：

1. `signal_strength`
   评估信号词是否强、证据是否直接、风险触发是否清晰。
2. `robustness`
   评估证据链是否完整、法律依据是否齐全、chunk 与 rationale 是否足够支撑判断。
3. `cross_agent_consistency`
   评估多个 agent 是否对同一事实收敛，reflection / revision 后是否仍存在明显分歧。

同时，隐私/合法性与伦理/公平性问题不进入连续平均，而是单独作为 verifier 的二元红线 gate：

- `privacy_legality_redline`
- `ethics_fairness_redline`

因此系统中实际存在两层判断：

- 连续置信度：
  回答“这条风险识别稳不稳”
- 二元 redline gate：
  回答“即使稳，有没有触碰治理红线”

`Verifier` 在 [verifier_agent.py](/Users/belle/projects/挑战杯/risk_himate/app/agents/verifier_agent.py) 中消费这层结果，而不是自己重新生成一套独立置信度。

## 6. 当前这个包的定位

这个实现当前最适合：

- 本地原型验证
- 挑战杯项目演示
- 后续接前端页面
- 继续往更完整的 LangGraph / 多 Agent 产品化方向扩展

它还不算生产级系统，但已经具备清晰的结构、可测性和可扩展性，并且底层工作流已经完成 LangGraph-native 化。

## 7. 这个包里最需要继续改进的点

如果你接下来还要继续开发，这几个方向优先级最高：

### Prompt 设计

当前 prompt 已经结构化，但还需要进一步：

- 收紧各 Agent 的职责边界
- 强化 evidence 引用约束
- 强化“风险不存在时返回空数组”的约束
- 提高 subtype、severity、rationale 三者的一致性

尤其是：

- `geopolitics.md` 需要减少泛化误报
- `reflection.md` 需要更清楚地区分“漏判”“错分”“严重度问题”
- `verifier.md` 需要更明确地说明 accept / partial_accept / revert 的依据

### 阶段间状态表达

当前我们已经有统一的 `PipelineState`，也已经有 LangGraph-native 的节点式工作流，但展示还偏调试视角。后续建议补：

- 明确的 `stage0~stage5` 输出视图
- 面向前端的轻量中间结果 schema
- 更好的人类可读 summary

### 置信度标定

当前 `confidence.py` 已经把置信度从 verifier 中拆出来，但它仍然是启发式评分，不是经过标注数据校准后的统计模型。后续建议继续做：

- 用真实案例标定 `signal_strength / robustness / cross_agent_consistency` 的权重
- 明确哪些 TrustLLM 维度进入连续分，哪些必须保留为二元 gate
- 为不同风险类别建立不同的置信度阈值
- 在报告中补充更细的“低置信度原因”解释

### PDF 输入

当前包还没有 `--pdf` 原生参数。后续如果继续做，优先级很高，因为实际企业材料很多都是 PDF。

### LangGraph 分支能力

当前已经完成 LangGraph-native 架构，但还有一些典型的图工作流能力可以继续扩展：

- 更完整的 `human_review` 节点输入输出协议
- 更明确的 `retry` 逻辑
- `checkpoint` 与中断恢复
- 更细粒度的条件分支可视化

### 数据源接入

`company_name` 路径已经有 collector 骨架，但还需要更完整的外部 API 字段映射和证据去重。

## 8. 测试

运行测试：

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

当前测试已经覆盖 CLI、pipeline、history store、LLM adapter、prompt 结构等核心模块。

其中工作流测试现在已经在 LangGraph-native 架构下通过，未安装 `langgraph` 时则由兼容后备执行器保证行为一致。
