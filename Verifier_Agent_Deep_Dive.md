# Verifier Agent 详尽说明

这份文档用于详细说明 Risk-HiMATE 中 `Verifier Agent` 的功能定位、输入输出、内部判定逻辑、与其他模块的关系，以及一个完整案例。

对应代码位置：

- [risk_himate/app/agents/verifier_agent.py](/Users/belle/projects/挑战杯/risk_himate/app/agents/verifier_agent.py)
- [risk_himate/app/core/schemas.py](/Users/belle/projects/挑战杯/risk_himate/app/core/schemas.py)
- [risk_himate/app/workflows/pipeline.py](/Users/belle/projects/挑战杯/risk_himate/app/workflows/pipeline.py)
- [risk_himate/app/llm/prompts/verifier.md](/Users/belle/projects/挑战杯/risk_himate/app/llm/prompts/verifier.md)

---

## 1. 一句话定义

`Verifier Agent` 是整个多智能体风险识别流程中的**最终质检员**。

它不负责第一轮“发现风险”，而负责检查：

1. 前面 `Reflection Agent` 提出的问题是否真的被 `Revision Agent` 解决
2. 修正后的结果是否引入了新的错误
3. 当前结果是否足够可靠，能不能进入最终报告

所以它的核心职责不是“分析材料”，而是“审核分析结果”。

---

## 2. 它在整个工作流里的位置

在当前实现中，Verifier 位于以下阶段之后：

1. `Triage`
2. `Domain Agents`
3. `Reflection`
4. `Revision`
5. `Confidence`
6. `Verifier`
7. `Human Review / Finalize`

对应工作流片段在 [pipeline.py](/Users/belle/projects/挑战杯/risk_himate/app/workflows/pipeline.py) 中可以概括成：

- `reflection` 阶段输出 `reflection_result`
- `revision` 阶段输出 `revised_findings`
- `confidence` 阶段输出 `confidence_result`
- `verifier` 阶段输出 `verification_result`
- 如果 `verification_result.needs_human_review == true`，流程进入 `human_review`
- 否则直接进入 `finalize`

这一点很重要，因为 Verifier 不单独存在，它是前面几个阶段的**汇总性审核节点**。

---

## 3. 为什么必须要有 Verifier Agent

如果没有 Verifier，多智能体系统可能会出现几个问题：

### 3.1 Reflection 提出问题，但 Revision 没真正修好

例如：

- Reflection 说“漏掉了一条科技伦理风险”
- Revision 虽然新增了一条 finding
- 但新增 finding 的证据不足，或者子类仍然不对

如果没有 Verifier，这条“修正后的错误”会直接进入最终报告。

### 3.2 修正过度

例如：

- 原本只是一个中风险
- Revision 为了“显得修得充分”，把它改成了高风险
- 但原文证据根本不足以支持高风险

Verifier 的作用，就是防止“越修越错”。

### 3.3 系统需要保留“回退原始结果”的能力

当前实现中，Verifier 不只是“同意/不同意”，还允许：

- `accept`
- `partial_accept`
- `revert_to_original`

也就是说：

> 如果 revision 后的结果不如原始 findings，系统是允许回退到第一轮结果的。

这一点是非常关键的工程设计。

---

## 4. Verifier Agent 的输入

从代码和 prompt 看，Verifier Agent 的输入主要有 4 类。

---

### 4.1 原始 findings

来源：

- `state.domain_findings`

它表示五个专职风险 Agent 在第一轮 domain analysis 里产出的原始风险判断。

在代码里，Verifier 会先把它拍平成列表：

```python
original_findings = flatten_findings(state.domain_findings)
```

作用：

- 作为“原始版本”的参考
- 如果 verifier 最终给出 `revert_to_original`，系统就会回到这份结果

---

### 4.2 reflection 提出的问题

来源：

- `state.reflection_result`

如果有反思结果，Verifier 取其中的：

```python
issues = state.reflection_result.issues if state.reflection_result else []
```

这些 `issues` 就是 Verifier 的重点审核对象。

它们通常分三类：

- `missing_risk`
- `misclassified`
- `severity_issue`

也就是说，Verifier 并不是抽象地“看看修得行不行”，而是具体检查：

