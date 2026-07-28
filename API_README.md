# Risk-HiMATE API README

这份文档面向前端同学、协作者和联调人员，说明 Risk-HiMATE 后端服务如何启动、有哪些接口、每个接口怎么调用，以及前端最应该关注哪些返回字段。

## 1. 服务说明

Risk-HiMATE 当前已经封装成一个 HTTP 后端服务。前端不需要了解多智能体内部细节，只需要按接口发送请求并读取 JSON 返回结果即可。

后端默认本地地址：

```text
http://127.0.0.1:8000
```

如果后端通过 `ngrok`、`cloudflared` 或云服务器暴露公网，那么把上面的地址替换成对应公网地址即可。

例如：

```text
https://your-domain-or-tunnel-url
```

## 2. 启动方式

在项目根目录执行：

```bash
python3 -m risk_himate.app.api.server
```

启动成功后：

- 接口服务地址：`http://127.0.0.1:8000`
- 内置前端页面：`http://127.0.0.1:8000/`

## 3. 当前可用接口

- `GET /health`
- `POST /analyze`
- `POST /analyze/report-only`
- `GET /reports/{company}`

## 4. 通用返回格式

大多数接口都会返回如下外层结构：

```json
{
  "success": true,
  "message": "ok",
  "workflow_backend": "langgraph",
  "data": {}
}
```

字段说明：

- `success`
  请求是否成功。
- `message`
  返回信息，通常为 `ok`。
- `workflow_backend`
  当前工作流执行方式，常见值：
  - `langgraph`
  - `sequential_fallback`
- `data`
  具体业务数据。

## 5. 健康检查接口

### 请求

```http
GET /health
```

### curl 示例

```bash
curl http://127.0.0.1:8000/health
```

### 返回示例

```json
{
  "success": true,
  "message": "ok",
  "workflow_backend": "langgraph",
  "history_store": "none",
  "collector_mode": "auto",
  "llm_available": true
}
```

### 字段说明

- `workflow_backend`
  当前是否使用 LangGraph 作为真实工作流执行后端。
- `history_store`
  历史记录存储方式，例如 `none`、`json`、`sqlite`。
- `collector_mode`
  企业资料采集模式，例如 `auto`、`local`、`external`。
- `llm_available`
  当前是否检测到可用的大模型配置。

### 前端用途

- 页面初始化时检查后端是否在线
- 显示“模型是否已连接”
- 显示“当前是否为 LangGraph-native 运行”

## 6. 主分析接口

### 请求

```http
POST /analyze
Content-Type: application/json
```

### 请求体示例

```json
{
  "input_type": "document",
  "company_name": "测试企业",
  "raw_text": "本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。",
  "metadata": {},
  "llm_mode": "llm",
  "report_only": false
}
```

### 请求字段说明

- `input_type`
  必填，可选值：
  - `document`
  - `company_name`

- `company_name`
  企业名称，可为空。

- `raw_text`
  当 `input_type=document` 时传入待分析文本。

- `metadata`
  扩展信息，通常可传空对象 `{}`。

- `llm_mode`
  可选值：
  - `auto`
  - `rule`
  - `llm`

- `report_only`
  是否只返回正式报告。
  对 `/analyze` 接口来说通常传 `false`。

### curl 示例

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "input_type": "document",
    "company_name": "测试企业",
    "raw_text": "本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。",
    "llm_mode": "llm"
  }'
