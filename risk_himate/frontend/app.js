const state = {
  health: null,
  reportPayload: null,
};

const $ = (selector) => document.querySelector(selector);

function setHealthBadge(text, kind) {
  const badge = $("#health-badge");
  badge.textContent = text;
  badge.className = `status-badge ${kind}`;
}

async function fetchHealth() {
  setHealthBadge("检查中", "status-pending");
  try {
    const response = await fetch("/health");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    state.health = data;
    $("#health-workflow").textContent = data.workflow_backend;
    $("#health-llm").textContent = data.llm_available ? "已连接" : "未配置";
    $("#health-collector").textContent = data.collector_mode;
    $("#health-history").textContent = data.history_store;
    setHealthBadge("在线", "status-ok");
  } catch (error) {
    $("#health-workflow").textContent = "-";
    $("#health-llm").textContent = "-";
    $("#health-collector").textContent = "-";
    $("#health-history").textContent = "-";
    setHealthBadge("离线", "status-fail");
    console.error(error);
  }
}

function toggleInputMode(nextType) {
  $("#input-type").value = nextType;
  document.querySelectorAll(".toggle").forEach((button) => {
    button.classList.toggle("active", button.dataset.inputType === nextType);
  });
  const isCompanyMode = nextType === "company_name";
  $("#raw-text-field").classList.toggle("field-hidden", isCompanyMode);
  $("#metadata-field").classList.toggle("field-hidden", !isCompanyMode);
}

function loadDemo() {
  $("#company-name").value = "测试企业";
  $("#raw-text").value = "本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。";
  $("#llm-mode").value = "auto";
  $("#report-only").checked = false;
  toggleInputMode("document");
}

function showError(message) {
  $("#error-state").classList.remove("hidden");
  $("#error-message").textContent = message;
}

function clearError() {
  $("#error-state").classList.add("hidden");
  $("#error-message").textContent = "";
}

function showLoading(visible) {
  $("#loading-state").classList.toggle("hidden", !visible);
}