> reflection 提出的这些问题，revision 到底解决了没有。

---

### 4.3 revised findings

来源：

- `state.revised_findings`

代码中会同样拍平成列表：

```python
revised_findings = flatten_findings(state.revised_findings)
```

这就是 Verifier 当前主要审核的对象。

可以理解成：

- `original_findings` 是原始版本
- `revised_findings` 是修正版本
- `issues` 是审核清单

Verifier 的任务就是：  
拿着审核清单，去看修正版本是否真的比原始版本更好。

---

### 4.4 独立置信度结果

来源：

- `state.confidence_result`

也就是前一阶段 `Confidence Evaluator` 的输出。

这个结果里有：

- `confidence_score`
- `signal_strength`
- `robustness`
- `cross_agent_consistency`
- `gate_flags`

Verifier 并不会重新计算这些值，而是把它们作为审核判断的重要依据。

---

## 5. Verifier 的输出

Verifier 输出的结构定义在 [schemas.py](/Users/belle/projects/挑战杯/risk_himate/app/core/schemas.py)：

```python
class VerificationResult(BaseModel):
    verdict: Literal["accept", "partial_accept", "revert_to_original"]
    confidence: float
    accepted_finding_ids: list[str]
    rejected_finding_ids: list[str]
    needs_human_review: bool
    notes: str
```

下面逐个解释。

---

### 5.1 `verdict`

最终裁决，只有三种值：

- `accept`
- `partial_accept`
- `revert_to_original`

含义如下。

#### `accept`

表示：

- revision 基本解决了 reflection 提出的主要问题
- 没有明显引入新的错误
- 当前结果可以作为最终版本使用

#### `partial_accept`

表示：

- revision 解决了一部分问题
- 但仍有部分问题没解决，或者有残留风险
- 当前结果可以参考，但最好保留人工复核

#### `revert_to_original`

表示：

- 修正后的结果不够好
- 问题没修好，或者修坏了
- 应该回退到第一轮的原始 findings

这一裁决会直接影响最终报告使用哪一版 findings。

在 [pipeline.py](/Users/belle/projects/挑战杯/risk_himate/app/workflows/pipeline.py) 中：

```python
if state.verification_result.verdict == "revert_to_original":
    return flatten_findings(state.domain_findings)
return flatten_findings(state.revised_findings)
```

所以 `verdict` 不是展示字段，而是真正影响后续系统行为的控制信号。

---

### 5.2 `confidence`

这是 Verifier 对自身裁决的置信度。

注意，它和前面的 `confidence_score` 不是一个东西：

- `confidence_score`：风险识别结果本身稳不稳
- `verification_result.confidence`：Verifier 对自己这次审核裁决有多确定

当前规则版中，它的计算方式是：

```python
confidence = round(min(0.98, max(0.0, 0.5 * resolution_rate + 0.5 * confidence_score)), 2)
```

也就是：

- 一半看 `resolution_rate`
- 一半看 `confidence_score`

再截断到 `0.00 ~ 0.98` 之间。

---

### 5.3 `accepted_finding_ids`

表示哪些 finding 被 Verifier 接受。

它有两个作用：

1. 系统内部跟踪哪些风险结论通过了审核
2. 前端可以展示“已核验通过”的风险条目

---

### 5.4 `rejected_finding_ids`

表示哪些 finding 没通过 Verifier 审核。

这个字段的意义在于：

- 告诉系统哪些修正后的结论不能被完全采纳
- 便于后续调试定位具体问题

---

### 5.5 `needs_human_review`

这是 Verifier 非常重要的一个输出字段。

它表示：

> 当前结果是否建议人工复核。

当前规则版的判定条件是：

```python
needs_human_review = confidence_score < 0.6 or has_cross_agent_disagreement or gate_triggered
```

也就是说，只要满足下面任意一条，就会建议人工复核：

- 置信度偏低
- 存在跨 agent 分歧
- 触发了隐私/合法性或伦理/公平性红线

---

### 5.6 `notes`

这是 Verifier 的文字说明。

它会解释：

- 为什么 accept
- 为什么 partial_accept
- 为什么 revert
- 当前 confidence_score 是多少
- 是否触发了 gate_flags