```

## 7. /analyze 返回结构

### 返回示例

```json
{
  "success": true,
  "message": "ok",
  "workflow_backend": "langgraph",
  "data": {
    "report": { "...": "..." },
    "debug": { "...": "..." }
  }
}
```

### 说明

- `data.report`
  正式报告，适合直接展示给用户。
- `data.debug`
  中间过程，适合做“多 agent 工作流展示页”。

## 8. 正式报告 report 结构

`data.report` 中的核心字段如下：

```json
{
  "company": "测试企业",
  "timestamp": "2026-07-28T12:00:00",
  "overall_risk_level": "medium",
  "overall_score": 60.04,
  "confidence": 0.79,
  "confidence_breakdown": { "...": "..." },
  "risk_details": [],
  "top3_risks": [],
  "human_review_items": [],
  "lifecycle_stage_groups": [],
  "propagation_hints": [],
  "gate_flags": { "...": "..." },
  "trend": null,
  "trend_delta": null,
  "top_categories": []
}
```

### 前端最应该优先展示的字段

- `overall_risk_level`
- `overall_score`
- `confidence`
- `risk_details`
- `top3_risks`
- `human_review_items`

## 9. 单条风险对象结构

`risk_details`、`top3_risks`、`human_review_items` 中每项结构基本一致：

```json
{
  "finding_id": "data_compliance-chunk-000-01",
  "category": "数据合规风险",
  "subtype": "跨境数据传输",
  "severity": "high",
  "score": 85.0,
  "confidence": 0.91,
  "evidence": "数据存储在境外服务器，未向用户明确告知。",
  "suggestion": "建议建立数据出境评估与用户告知机制。",
  "legal_basis": ["个人信息保护法", "数据安全法"],
  "trigger_signal_matched": ["境外服务器", "未明确告知"],
  "related_category_hint": ["地缘博弈风险"],
  "lifecycle_stage_hint": "数据运营",
  "cross_agent_disagreement": false,
  "needs_human_review": false,
  "revision_reason": null
}
```

### 重点字段解释

- `category`
  一级风险类别
- `subtype`
  二级风险子类
- `severity`
  严重程度：`low` / `medium` / `high`
- `score`
  单条风险分数
- `confidence`
  单条风险置信度
- `evidence`
  原文证据
- `suggestion`
  治理建议
- `legal_basis`
  法规依据
- `needs_human_review`
  是否建议人工复核

## 10. 置信度结构

`report.confidence_breakdown` 的结构如下：

```json
{
  "confidence_score": 0.79,
  "signal_strength": 0.86,
  "robustness": 0.75,
  "cross_agent_consistency": 0.77,
  "disagreement_flags": [],
  "gate_flags": {
    "privacy_legality_redline": true,
    "ethics_fairness_redline": false,
    "triggered_reasons": ["data_compliance-chunk-000:触发隐私/合法性红线"]
  },
  "summary": "证据较强，但存在隐私/合法性红线。"
}
```

### 用途

- 展示总体置信度
- 展示置信度由哪些部分组成
- 展示是否触发治理红线

## 11. debug 中间过程结构

`data.debug` 用于展示多 agent 的执行过程。

其核心结构如下：

```json
{
  "workflow_backend": "langgraph",
  "pipeline_state": {
    "chunks": [],
    "triage_results": [],
    "domain_findings": {},
    "reflection_result": null,
    "revised_findings": {},
    "confidence_result": null,
    "verification_result": null,
    "final_findings": [],
    "risk_report": {}
  }
}
```

### 前端如果要展示 agent 过程，重点读取这些字段

- `pipeline_state.chunks`
- `pipeline_state.triage_results`
- `pipeline_state.domain_findings`
- `pipeline_state.reflection_result`
- `pipeline_state.revised_findings`
- `pipeline_state.confidence_result`
- `pipeline_state.verification_result`
- `pipeline_state.final_findings`

## 12. 各阶段字段说明

### 12.1 `chunks`

文本切块结果，表示原始材料被拆成了哪些块。

```json
[
  {
    "chunk_id": "chunk-000",
    "text": "本公司收集用户面部识别数据用于广告推送...",
    "source_type": "document",
    "source_name": null,
    "page": null,
    "paragraph_index": 0
  }
]
```

### 12.2 `triage_results`

初评结果，表示哪些块被认为与风险相关。

```json
[
  {
    "chunk_id": "chunk-000",
    "text": "本公司收集用户面部识别数据用于广告推送...",
    "candidate_risk_types": ["数据合规风险", "科技伦理风险"],
    "relevance_score": 0.92,
    "rationale": "涉及敏感个人信息采集、告知不足与境外存储。"
  }
]
```

### 12.3 `domain_findings`

五个专职 agent 的原始分析结果。结构是对象，key 为风险类别，value 为风险数组。

```json
{
  "算法安全风险": [],
  "数据合规风险": [],
  "科技伦理风险": [],
  "知识产权风险": [],
  "地缘博弈风险": []
}
```

### 12.4 `reflection_result`

反思阶段的结果，用于指出遗漏、错分或严重度问题。

```json
{
  "issues": [
    {
      "issue_id": "issue-001",
      "issue_type": "missing_risk",
      "category": "科技伦理风险",
      "chunk_id": "chunk-000",
      "related_finding_id": null,
      "description": "可能遗漏透明度不足问题",
      "suggested_fix": "补充伦理风险 finding",
      "suggested_category": "科技伦理风险",
      "suggested_subtype": "透明度不足",
      "suggested_severity": "medium",
      "confidence": 0.74
    }
  ],
  "overall_confidence": 0.78,
  "summary": "存在轻度遗漏，建议补充伦理类风险。"
}
```

### 12.5 `revised_findings`

修正后的 findings，结构和 `domain_findings` 类似，适合前端做“修正前 / 修正后”对比。

### 12.6 `confidence_result`

独立置信度评估结果，通常与 `report.confidence_breakdown` 对应。

### 12.7 `verification_result`

核验阶段结果：

```json
{
  "verdict": "accept",
  "confidence": 0.83,
  "accepted_finding_ids": ["finding-001"],
  "rejected_finding_ids": [],
  "needs_human_review": false,
  "notes": "修正结果基本合理，可接受。"
}
```

## 13. 只返回正式报告的接口

### 请求

```http
POST /analyze/report-only
Content-Type: application/json
```

请求体与 `/analyze` 相同。

### 返回结构

```json
{
  "success": true,
  "message": "ok",
  "workflow_backend": "langgraph",
  "data": {
    "report": { "...": "..." }
  }
}
```

### 适合场景

- 前端只做结果页
- 不展示中间 agent 过程
- 希望简化前端逻辑

## 14. 获取历史报告接口

### 请求

```http
GET /reports/{company}
```

例如：

```bash
curl http://127.0.0.1:8000/reports/测试企业
```

### 返回示例

```json
{
  "success": true,
  "message": "ok",
  "workflow_backend": null,
  "data": {
    "report": { "...": "..." }
  }
}
```

### 注意

- 该接口依赖历史存储已启用
- 如果没有历史记录，会返回 404

## 15. 前端调用示例

### fetch 示例

```javascript
async function analyzeRisk() {
  const resp = await fetch("http://127.0.0.1:8000/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      input_type: "document",
      company_name: "测试企业",
      raw_text: "本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。",
      llm_mode: "llm"
    })
  });

  const result = await resp.json();
  return result;
}
```

## 16. 前端优先接哪些字段

### 如果前端先做主结果页

优先接这些字段：

- `data.report.overall_risk_level`
- `data.report.overall_score`
- `data.report.confidence`
- `data.report.risk_details`
- `data.report.top3_risks`
- `data.report.human_review_items`

### 如果前端要做“agent 过程展示页”

再接这些字段：

- `data.debug.pipeline_state.triage_results`
- `data.debug.pipeline_state.domain_findings`
- `data.debug.pipeline_state.reflection_result`
- `data.debug.pipeline_state.revised_findings`
- `data.debug.pipeline_state.confidence_result`
- `data.debug.pipeline_state.verification_result`

## 17. 常见报错说明

### 400 Bad Request

通常是请求参数不符合要求，例如：

- `llm_mode=llm` 但没有配置 LLM 环境变量
- `input_type` 不合法

### 404 Not Found

通常是：

- 调用了不存在的接口
- 请求的历史报告不存在

### 500 Internal Server Error

通常是：

- pipeline 执行异常
- 后端配置不完整
- 模型或采集器运行异常

## 18. 跨域说明

如果别人的前端和你的后端不是同一个域名，浏览器可能会遇到 CORS 跨域问题。

也就是说：

- 本地静态页面直接调本地接口，一般没问题
- 独立部署在其他地址的前端，可能需要后端额外开启 CORS

如果联调时报跨域错误，需要在后端补充 CORS 配置。

## 19. 推荐前端页面拆分

前端可以按下面几块页面或模块来接：

- 健康状态区
  使用 `/health`
- 输入页
  提交到 `/analyze`
- 结果总览页
  读取 `data.report`
- Agent 过程页
  读取 `data.debug.pipeline_state`
- 历史报告页
  使用 `/reports/{company}`

## 20. 接口代码位置

后端接口实现代码在：

- [risk_himate/app/api/server.py](/Users/belle/projects/挑战杯/risk_himate/app/api/server.py)
- [risk_himate/app/api/api_schemas.py](/Users/belle/projects/挑战杯/risk_himate/app/api/api_schemas.py)

核心数据结构定义在：

- [risk_himate/app/core/schemas.py](/Users/belle/projects/挑战杯/risk_himate/app/core/schemas.py)
