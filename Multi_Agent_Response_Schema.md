# Multi-Agent 科创企业风险识别系统 Response Schema

## 1. 整体信息流

    Input Document
          ↓
    Prepare Agent
          ↓
    Triage Agent
          ↓
    Parallel Domain Agents
          ↓
    Finding Aggregation
          ↓
    Reflection Agent
          ↓
    Revision Agent
          ↓
    Risk Scoring Engine
          ↓
    Confidence Module
          ↓
    Verifier Agent
          ↓
    Final Report

核心目标：

建立：

`Evidence → Finding → Revision → Score → Decision`

完整可追溯链路。

------------------------------------------------------------------------

# 2. Prepare Agent Response

## 职责

-   企业材料标准化
-   文档解析
-   Chunk切分
-   Metadata构建

## Response Schema

``` json
{
  "analysis_id": "AI_COMPANY_001",

  "company_profile": {
    "company_name": "",
    "industry": "",
    "development_stage": "",
    "business_area": []
  },

  "source_documents": [],

  "chunks": [
    {
      "chunk_id": "",
      "text": "",
      "metadata": {
        "source": "",
        "page": "",
        "lifecycle_stage": ""
      }
    }
  ]
}
```

------------------------------------------------------------------------

# 3. Triage Agent Response

## 职责

风险相关性筛选。

注意：

Triage 不输出最终风险判断，只负责召回。

## Response Schema

``` json
{
  "triage_results": [
    {
      "chunk_id": "C001",

      "domain_scores": {
        "algorithm_safety": 0.8,
        "data_compliance": 0.7,
        "tech_ethics": 0.3,
        "ip_risk": 0.1,
        "geopolitical_risk": 0.6
      },

      "retrieval_level": {
        "priority": "high",
        "reason": ""
      },

      "evidence_spans": []
    }
  ]
}
```

------------------------------------------------------------------------

# 4. Domain Agent Response

五类专业 Agent：

-   AlgorithmSafetyAgent
-   DataComplianceAgent
-   TechEthicsAgent
-   IPRiskAgent
-   GeopoliticalRiskAgent

统一输出：

`RiskFinding`

``` json
{
  "finding_id": "F001",

  "agent_type": "DataComplianceAgent",

  "risk_category": "data_compliance",

  "risk_subcategory": "cross_border_data_transfer",

  "risk_exists": true,

  "severity": {
    "level": "high",
    "score": 85,
    "basis": ""
  },

  "evidence": [
    {
      "evidence_id": "E001",
      "chunk_id": "C001",
      "quote": "",
      "source": ""
    }
  ],

  "reasoning": "",

  "regulation_reference": [],

  "risk_indicator_mapping": {
    "indicator": "",
    "score": 85
  },

  "related_categories": [],

  "confidence": 0.85
}
```

------------------------------------------------------------------------

# 5. Finding Aggregation Response

## 职责

-   Finding去重
-   冲突解决
-   风险融合
-   建立风险关系

``` json
{
  "aggregated_findings": [
    {
      "finding_id": "AF001",

      "primary_category": "",

      "supporting_agents": [],

      "merged_evidence": [],

      "severity": {},

      "risk_interaction": {
        "exists": true,
        "interaction_type": "risk_amplification",
        "related_risk": ""
      }
    }
  ]
}
```

------------------------------------------------------------------------

# 6. Reflection Agent Response

职责：

-   查漏判
-   查错分
-   查严重度

``` json
{
  "reflection_result": {

    "issues": [
      {
        "issue_id": "I001",

        "finding_id": "AF001",

        "issue_type": "",

        "description": "",

        "suggested_action": ""
      }
    ],

    "coverage_analysis": {

      "missed_chunks": [],

      "missing_domains": []
    }
  }
}
```

------------------------------------------------------------------------

# 7. Revision Agent Response

必须保留修改轨迹。

``` json
{
  "revision_result": {

    "updated_findings": [],

    "new_findings": [],

    "revision_trace": [
      {
        "issue_id": "",

        "resolved": true,

        "modification": ""
      }
    ]
  }
}
```

------------------------------------------------------------------------

# 8. Risk Scoring Engine Response

作用：

将风险 Finding 转化为企业综合风险评分。

流程：

    Finding
     ↓
    Risk Indicator Score
     ↓
    AHP + Entropy Weight
     ↓
    Choquet Integral
     ↓
    Overall Risk Score

``` json
{
  "risk_score": {

    "indicator_scores": {},

    "weights": {},

    "interaction_effects": [],

    "overall_score": 75,

    "risk_level": "medium"
  }
}
```

------------------------------------------------------------------------

# 9. Confidence Module Response

职责：

评价结果可信程度。

不负责风险高低判断。

``` json
{
  "confidence": {

    "overall": 0.86,

    "components": {

      "evidence_strength": 0.9,

      "source_reliability": 0.85,

      "agent_consistency": 0.8,

      "revision_stability": 0.88
    },

    "uncertainty_sources": []
  }
}
```

------------------------------------------------------------------------

# 10. Redline Gate Response

独立治理规则。

``` json
{
  "redline_result": {

    "triggered": true,

    "type": "privacy_legality",

    "rule_id": "",

    "evidence_ids": [],

    "trigger_reason": "",

    "action": "mandatory_human_review"
  }
}
```

------------------------------------------------------------------------

# 11. Verifier Agent Response

最终质量审核。

``` json
{
  "verification": {

    "decision": "accept",

    "checks": {

      "reflection_resolved": true,

      "evidence_supported": true,

      "confidence_sufficient": true,

      "redline_checked": true
    },

    "human_review_required": false
  }
}
```

------------------------------------------------------------------------

# 12. Final Report Response

``` json
{
  "company": "",

  "overall_assessment": {

    "risk_score": 70,

    "risk_level": "medium",

    "confidence": 0.86
  },

  "top_risks": [],

  "risk_trace": [
    "Triage",
    "DomainAgent",
    "Reflection",
    "Revision",
    "Verification"
  ],

  "human_review_items": []
}
```

------------------------------------------------------------------------

# Summary

最终系统形成：

    Raw Text
     ↓
    Chunk
     ↓
    TriageResult
     ↓
    RiskFinding
     ↓
    AggregatedFinding
     ↓
    ReflectionIssue
     ↓
    RevisionTrace
     ↓
    RiskScore
     ↓
    Confidence
     ↓
    Verification
     ↓
    FinalReport

每条风险均具备：

`Evidence → Agent → Revision → Score → Decision`

完整生命周期。