这个字段非常适合前端直接展示成“审核意见”。

---

## 6. Verifier Agent 的规则版判定逻辑

下面是当前代码中最值得讲清楚的部分。

---

### 6.1 第一步：计算 reflection 问题解决了多少

代码里先遍历 `issues`，看每个问题在 `revised_findings` 中是否得到解决。

#### 对 `missing_risk`

Verifier 会检查：

- revised findings 中是否出现了对应 `chunk_id`
- 且 category 与 `suggested_category` 一致

简化理解：

> Reflection 说你漏了一类风险，那 revision 至少要在对应 chunk 上补出这一类风险，才算解决。

#### 对 `misclassified`

Verifier 会找到对应的 finding，看：

- `matched.subtype == issue.suggested_subtype`

也就是：

> Reflection 说你分错子类，那 revision 必须把 subtype 改成建议子类。

#### 对 `severity_issue`

Verifier 会看：

- `matched.severity == issue.suggested_severity`

也就是：

> Reflection 说严重度不合理，那 revision 必须把严重度调到建议值。

---

### 6.2 第二步：计算 `resolution_rate`

```python
resolution_rate = 1.0 if not issues else resolved / len(issues)
```

含义：

- 如果 reflection 没提任何问题，默认解决率 `1.0`
- 否则就是“解决了多少个问题 / 总共多少个问题”

这是 Verifier 做出 `accept / partial_accept / revert` 的第一核心指标。

---

### 6.3 第三步：结合置信度算出 Verifier 自身 confidence

```python
confidence_score = confidence_result.confidence_score if confidence_result else 0.7
confidence = round(min(0.98, max(0.0, 0.5 * resolution_rate + 0.5 * confidence_score)), 2)
```

这说明当前 Verifier 的自信程度并不是完全主观的，它同时依赖：

- 问题解决率 `resolution_rate`
- 前面独立置信度模块给出的 `confidence_score`

---

### 6.4 第四步：先给一个基础 verdict

代码逻辑：

```python
if resolution_rate >= 0.85:
    verdict = "accept"
elif resolution_rate >= 0.4:
    verdict = "partial_accept"
else:
    verdict = "revert_to_original"
```

也就是：

- `>= 0.85`：大部分问题已解决，初判为 `accept`
- `0.4 ~ 0.85`：只解决了一部分，初判为 `partial_accept`
- `< 0.4`：问题解决得太少，初判为 `revert_to_original`

---

### 6.5 第五步：再根据红线和置信度做二次修正

代码逻辑：

```python
if verdict == "accept" and confidence_score < 0.55:
    verdict = "partial_accept"
if verdict == "accept" and gate_triggered:
    verdict = "partial_accept"
if verdict == "partial_accept" and confidence_score < 0.35 and resolution_rate < 0.55:
    verdict = "revert_to_original"
```

这一步说明：

- 即使问题解决率高，也不代表一定能 `accept`
- 如果置信度太低，或者触发红线，仍然会降级成 `partial_accept`
- 如果本来就只是 `partial_accept`，同时置信度又很差，那会继续降级成 `revert_to_original`

这一层就是 Verifier 和 Confidence / Gate 联动的关键。

---

## 7. Verifier 与 Human Review 的关系

Verifier 的另一个关键功能，是决定是否进入人工复核路径。

在 [pipeline.py](/Users/belle/projects/挑战杯/risk_himate/app/workflows/pipeline.py) 中：

```python
if state.verification_result and state.verification_result.needs_human_review:
    return "human_review"
return "finalize"
```

也就是说：

- 如果 Verifier 判断需要人工复核，流程不直接 finalize
- 系统会先标记进入 `human_review`

因此 Verifier 不只是一个“评分器”，它还是整个流程中的**路由器**。

---

## 8. LLM 版 Verifier 和规则版 Verifier

当前 Verifier 实现支持两种工作方式。

---

### 8.1 规则版

入口：

```python
_verify_with_rules(state)
```

特点：

- 稳定
- 可解释
- 不依赖外部模型
- 非常适合 demo、测试和答辩时说明逻辑

---

### 8.2 LLM 版

入口：

```python
_verify_with_llm(state)
```

它会把下面这些信息打包进 prompt：

