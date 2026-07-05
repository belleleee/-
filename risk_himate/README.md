# Risk-HiMATE Package

这个目录是项目的可运行主体实现。你可以把它理解为“真正执行企业风险分析”的应用层，顶层仓库里的 `HiMATE-main/` 则更多是论文参考和方法来源。

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
  当前的核心调度入口

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

## 5. 当前这个包的定位

这个实现当前最适合：

- 本地原型验证
- 挑战杯项目演示
- 后续接前端页面
- 继续往 LangGraph / 多 Agent 产品化方向扩展

它还不算生产级系统，但已经具备清晰的结构、可测性和可扩展性。

## 6. 这个包里最需要继续改进的点

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

当前我们已经有 `PipelineState`，但展示还偏调试视角。后续建议补：

- 明确的 `stage0~stage5` 输出视图
- 面向前端的轻量中间结果 schema
- 更好的人类可读 summary

### PDF 输入

当前包还没有 `--pdf` 原生参数。后续如果继续做，优先级很高，因为实际企业材料很多都是 PDF。

### 数据源接入

`company_name` 路径已经有 collector 骨架，但还需要更完整的外部 API 字段映射和证据去重。

## 7. 测试

运行测试：

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

当前测试已经覆盖 CLI、pipeline、history store、LLM adapter、prompt 结构等核心模块。
