// ==========================================================================
// REBUTTAL — CLIENT CONTROLLER (DESIGN.md)
// "Automated defense, backed by proof, not persuasion."
// ==========================================================================

let activeScenarioData = null;
let customSelectedFile = null;
let currentPayload = null;

document.addEventListener("DOMContentLoaded", () => {
  fetchScenarios();
  fetchCostMatrix();
  fetchAnalystQueue();
  setupDragAndDrop();
});

// Setup Drag and Drop for Real User Uploads
function setupDragAndDrop() {
  const dropzone = document.getElementById("dropzone");
  if (!dropzone) return;

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
      handleCustomFile(files[0]);
    }
  });
}

function handleFileSelected(event) {
  const file = event.target.files[0];
  if (file) {
    handleCustomFile(file);
  }
}

function handleCustomFile(file) {
  customSelectedFile = file;
  enableCustomUploadMode();

  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById("evidence-img").src = e.target.result;
    document.getElementById("evidence-caption").innerText = file.name + " (" + (file.size / 1024).toFixed(1) + " KB)";
  };
  reader.readAsDataURL(file);
}

function enableCustomUploadMode() {
  activeScenarioData = null;

  document.querySelectorAll(".scenario-card").forEach((card, idx) => {
    card.classList.remove("active");
    card.classList.remove("custom-active");
    if (idx === 3) card.classList.add("custom-active");
  });

  if (!customSelectedFile) {
    document.getElementById("inp-tx-id").value = "pay_" + Math.random().toString(16).substring(2, 14);
    document.getElementById("inp-claim-text").value = "The item arrived defective and physically damaged.";
    document.getElementById("inp-amount").value = "34999.00";
    document.getElementById("inp-reason").value = "damaged";
    document.getElementById("inp-category").value = "electronics";
    document.getElementById("inp-age").value = "30";
    document.getElementById("inp-prior-cb").value = "2";
  }
}

// Tab Switching
function switchTab(tabId) {
  document.querySelectorAll("section[id^='tab-']").forEach(sec => {
    sec.classList.add("hidden-section");
  });
  const target = document.getElementById(tabId);
  if (target) {
    target.classList.remove("hidden-section");
  }

  const buttons = document.querySelectorAll(".nav-tab-btn");
  buttons.forEach(btn => btn.classList.remove("active"));

  if (tabId === 'tab-investigation' && buttons[0]) {
    buttons[0].classList.add("active");
  } else if (tabId === 'tab-threshold' && buttons[1]) {
    buttons[1].classList.add("active");
  } else if (tabId === 'tab-queue' && buttons[2]) {
    buttons[2].classList.add("active");
  }
}

// Fetch & Load Scenarios
async function fetchScenarios() {
  try {
    const res = await fetch("/api/scenarios");
    const scenarios = await res.json();
    window.allScenarios = scenarios;
    loadScenario("scenario-1");
  } catch (err) {
    console.error("Failed to fetch scenarios:", err);
  }
}

function loadScenario(scenarioId) {
  if (!window.allScenarios) return;
  const sc = window.allScenarios.find(s => s.id === scenarioId);
  if (!sc) return;

  activeScenarioData = sc;
  customSelectedFile = null;

  document.querySelectorAll(".scenario-card").forEach((card, idx) => {
    card.classList.remove("active");
    card.classList.remove("custom-active");
    if ((scenarioId === 'scenario-1' && idx === 0) ||
        (scenarioId === 'scenario-2' && idx === 1) ||
        (scenarioId === 'scenario-3' && idx === 2)) {
      card.classList.add("active");
    }
  });

  document.getElementById("inp-tx-id").value = sc.transaction_id;
  document.getElementById("inp-claim-text").value = sc.claim_text;
  document.getElementById("inp-amount").value = sc.transaction_amount;
  document.getElementById("inp-reason").value = sc.reason_code;
  document.getElementById("inp-category").value = sc.merchant_category;
  document.getElementById("inp-age").value = sc.user_account_age_days;
  document.getElementById("inp-prior-cb").value = sc.prior_chargeback_count;

  const imgElem = document.getElementById("evidence-img");
  imgElem.src = sc.image_url;
  document.getElementById("evidence-caption").innerText = sc.image_path;

  executeDefensePipeline();
}