- `confidence_result`
- `original_findings`
- `reflection_issues`
- `revised_findings`

然后要求模型只返回固定 JSON：

```json
{
  "verdict": "accept|partial_accept|revert_to_original",
  "confidence": 0.85,
  "accepted_finding_ids": ["id1"],
  "rejected_finding_ids": ["id2"],
  "needs_human_review": false,
  "notes": "说明"
}
```

如果 LLM 出错，系统会自动回退到规则版：

```python
if self.llm_client and self.llm_client.is_configured():
    try:
        return self._verify_with_llm(state)
    except Exception:
        return self._verify_with_rules(state)
return self._verify_with_rules(state)
```

所以当前设计是：

- LLM 优先
- 规则兜底

---

## 9. 完整案例

下面给一个尽量贴近当前项目设定的完整例子。

---

### 9.1 原始输入材料

```text
本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。
```

---

### 9.2 第一轮 Domain Agent 输出

假设第一轮输出如下：

```json
{
  "数据合规风险": [
    {
      "finding_id": "data-001",
      "category": "数据合规风险",
      "subtype": "数据采集合规",
      "exists": true,
      "severity": "medium",
      "confidence": 0.86,
      "evidence": "本公司收集用户面部识别数据用于广告推送",
      "evidence_chunk_ids": ["chunk-000"],
      "rationale": "涉及敏感个人信息采集，但严重度暂定为中。",
      "legal_basis": ["个人信息保护法"],
      "trigger_signal_matched": ["面部识别数据"],
      "related_category_hint": []
    }
  ]
}
```

这里的问题是：

- 识别到人脸数据采集了
- 但没有把“境外服务器”和“未明确告知”充分纳入
- 严重度可能偏低

---

### 9.3 Reflection 输出

Reflection 可能给出：

```json
{
  "issues": [
    {
      "issue_id": "issue-001",
      "issue_type": "severity_issue",
      "related_finding_id": "data-001",
      "chunk_id": "chunk-000",
      "description": "该风险同时涉及敏感个人信息采集、境外存储和未明确告知，严重度可能偏低。",
      "suggested_fix": "将严重度调整为 high。",
      "suggested_category": "数据合规风险",
      "suggested_subtype": "数据共享与出境",
      "suggested_severity": "high",
      "confidence": 0.88
    },
    {
      "issue_id": "issue-002",
      "issue_type": "missing_risk",
      "category": "科技伦理风险",
      "chunk_id": "chunk-000",
      "description": "可能遗漏透明度不足问题。",
      "suggested_fix": "补充科技伦理风险 finding。",
      "suggested_category": "科技伦理风险",
      "suggested_subtype": "模型迭代变更披露",
      "suggested_severity": "medium",
      "confidence": 0.62
    }
  ],
  "overall_confidence": 0.79,
  "summary": "存在严重度低估和伦理风险遗漏。"
}
```

---

### 9.4 Revision 输出

Revision 之后，系统可能得到：

```json
{
  "数据合规风险": [
    {
      "finding_id": "data-001",
      "category": "数据合规风险",
      "subtype": "数据共享与出境",
      "exists": true,
      "severity": "high",
      "confidence": 0.91,
      "evidence": "数据存储在境外服务器，未向用户明确告知。",
      "evidence_chunk_ids": ["chunk-000"],
      "rationale": "同时涉及敏感个人信息、境外存储和告知不足。",
      "legal_basis": ["个人信息保护法", "数据安全法"],
      "trigger_signal_matched": ["境外服务器", "未明确告知"],
      "related_category_hint": ["地缘博弈风险"],
      "revision_reason": "根据 reflection 调整严重度并补充跨境数据传输特征。"
    }
  ],
  "科技伦理风险": [
    {
      "finding_id": "ethics-001",
      "category": "科技伦理风险",
      "subtype": "单样本决策可追溯",
      "exists": true,
      "severity": "medium",
      "confidence": 0.58,
      "evidence": "未向用户明确告知。",
      "evidence_chunk_ids": ["chunk-000"],
      "rationale": "存在一定透明度不足迹象。",
      "legal_basis": ["新一代人工智能伦理规范"],
      "trigger_signal_matched": ["未明确告知"],
      "related_category_hint": [],
      "revision_reason": "根据 reflection 补充伦理类风险。"
    }
  ]
}
```