function toPercent(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function severityClass(severity) {
  return ["high", "medium", "low"].includes(severity) ? severity : "";
}

function formatLevel(level) {
  const map = {
    high: "高风险",
    medium: "中风险",
    low: "低风险",
  };
  return map[level] || level || "-";
}

function renderTopRisks(risks) {
  const container = $("#top-risks");
  if (!risks?.length) {
    container.innerHTML = "<p class='muted'>暂无风险明细。</p>";
    return;
  }
  container.innerHTML = risks
    .map(
      (risk) => `
        <article class="risk-card">
          <h3>${risk.category} / ${risk.subtype}</h3>
          <div class="risk-meta">
            <span class="pill ${severityClass(risk.severity)}">${formatLevel(risk.severity)}</span>
            <span class="pill">分数 ${risk.score}</span>
            <span class="pill">置信度 ${risk.confidence}</span>
          </div>
          <p>${risk.suggestion || "暂无建议。"}</p>
          <div class="mini-meta">
            ${(risk.legal_basis || []).map((item) => `<span class="pill">${item}</span>`).join("")}
          </div>
        </article>
      `,
    )
    .join("");
}

function renderConfidence(report) {
  const breakdown = report.confidence_breakdown;
  const container = $("#confidence-breakdown");
  const gateContainer = $("#gate-flags");
  if (!breakdown) {
    container.innerHTML = "<p class='muted'>当前返回未包含置信度拆解。</p>";
    gateContainer.innerHTML = "";
    return;
  }

  const items = [
    ["总体置信度", report.confidence],
    ["信号强度", breakdown.signal_strength],
    ["鲁棒性", breakdown.robustness],
    ["跨 Agent 一致性", breakdown.cross_agent_consistency],
  ];
  container.innerHTML = items
    .map(
      ([label, value]) => `
        <div class="confidence-item">
          <div class="confidence-head">
            <span>${label}</span>
            <strong>${toPercent(value)}</strong>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${toPercent(value)}"></div>
          </div>
        </div>
      `,
    )
    .join("");

  const gateFlags = breakdown.gate_flags || {};
  const reasons = gateFlags.triggered_reasons || [];
  gateContainer.innerHTML = `
    <div class="gate-item ${gateFlags.privacy_legality_redline ? "alert" : ""}">
      隐私 / 合法性红线：${gateFlags.privacy_legality_redline ? "已触发" : "未触发"}
    </div>
    <div class="gate-item ${gateFlags.ethics_fairness_redline ? "alert" : ""}">
      伦理 / 公平性红线：${gateFlags.ethics_fairness_redline ? "已触发" : "未触发"}
    </div>
    ${reasons.length ? `<div class="gate-item"><strong>触发原因</strong><div>${reasons.join("<br/>")}</div></div>` : ""}
  `;
}

function renderLifecycle(groups) {
  const container = $("#lifecycle-groups");
  if (!groups?.length) {
    container.innerHTML = "<p class='muted'>暂无生命周期分组。</p>";
    return;
  }
  container.innerHTML = groups
    .map(
      (group) => `
        <article class="lifecycle-card">
          <div>
            <h3>${group.stage}</h3>
            <p>${group.summary}</p>
          </div>
          <div class="subrisk-list">
            ${(group.risk_details || [])
              .map(
                (detail) => `
                  <div class="subrisk-item">
                    <strong>${detail.category} / ${detail.subtype}</strong>
                    <p>严重度：${formatLevel(detail.severity)} ｜ 分数：${detail.score} ｜ 置信度：${detail.confidence}</p>
                    <p>${detail.evidence || "暂无证据。"}</p>
                  </div>
                `,
              )
              .join("")}
          </div>
          ${
            group.propagation_hints?.length
              ? `<div class="hint-list">${group.propagation_hints.map((hint) => `<div class="hint">${hint}</div>`).join("")}</div>`
              : ""
          }
        </article>
      `,
    )
    .join("");
}

function shortText(text, max = 180) {
  if (!text) {
    return "暂无内容。";
  }
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function renderFindingList(findings, options = {}) {
  if (!findings?.length) {
    return `<div class="agent-empty">${options.emptyText || "该阶段没有产出内容。"}</div>`;
  }

  return `
    <div class="agent-findings">
      ${findings
        .map((finding) => {
          const title = finding.subtype
            ? `${finding.category || options.category || "风险"} / ${finding.subtype}`
            : finding.category || options.category || "风险";
          const confidence = finding.confidence ?? finding.relevance_score;
          const evidence = finding.evidence || finding.text || "";
          const rationale = finding.rationale || finding.description || "";
          const tags = [];
          if (finding.severity) {
            tags.push(`<span class="pill ${severityClass(finding.severity)}">${formatLevel(finding.severity)}</span>`);
          }
          if (typeof confidence === "number") {
            tags.push(`<span class="pill">置信度 ${confidence}</span>`);
          }
          if (finding.chunk_id) {
            tags.push(`<span class="pill">chunk ${finding.chunk_id}</span>`);
          }
          if (finding.issue_type) {
            tags.push(`<span class="pill">${finding.issue_type}</span>`);
          }

          return `
            <article class="agent-finding">
              <strong>${title}</strong>
              <div class="mini-meta">${tags.join("")}</div>
              <p>${shortText(evidence)}</p>
              ${rationale ? `<p>${shortText(rationale, 220)}</p>` : ""}
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderMetaList(items, emptyText) {
  if (!items?.length) {
    return `<div class="agent-empty">${emptyText}</div>`;
  }
  return `
    <div class="agent-meta-list">
      ${items
        .map(
          (item) => `
            <article class="agent-meta-item">
              <strong>${item.title}</strong>
              <pre>${item.body}</pre>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderAgentWorkbench(debug) {
  const container = $("#agent-workbench");
  const pipelineState = debug?.pipeline_state;
  if (!debug || !pipelineState) {
    container.innerHTML = "<div class='agent-empty'>当前请求未返回足够的 agent 中间结果。</div>";
    return;
  }

  const domainFindings = pipelineState.domain_findings || {};
  const revisedFindings = pipelineState.revised_findings || {};
  const reflectionIssues = debug.reflection_result?.issues || [];
  const confidenceResult = debug.confidence_result || null;
  const verifierResult = debug.verification_result || null;

  const domainStages = [
    {
      key: "triage",
      title: "Stage 0 · Triage Agent",
      description: "先切块、筛选可疑证据，并给出候选风险类别。",
      body: renderFindingList(debug.triage_results || [], { emptyText: "Triage 没有筛出候选文本块。" }),
    },
    {
      key: "algorithm",
      title: "Stage 1 · 算法安全 Agent",
      description: "只负责识别算法操纵诱导、模型失控故障、外部对抗滥用等算法安全问题。",
      body: renderFindingList(domainFindings["算法安全风险"] || [], { category: "算法安全风险", emptyText: "当前文本没有命中算法安全风险。" }),
    },
    {
      key: "data",
      title: "Stage 1 · 数据合规 Agent",
      description: "识别数据采集、共享出境、存储泄漏和敏感个人信息处理相关风险。",
      body: renderFindingList(domainFindings["数据合规风险"] || [], { category: "数据合规风险", emptyText: "当前文本没有命中数据合规风险。" }),
    },
    {
      key: "ethics",
      title: "Stage 1 · 科技伦理 Agent",
      description: "关注透明度、公平性、人工干预和可追溯责任等伦理治理风险。",
      body: renderFindingList(domainFindings["科技伦理风险"] || [], { category: "科技伦理风险", emptyText: "当前文本没有命中科技伦理风险。" }),
    },
    {
      key: "ip",
      title: "Stage 1 · 知识产权 Agent",
      description: "关注专利侵权、技术秘密、职务发明和开源软件合规。",
      body: renderFindingList(domainFindings["知识产权风险"] || [], { category: "知识产权风险", emptyText: "当前文本没有命中知识产权风险。" }),
    },
    {
      key: "geo",
      title: "Stage 1 · 地缘博弈 Agent",
      description: "关注出口管制、实体清单、外国投资审查和跨境技术流动限制。",
      body: renderFindingList(domainFindings["地缘博弈风险"] || [], { category: "地缘博弈风险", emptyText: "当前文本没有命中地缘博弈风险。" }),
    },
    {
      key: "reflection",
      title: "Stage 2 · Reflection Agent",
      description: "检查有没有漏判、错分、严重度不合理或跨 agent 分歧。",
      body: renderFindingList(reflectionIssues, { emptyText: "Reflection 没有发现明显问题。" }),
    },
    {
      key: "revision",
      title: "Stage 3 · Revision Agent",
      description: "根据 reflection 的问题清单修正 findings，形成 revised findings。",
      body: renderMetaList(
        Object.entries(revisedFindings).map(([category, findings]) => ({
          title: `${category}（${findings.length} 条）`,
          body: findings.length
            ? findings
                .map((finding) => `${finding.subtype} ｜ ${finding.severity} ｜ confidence=${finding.confidence}\n${finding.revision_reason || "无单独 revision 说明"}`)
                .join("\n\n")
            : "无修正结果",
        })),
        "Revision 阶段没有产出修正结果。",
      ),
    },
    {
      key: "confidence",
      title: "Stage 4 · Confidence Evaluator",
      description: "根据信号强度、鲁棒性和跨 agent 一致性计算连续置信度，并补充红线 gate。",
      body: confidenceResult
        ? renderMetaList(
            [
              {
                title: "连续置信度",
                body: `confidence_score=${confidenceResult.confidence_score}\nsignal_strength=${confidenceResult.signal_strength}\nrobustness=${confidenceResult.robustness}\ncross_agent_consistency=${confidenceResult.cross_agent_consistency}`,
              },
              {
                title: "红线 Gate",
                body: JSON.stringify(confidenceResult.gate_flags || {}, null, 2),
              },
            ],
            "当前没有置信度结果。",
          )
        : `<div class="agent-empty">当前没有置信度结果。</div>`,
    },
    {
      key: "verifier",
      title: "Stage 5 · Verifier Agent",
      description: "独立核验 revision 是否解决了问题，并决定 accept / partial_accept / revert。",
      body: verifierResult
        ? renderMetaList(
            [
              {
                title: `裁决：${verifierResult.verdict}`,
                body: `confidence=${verifierResult.confidence}\nneeds_human_review=${verifierResult.needs_human_review}\naccepted=${(verifierResult.accepted_finding_ids || []).join(", ") || "-" }\nrejected=${(verifierResult.rejected_finding_ids || []).join(", ") || "-"}`,
              },
              {
                title: "核验说明",
                body: verifierResult.notes || "暂无说明。",
              },
            ],
            "当前没有核验结果。",
          )
        : `<div class="agent-empty">当前没有核验结果。</div>`,
    },
  ];

  container.innerHTML = domainStages
    .map(
      (stage) => `
        <article class="agent-stage-card">
          <div class="agent-stage-head">
            <div>
              <h3>${stage.title}</h3>
              <p>${stage.description}</p>
            </div>
          </div>
          <div class="agent-stage-body">
            ${stage.body}
          </div>
        </article>
      `,
    )
    .join("");
}

function renderDebug(debug) {
  const container = $("#debug-cards");
  if (!debug) {
    container.innerHTML = "<p class='muted'>当前请求未返回 debug 数据。</p>";
    return;
  }

  const cards = [
    {
      title: "Triage",
      body: `chunk_count=${debug.chunk_count}\ntriage_count=${debug.triage_count}\n${JSON.stringify(debug.triage_results || [], null, 2)}`,
    },
    {
      title: "Reflection",
      body: JSON.stringify(debug.reflection_result || {}, null, 2),
    },
    {
      title: "Confidence",
      body: JSON.stringify(debug.confidence_result || {}, null, 2),
    },
    {
      title: "Verifier",
      body: JSON.stringify(debug.verification_result || {}, null, 2),
    },
  ];
  container.innerHTML = cards
    .map(
      (card) => `
        <article class="debug-card">
          <strong>${card.title}</strong>
          <pre>${card.body}</pre>
        </article>
      `,
    )
    .join("");
}

function renderReport(payload) {
  const report = payload.report;
  const debug = payload.debug;
  state.reportPayload = payload;

  $("#report-section").classList.remove("hidden");
  $("#report-timestamp").textContent = report.timestamp || "-";
  $("#overall-level").textContent = formatLevel(report.overall_risk_level);
  $("#overall-score").textContent = report.overall_score ?? "-";
  $("#overall-confidence").textContent = report.confidence ?? "-";
  $("#human-review-count").textContent = report.human_review_items?.length ?? 0;

  renderTopRisks(report.top3_risks || report.risk_details || []);
  renderConfidence(report);
  renderLifecycle(report.lifecycle_stage_groups || []);
  renderAgentWorkbench(debug);
  renderDebug(debug);
}

async function submitAnalysis(event) {
  event.preventDefault();
  clearError();
  showLoading(true);

  let metadata = {};
  if ($("#input-type").value === "company_name" && $("#metadata").value.trim()) {
    try {
      metadata = JSON.parse($("#metadata").value.trim());
    } catch (error) {
      showLoading(false);
      showError("metadata 不是合法 JSON，请先修正。");
      return;
    }
  }

  const payload = {
    input_type: $("#input-type").value,
    company_name: $("#company-name").value.trim() || null,
    raw_text: $("#input-type").value === "document" ? ($("#raw-text").value.trim() || null) : null,
    metadata,
    llm_mode: $("#llm-mode").value,
    report_only: $("#report-only").checked,
  };

  const endpoint = payload.report_only ? "/analyze/report-only" : "/analyze";

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "请求失败");
    }
    renderReport(data.data);
    $("#report-section").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showError(String(error.message || error));
  } finally {
    showLoading(false);
  }
}

function bindEvents() {
  document.querySelectorAll(".toggle").forEach((button) => {
    button.addEventListener("click", () => toggleInputMode(button.dataset.inputType));
  });
  $("#load-demo").addEventListener("click", loadDemo);
  $("#refresh-health").addEventListener("click", fetchHealth);
  $("#analyze-form").addEventListener("submit", submitAnalysis);
  $("#scroll-to-form").addEventListener("click", () => {
    $("#analysis-form").scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

bindEvents();
fetchHealth();
loadDemo();