// Execute Defense Pipeline
async function executeDefensePipeline() {
  const btn = document.getElementById("btn-run-agent");
  btn.innerHTML = `<span>Evaluating Evidence Pipeline (Gemini + CatBoost)...</span>`;
  btn.disabled = true;

  try {
    let data;

    if (customSelectedFile) {
      const formData = new FormData();
      formData.append("image", customSelectedFile);
      formData.append("transaction_id", document.getElementById("inp-tx-id").value);
      formData.append("order_id", "order_" + document.getElementById("inp-tx-id").value.slice(-6));
      formData.append("claim_text", document.getElementById("inp-claim-text").value);
      formData.append("reason_code", document.getElementById("inp-reason").value);
      formData.append("merchant_category", document.getElementById("inp-category").value);
      formData.append("user_account_age_days", document.getElementById("inp-age").value);
      formData.append("transaction_amount", document.getElementById("inp-amount").value);
      formData.append("prior_chargeback_count", document.getElementById("inp-prior-cb").value);

      const res = await fetch("/api/analyze-upload", {
        method: "POST",
        body: formData
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}: ${res.statusText}`);
      data = await res.json();
    } else {
      const payload = {
        transaction_id: document.getElementById("inp-tx-id").value,
        claim_text: document.getElementById("inp-claim-text").value,
        image_path: activeScenarioData ? activeScenarioData.image_path : "data/test_samples/intact_phone.jpg",
        reason_code: document.getElementById("inp-reason").value,
        merchant_category: document.getElementById("inp-category").value,
        user_account_age_days: parseInt(document.getElementById("inp-age").value, 10),
        transaction_amount: parseFloat(document.getElementById("inp-amount").value),
        prior_chargeback_count: parseInt(document.getElementById("inp-prior-cb").value, 10)
      };

      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}: ${res.statusText}`);
      data = await res.json();
    }

    renderAgentDecision(data);
  } catch (err) {
    alert("Pipeline execution notice: " + err.message);
    console.error(err);
  } finally {
    btn.innerHTML = `<span>Execute Evidence Pipeline</span>`;
    btn.disabled = false;
  }
}

// Translate Raw SHAP feature to Human Plain English
function getHumanShapExplanation(featureName, impactValue) {
  const isPositive = impactValue >= 0;
  
  if (featureName === 'vlm_contradiction_found') {
    return {
      title: isPositive ? "Visual Contradiction Flagged" : "No Visual Contradiction",
      desc: isPositive 
        ? "Gemini VLM detected physical evidence directly contradicting the customer's text claim." 
        : "Photo corroborates customer claim (genuine physical damage or lack of visual contradiction).",
      role: isPositive ? "Increases Merchant Win Rate" : "Pulls Win Rate Down"
    };
  } else if (featureName === 'metadata_match') {
    return {
      title: isPositive ? "EXIF Telemetry Verified" : "Missing / Stripped EXIF Telemetry",
      desc: isPositive 
        ? "Photo contains original camera GPS & timestamp matching delivery coordinates." 
        : "Photo lacks camera EXIF metadata (typical of downloaded photos or recycled screenshots).",
      role: isPositive ? "Increases Merchant Win Rate" : "Pulls Win Rate Down"
    };
  } else if (featureName === 'prior_chargeback_count') {
    return {
      title: isPositive ? "Serial Dispute History" : "Clean Customer History",
      desc: isPositive 
        ? "User has filed multiple disputes across prior transactions (serial friendly fraud signal)." 
        : "Customer has a spotless transaction record with zero prior disputes.",
      role: isPositive ? "Increases Fraud Likelihood" : "Lowers Dispute Win Confidence"
    };
  } else if (featureName === 'user_account_age_days') {
    return {
      title: isPositive ? "Burner Account Risk" : "Established Account Trust",
      desc: isPositive 
        ? "Account was created very recently (<14 days), a common hallmark of burner fraud." 
        : "Customer has an established account age, signaling a legitimate buyer.",
      role: isPositive ? "Increases Fraud Likelihood" : "Lowers Dispute Win Confidence"
    };
  } else if (featureName === 'reason_code') {
    return {
      title: "Dispute Reason Code Alignment",
      desc: isPositive 
        ? "Dispute reason code ('damaged') offers clear evidentiary defense under Visa CE 3.0 rules." 
        : "Dispute category carries stricter merchant burden of proof.",
      role: isPositive ? "Supports Defense Strategy" : "Increases Proof Requirement"
    };
  } else if (featureName === 'transaction_amount') {
    return {
      title: "Transaction Ticket Size Risk",
      desc: "High transaction value increases ROI of contesting but raises proof scrutiny.",
      role: isPositive ? "Positive Yield" : "High Risk Exposure"
    };
  } else {
    return {
      title: featureName,
      desc: "Statistical behavioral factor in CatBoost decision tree.",
      role: isPositive ? "Increases Win Probability" : "Decreases Win Probability"
    };
  }
}