---

### 9.5 独立置信度结果

```json
{
  "confidence_score": 0.72,
  "signal_strength": 0.88,
  "robustness": 0.69,
  "cross_agent_consistency": 0.61,
  "disagreement_flags": [],
  "gate_flags": {
    "privacy_legality_redline": true,
    "ethics_fairness_redline": false,
    "triggered_reasons": [
      "data_compliance-chunk-000:触发隐私/合法性红线"
    ]
  },
  "summary": "数据合规风险证据较强，但触发隐私/合法性红线。"
}
```

---

### 9.6 Verifier 如何处理这个案例

#### 对 `issue-001`：severity_issue

Reflection 建议：

- `suggested_severity = high`

Revision 后：

- `data-001.severity = high`

所以这条问题被视为已解决。

#### 对 `issue-002`：missing_risk

Reflection 说遗漏了科技伦理风险。

Revision 后：

- 确实新增了一条 `科技伦理风险`
- `chunk_id` 也匹配 `chunk-000`

所以这条也被视为已解决。

#### 因此：

- `resolved = 2`
- `len(issues) = 2`
- `resolution_rate = 1.0`

基础 verdict 会先被判成：

```text
accept
```

但是注意：

- `gate_flags.privacy_legality_redline = true`

根据代码逻辑：

```python
if verdict == "accept" and gate_triggered:
    verdict = "partial_accept"
```

所以最终 verdict 会从 `accept` 降级成：

```text
partial_accept
```

这非常符合系统设计思想：

> 即使修正得不错，只要触发红线，也不应该过于乐观地直接完全接受。

---

### 9.7 最终可能输出的 VerificationResult

```json
{
  "verdict": "partial_accept",
  "confidence": 0.86,
  "accepted_finding_ids": ["data-001", "ethics-001"],
  "rejected_finding_ids": [],
  "needs_human_review": true,
  "notes": "Revisions addressed part of the reflected issues. confidence_score=0.72. gate_flags=data_compliance-chunk-000:触发隐私/合法性红线."
}
```

这里的逻辑是：

- 问题解决率很高
- 置信度也不低
- 但存在隐私/合法性红线
- 所以不能完全 accept
- 同时需要人工复核

---

## 10. 另一个“回退原始结果”的例子

假设 Reflection 提出 3 个问题，但 Revision 只修好了 1 个：

- `resolved = 1`
- `issues = 3`
- `resolution_rate = 0.33`

那么基础 verdict 就会变成：

```text
revert_to_original
```

这时候系统最终就不会采用修正后的 findings，而是直接回到第一轮原始 findings。

这正是 Verifier 的关键价值之一：

> 它让系统有能力承认“这次修得不行”，而不是硬着头皮把错误修正版输出出去。

---

## 11. 对外介绍时可以怎么总结

如果你要对队友、老师或评委介绍，可以用下面这段总结：

> Verifier Agent 是整个多智能体风险识别流程中的最终质检节点。它的输入包括第一轮专职 Agent 的原始结果、Reflection 提出的问题、Revision 修正后的结果以及独立置信度评估结果。它的任务不是重新识别风险，而是判断修正是否真正解决了前面发现的问题，是否引入了新的错误，以及当前结果是否足够可靠。最终它输出一个结构化裁决，包括 accept、partial_accept 或 revert_to_original，同时给出置信度、通过/未通过的 finding 列表，以及是否需要人工复核。它的作用是保证系统最终报告不是“前面改完就直接输出”，而是经过独立审核后才进入最终交付。 

---

## 12. 最适合放进 PPT 的简化版

### Verifier Agent

- **角色**：最终质检员，不负责找风险，负责审结果  
- **输入**：
  - 原始 findings
  - reflection issues
  - revised findings
  - confidence result
- **检查内容**：
  - 问题是否真正被修正
  - 修正是否引入新错误
  - 是否触发红线或低置信度
- **输出**：
  - `accept`
  - `partial_accept`
  - `revert_to_original`
  - `needs_human_review`
- **价值**：
  - 保证最终报告经过独立复核
  - 支持“修不好就回退原始结果”