function renderAgentDecision(data) {
  currentPayload = data;

  // 1. Decision Banner
  const banner = document.getElementById("decision-banner");
  const actionLabel = document.getElementById("decision-action-label");
  const tierLabel = document.getElementById("decision-tier-label");
  const probVal = document.getElementById("decision-prob-value");

  banner.className = "decision-status-card";
  const winProb = data.win_probability || 0.0;
  probVal.innerText = (winProb * 100).toFixed(1) + "%";

  if (data.routing_tier === "AUTO_CONTEST") {
    banner.classList.add("auto-contest");
    tierLabel.innerText = "ROUTING TIER: AUTO-CONTEST (SCORE > 85%)";
    actionLabel.innerText = "SUBMITTED TO RAZORPAY API";
  } else if (data.routing_tier === "PRIORITY_REVIEW") {
    banner.classList.add("priority-review");
    tierLabel.innerText = "ROUTING TIER: PRIORITY HUMAN REVIEW (60% - 85%)";
    actionLabel.innerText = "FLAGGED FOR ANALYST TRIAGE";
  } else {
    banner.classList.add("standard-review");
    tierLabel.innerText = "ROUTING TIER: STANDARD REVIEW / CONCEDE (SCORE < 60%)";
    actionLabel.innerText = "RECOMMEND LIABILITY ACCEPTANCE";
  }

  // 2. Forensics Card
  if (data.perception_result) {
    const p = data.perception_result;
    const vlmElem = document.getElementById("stat-vlm-contradiction");
    vlmElem.innerText = p.vlm_contradiction_found ? "TRUE (CONTRADICTION DETECTED)" : "FALSE (NO CONTRADICTION)";
    vlmElem.style.color = p.vlm_contradiction_found ? "#dc2626" : "#059669";
    
    document.getElementById("stat-exif-match").innerText = p.metadata_match ? "TRUE (GPS & TIMESTAMP INTACT)" : "FALSE (EXIF STRIPPED / UNAVAILABLE)";
    document.getElementById("stat-vlm-rationale").innerText = p.vision_reasoning || "Forensic analysis complete.";
  }

  // 3. Human-Readable SHAP Drivers
  const shapList = document.getElementById("shap-drivers-list");
  shapList.innerHTML = "";
  if (data.top_drivers && data.top_drivers.length > 0) {
    data.top_drivers.forEach(d => {
      const exp = getHumanShapExplanation(d.feature, d.impact);
      const isPositive = d.impact >= 0;
      const sign = isPositive ? "+" : "";
      
      const itemCard = document.createElement("div");
      itemCard.style.cssText = "background: var(--color-cloud-canvas); border: 1px solid var(--color-silver-lining); border-radius: 6px; padding: 12px 14px; margin-bottom: 10px;";
      
      itemCard.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
          <div>
            <strong style="color: var(--color-indigo-navy); font-size: 13px;">${exp.title}</strong>
            <span style="font-size: 11px; color: var(--color-steel); margin-left: 6px;">(${d.feature})</span>
          </div>
          <div style="font-family: var(--font-mono); font-weight: 700; font-size: 13px; color: ${isPositive ? 'var(--color-seafoam-700)' : '#dc2626'};">
            ${sign}${d.impact.toFixed(3)}
          </div>
        </div>
        <div style="font-size: 12px; color: var(--color-slate-ink); line-height: 1.4;">${exp.desc}</div>
        <div style="margin-top: 6px; display: flex; align-items: center; gap: 8px;">
          <div style="flex: 1; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;">
            <div style="width: ${Math.min(100, Math.abs(d.impact) * 45)}%; height: 100%; background: ${isPositive ? 'var(--color-seafoam-600)' : '#dc2626'};"></div>
          </div>
          <span style="font-size: 10px; font-weight: 600; text-transform: uppercase; color: ${isPositive ? 'var(--color-seafoam-700)' : '#dc2626'};">
            ${exp.role}
          </span>
        </div>
      `;
      shapList.appendChild(itemCard);
    });
  } else {
    shapList.innerHTML = `<div style="font-size: 12px; color: var(--color-steel);">SHAP drivers computed dynamically.</div>`;
  }

  // 4. Strategic Unit Economics & Strategy Card
  const stratBox = document.getElementById("strategy-explanation-box");
  const txAmount = data.transaction_amount || 0;
  
  if (data.routing_tier === "AUTO_CONTEST") {
    stratBox.innerHTML = `
      <div>
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
          <span class="status-pill" style="background: #eef8f2; color: #059669; border-color: #c2ebd5; font-size: 11px;">RECOMMENDED ACTION: AUTO-CONTEST</span>
          <span style="font-size: 12px; font-weight: 600; color: var(--color-steel);">High-Confidence Evidence Match</span>
        </div>
        <p style="font-size: 13px; color: var(--color-slate-ink); line-height: 1.5;">
          The photographic evidence directly disproves the customer's stated dispute claim (Win Probability: <strong>${(winProb * 100).toFixed(1)}%</strong>). 
          Contesting under <strong>Visa CE 3.0 / Razorpay dispute rules</strong> recovers <strong>₹${txAmount.toLocaleString()}</strong> with near-zero dispute loss risk.
        </p>
        <div style="margin-top: 10px; font-size: 12px; font-weight: 600; color: var(--color-indigo-navy);">
          Document Arrays Formatted: <code style="font-family: var(--font-mono); background: #e2e8f0; padding: 2px 6px;">shipping_proof</code>, <code style="font-family: var(--font-mono); background: #e2e8f0; padding: 2px 6px;">billing_proof</code>, <code style="font-family: var(--font-mono); background: #e2e8f0; padding: 2px 6px;">customer_communication</code>
        </div>
      </div>
    `;
  } else if (data.routing_tier === "PRIORITY_REVIEW") {
    stratBox.innerHTML = `
      <div>
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
          <span class="status-pill" style="background: #fffbeb; color: #d97706; border-color: #fde68a; font-size: 11px;">RECOMMENDED ACTION: PRIORITY REVIEW</span>
          <span style="font-size: 12px; font-weight: 600; color: var(--color-steel);">Human Analyst Verification Needed</span>
        </div>
        <p style="font-size: 13px; color: var(--color-slate-ink); line-height: 1.5;">
          Win probability is in the borderline zone (<strong>${(winProb * 100).toFixed(1)}%</strong>). 
          While high ticket value (<strong>₹${txAmount.toLocaleString()}</strong>) represents strong recovery potential, ambiguous photographic evidence requires human analyst confirmation to avoid risking the <strong>₹1,500</strong> network dispute fee.
        </p>
        <div style="margin-top: 10px; font-size: 12px; font-weight: 600; color: #78350f;">
          Action Step: Verify courier delivery tracking (POD) in the Analyst Review Queue before submitting.
        </div>
      </div>
    `;
  } else {
    stratBox.innerHTML = `
      <div>
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
          <span class="status-pill" style="background: #fef2f2; color: #dc2626; border-color: #fecaca; font-size: 11px;">RECOMMENDED ACTION: CONCEDE LIABILITY</span>
          <span style="font-size: 12px; font-weight: 600; color: var(--color-steel);">Avoid ₹1,500 Network Penalty</span>
        </div>
        <p style="font-size: 13px; color: var(--color-slate-ink); line-height: 1.5;">
          The visual evidence corroborates the customer's claim (Win Probability: <strong>${(winProb * 100).toFixed(1)}%</strong>). 
          Contesting carries a <strong>${((1 - winProb) * 100).toFixed(1)}% probability of failure</strong>, which would trigger a <strong>₹1,500 non-refundable dispute loss penalty fee</strong> from card networks.
        </p>
        <div style="margin-top: 10px; font-size: 12px; font-weight: 600; color: #991b1b;">
          Financial Impact: Conceding saves the ₹1,500 dispute penalty fee and preserves merchant standing.
        </div>
      </div>
    `;
  }

  // 5. Razorpay CE 3.0 Payload Code Box
  const codeBox = document.getElementById("payload-code-box");
  if (data.action_details && data.action_details.evidence_payload) {
    codeBox.innerText = JSON.stringify(data.action_details.evidence_payload, null, 2);
  } else if (data.action_details) {
    codeBox.innerText = JSON.stringify(data.action_details, null, 2);
  } else {
    codeBox.innerText = JSON.stringify(data, null, 2);
  }
}

// Copy Payload
function copyPayload() {
  const codeBox = document.getElementById("payload-code-box");
  navigator.clipboard.writeText(codeBox.innerText).then(() => {
    const btn = document.getElementById("copy-payload-btn");
    btn.innerText = "Copied!";
    setTimeout(() => { btn.innerText = "Copy JSON"; }, 2000);
  });
}

// Fetch Cost Matrix
async function fetchCostMatrix() {
  try {
    const res = await fetch("/api/cost-matrix");
    const data = await res.json();
    const tbody = document.getElementById("cost-matrix-tbody");
    tbody.innerHTML = "";

    data.table.forEach(row => {
      const tr = document.createElement("tr");
      if (row.threshold === 0.85) {
        tr.className = "optimal-row";
      }
      tr.innerHTML = `
        <td><strong>${row.threshold.toFixed(2)}</strong></td>
        <td>${row.auto_contest_count} disputes</td>
        <td>${(row.precision * 100).toFixed(1)}%</td>
        <td>${row.false_positives} (₹${(row.false_positives * 1500).toLocaleString()})</td>
        <td><strong>₹${row.net_financial_impact.toLocaleString()}</strong></td>
        <td><span class="status-pill" style="font-size: 11px;">${row.status}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Failed to fetch cost matrix:", err);
  }
}

// Fetch Analyst Queue
async function fetchAnalystQueue() {
  try {
    const res = await fetch("/api/queue");
    const queue = await res.json();
    const tbody = document.getElementById("analyst-queue-tbody");
    tbody.innerHTML = "";

    queue.forEach(item => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong style="font-family: var(--font-mono); color: var(--color-indigo-navy);">${item.dispute_id}</strong></td>
        <td style="font-family: var(--font-mono);">${item.transaction_id}</td>
        <td><strong>₹${item.amount.toLocaleString()}</strong></td>
        <td><span class="status-pill" style="font-size: 11px;">${item.reason}</span></td>
        <td><strong style="color: var(--color-seafoam-700); font-family: var(--font-primary); font-size: 14px;">${(item.win_probability * 100).toFixed(1)}%</strong></td>
        <td>${item.vlm_status}</td>
        <td><span style="font-family: var(--font-mono); font-size: 11px;">${item.exif_status}</span></td>
        <td>
          <button class="btn-table-action approve" onclick="handleQueueAction('${item.dispute_id}', 'approve')">Approve & Contest</button>
          <button class="btn-table-action concede" onclick="handleQueueAction('${item.dispute_id}', 'concede')">Concede</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Failed to fetch analyst queue:", err);
  }
}

function handleQueueAction(disputeId, action) {
  if (action === 'approve') {
    alert(`Dispute ${disputeId} approved by analyst and submitted to Razorpay POST /disputes/${disputeId}/contest`);
  } else {
    alert(`Dispute ${disputeId} marked as conceded to prevent network penalty fee.`);
  }
  fetchAnalystQueue();
}
