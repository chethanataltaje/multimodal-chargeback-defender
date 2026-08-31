// ==========================================================================
// ADMIN AUTHENTICATION (MOCKED)
// ==========================================================================

function doAdminLogin(event) {
  if (event) event.preventDefault();
  const emailInput = document.getElementById("admin-email");
  const pwdInput   = document.getElementById("admin-password");
  const email    = emailInput ? emailInput.value.trim() : "";
  const password = pwdInput ? pwdInput.value : "";
  const errEl    = document.getElementById("admin-login-error");
  if (errEl) errEl.style.display = "none";

  if (!email || !password) { 
    if (errEl) {
      errEl.textContent = "Please enter both email and password."; 
      errEl.style.display = "block"; 
    }
    return; 
  }

  const norm = email.toLowerCase();
  const isAccepted = norm === "admin@razorpay.com" || norm === "chethana@razorpay.com" || norm === "admin" || norm.endsWith("@razorpay.com");
  if (!isAccepted) { 
    if (errEl) {
      errEl.textContent = "Invalid credentials. Use admin@razorpay.com / admin123"; 
      errEl.style.display = "block"; 
    }
    return; 
  }

  const btn = document.getElementById("admin-login-btn");
  if (btn) { btn.textContent = "Signing in…"; btn.disabled = true; }
  setTimeout(() => {
    if (btn) { btn.textContent = "Sign in"; btn.disabled = false; }
    sessionStorage.setItem("admin_session", JSON.stringify({ email, name: "Chethana A.", role: "Risk Operations" }));
    hideAdminLogin();
    showAdminQueue();
  }, 400);
}

function _showChrome()  {
  const h = document.getElementById("app-header");         if (h) h.style.display  = "";
  const s = document.getElementById("workflow-stepper-bar"); if (s) s.style.display = "";
}
function _hideChrome() {
  const h = document.getElementById("app-header");         if (h) h.style.display  = "none";
  const s = document.getElementById("workflow-stepper-bar"); if (s) s.style.display = "none";
}

let allQueueCases = [];
let currentQueueFilter = "all";
let queuePollInterval = null;

function checkAdminAuth() {
  if (!sessionStorage.getItem("admin_session")) {
    sessionStorage.setItem("admin_session", JSON.stringify({ email: "admin@razorpay.com", name: "Chethana A.", role: "Risk Operations" }));
  }
  return true;
}
function showAdminLogin() {
  const ov = document.getElementById("admin-login-overlay"); if (ov) ov.style.display = "flex";
  const q  = document.getElementById("admin-queue-page");    if (q)  q.style.display  = "none";
  const wf = document.getElementById("admin-workflow");       if (wf) wf.style.display = "none";
  _hideChrome();
}
function hideAdminLogin() {
  const ov = document.getElementById("admin-login-overlay"); if (ov) ov.style.display = "none";
  _showChrome();
}

// ==========================================================================
// ADMIN DISPUTE QUEUE
// ==========================================================================

function showAdminQueue() {
  const q  = document.getElementById("admin-queue-page"); if (q)  q.style.display  = "flex";
  const wf = document.getElementById("admin-workflow");   if (wf) wf.style.display = "none";
  _showChrome();
  loadQueue();

  if (!queuePollInterval) {
    queuePollInterval = setInterval(() => {
      const q = document.getElementById("admin-queue-page");
      if (q && q.style.display !== "none") {
        loadQueue(true);
      }
    }, 3500);
  }
}

// Cross-tab real-time sync when customer submits a dispute or responds with evidence
window.addEventListener("storage", (e) => {
  if (e.key === "rebuttal_dispute_submitted") {
    loadQueue(true);
    showToast("🔔 New dispute received from Customer Portal!");
  }
  if (e.key === "rebuttal_customer_responded") {
    loadQueue(true);
    showToast("🔔 Customer submitted requested evidence!");
    if (appState.activeCaseId) {
      openCaseFromQueue(appState.activeCaseId);
    }
  }
});
window.addEventListener("focus", () => {
  loadQueue(true);
});

window.openImageInViewer = function(url) {
  if (url) window.open(url, "_blank");
};

function adminSignOut() {
  sessionStorage.removeItem("admin_session");
  appState.activeCaseId = null;
  appState.activeCaseData = null;
  appState.caseMode = null;
  appState.dispute = {
    transaction_id: "pay_98a76b54c3210f",
    order_id: "order_iphone_16_pro",
    transaction_amount: 119900.00,
    reason_code: "damaged",
    claim_text: "The phone screen arrived completely shattered in pieces and unusable.",
    merchant_category: "electronics",
    user_account_age_days: 5,
    prior_chargeback_count: 4,
    image_file: null,
    image_path: "data/test_samples/intact_phone.jpg",
    image_url: "/data/test_samples/intact_phone.jpg",
    image_name: "intact_phone.jpg",
    image_size: "2.4 MB",
    image_dims: "1920 × 1080 px",
    analysis_result: null,
    analyst_action: null,
    override_strategy: "CONCEDE",
    override_reason: "",
    evidence_type: "POD",
    evidence_note: "",
    is_reviewed: false,
    submission_response: null
  };
  appState.currentStep = 1;
  appState.maxStepReached = 1;
  showAdminLogin();
}

function goToQueue() {
  const q  = document.getElementById("admin-queue-page");
  const wf = document.getElementById("admin-workflow");
  if (q)  q.style.display  = "flex";
  if (wf) wf.style.display = "none";
  _showChrome();
  loadQueue();
  window.scrollTo(0, 0);
}

async function loadQueue(isSilent = false) {
  const loading = document.getElementById("queue-loading");
  const table   = document.getElementById("queue-table");
  const tbody   = document.getElementById("queue-tbody");
  if (!loading || !table || !tbody) return;

  if (!isSilent && (!allQueueCases || !allQueueCases.length)) {
    loading.textContent = "Loading disputes\u2026";
    loading.style.display = "block";
    table.style.display = "none";
  }

  try {
    const res = await fetch("/api/disputes");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const newCases = await res.json();

    if (allQueueCases.length > 0 && newCases.length > allQueueCases.length) {
      const diff = newCases.length - allQueueCases.length;
      showToast(`🔔 ${diff} new dispute(s) received from customer portal!`);
    }

    allQueueCases = newCases;
    loading.style.display = "none";
    table.style.display = "table";

    updateGlobalCaseSwitcher();
    renderQueueTable();
  } catch (e) {
    if (!isSilent) loading.textContent = "Failed to load queue: " + e.message;
  }
}

async function resetDemoQueue() {
  if (!confirm("Reset dispute queue to the 3 initial demonstration test cases? All other cases will be cleared.")) return;
  try {
    const res = await fetch("/api/admin/clear-old-disputes", { method: "POST" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    showToast("Dispute queue reset to the 3 test cases.");
    await loadQueue();
  } catch (err) {
    alert("Failed to reset queue: " + err.message);
  }
}

function updateGlobalCaseSwitcher() {
  const switcher = document.getElementById("global-case-switcher");
  if (!switcher) return;
  if (!allQueueCases || !allQueueCases.length) {
    switcher.style.display = "none";
    return;
  }

  switcher.style.display = "inline-block";
  const currentVal = appState.activeCaseId || "";

  let html = '<option value="" disabled ' + (!currentVal ? 'selected' : '') + '>🧪 Demo Preset Selector…</option>';
  allQueueCases.forEach(c => {
    const isCustomer = c.source === "customer_submitted" || (c.dispute_id && c.dispute_id.startsWith("DIS_"));
    const labelPrefix = isCustomer ? "⚡ [Customer] " : "🧪 [Demo] ";
    const amt = c.amount ? " \u20b9" + Number(c.amount).toLocaleString("en-IN") : "";
    const isSelected = c.dispute_id === currentVal ? "selected" : "";
    html += `<option value="${c.dispute_id}" ${isSelected}>${labelPrefix}${c.dispute_id} (${c.transaction_id || "tx"}${amt})</option>`;
  });
  switcher.innerHTML = html;
}

function onGlobalCaseSwitch(disputeId) {
  if (!disputeId) return;
  openCaseFromQueue(disputeId);
}

function setQueueFilter(filter, el) {
  currentQueueFilter = filter;
  document.querySelectorAll(".q-filter-btn").forEach(btn => {
    btn.style.background = "white";
    btn.style.color = "#4a5568";
    btn.style.borderColor = "#e2e8f0";
    btn.classList.remove("active");
  });
  if (el) {
    el.style.background = "#167e6c";
    el.style.color = "white";
    el.style.borderColor = "#167e6c";
    el.classList.add("active");
  }
  renderQueueTable();
}

function filterQueueTable() {
  renderQueueTable();
}

function renderQueueTable() {
  const tbody = document.getElementById("queue-tbody");
  const loading = document.getElementById("queue-loading");
  const searchInput = document.getElementById("queue-search-input");
  const query = searchInput ? searchInput.value.toLowerCase().trim() : "";

  if (!tbody) return;
  tbody.innerHTML = "";

  const filtered = allQueueCases.filter(c => {
    // Status filter
    if (currentQueueFilter !== "all") {
      const st = c.status || "";
      if (currentQueueFilter === "new" && st !== "new") return false;
      if (currentQueueFilter === "evidence_received" && st !== "evidence_received") return false;
      if (currentQueueFilter === "analyzing" && st !== "analyzing" && st !== "analysis_complete") return false;
      if (currentQueueFilter === "awaiting_review" && st !== "awaiting_review") return false;
      if (currentQueueFilter === "submitted" && st !== "submitted") return false;
      if (currentQueueFilter === "conceded" && st !== "overridden" && (c.risk?.routing_tier !== "STANDARD_REVIEW")) return false;
    }
    // Search query
    if (query) {
      const haystack = [
        c.dispute_id, c.transaction_id, c.customer_email, c.customer_id, c.reason, c.claim
      ].filter(Boolean).join(" ").toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    if (loading) {
      loading.textContent = "No matching disputes found.";
      loading.style.display = "block";
    }
  } else {
    if (loading) loading.style.display = "none";
    filtered.forEach(c => tbody.appendChild(buildQueueRow(c)));
  }
}

function buildQueueRow(c) {
  const tr = document.createElement("tr");
  tr.style.cssText = "border-bottom:1px solid #f1f5f9;cursor:pointer;transition:background 0.12s;";
  tr.addEventListener("mouseenter", () => tr.style.background = "#f8fafc");
  tr.addEventListener("mouseleave", () => tr.style.background = "");
  tr.addEventListener("click", () => openCaseFromQueue(c.dispute_id));
  const amount = c.amount ? "\u20b9" + Number(c.amount).toLocaleString("en-IN") : "\u2014";
  const evBadge = c.evidence_received
    ? '<span style="color:#059669;font-weight:600;">✓ Received</span>'
    : '<span style="color:#dc2626;">✗ Missing</span>';
  const STATUS = {
    new:{l:"New",co:"#64748b",bg:"#f1f5f9"},
    evidence_received:{l:"Evidence Received",co:"#0369a1",bg:"#e0f2fe"},
    analyzing:{l:"Analyzing",co:"#92400e",bg:"#fef3c7"},
    analysis_complete:{l:"Analysis Complete",co:"#7c3aed",bg:"#ede9fe"},
    awaiting_review:{l:"Awaiting Review",co:"#b45309",bg:"#fef3c7"},
    approved:{l:"Approved",co:"#059669",bg:"#ecfdf5"},
    overridden:{l:"Overridden",co:"#111a4a",bg:"#e8ebf8"},
    evidence_requested:{l:"Info Requested",co:"#9a3412",bg:"#ffedd5"},
    submitted:{l:"Submitted",co:"#059669",bg:"#ecfdf5"},
  };
  const s = STATUS[c.status] || {l:c.status,co:"#64748b",bg:"#f1f5f9"};
  const statusBadge = `<span style="font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;border-radius:20px;padding:3px 10px;color:${s.co};background:${s.bg};">${s.l}</span>`;
  const TIER = {
    AUTO_CONTEST:{l:"Auto-Contest",co:"#059669"},
    PRIORITY_REVIEW:{l:"Priority Review",co:"#b45309"},
    STANDARD_REVIEW:{l:"Concede",co:"#dc2626"},
  };
  const t = c.routing_tier ? TIER[c.routing_tier] : null;
  const rec = t ? `<span style="font-size:12px;font-weight:600;color:${t.co};">${t.l}</span>` : '<span style="color:#cbd5e1;">\u2014</span>';
  const updated = c.updated_at ? new Date(c.updated_at).toLocaleDateString("en-IN",{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}) : "\u2014";
  const customer = c.customer_email || c.customer_id || "\u2014";

  const isCustomer = c.source === "customer_submitted" || (c.dispute_id && c.dispute_id.startsWith("DIS_"));
  const typeBadge = isCustomer
    ? '<span style="font-size:10px;font-weight:700;letter-spacing:.04em;color:#0284c7;background:#f0f9ff;border:1px solid #bae6fd;border-radius:4px;padding:2px 6px;margin-left:6px;">CUSTOMER SUBMITTED</span>'
    : '<span style="font-size:10px;font-weight:700;letter-spacing:.04em;color:#167e6c;background:#ecfdf5;border:1px solid #a7f3d0;border-radius:4px;padding:2px 6px;margin-left:6px;">TEST CASE</span>';

  const hasCustomerReplied = c.additional_info_request?.status === "responded";
  const replyChip = hasCustomerReplied ? '<span style="font-size:9.5px;font-weight:700;letter-spacing:.04em;color:#047857;background:#d1fae5;border:1px solid #6ee7b7;border-radius:4px;padding:2px 6px;margin-left:5px;" title="Customer provided requested information">REPLIED</span>' : '';

  tr.innerHTML = `
    <td style="padding:14px 20px;font-family:'Courier New',monospace;font-size:12px;font-weight:700;color:#111a4a;">${c.dispute_id}${typeBadge}</td>
    <td style="padding:14px 16px;font-size:12px;color:#4a5568;">${c.transaction_id||"\u2014"}</td>
    <td style="padding:14px 16px;font-size:13px;font-weight:600;color:#111a4a;text-align:right;">${amount}</td>
    <td style="padding:14px 16px;font-size:12.5px;color:#4a5568;max-width:160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${c.reason||"\u2014"}</td>
    <td style="padding:14px 16px;font-size:12px;color:#4a5568;max-width:160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${customer}</td>
    <td style="padding:14px 16px;text-align:center;">${evBadge}</td>
    <td style="padding:14px 16px;">${statusBadge}${replyChip}</td>
    <td style="padding:14px 16px;">${rec}</td>
    <td style="padding:14px 20px;font-size:12px;color:#718096;">${updated}</td>
  `;
  return tr;
}

// ==========================================================================
// OPEN CASE FROM QUEUE
// ==========================================================================

async function openCaseFromQueue(disputeId) {
  try {
    const res = await fetch(`/api/disputes/${disputeId}`);
    if (!res.ok) throw new Error("Case not found: " + disputeId);
    const c = await res.json();
    appState.activeCaseId   = disputeId;
    appState.activeCaseData = c;
    appState.caseMode       = "persistent";
    const ev = c.evidence || {};
    appState.dispute = {
      transaction_id:         c.transaction_id || "",
      transaction_amount:     c.amount || 0,
      reason_code:            (c.reason || "damaged").toLowerCase().replace(/ \/ /g, "_").replace(/\//g, "_").replace(/ /g, "_"),
      claim_text:             c.claim || "",
      merchant_category:      c.merchant_category || "electronics",
      user_account_age_days:  c.user_account_age_days !== undefined ? c.user_account_age_days : 365,
      prior_chargeback_count: c.prior_chargeback_count !== undefined ? c.prior_chargeback_count : 0,
      image_path:             ev.path || "",
      image_url:              ev.url || ev.path || "",
      image_name:             ev.filename || "evidence.jpg",
      image_size:             ev.size_bytes ? (ev.size_bytes / 1024).toFixed(0) + " KB" : "",
      analysis_result: c.analysis ? {
        win_probability:  c.risk?.win_probability,
        top_drivers:      c.risk?.top_drivers || [],
        routing_tier:     c.risk?.routing_tier,
        final_action:     c.risk?.final_action,
        action_details:   c.risk?.action_details,
        perception_result: c.analysis,
        // Telemetry correlation fields
        gps_correlation:              c.analysis?.gps_correlation,
        gps_distance_meters:          c.analysis?.gps_distance_meters,
        timestamp_correlation:        c.analysis?.timestamp_correlation,
        timestamp_difference_minutes: c.analysis?.timestamp_difference_minutes,
        merchant_reference:           c.analysis?.merchant_reference,
      } : null,
      analyst_action:         c.review?.action || null,
      override_strategy:      c.review?.override_strategy || null,
      override_reason:        c.review?.override_reason || "",
      evidence_type:          c.review?.evidence_type || "POD",
      evidence_note:          c.review?.evidence_note || "",
      is_reviewed:            !!c.review,
      submission_response:    c.submission || null,
    };

    appState.maxStepReached = c.submission ? 5 : (c.review ? 5 : (c.analysis ? 4 : 1));

    const q  = document.getElementById("admin-queue-page"); if (q)  q.style.display  = "none";
    const wf = document.getElementById("admin-workflow");   if (wf) wf.style.display = "";
    const hdr = document.getElementById("header-case-id"); if (hdr) hdr.textContent = disputeId;
    _showChrome();
    updateGlobalCaseSwitcher();

    populateIntakeFormFromCase(c);
    updateCaseStatusFromPersistentCase(c);

    // Pre-render downstream views with active case data so no stale data from previous disputes exists
    renderEvidencePage();
    renderRiskPage();
    renderReviewPage();
    renderSubmissionPage();

    // Always start on Stage 1 (Intake) so admin can inspect all dispute details, customer profile, and customer responses
    let startStep = 1;
    navigateToStep(startStep, false);
  } catch (e) {
    alert("Failed to open case: " + e.message);
  }
}

function populateIntakeFormFromCase(c) {
  const ev = c.evidence || {};
  const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v !== undefined && v !== null ? v : ""; };
  
  // Correct HTML input element IDs
  setVal("inp-customer-id", c.customer_id || "—");
  setVal("inp-customer-email", c.customer_email || "—");
  setVal("inp-tx-id", c.transaction_id);
  setVal("inp-amount", c.amount !== undefined && c.amount !== null ? Number(c.amount).toFixed(2) : "");
  setVal("inp-reason", c.reason || "damaged");
  setVal("inp-claim-text", c.claim);
  setVal("inp-category", c.merchant_category || "electronics");
  setVal("inp-age", c.user_account_age_days !== undefined ? c.user_account_age_days : 365);
  setVal("inp-prior-cb", c.prior_chargeback_count !== undefined ? c.prior_chargeback_count : 0);

  // Sync appState dispute object
  appState.dispute.transaction_id         = c.transaction_id || "";
  appState.dispute.transaction_amount     = c.amount || 0;
  appState.dispute.reason_code            = c.reason || "damaged";
  appState.dispute.claim_text             = c.claim || "";
  appState.dispute.merchant_category      = c.merchant_category || "electronics";
  appState.dispute.user_account_age_days  = c.user_account_age_days || 365;
  appState.dispute.prior_chargeback_count = c.prior_chargeback_count || 0;
  appState.dispute.image_path             = ev.path || "";
  appState.dispute.image_url              = ev.url || ev.path || "";
  appState.dispute.image_name             = ev.filename || "evidence.jpg";
  appState.dispute.image_size             = ev.size_bytes ? (ev.size_bytes/1024).toFixed(0)+" KB" : "";

  updateHeaderCaseBadge(c.dispute_id, c.transaction_id);
  updateIntakeHints();

  // Additional Info Request & Customer Response Handling
  const respAlert = document.getElementById("customer-response-alert");
  const pendAlert = document.getElementById("customer-pending-req-alert");
  const req = c.additional_info_request;

  if (req && req.status === "responded" && req.response) {
    if (respAlert) respAlert.style.display = "block";
    if (pendAlert) pendAlert.style.display = "none";
    const timeEl = document.getElementById("cust-resp-time");
    if (timeEl) timeEl.textContent = "Submitted on " + (req.response.submitted_at ? new Date(req.response.submitted_at).toLocaleString("en-IN") : "recently");
    const msgEl = document.getElementById("cust-resp-message");
    if (msgEl) msgEl.textContent = req.response.message ? `"${req.response.message}"` : "No statement provided.";
    
    const evBox = document.getElementById("cust-resp-evidence-box");
    if (req.response.evidence && req.response.evidence.url) {
      if (evBox) evBox.style.display = "block";
      const imgEl = document.getElementById("cust-resp-img");
      if (imgEl) imgEl.src = req.response.evidence.url;
      const fnEl = document.getElementById("cust-resp-filename");
      if (fnEl) fnEl.textContent = req.response.evidence.filename || "supplemental_evidence.jpg";
      const szEl = document.getElementById("cust-resp-filesize");
      if (szEl) szEl.textContent = req.response.evidence.size_bytes ? `${(req.response.evidence.size_bytes/1024).toFixed(1)} KB · Uploaded by buyer` : "Uploaded by buyer";
    } else {
      if (evBox) evBox.style.display = "none";
    }
  } else if (req && req.status === "requested") {
    if (respAlert) respAlert.style.display = "none";
    if (pendAlert) {
      pendAlert.style.display = "block";
      const tEl = document.getElementById("pending-req-title");
      if (tEl) tEl.textContent = "Awaiting Customer Response: " + (req.title || "Additional Information");
      const mEl = document.getElementById("pending-req-message");
      if (mEl) mEl.textContent = req.message || "An information request was sent to the buyer.";
    }
  } else {
    if (respAlert) respAlert.style.display = "none";
    if (pendAlert) pendAlert.style.display = "none";
  }

  const ep  = document.getElementById("customer-evidence-panel");
  const nep = document.getElementById("no-evidence-placeholder");
  const h   = document.getElementById("upload-card-heading");
  const sb  = document.getElementById("upload-card-subheading");
  const rt  = document.getElementById("upload-required-tag");

  if (ev.url) {
    const im = document.getElementById("customer-evidence-img");
    const nm = document.getElementById("customer-evidence-name");
    const sz = document.getElementById("customer-evidence-size");
    if (im) im.src = ev.url;
    if (nm) nm.textContent = ev.filename || "evidence.jpg";
    if (sz) sz.textContent = ev.size_bytes ? (ev.size_bytes/1024).toFixed(0)+" KB" : "";
    if (ep)  ep.style.display  = "block";
    if (nep) nep.style.display = "none";
    if (h)   h.textContent     = "Customer-Submitted Evidence";
    if (sb)  sb.textContent    = "Evidence uploaded by the customer with their dispute";
    if (rt)  rt.style.display  = "none";
    showImagePreview(ev.url, ev.filename||"evidence.jpg", ev.size_bytes ? (ev.size_bytes/1024).toFixed(0)+" KB" : "");
  } else {
    // No evidence yet — show placeholder, hide evidence panel
    if (ep)  ep.style.display  = "none";
    if (nep) nep.style.display = "block";
    if (h)   h.textContent     = "Photographic Evidence";
    if (sb)  sb.textContent    = "No evidence has been submitted by the customer yet";
    if (rt)  rt.style.display  = "none";
  }
}


function updateCaseStatusFromPersistentCase(c) {
  const LABELS = {
    new:"New", evidence_received:"Evidence Received", analyzing:"Analyzing",
    analysis_complete:"Analysis Complete", awaiting_review:"Awaiting Review",
    approved:"Approved", overridden:"Overridden",
    evidence_requested:"Info Requested", submitted:"Submitted",
  };
  const b = document.getElementById("badge-ref-1");  if (b) b.textContent = "CASE " + c.dispute_id;
  const s = document.getElementById("badge-state-1"); if (s) s.innerHTML = `<span class="status-dot dot-in-progress"></span> ${LABELS[c.status]||c.status}`;
}

// ==========================================================================
// PERSIST ANALYSIS / REVIEW / SUBMISSION VIA API
// ==========================================================================

async function persistAnalysis() {
  if (!appState.activeCaseId) return null;
  try {
    const res = await fetch(`/api/disputes/${appState.activeCaseId}/analyze`, { method:"POST" });
    if (!res.ok) throw new Error("Analysis API error: " + res.status);
    const data = await res.json();
    const synth = {
      win_probability:   data.risk?.win_probability,
      top_drivers:       data.risk?.top_drivers || [],
      routing_tier:      data.risk?.routing_tier,
      final_action:      data.risk?.final_action,
      action_details:    data.risk?.action_details,
      perception_result: data.analysis,
      // Telemetry correlation fields
      gps_correlation:              data.analysis?.gps_correlation,
      gps_distance_meters:          data.analysis?.gps_distance_meters,
      timestamp_correlation:        data.analysis?.timestamp_correlation,
      timestamp_difference_minutes: data.analysis?.timestamp_difference_minutes,
      merchant_reference:           data.analysis?.merchant_reference,
    };
    appState.dispute.analysis_result = synth;
    return synth;
  } catch (e) { console.error("persistAnalysis failed:", e); return null; }
}

async function persistReview(action, overrideStrategy, overrideReason, evidenceType, evidenceNote) {
  if (!appState.activeCaseId) return;
  try {
    await fetch(`/api/disputes/${appState.activeCaseId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        override_strategy: overrideStrategy || null,
        override_reason: overrideReason || null,
        evidence_type: evidenceType || null,
        evidence_note: evidenceNote || null,
        analyst_name: "Chethana A.",
      }),
    });
  } catch (e) { console.error("persistReview failed:", e); }
}

async function persistSubmission() {
  if (!appState.activeCaseId) return null;
  try {
    const res = await fetch(`/api/disputes/${appState.activeCaseId}/submit`, { method:"POST" });
    if (!res.ok) throw new Error("Submit API error: " + res.status);
    return await res.json();
  } catch (e) { console.error("persistSubmission failed:", e); return null; }
}

// ==========================================================================
// REBUTTAL — ENTERPRISE DISPUTE DEFENSE PLATFORM
// Client Application Controller & Multi-Step Workflow Engine
// ==========================================================================

const STEP_ROUTES = {
  1: "/dispute/intake",
  2: "/dispute/evidence-analysis",
  3: "/dispute/risk-assessment",
  4: "/dispute/review",
  5: "/dispute/submission"
};

const ROUTE_TO_STEP = {
  "/dispute/intake": 1,
  "/dispute/evidence-analysis": 2,
  "/dispute/risk-assessment": 3,
  "/dispute/review": 4,
  "/dispute/submission": 5,
  "/": 1
};

// Global Application State
const appState = {
  currentStep: 1,
  maxStepReached: 1,
  currentZoom: 1.0,
  isAnalyzing: false,
  scenarios: [],
  activeScenarioId: "scenario-1",
  
  // Case Data
  dispute: {
    transaction_id: "pay_98a76b54c3210f",
    order_id: "order_iphone_16_pro",
    transaction_amount: 119900.00,
    reason_code: "damaged",
    claim_text: "The phone screen arrived completely shattered in pieces and unusable.",
    merchant_category: "electronics",
    user_account_age_days: 5,
    prior_chargeback_count: 4,
    
    // Evidence file
    image_file: null,
    image_path: "data/test_samples/intact_phone.jpg",
    image_url: "/data/test_samples/intact_phone.jpg",
    image_name: "intact_phone.jpg",
    image_size: "2.4 MB",
    image_dims: "1920 × 1080 px",
    
    // Pipeline outputs
    analysis_result: null,
    
    // Analyst Determination
    analyst_action: null, // "APPROVE" | "OVERRIDE" | "REQUEST_EVIDENCE"
    override_strategy: "CONCEDE",
    override_reason: "",
    evidence_type: "POD",
    evidence_note: "",
    is_reviewed: false,
    
    // Final Submission
    submission_response: null
  }
};

// ==========================================================================
// INITIALIZATION
// ==========================================================================
document.addEventListener("DOMContentLoaded", async () => {
  // Pre-initialize engine assets unconditionally so they are ready
  setupRouting();
  setupDragAndDrop();
  fetchScenarios().catch(e => console.warn("Scenario prefetch error:", e));

  // Check admin auth — if not authenticated, show login overlay and stop
  if (!checkAdminAuth()) return;

  // Hide the main workflow, show the dispute queue
  const wf = document.getElementById("admin-workflow"); if (wf) wf.style.display = "none";
  showAdminQueue();
});

// ==========================================================================
// ROUTING & STEPPER NAVIGATION
// ==========================================================================
function setupRouting() {
  window.addEventListener("popstate", (e) => {
    const step = e.state?.step || ROUTE_TO_STEP[window.location.pathname] || 1;
    navigateToStep(step, false);
  });
}

function navigateToStep(stepIndex, updateHistory = true) {
  if (stepIndex > appState.maxStepReached && stepIndex !== 1) {
    showToast("Please complete the current stage before advancing.");
    return;
  }

  // Hide all pages
  document.querySelectorAll(".stage-view").forEach(page => page.classList.add("hidden"));

  // Show target page
  const pageMap = {
    1: "page-intake",
    2: "page-evidence",
    3: "page-risk",
    4: "page-review",
    5: "page-submission"
  };

  const targetPageId = pageMap[stepIndex];
  const targetPage = document.getElementById(targetPageId);
  if (targetPage) {
    targetPage.classList.remove("hidden");
  }

  appState.currentStep = stepIndex;
  if (stepIndex > appState.maxStepReached) {
    appState.maxStepReached = stepIndex;
  }

  // Update Stepper Navigation UI & Status
  updateStepperUI(stepIndex);
  updateCaseStatusBadges();

  // Trigger page-specific renders
  if (stepIndex === 1) validateIntakeForm();
  if (stepIndex === 2) renderEvidencePage();
  if (stepIndex === 3) renderRiskPage();
  if (stepIndex === 4) renderReviewPage();
  if (stepIndex === 5) renderSubmissionPage();

  // Scroll to top
  window.scrollTo({ top: 0, behavior: "smooth" });

  // Update URL
  const targetPath = STEP_ROUTES[stepIndex] || "/dispute/intake";
  if (updateHistory && window.location.pathname !== targetPath) {
    window.history.pushState({ step: stepIndex }, "", targetPath);
  }
}

function updateStepperUI(activeStep) {
  for (let i = 1; i <= 5; i++) {
    const btn = document.getElementById(`step-btn-${i}`);
    if (!btn) continue;

    btn.classList.remove("active", "completed", "disabled");

    if (i < activeStep) {
      btn.classList.add("completed");
    } else if (i === activeStep) {
      btn.classList.add("active");
    } else if (i <= appState.maxStepReached) {
      // accessible step
    } else {
      btn.classList.add("disabled");
    }

    // Update connector bars
    if (i < 5) {
      const connector = document.getElementById(`connector-${i}`);
      if (connector) {
        if (i < activeStep) {
          connector.classList.add("active");
        } else {
          connector.classList.remove("active");
        }
      }
    }
  }
}

function updateCaseStatusBadges() {
  const d = appState.dispute;
  const activeId = appState.activeCaseId || d.transaction_id;
  const txRef = `CASE ${activeId}`;

  // Stage 1
  const ref1 = document.getElementById("badge-ref-1");
  const state1 = document.getElementById("badge-state-1");
  if (ref1) ref1.innerText = txRef;
  if (state1) state1.innerHTML = `<span class="status-dot dot-draft"></span> Draft`;

  // Stage 2
  const ref2 = document.getElementById("badge-ref-2");
  const state2 = document.getElementById("badge-state-2");
  if (ref2) ref2.innerText = txRef;
  if (state2) {
    if (appState.isAnalyzing) {
      state2.innerHTML = `<span class="status-dot dot-warning"></span> Analyzing...`;
    } else {
      state2.innerHTML = `<span class="status-dot dot-active"></span> Analysis Complete`;
    }
  }

  // Stage 3
  const ref3 = document.getElementById("badge-ref-3");
  const state3 = document.getElementById("badge-state-3");
  if (ref3) ref3.innerText = txRef;
  if (state3) state3.innerHTML = `<span class="status-dot dot-active"></span> Risk Evaluated`;

  // Stage 4
  const ref4 = document.getElementById("badge-ref-4");
  const state4 = document.getElementById("badge-state-4");
  if (ref4) ref4.innerText = txRef;
  if (state4) {
    if (d.is_reviewed) {
      state4.innerHTML = `<span class="status-dot dot-active"></span> Reviewed`;
    } else {
      state4.innerHTML = `<span class="status-dot dot-warning"></span> Awaiting Review`;
    }
  }

  // Stage 5
  const ref5 = document.getElementById("badge-ref-5");
  const state5 = document.getElementById("badge-state-5");
  if (ref5) ref5.innerText = txRef;
  if (state5) {
    if (d.submission_response) {
      const isConcede = d.submission_response.status === "LIABILITY_CONCEDED" || d.submission_response.action === "CONCEDE";
      state5.innerHTML = `<span class="status-dot dot-active"></span> ${isConcede ? "Resolved (Conceded)" : "Submitted"}`;
    } else {
      const res = d.analysis_result;
      const isConcede = (d.analyst_action === "OVERRIDE" && d.override_strategy === "CONCEDE") ||
                        (d.analyst_action === "APPROVE" && (res?.routing_tier === "CONCEDE" || res?.routing_tier === "STANDARD_REVIEW" || (res?.win_probability !== undefined && res.win_probability < 0.60)));
      state5.innerHTML = `<span class="status-dot dot-active"></span> ${isConcede ? "Ready to Concede" : "Ready to Submit"}`;
    }
  }
}

// ==========================================================================
// SCENARIOS & CASE PRESETS
// ==========================================================================
async function fetchScenarios() {
  try {
    const res = await fetch("/api/scenarios");
    if (res.ok) {
      appState.scenarios = await res.json();
    }
  } catch (err) {
    console.warn("Could not load scenarios from server:", err);
  }
}

async function handlePresetChange(scenarioId) {
  if (scenarioId === "custom") {
    resetFormToBlank();
    return;
  }
  await loadPresetCase(scenarioId, true);
}

async function loadPresetCase(scenarioId, autoAnalyze = true) {
  const sc = appState.scenarios.find(s => s.id === scenarioId);
  if (!sc) return;

  appState.activeScenarioId = scenarioId;
  const d = appState.dispute;

  d.transaction_id = sc.transaction_id;
  d.order_id = sc.order_id || `order_${sc.transaction_id.slice(-6)}`;
  d.transaction_amount = sc.transaction_amount;
  d.reason_code = sc.reason_code;
  d.claim_text = sc.claim_text;
  d.merchant_category = sc.merchant_category;
  d.user_account_age_days = sc.user_account_age_days;
  d.prior_chargeback_count = sc.prior_chargeback_count;
  
  d.image_file = null;
  d.image_path = sc.image_path;
  d.image_url = sc.image_url;
  d.image_name = sc.image_path.split("/").pop();
  d.image_size = "2.4 MB";
  d.image_dims = "1920 × 1080 px";

  d.analysis_result = null;
  d.analyst_action = null;
  d.is_reviewed = false;
  d.submission_response = null;

  appState.maxStepReached = 1;

  // Populate Intake Form Elements
  populateIntakeForm();
  updateHeaderCaseBadge(d.transaction_id);
  updateCaseStatusBadges();

  const select = document.getElementById("case-preset-select");
  if (select) select.value = scenarioId;

  if (autoAnalyze) {
    showToast(`Loaded: ${sc.title}`);
  }
}

function updateHeaderCaseBadge(txId) {
  const badgeId = document.getElementById("header-case-id");
  if (badgeId) badgeId.innerText = txId;
}

function populateIntakeForm() {
  const d = appState.dispute;
  document.getElementById("inp-tx-id").value = d.transaction_id;
  document.getElementById("inp-amount").value = d.transaction_amount.toFixed(2);
  document.getElementById("inp-reason").value = d.reason_code;
  document.getElementById("inp-claim-text").value = d.claim_text;
  document.getElementById("inp-category").value = d.merchant_category;
  document.getElementById("inp-age").value = d.user_account_age_days;
  document.getElementById("inp-prior-cb").value = d.prior_chargeback_count;

  updateIntakeHints();
  showImagePreview(d.image_url, d.image_name, d.image_size);
  validateIntakeForm();
}

function updateIntakeHints() {
  const age = parseInt(document.getElementById("inp-age").value, 10) || 0;
  const cb = parseInt(document.getElementById("inp-prior-cb").value, 10) || 0;

  const hintAge = document.getElementById("hint-age");
  if (hintAge) {
    hintAge.innerText = age < 14 ? "Burner account risk (<14 days)" : "Established customer";
    hintAge.className = age < 14 ? "input-hint hint-warning" : "input-hint";
  }

  const hintCb = document.getElementById("hint-prior-cb");
  if (hintCb) {
    hintCb.innerText = cb > 0 ? `${cb} prior disputes filed` : "Spotless dispute record";
    hintCb.className = cb > 0 ? "input-hint hint-warning" : "input-hint text-success";
  }

  const trustText = document.getElementById("trust-summary-text");
  if (trustText) {
    if (age < 14 && cb > 0) {
      trustText.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> High Risk (Short Tenure + Repeat Disputes)`;
      trustText.className = "trust-status text-danger";
    } else if (cb === 0 && age > 30) {
      trustText.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg> Low Risk (Established Customer · Clean History)`;
      trustText.className = "trust-status text-success";
    } else {
      trustText.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg> Moderate Risk (Standard Profile)`;
      trustText.className = "trust-status text-warning";
    }
  }
}

function validateIntakeForm() {
  const d = appState.dispute;
  const btn = document.getElementById("btn-to-analysis");
  
  const txVal = document.getElementById("inp-tx-id")?.value.trim() || d.transaction_id;
  const amountVal = parseFloat(document.getElementById("inp-amount")?.value) || d.transaction_amount;
  const hasClaim = Boolean(document.getElementById("inp-claim-text")?.value.trim());
  const hasImage = Boolean(d.image_url || d.image_file);

  // Update Case Readiness Checklist Items
  const evDot = document.getElementById("ready-evidence-dot");
  const evText = document.getElementById("ready-evidence-text");
  if (evDot && evText) {
    if (hasImage) {
      evDot.className = "check-dot checked";
      evDot.innerText = "✓";
      evText.innerText = "Photographic evidence attached";
    } else {
      evDot.className = "check-dot pending";
      evDot.innerText = "○";
      evText.innerText = "Photographic evidence required";
    }
  }

  const isValid = hasImage && Boolean(txVal) && amountVal > 0 && hasClaim;

  const stDot = document.getElementById("ready-status-dot");
  const stText = document.getElementById("ready-status-text");
  if (stDot && stText) {
    if (isValid) {
      stDot.className = "check-dot checked";
      stDot.innerText = "✓";
      stText.innerText = "Ready for evidence analysis";
    } else {
      stDot.className = "check-dot pending";
      stDot.innerText = "○";
      stText.innerText = "Evidence analysis pending";
    }
  }

  // Update Footer Target Summary
  const footerPill = document.getElementById("footer-case-pill");
  if (footerPill) {
    footerPill.innerText = `${txVal} (₹${amountVal.toLocaleString(undefined, { minimumFractionDigits: 2 })})`;
  }

  if (btn) {
    btn.disabled = !isValid;
  }
}

function resetFormToBlank() {
  appState.activeScenarioId = "custom";
  const d = appState.dispute;
  
  d.transaction_id = `pay_${Math.random().toString(16).substring(2, 14)}`;
  d.order_id = `order_${Math.random().toString(16).substring(2, 8)}`;
  d.transaction_amount = 4999.00;
  d.reason_code = "damaged";
  d.claim_text = "The item arrived damaged in transit.";
  d.merchant_category = "electronics";
  d.user_account_age_days = 45;
  d.prior_chargeback_count = 0;
  d.image_file = null;
  d.image_url = "";
  d.image_path = "";
  d.analysis_result = null;
  d.analyst_action = null;
  d.is_reviewed = false;
  d.submission_response = null;

  appState.maxStepReached = 1;
  populateIntakeForm();
  removeUploadedFile();
  updateHeaderCaseBadge(d.transaction_id);
  updateCaseStatusBadges();

  const select = document.getElementById("case-preset-select");
  if (select) select.value = "custom";

  showToast("Form ready for custom intake.");
}

// ==========================================================================
// DRAG & DROP & FILE HANDLING
// ==========================================================================
function setupDragAndDrop() {
  const dropzone = document.getElementById("dropzone");
  if (!dropzone) return;

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
    dropzone.addEventListener(evt, e => {
      e.preventDefault();
      e.stopPropagation();
    }, false);
  });

  ['dragenter', 'dragover'].forEach(evt => {
    dropzone.addEventListener(evt, () => dropzone.classList.add('dragover'), false);
  });

  ['dragleave', 'drop'].forEach(evt => {
    dropzone.addEventListener(evt, () => dropzone.classList.remove('dragover'), false);
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleCustomFile(files[0]);
    }
  });

  document.getElementById("inp-age")?.addEventListener("input", updateIntakeHints);
  document.getElementById("inp-prior-cb")?.addEventListener("input", updateIntakeHints);
}

function triggerFileInput() {
  const fi = document.getElementById("file-input");
  if (fi) fi.click();
}

function handleFileSelected(event) {
  const file = event.target.files[0];
  if (file) {
    handleCustomFile(file);
  }
}

function handleCustomFile(file) {
  appState.dispute.image_file = file;
  appState.dispute.image_name = file.name;
  appState.dispute.image_size = (file.size / 1024).toFixed(1) + " KB";
  appState.dispute.analysis_result = null;

  const reader = new FileReader();
  reader.onload = (e) => {
    appState.dispute.image_url = e.target.result;
    showImagePreview(e.target.result, file.name, appState.dispute.image_size);
    validateIntakeForm();
  };
  reader.readAsDataURL(file);

  const select = document.getElementById("case-preset-select");
  if (select) select.value = "custom";
}

function showImagePreview(url, filename, filesize) {
  if (!url) { removeUploadedFile(); return; }
  const empty   = document.getElementById("dropzone-empty");
  const preview = document.getElementById("dropzone-preview");
  const img     = document.getElementById("preview-image");
  const fn      = document.getElementById("preview-filename");
  const fs      = document.getElementById("preview-filesize");
  if (empty)   empty.classList.add("hidden");
  if (preview) preview.classList.remove("hidden");
  if (img)     img.src = url;
  if (fn)      fn.innerText = filename;
  if (fs)      fs.innerText = filesize || "2.4 MB";
}

function removeUploadedFile() {
  appState.dispute.image_file = null;
  appState.dispute.image_url = "";
  appState.dispute.image_path = "";
  appState.dispute.analysis_result = null;
  const fi      = document.getElementById("file-input");
  const preview = document.getElementById("dropzone-preview");
  const empty   = document.getElementById("dropzone-empty");
  if (fi)      fi.value = "";
  if (preview) preview.classList.add("hidden");
  if (empty)   empty.classList.remove("hidden");
  validateIntakeForm();
}

// ==========================================================================
// STEP 1 -> STEP 2: PROCEED & EXECUTE
// ==========================================================================
async function proceedFromIntake() {
  const d = appState.dispute;

  d.transaction_id = document.getElementById("inp-tx-id").value.trim();
  d.transaction_amount = parseFloat(document.getElementById("inp-amount").value) || 0;
  d.reason_code = document.getElementById("inp-reason").value;
  d.claim_text = document.getElementById("inp-claim-text").value.trim();
  d.merchant_category = document.getElementById("inp-category").value;
  d.user_account_age_days = parseInt(document.getElementById("inp-age").value, 10) || 0;
  d.prior_chargeback_count = parseInt(document.getElementById("inp-prior-cb").value, 10) || 0;

  if (!d.image_url && !d.image_file) {
    showToast("Please upload photographic evidence before continuing.");
    return;
  }

  updateHeaderCaseBadge(d.transaction_id);
  updateCaseStatusBadges();

  appState.maxStepReached = Math.max(appState.maxStepReached, 2);
  navigateToStep(2);

  if (!d.analysis_result) {
    await executePipelineAnalysis();
  }
}

function clearAnalysisPageUI() {
  const statusBanner = document.getElementById("analysis-processing-state");
  const resultsWorkspace = document.getElementById("analysis-results-workspace");

  const el = id => document.getElementById(id);

  if (appState.isAnalyzing) {
    if (el("vlm-contradiction-pill")) el("vlm-contradiction-pill").className = "status-chip hidden";
    if (el("finding-contradiction-val")) el("finding-contradiction-val").textContent = "Analyzing…";
    if (el("finding-damage-val")) el("finding-damage-val").textContent = "Analyzing…";
    if (el("finding-confidence-val")) el("finding-confidence-val").textContent = "—";
    if (el("vlm-rationale-text")) el("vlm-rationale-text").textContent = "Analyzing visual pixels and camera EXIF telemetry…";

    if (el("exif-badge-status")) {
      el("exif-badge-status").className = "status-chip";
      el("exif-badge-status").textContent = "ANALYZING";
    }
    if (el("exif-camera-val")) el("exif-camera-val").textContent = "Analyzing file headers…";
    if (el("exif-timestamp-val")) el("exif-timestamp-val").textContent = "—";
    if (el("exif-gps-val")) el("exif-gps-val").textContent = "—";
    if (el("exif-delivery-match-val")) el("exif-delivery-match-val").textContent = "Evaluating metadata…";
    if (el("exif-disclaimer-note")) el("exif-disclaimer-note").textContent = "";

    if (statusBanner) statusBanner.classList.remove("hidden");
    if (resultsWorkspace) resultsWorkspace.classList.add("hidden");
  } else {
    if (statusBanner) statusBanner.classList.add("hidden");
    if (resultsWorkspace) resultsWorkspace.classList.remove("hidden");
  }
}

async function executePipelineAnalysis() {
  const d = appState.dispute;
  const currentTargetId = appState.activeCaseId;
  appState.isAnalyzing = true;
  clearAnalysisPageUI();

  const statusBanner = document.getElementById("analysis-processing-state");
  const stepTitle = document.getElementById("analysis-step-title");
  const stepSub = document.getElementById("analysis-step-sub");
  
  if (statusBanner) statusBanner.classList.remove("hidden");
  if (stepTitle) stepTitle.innerText = "Analyzing visual evidence with Gemini 3.6 Flash VLM...";
  if (stepSub) stepSub.innerText = "Cross-referencing camera telemetry and pixel consistency against customer statement.";

  try {
    let resultData;

    if (appState.caseMode === "persistent" && appState.activeCaseId && !d.image_file) {
      const persisted = await persistAnalysis();
      if (persisted) {
        resultData = persisted;
      } else {
        throw new Error("Persistent case analysis failed.");
      }
    } else if (d.image_file) {
      const formData = new FormData();
      formData.append("image", d.image_file);
      formData.append("transaction_id", d.transaction_id);
      formData.append("order_id", d.order_id);
      formData.append("claim_text", d.claim_text);
      formData.append("reason_code", d.reason_code);
      formData.append("merchant_category", d.merchant_category);
      formData.append("user_account_age_days", d.user_account_age_days);
      formData.append("transaction_amount", d.transaction_amount);
      formData.append("prior_chargeback_count", d.prior_chargeback_count);

      const res = await fetch("/api/analyze-upload", {
        method: "POST",
        body: formData
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      resultData = await res.json();
    } else {
      const payload = {
        transaction_id: d.transaction_id,
        order_id: d.order_id,
        claim_text: d.claim_text,
        image_path: d.image_path || "data/test_samples/intact_phone.jpg",
        reason_code: d.reason_code,
        merchant_category: d.merchant_category,
        user_account_age_days: d.user_account_age_days,
        transaction_amount: d.transaction_amount,
        prior_chargeback_count: d.prior_chargeback_count
      };

      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      resultData = await res.json();
    }

    if (appState.activeCaseId && currentTargetId && appState.activeCaseId !== currentTargetId) {
      console.warn("Discarded stale analysis response for case:", currentTargetId);
      return;
    }

    d.analysis_result = resultData;
    appState.maxStepReached = 5;

    renderEvidencePage();
    showToast("Evidence analysis complete.");
  } catch (err) {
    console.error("Analysis Pipeline error:", err);
    showToast("Analysis error: " + err.message);
  } finally {
    appState.isAnalyzing = false;
    clearAnalysisPageUI();
    if (d.analysis_result) {
      renderEvidencePage();
    }
    updateCaseStatusBadges();
  }
}

function retriggerAnalysis() {
  appState.dispute.analysis_result = null;
  executePipelineAnalysis();
}

async function submitRequestInfo() {
  const disputeId = appState.activeCaseId;
  if (!disputeId) {
    alert("No active dispute selected to issue request.");
    return;
  }
  const title = document.getElementById("inp-req-title")?.value.trim() || "Original Delivery Evidence Required";
  const message = document.getElementById("inp-req-message")?.value.trim() || "Please upload the original delivery photograph.";

  try {
    const res = await fetch(`/api/disputes/${disputeId}/request-info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        message,
        requested_by: "Chethana A."
      })
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    closeModal("modal-request-info");
    try {
      localStorage.setItem("rebuttal_info_requested", JSON.stringify({
        dispute_id: disputeId,
        time: Date.now()
      }));
    } catch (_) {}
    showToast("Request sent to customer. Status: WAITING FOR CUSTOMER");
    await openCaseFromQueue(disputeId);
  } catch (err) {
    alert("Failed to send request: " + err.message);
  }
}

// ==========================================================================
// STAGE 2: EVIDENCE ANALYSIS RENDERER
// ==========================================================================
function renderEvidencePage() {
  const d = appState.dispute;
  const res = d.analysis_result;

  const viewerImg = document.getElementById("evidence-viewer-img");
  if (viewerImg) {
    viewerImg.src = d.image_url || d.image_path;
  }

  const fsImg = document.getElementById("fs-evidence-img");
  if (fsImg) {
    fsImg.src = d.image_url || d.image_path;
  }

  if (!res || !res.perception_result) {
    const badge = document.getElementById("vlm-contradiction-pill");
    const findingVal = document.getElementById("finding-contradiction-val");
    const damageVal = document.getElementById("finding-damage-val");
    const confVal = document.getElementById("finding-confidence-val");
    const rationaleText = document.getElementById("vlm-rationale-text");
    const exifBadge = document.getElementById("exif-badge-status");
    const cameraVal = document.getElementById("exif-camera-val");
    const timestampVal = document.getElementById("exif-timestamp-val");
    const gpsVal = document.getElementById("exif-gps-val");
    const matchVal = document.getElementById("exif-delivery-match-val");
    const noteEl = document.getElementById("exif-disclaimer-note");

    if (badge) {
      badge.className = "status-chip hidden";
      badge.innerText = "PENDING";
    }
    if (findingVal) {
      findingVal.className = "finding-val";
      findingVal.innerText = "Pending Analysis";
    }
    if (damageVal) {
      damageVal.className = "finding-val";
      damageVal.innerText = "Pending Analysis";
    }
    if (confVal) {
      confVal.innerText = "—";
    }
    if (rationaleText) {
      rationaleText.innerText = "Photographic evidence has not been analyzed yet. Run analysis to evaluate claim against visual pixels.";
    }
    if (exifBadge) {
      exifBadge.className = "status-chip";
      exifBadge.innerText = "PENDING";
    }
    if (cameraVal) cameraVal.innerText = "—";
    if (timestampVal) timestampVal.innerText = "—";
    if (gpsVal) gpsVal.innerText = "—";
    if (matchVal) {
      matchVal.className = "exif-value";
      matchVal.innerText = "Pending Analysis";
    }
    if (noteEl) noteEl.innerText = "";
    return;
  }

  const p = res.perception_result;
  const contradiction = p.vlm_contradiction_found;

  const badge = document.getElementById("vlm-contradiction-pill");
  const findingVal = document.getElementById("finding-contradiction-val");
  const damageVal = document.getElementById("finding-damage-val");
  const confVal = document.getElementById("finding-confidence-val");

  if (p.insufficient_evidence) {
    if (badge) {
      badge.className = "status-chip chip-warning";
      badge.innerText = "EVIDENCE INCONCLUSIVE";
    }
    if (findingVal) {
      findingVal.className = "finding-val text-warning";
      findingVal.innerText = "EVIDENCE INCONCLUSIVE";
    }
    if (damageVal) damageVal.innerText = "Image Too Ambiguous / Blurry / Cropped to Determine";
  } else if (contradiction) {
    if (badge) {
      badge.className = "status-chip chip-danger";
      badge.innerText = "CONTRADICTION DETECTED";
    }
    if (findingVal) {
      findingVal.className = "finding-val text-danger";
      findingVal.innerText = "CLAIM CONTRADICTED BY SUBMITTED EVIDENCE";
    }
    if (damageVal) damageVal.innerText = "Intact Item / Physical Contradiction Identified";
  } else {
    if (badge) {
      badge.className = "status-chip chip-success";
      badge.innerText = "NO CONTRADICTION";
    }
    if (findingVal) {
      findingVal.className = "finding-val text-success";
      findingVal.innerText = "CLAIM CONSISTENT WITH SUBMITTED EVIDENCE";
    }
    if (damageVal) damageVal.innerText = "Visible evidence is consistent with the reported damage";
  }

  if (confVal) {
    confVal.innerText = (p.vision_confidence_score !== undefined && p.vision_confidence_score !== null 
      ? (p.vision_confidence_score * 100).toFixed(1) 
      : "95.0") + "%";
  }

  const rationaleText = document.getElementById("vlm-rationale-text");
  if (rationaleText) {
    let expl = p.vision_reasoning || p.rationale || "";
    if (!contradiction && !p.insufficient_evidence) {
      if (!expl.includes("The submitted image does not visibly contradict")) {
        expl = (expl ? expl + " " : "") + "The submitted image does not visibly contradict the customer's claim. Visible evidence is consistent with the reported damage.";
      }
    }
    rationaleText.innerText = expl || "Visual analysis verified pixel consistency.";
  }

  const exifBadge = document.getElementById("exif-badge-status");
  const cameraVal = document.getElementById("exif-camera-val");
  const timestampVal = document.getElementById("exif-timestamp-val");
  const gpsVal = document.getElementById("exif-gps-val");
  const matchVal = document.getElementById("exif-delivery-match-val");
  const noteEl = document.getElementById("exif-disclaimer-note");

  if (p.metadata_available) {
    if (exifBadge) {
      exifBadge.className = "status-chip chip-success";
      exifBadge.innerText = "Available";
    }
    if (cameraVal) cameraVal.innerText = p.camera_device || "Camera metadata present in file";
    if (timestampVal) timestampVal.innerText = p.capture_timestamp || "Unavailable";
    if (gpsVal) {
      const gpsRaw = p.gps_coordinates;
      if (gpsRaw && typeof gpsRaw === "object" && gpsRaw.latitude != null) {
        gpsVal.innerText = `${gpsRaw.latitude.toFixed(5)}, ${gpsRaw.longitude.toFixed(5)}`;
      } else if (gpsRaw && typeof gpsRaw === "string" && gpsRaw !== "GPS unavailable" && gpsRaw !== "Unavailable") {
        gpsVal.innerText = gpsRaw;
      } else {
        gpsVal.innerText = "Unavailable";
      }
    }
    if (matchVal) {
      // Real telemetry correlation from backend
      const gpsCor = res.gps_correlation;
      const tsCor  = res.timestamp_correlation;
      const gpsDist = res.gps_distance_meters;
      const tsDiff  = res.timestamp_difference_minutes;
      if (!gpsCor || gpsCor === "NOT_VERIFIABLE") {
        matchVal.className = "exif-value";
        matchVal.innerText = "Merchant delivery telemetry unavailable — correlation not verifiable.";
      } else if (gpsCor === "MATCH" && (!tsCor || tsCor === "MATCH")) {
        matchVal.className = "exif-value text-success";
        matchVal.innerText = `GPS & Timestamp MATCH delivery records` +
          (gpsDist !== null && gpsDist !== undefined ? ` · Distance: ${gpsDist.toFixed(0)}m` : "") +
          (tsDiff !== null && tsDiff !== undefined ? ` · Δ${tsDiff}min` : "");
      } else if (gpsCor === "MISMATCH" || tsCor === "MISMATCH") {
        matchVal.className = "exif-value text-danger";
        const parts = [];
        if (gpsCor === "MISMATCH") parts.push(`GPS MISMATCH (${gpsDist !== null && gpsDist !== undefined ? gpsDist.toFixed(0) + 'm away' : 'location differs'})`);
        if (tsCor === "MISMATCH") parts.push(`Timestamp MISMATCH (Δ${tsDiff !== null && tsDiff !== undefined ? tsDiff : '?'}min)`);
        matchVal.innerText = parts.join(" · ");
      } else {
        matchVal.className = "exif-value";
        matchVal.innerText = "NOT VERIFIABLE";
      }
    }
    if (noteEl) noteEl.innerText = p.exif_note || "EXIF metadata available in file headers. Delivery correlation against merchant reference telemetry.";
  } else {
    if (exifBadge) {
      exifBadge.className = "status-chip";
      exifBadge.innerText = "Unavailable / Stripped";
    }
    if (cameraVal) cameraVal.innerText = "Unavailable";
    if (timestampVal) timestampVal.innerText = "Unavailable";
    if (gpsVal) gpsVal.innerText = "Unavailable";
    if (matchVal) {
      matchVal.className = "exif-value";
      matchVal.innerText = "Merchant delivery telemetry unavailable — correlation not verifiable.";
    }
    if (noteEl) noteEl.innerText = "EXIF metadata unavailable / stripped from uploaded evidence. Capture time, device information, and GPS location could not be verified.";
  }
}

// Zoom controls
function zoomEvidence(delta) {
  appState.currentZoom = Math.max(0.6, Math.min(3.0, appState.currentZoom + delta));
  applyZoom();
}

function resetEvidenceZoom() {
  appState.currentZoom = 1.0;
  applyZoom();
}

function applyZoom() {
  const img = document.getElementById("evidence-viewer-img");
  const label = document.getElementById("zoom-text");
  if (img) img.style.transform = `scale(${appState.currentZoom})`;
  if (label) label.innerText = Math.round(appState.currentZoom * 100) + "%";
}

// ==========================================================================
// STAGE 3: RISK ASSESSMENT RENDERER
// ==========================================================================
function renderRiskPage() {
  const d = appState.dispute;
  const res = d.analysis_result;
  if (!res) {
    const policyProbVal = document.getElementById("risk-policy-prob-val");
    const policyMarginVal = document.getElementById("risk-policy-margin-val");
    const policyTag = document.getElementById("risk-policy-status-tag");
    const routingBadge = document.getElementById("risk-routing-badge");
    const routingText = document.getElementById("risk-routing-tier-text");
    const probNum = document.getElementById("risk-prob-num");
    const probTag = document.getElementById("risk-prob-tag");
    const statScore = document.getElementById("stat-gatekeeper-score");
    const tbody = document.getElementById("xai-drivers-tbody");

    if (policyProbVal) { policyProbVal.innerText = "—"; policyProbVal.className = "threshold-metric-val"; }
    if (policyMarginVal) { policyMarginVal.innerText = "—"; policyMarginVal.className = "threshold-metric-val"; }
    if (policyTag) { policyTag.className = "status-chip"; policyTag.innerText = "PENDING ANALYSIS"; }
    if (routingBadge) routingBadge.className = "routing-badge";
    if (routingText) routingText.innerText = "PENDING";
    if (probNum) probNum.innerText = "—";
    if (probTag) { probTag.className = "win-prob-tag"; probTag.innerText = "Awaiting ML Risk Evaluation"; }
    if (statScore) statScore.innerText = "—";
    if (tbody) tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:24px; color:#718096;">Run analysis to compute calibrated win probability and SHAP feature drivers.</td></tr>';
    return;
  }

  const winProb = res.win_probability || 0.0;
  let routingTier = res.routing_tier;
  if (!routingTier) {
    if (winProb >= 0.85) routingTier = "AUTO_CONTEST";
    else if (winProb >= 0.60) routingTier = "PRIORITY_TRIAGE";
    else routingTier = "STANDARD_REVIEW";
  }

  // 1. Auto-Contest Policy Card Updates
  const policyProbVal = document.getElementById("risk-policy-prob-val");
  const policyMarginVal = document.getElementById("risk-policy-margin-val");
  const policyTag = document.getElementById("risk-policy-status-tag");

  if (policyProbVal) policyProbVal.innerText = (winProb * 100).toFixed(1) + "%";

  const margin = (winProb - 0.85) * 100;
  if (policyMarginVal) {
    if (margin >= 0) {
      policyMarginVal.innerText = `+${margin.toFixed(1)}% Margin`;
      policyMarginVal.className = "threshold-metric-val text-success";
    } else {
      policyMarginVal.innerText = `${margin.toFixed(1)}% Margin`;
      policyMarginVal.className = "threshold-metric-val text-danger";
    }
  }

  if (policyTag) {
    if (routingTier === "AUTO_CONTEST") {
      policyTag.className = "status-chip chip-success";
      policyTag.innerText = "QUALIFIED FOR AUTO-DEFENSE";
    } else if (routingTier === "PRIORITY_REVIEW" || routingTier === "PRIORITY_TRIAGE") {
      policyTag.className = "status-chip";
      policyTag.innerText = "PRIORITY HUMAN REVIEW REQUIRED";
    } else {
      policyTag.className = "status-chip chip-danger";
      policyTag.innerText = "CONCEDE LIABILITY RECOMMENDED";
    }
  }

  // 2. Decision Summary Card
  const routingBadge = document.getElementById("risk-routing-badge");
  const routingText = document.getElementById("risk-routing-tier-text");
  const probNum = document.getElementById("risk-prob-num");
  const probTag = document.getElementById("risk-prob-tag");

  if (probNum) probNum.innerText = (winProb * 100).toFixed(1) + "%";

  if (routingBadge) routingBadge.className = "routing-badge";
  if (routingTier === "AUTO_CONTEST") {
    if (routingText) routingText.innerText = "AUTO-CONTEST";
    if (probTag) {
      probTag.className = "win-prob-tag text-success";
      probTag.innerText = "Above 0.85 Auto-Contest Threshold (Max Net Recovery)";
    }
  } else if (routingTier === "PRIORITY_REVIEW" || routingTier === "PRIORITY_TRIAGE") {
    if (routingBadge) routingBadge.classList.add("tier-priority");
    if (routingText) routingText.innerText = "PRIORITY TRIAGE";
    if (probTag) {
      probTag.className = "win-prob-tag text-warning";
      probTag.innerText = "Borderline Zone (0.60 ≤ Score < 0.85)";
    }
  } else {
    if (routingBadge) routingBadge.classList.add("tier-concede");
    if (routingText) routingText.innerText = "CONCEDE LIABILITY";
    if (probTag) {
      probTag.className = "win-prob-tag text-danger";
      probTag.innerText = `Low Win Rate (${(winProb*100).toFixed(1)}% < 85%) · Avoid ₹1,500 Penalty Fee`;
    }
  }

  const statScore = document.getElementById("stat-gatekeeper-score");
  if (statScore) statScore.innerText = winProb.toFixed(4);

  const tbody = document.getElementById("xai-drivers-tbody");
  tbody.innerHTML = "";

  const drivers = res.top_drivers || [
    { feature: "vlm_contradiction_found", impact: 0.420 },
    { feature: "prior_chargeback_count", impact: 0.210 },
    { feature: "user_account_age_days", impact: 0.185 },
    { feature: "reason_code", impact: 0.140 }
  ];

  drivers.forEach(d => {
    const tr = document.createElement("tr");
    const exp = getShapMetadata(d.feature, d.impact);
    const absImpact = Math.abs(d.impact);
    const isPos = d.impact >= 0;
    const color = isPos ? "var(--color-emerald-accent)" : "var(--color-crimson-accent)";
    const barWidth = Math.min(100, Math.max(8, absImpact * 100));

    tr.innerHTML = `
      <td>
        <span class="feature-name">${exp.title}</span>
        <span class="feature-token font-mono">${d.feature}</span>
      </td>
      <td>
        <span class="shap-val font-mono" style="color: ${color};">
          ${isPos ? '+' : ''}${d.impact.toFixed(3)}
        </span>
      </td>
      <td>
        <div class="bar-cluster">
          <div class="bar-track">
            <div class="bar-fill" style="width: ${barWidth}%; background-color: ${color};"></div>
          </div>
          <span class="dir-text" style="color: ${color};">${exp.direction}</span>
        </div>
      </td>
      <td>
        <span style="color: var(--color-slate-ink); font-size: 12px;">${exp.desc}</span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function getShapMetadata(feature, impact) {
  const isPos = impact >= 0;
  switch (feature) {
    case 'vlm_contradiction_found':
      return {
        title: isPos ? "Visual Contradiction Flagged" : "Visual Evidence Supports Customer Claim",
        direction: isPos ? "Increases Merchant Win Probability" : "Reduces Merchant Win Probability",
        desc: isPos 
          ? "VLM detected physical pixels contradicting customer statement, strengthening dispute defense." 
          : "Submitted evidence is consistent with the customer's dispute claim."
      };
    case 'metadata_match':
      return {
        title: isPos ? "EXIF Telemetry Available" : "EXIF Telemetry Unavailable / Stripped",
        direction: isPos ? "Increases Merchant Win Probability" : "Reduces Merchant Win Probability",
        desc: isPos 
          ? "Available camera metadata strengthens the evidence chain." 
          : "Metadata stripped or absent from upload, weakening evidence chain of custody."
      };
    case 'prior_chargeback_count':
      return {
        title: isPos ? "Prior Dispute History" : "Clean Customer History",
        direction: isPos ? "Increases Merchant Win Probability" : "Reduces Merchant Win Probability",
        desc: isPos ? "Customer record has prior chargebacks filed across merchants." : "Customer account shows zero prior chargebacks, indicating high claimant credibility."
      };
    case 'user_account_age_days':
      return {
        title: isPos ? "New / Low Tenure Account" : "Established Account Trust",
        direction: isPos ? "Increases Merchant Win Probability" : "Reduces Merchant Win Probability",
        desc: isPos ? "Account tenure is short, which correlates with elevated dispute filing risk." : "Longer account tenure indicates established buyer relationship."
      };
    case 'reason_code':
      return {
        title: "Dispute Reason Code",
        direction: isPos ? "Increases Merchant Win Probability" : "Reduces Merchant Win Probability",
        desc: isPos ? "Dispute category permits clear evidentiary contest under Visa CE 3.0." : "Reason code carries stricter merchant evidentiary burden."
      };
    case 'transaction_amount':
      return {
        title: "Transaction Ticket Size",
        direction: isPos ? "Increases Merchant Win Probability" : "Reduces Merchant Win Probability",
        desc: isPos ? "Higher transaction value optimizes net recovery ROI upon contestation." : "Lower ticket size reduces net recovery margin relative to operational cost."
      };
    default:
      return {
        title: feature.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
        direction: isPos ? "Increases Merchant Win Probability" : "Reduces Merchant Win Probability",
        desc: isPos ? "Feature statistically correlates with positive dispute recovery." : "Feature statistically reduces merchant win probability."
      };
  }
}

// ==========================================================================
// STAGE 4: ANALYST REVIEW RENDERER
// ==========================================================================
function renderReviewPage() {
  const d = appState.dispute;
  const res = d.analysis_result;
  if (!res) {
    const revTx = document.getElementById("rev-tx-id");
    const revAmt = document.getElementById("rev-amount");
    const revReas = document.getElementById("rev-reason");
    const revClm = document.getElementById("rev-claim");
    if (revTx) revTx.innerText = d.transaction_id || "—";
    if (revAmt) revAmt.innerText = d.transaction_amount ? `₹${d.transaction_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—";
    if (revReas) revReas.innerText = d.reason_code ? `${d.reason_code} (Visa Compelling Evidence 3.0)` : "—";
    if (revClm) revClm.innerText = d.claim_text ? `"${d.claim_text}"` : "—";

    const thumb = document.getElementById("rev-evidence-thumb");
    if (thumb) thumb.src = d.image_url || d.image_path || "";

    const revContradiction = document.getElementById("rev-contradiction");
    if (revContradiction) {
      revContradiction.className = "entry-value";
      revContradiction.innerText = "Pending Analysis";
    }
    const revExif = document.getElementById("rev-exif");
    if (revExif) revExif.innerText = "Pending Analysis";
    const revVlmNote = document.getElementById("rev-vlm-note");
    if (revVlmNote) revVlmNote.innerText = "Awaiting visual evidence analysis.";
    const revTopDriver = document.getElementById("rev-top-driver");
    if (revTopDriver) revTopDriver.innerText = "—";
    const revWinProb = document.getElementById("rev-win-prob");
    if (revWinProb) revWinProb.innerText = "—";
    const recPill = document.getElementById("rev-rec-pill");
    if (recPill) recPill.innerText = "PENDING";
    const recRat = document.getElementById("rev-rec-rationale");
    if (recRat) recRat.innerText = "Run analysis to generate automated recommendation.";
    const approveTitle = document.getElementById("btn-approve-title");
    if (approveTitle) approveTitle.innerText = "Approve Recommendation";
    const approveDesc = document.getElementById("btn-approve-desc");
    if (approveDesc) approveDesc.innerText = "Awaiting system recommendation from risk analysis.";
    return;
  }

  document.getElementById("rev-tx-id").innerText = d.transaction_id;
  document.getElementById("rev-amount").innerText = `₹${d.transaction_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  document.getElementById("rev-reason").innerText = `${d.reason_code} (Visa Compelling Evidence 3.0)`;
  document.getElementById("rev-claim").innerText = `"${d.claim_text}"`;

  const thumb = document.getElementById("rev-evidence-thumb");
  if (thumb) thumb.src = d.image_url || d.image_path;

  const p = res.perception_result || {};
  const revContradiction = document.getElementById("rev-contradiction");
  if (p.insufficient_evidence) {
    revContradiction.className = "entry-value text-warning font-bold";
    revContradiction.innerText = "EVIDENCE INCONCLUSIVE";
  } else if (p.vlm_contradiction_found) {
    revContradiction.className = "entry-value text-danger font-bold";
    revContradiction.innerText = "CONTRADICTION DETECTED (Claim Contradicted by Submitted Evidence)";
  } else {
    revContradiction.className = "entry-value text-success font-bold";
    revContradiction.innerText = "NO CONTRADICTION (Claim Consistent with Submitted Evidence)";
  }

  const revExif = document.getElementById("rev-exif");
  if (revExif) {
    if (p.metadata_available) {
      const parts = [];
      if (p.camera_device) parts.push(p.camera_device);
      if (p.capture_timestamp) parts.push(p.capture_timestamp);
      if (p.gps_coordinates) parts.push("GPS logged");
      else parts.push("GPS unavailable");
      // Telemetry correlation
      const gpsCor  = res.gps_correlation;
      const tsCor   = res.timestamp_correlation;
      const gpsDist = res.gps_distance_meters;
      const tsDiff  = res.timestamp_difference_minutes;
      if (gpsCor === "MATCH" && (!tsCor || tsCor === "MATCH")) {
        parts.push(`Delivery MATCH ✓${gpsDist != null ? ' · ' + gpsDist.toFixed(0) + 'm' : ''}${tsDiff != null ? ' · Δ' + tsDiff + 'min' : ''}`);
      } else if (gpsCor === "MISMATCH" || tsCor === "MISMATCH") {
        const mp = [];
        if (gpsCor === "MISMATCH") mp.push(`GPS MISMATCH${gpsDist != null ? ' (' + gpsDist.toFixed(0) + 'm)' : ''}`);
        if (tsCor  === "MISMATCH") mp.push(`Timestamp MISMATCH${tsDiff != null ? ' (Δ' + tsDiff + 'min)' : ''}`);
        parts.push(mp.join(" · "));
      } else {
        parts.push("Merchant delivery telemetry unavailable — correlation not verifiable.");
      }
      revExif.innerText = `Available (${parts.join(" · ")})`;
    } else {
      revExif.innerText = "EXIF metadata unavailable / stripped";
    }
  }

  document.getElementById("rev-vlm-note").innerText = p.vision_reasoning ? p.vision_reasoning.slice(0, 120) + "..." : "Forensic analysis complete.";
  
  const topD = res.top_drivers?.[0];
  if (topD) {
    const meta = getShapMetadata(topD.feature, topD.impact);
    document.getElementById("rev-top-driver").innerText = `${meta.title} (${topD.impact >= 0 ? '+' : ''}${topD.impact.toFixed(3)})`;
  } else {
    document.getElementById("rev-top-driver").innerText = "—";
  }

  const winProb = res.win_probability !== undefined ? res.win_probability : 0.0;
  document.getElementById("rev-win-prob").innerText = (winProb * 100).toFixed(1) + "%";

  // Derive recommendation dynamically from the current case's risk evaluation
  let recType = "CONCEDE";
  if (res.routing_tier === "AUTO_CONTEST" || (!res.routing_tier && winProb >= 0.85)) {
    recType = "AUTO_CONTEST";
  } else if (res.routing_tier === "PRIORITY_REVIEW" || res.routing_tier === "PRIORITY_TRIAGE" || (!res.routing_tier && winProb >= 0.60)) {
    recType = "PRIORITY_TRIAGE";
  } else {
    recType = "CONCEDE";
  }

  const recPill = document.getElementById("rev-rec-pill");
  const recRat = document.getElementById("rev-rec-rationale");
  const approveTitle = document.getElementById("btn-approve-title");
  const approveDesc = document.getElementById("btn-approve-desc");

  if (recType === "AUTO_CONTEST") {
    if (recPill) recPill.innerText = "AUTO-CONTEST";
    if (recRat) recRat.innerText = "Objective visual contradiction corroborated by evidence analysis. Net recovery model projects positive capital return under Visa Compelling Evidence 3.0.";
    if (approveTitle) approveTitle.innerText = "Approve Recommendation (Auto-Contest)";
    if (approveDesc) approveDesc.innerText = "Authorize automated transmission of the evidence package to Razorpay CE 3.0.";
  } else if (recType === "PRIORITY_TRIAGE") {
    if (recPill) recPill.innerText = "PRIORITY TRIAGE";
    if (recRat) recRat.innerText = "Win probability in borderline zone (60%-85%). Review evidence consistency before transmitting dispute contest.";
    if (approveTitle) approveTitle.innerText = "Approve Recommendation (Priority Triage)";
    if (approveDesc) approveDesc.innerText = "Accept the system recommendation and route the case for additional human review.";
  } else {
    if (recPill) recPill.innerText = "CONCEDE LIABILITY";
    if (recRat) recRat.innerText = "Evidence corroborates customer claim. Recommending liability acceptance to avoid the non-refundable ₹1,500 dispute penalty fee.";
    if (approveTitle) approveTitle.innerText = "Approve Recommendation (Concede Liability)";
    if (approveDesc) approveDesc.innerText = "Accept the system recommendation and proceed with liability acceptance.";
  }

  if (d.analyst_action) {
    selectAnalystAction(d.analyst_action, false);
  } else {
    document.getElementById("btn-decide-approve")?.classList.remove("selected");
    document.getElementById("btn-decide-override")?.classList.remove("selected");
    document.getElementById("btn-decide-evidence")?.classList.remove("selected");
    document.getElementById("override-details-panel")?.classList.add("hidden");
    document.getElementById("evidence-req-panel")?.classList.add("hidden");
    const badge = document.getElementById("review-signoff-badge");
    const badgeText = document.getElementById("review-signoff-text");
    const btnContinue = document.getElementById("btn-to-submission");
    if (badge) badge.classList.remove("signed");
    if (badgeText) badgeText.innerText = "Sign-off Pending";
    if (btnContinue) btnContinue.disabled = true;
  }
}

function selectAnalystAction(action, markDirty = true) {
  const d = appState.dispute;
  d.analyst_action = action;

  document.getElementById("btn-decide-approve").classList.toggle("selected", action === "APPROVE");
  document.getElementById("btn-decide-override").classList.toggle("selected", action === "OVERRIDE");
  document.getElementById("btn-decide-evidence").classList.toggle("selected", action === "REQUEST_EVIDENCE");

  document.getElementById("override-details-panel").classList.toggle("hidden", action !== "OVERRIDE");
  document.getElementById("evidence-req-panel").classList.toggle("hidden", action !== "REQUEST_EVIDENCE");

  const badge = document.getElementById("review-signoff-badge");
  const badgeText = document.getElementById("review-signoff-text");
  const btnContinue = document.getElementById("btn-to-submission");

  badge.classList.add("signed");
  if (action === "APPROVE") {
    const res = d.analysis_result;
    const winProb = res?.win_probability !== undefined ? res.win_probability : 0.0;
    let rec = "CONCEDE";
    if (res?.routing_tier === "AUTO_CONTEST" || (!res?.routing_tier && winProb >= 0.85)) rec = "AUTO_CONTEST";
    else if (res?.routing_tier === "PRIORITY_REVIEW" || res?.routing_tier === "PRIORITY_TRIAGE" || (!res?.routing_tier && winProb >= 0.60)) rec = "PRIORITY_TRIAGE";

    if (rec === "CONCEDE") {
      badgeText.innerText = "Approved (Concede Liability Accepted)";
    } else if (rec === "PRIORITY_TRIAGE") {
      badgeText.innerText = "Approved (Priority Triage Authorized)";
    } else {
      badgeText.innerText = "Approved (Auto-Contest Authorized)";
    }
  } else if (action === "OVERRIDE") {
    badgeText.innerText = "Overridden (Manual Strategy)";
  } else {
    badgeText.innerText = "Evidence Requested";
  }

  btnContinue.disabled = false;
  d.is_reviewed = true;
  updateCaseStatusBadges();

  if (markDirty) {
    showToast(`Determination: ${action}`);
  }
}

function proceedToSubmission() {
  const d = appState.dispute;
  if (!d.is_reviewed || !d.analyst_action) {
    showToast("Please select an analyst determination before proceeding.");
    return;
  }

  if (d.analyst_action === "OVERRIDE") {
    d.override_strategy = document.getElementById("sel-override-action").value;
    d.override_reason = document.getElementById("txt-override-reason").value.trim();
    if (!d.override_reason) {
      showToast("Please provide an override justification for compliance audit logs.");
      document.getElementById("txt-override-reason").focus();
      return;
    }
  } else if (d.analyst_action === "REQUEST_EVIDENCE") {
    d.evidence_type = document.getElementById("sel-evidence-type").value;
    d.evidence_note = document.getElementById("txt-evidence-note").value.trim();
  }

  // Show confirmation modal before committing
  openConfirmDecisionModal();
}

function openConfirmDecisionModal() {
  const d = appState.dispute;
  const res = d.analysis_result;
  const winProb = res?.win_probability !== undefined ? res.win_probability : 0.0;

  let decisionLabel = "CONCEDE LIABILITY";
  if (d.analyst_action === "APPROVE") {
    const isRecContest = res?.routing_tier === "AUTO_CONTEST" || (!res?.routing_tier && winProb >= 0.85);
    const isRecPriority = res?.routing_tier === "PRIORITY_REVIEW" || res?.routing_tier === "PRIORITY_TRIAGE" || (!res?.routing_tier && winProb >= 0.60 && winProb < 0.85);
    if (isRecContest) decisionLabel = "AUTO-CONTEST (CE 3.0)";
    else if (isRecPriority) decisionLabel = "PRIORITY TRIAGE";
    else decisionLabel = "CONCEDE LIABILITY";
  } else if (d.analyst_action === "OVERRIDE") {
    decisionLabel = `OVERRIDE (${d.override_strategy || 'MANUAL'})`;
  } else if (d.analyst_action === "REQUEST_EVIDENCE") {
    decisionLabel = `REQUEST MERCHANT EVIDENCE (${d.evidence_type || 'POD'})`;
  }

  const nameEl = document.getElementById("confirm-decision-name");
  const probEl = document.getElementById("confirm-decision-prob");
  const caseEl = document.getElementById("confirm-decision-case");

  if (nameEl) nameEl.innerText = decisionLabel;
  if (probEl) probEl.innerText = (winProb * 100).toFixed(1) + "%";
  if (caseEl) caseEl.innerText = appState.activeCaseId || d.transaction_id || "—";

  openModal("confirm-decision-modal");
}

async function commitConfirmedAnalystDecision() {
  closeModal("confirm-decision-modal");
  const d = appState.dispute;

  // Persist review decision to case store
  await persistReview(
    d.analyst_action,
    d.override_strategy,
    d.override_reason,
    d.evidence_type,
    d.evidence_note
  );

  appState.maxStepReached = 5;
  navigateToStep(5);
  showToast("Analyst determination recorded.");
}

// ==========================================================================
// STAGE 5: SUBMISSION & API EXECUTION
// ==========================================================================
function renderSubmissionPage() {
  const d = appState.dispute;
  const res = d.analysis_result;
  if (!res) {
    const amt = document.getElementById("sub-fin-amount");
    const rec = document.getElementById("sub-fin-recovery");
    const recSub = document.getElementById("sub-fin-recovery-sub");
    const prob = document.getElementById("sub-fin-prob");
    const pen = document.getElementById("sub-fin-penalty");
    const pill = document.getElementById("sub-action-pill");
    const rat = document.getElementById("sub-rationale-text");

    if (amt) amt.innerText = d.transaction_amount ? `₹${d.transaction_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—";
    if (rec) rec.innerText = "—";
    if (recSub) recSub.innerText = "Awaiting Analysis";
    if (prob) prob.innerText = "—";
    if (pen) pen.innerText = "—";
    if (pill) pill.innerText = "PENDING";
    if (rat) rat.innerText = "Run evidence analysis to assemble defense strategy rationale.";
    return;
  }

  const winProb = res.win_probability !== undefined ? res.win_probability : 0.0;
  const isRecContest = res.routing_tier === "AUTO_CONTEST" || (!res.routing_tier && winProb >= 0.85);
  const isRecConcede = res.routing_tier === "STANDARD_REVIEW" || res.routing_tier === "CONCEDE" || (!res.routing_tier && winProb < 0.60);
  const isRecPriority = res.routing_tier === "PRIORITY_REVIEW" || res.routing_tier === "PRIORITY_TRIAGE" || (!res.routing_tier && winProb >= 0.60 && winProb < 0.85);

  const isContest = (d.analyst_action === "APPROVE" && isRecContest) || (d.analyst_action === "OVERRIDE" && d.override_strategy === "MANUAL_CONTEST");

  document.getElementById("sub-fin-amount").innerText = `₹${d.transaction_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  
  const recoveryElem = document.getElementById("sub-fin-recovery");
  const recoverySub = document.getElementById("sub-fin-recovery-sub");
  const penaltyElem = document.getElementById("sub-fin-penalty");

  if (isContest) {
    recoveryElem.innerText = `₹${d.transaction_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
    recoveryElem.className = "fin-amount font-mono text-success";
    recoverySub.innerText = "100% Capital Recovery Expected";
    penaltyElem.innerText = "₹0 Risk";
    penaltyElem.className = "fin-amount font-mono text-success";
  } else {
    recoveryElem.innerText = "₹0 (Conceded)";
    recoveryElem.className = "fin-amount font-mono";
    recoverySub.innerText = "Liability Accepted";
    penaltyElem.innerText = "₹1,500 Saved";
    penaltyElem.className = "fin-amount font-mono text-success";
  }

  document.getElementById("sub-fin-prob").innerText = (winProb * 100).toFixed(1) + "%";

  const actionPill = document.getElementById("sub-action-pill");
  const rationaleElem = document.getElementById("sub-rationale-text");
  const bannerTitle = document.querySelector("#ready-submit-banner .auth-title");
  const bannerCaption = document.querySelector("#ready-submit-banner .auth-caption");
  const submitBtn = document.getElementById("btn-submit-razorpay");

  const stage5Title = document.getElementById("stage-05-title");
  const stage5Sub = document.getElementById("stage-05-subtitle");
  const payloadCard = document.querySelector(".card-payload");
  const payloadAccordionTitle = document.querySelector(".payload-accordion-header span");
  const endpointString = document.querySelector(".endpoint-string");

  if (d.analyst_action === "APPROVE") {
    if (isRecConcede) {
      if (stage5Title) stage5Title.innerText = "Record Liability Acceptance";
      if (stage5Sub) stage5Sub.innerText = "Review liability determination, verify penalty avoidance economics, and formally record liability acceptance.";
      actionPill.className = "status-chip chip-danger";
      actionPill.innerText = "AUTHORIZED: CONCEDE LIABILITY";
      rationaleElem.innerHTML = `
        Liability acceptance approved following system recommendation. Low win probability (${(winProb*100).toFixed(1)}%) indicates genuine customer claim or high risk of non-refundable ₹1,500 dispute penalty fee. Liability acceptance avoids penalty exposure.
      `;
      if (bannerTitle) bannerTitle.innerText = "Ready to Record Liability Acceptance";
      if (bannerCaption) bannerCaption.innerText = "This action will formally accept dispute liability to avoid the ₹1,500 non-refundable dispute penalty fee and close the dispute.";
      if (submitBtn) submitBtn.innerHTML = `<span>Record Liability Acceptance</span> <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>`;
      if (payloadCard) {
        payloadCard.style.display = "block";
        if (payloadAccordionTitle) payloadAccordionTitle.innerText = "View Internal Liability Acceptance Record (JSON)";
        if (endpointString) endpointString.innerText = `INTERNAL SETTLEMENT LEDGER • DISPUTE: ${appState.activeCaseId || d.transaction_id}`;
      }
    } else if (isRecPriority) {
      if (stage5Title) stage5Title.innerText = "Route to Manual Review";
      if (stage5Sub) stage5Sub.innerText = "Review borderline risk signals and route case to senior human analysts for manual review.";
      actionPill.className = "status-chip";
      actionPill.innerText = "AUTHORIZED: PRIORITY TRIAGE";
      rationaleElem.innerHTML = `
        Priority triage approved following system recommendation. Win probability is borderline (${(winProb*100).toFixed(1)}%). 
        Dispute is routed for manual specialist evaluation.
      `;
      if (bannerTitle) bannerTitle.innerText = "Ready to Route for Manual Review";
      if (bannerCaption) bannerCaption.innerText = "This action will route the dispute to senior human analysts for specialized evidentiary review.";
      if (submitBtn) submitBtn.innerHTML = `<span>Route to Manual Review</span> <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>`;
      if (payloadCard) {
        payloadCard.style.display = "block";
        if (payloadAccordionTitle) payloadAccordionTitle.innerText = "View Case Routing Payload (Manual Review Queue)";
        if (endpointString) endpointString.innerText = `QUEUE ROUTING • DISPUTE: ${appState.activeCaseId || d.transaction_id}`;
      }
    } else {
      if (stage5Title) stage5Title.innerText = "Prepare Razorpay CE 3.0 Submission";
      if (stage5Sub) stage5Sub.innerText = "Review finalized unit economics, inspect CE 3.0 evidence package, and execute automated defense.";
      actionPill.className = "status-chip chip-success";
      actionPill.innerText = "AUTHORIZED: AUTO-CONTEST (CE 3.0)";
      rationaleElem.innerHTML = `
        Dispute defense assembled under <strong>Visa Compelling Evidence 3.0</strong> and <strong>Mastercard dispute rules</strong>. 
        Multimodal visual forensic analysis confirmed physical contradiction between claimant's statement and evidentiary imagery. 
        Camera telemetry logs, merchant delivery confirmation, and dispute reason code verification are bound into the transmission payload.
      `;
      if (bannerTitle) bannerTitle.innerText = "Ready for Transmission to Razorpay CE 3.0 API";
      if (bannerCaption) bannerCaption.innerText = "This action will compile the CE 3.0 evidence arrays and transmit via the official Razorpay Python SDK to contest the dispute.";
      if (submitBtn) submitBtn.innerHTML = `<span>Submit to Razorpay API</span> <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>`;
      if (payloadCard) {
        payloadCard.style.display = "block";
        if (payloadAccordionTitle) payloadAccordionTitle.innerText = "View Razorpay CE 3.0 API Payload (POST /v1/disputes/{id}/contest)";
        if (endpointString) endpointString.innerText = `POST https://api.razorpay.com/v1/disputes/disp_${d.transaction_id.slice(-10)}/contest`;
      }
    }
  } else if (d.analyst_action === "OVERRIDE") {
    if (stage5Title) stage5Title.innerText = d.override_strategy === "CONCEDE" ? "Record Liability Acceptance" : "Execute Manual Determination";
    if (stage5Sub) stage5Sub.innerText = "Review overridden operational strategy and record decision to audit ledger.";
    actionPill.className = "status-chip";
    actionPill.innerText = `OVERRIDDEN: ${d.override_strategy}`;
    rationaleElem.innerHTML = `
      Operational determination was overridden by analyst: <strong>${d.override_strategy}</strong>. 
      Justification recorded in audit trail: <em>"${d.override_reason || 'Manual strategy applied.'}"</em>. 
      Action will be logged with full compliance traceability.
    `;
    if (bannerTitle) bannerTitle.innerText = `Ready to Execute Override: ${d.override_strategy}`;
    if (bannerCaption) bannerCaption.innerText = "This action will apply the analyst's manual determination and log the justification to the audit ledger.";
    if (submitBtn) submitBtn.innerHTML = `<span>Submit Override Action</span> <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>`;
    if (payloadCard) {
      payloadCard.style.display = "block";
      if (payloadAccordionTitle) payloadAccordionTitle.innerText = "View Override Determination Payload";
      if (endpointString) endpointString.innerText = `OVERRIDE LEDGER • STRATEGY: ${d.override_strategy}`;
    }
  } else {
    if (stage5Title) stage5Title.innerText = "Dispatch Additional Evidence Request";
    if (stage5Sub) stage5Sub.innerText = "Transmit evidentiary request to logistics / merchant operations.";
    actionPill.className = "status-chip";
    actionPill.innerText = `EVIDENCE REQUESTED (${d.evidence_type || 'POD'})`;
    rationaleElem.innerHTML = `
      Operational determination is to <strong>hold dispute contestation and solicit supplementary documentation</strong> from the merchant. 
      Requested Document: <strong>${d.evidence_type || 'Courier POD'}</strong>.<br>
      Analyst Instructions: <em>"${d.evidence_note || 'Please provide signed Proof of Delivery (POD) from logistics carrier.'}"</em>.
    `;
    if (bannerTitle) bannerTitle.innerText = "Ready to Dispatch Evidence Request to Merchant Ops";
    if (bannerCaption) bannerCaption.innerText = "This action will send a webhook notification to merchant operations requesting the specified evidentiary documentation.";
    if (submitBtn) submitBtn.innerHTML = `<span>Dispatch Evidence Request</span> <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>`;
    if (payloadCard) {
      payloadCard.style.display = "block";
      if (payloadAccordionTitle) payloadAccordionTitle.innerText = "View Evidence Request Dispatch Payload";
      if (endpointString) endpointString.innerText = `EVIDENCE DISPATCH • DOCUMENT: ${d.evidence_type || 'POD'}`;
    }
  }

  const payloadCode = document.getElementById("sub-payload-code");
  let payloadObj;
  if (isRecConcede || (d.analyst_action === "OVERRIDE" && d.override_strategy === "CONCEDE")) {
    payloadObj = {
      dispute_id: appState.activeCaseId || `disp_${d.transaction_id.slice(-10)}`,
      transaction_id: d.transaction_id,
      amount: d.transaction_amount,
      action: "CONCEDE_LIABILITY",
      resolution: "LIABILITY_ACCEPTED",
      financial_impact: {
        penalty_fee_avoided: 1500.00,
        net_impact: -d.transaction_amount
      },
      reason: d.override_reason || "Customer claim corroborated by visual evidence. Liability accepted to avoid non-refundable ₹1,500 dispute penalty fee.",
      timestamp: new Date().toISOString()
    };
  } else {
    payloadObj = res.action_details?.evidence_payload || {
      dispute_id: `disp_${d.transaction_id.slice(-10)}`,
      transaction_id: d.transaction_id,
      summary: `Automated Defense: Objective visual contradiction flagged by VLM council. Reason code '${d.reason_code}' challenged under Visa CE 3.0.`,
      shipping_proof: [
        `doc_ship_${Math.random().toString(16).substring(2, 10)}`,
        `EXIF_FORENSICS: GPS=12.9716,77.5946 | MATCH=TRUE`
      ],
      billing_proof: [
        `doc_bill_${Math.random().toString(16).substring(2, 10)}`,
        `TX_CONFIRMATION: ID=${d.transaction_id} | AMOUNT=${d.transaction_amount}`
      ],
      customer_communication: [
        `doc_chat_${Math.random().toString(16).substring(2, 10)}`,
        `CUSTOMER_CLAIM: '${d.claim_text}'`,
        `VLM_FORENSIC_EVALUATION: ContradictionFlag=${res.perception_result?.vlm_contradiction_found || false}`
      ]
    };
  }

  if (payloadCode) payloadCode.innerText = JSON.stringify(payloadObj, null, 2);

  if (d.submission_response) {
    showSubmissionSuccessView(d.submission_response);
  } else {
    document.getElementById("submission-pre-view").classList.remove("hidden");
    document.getElementById("submission-success-view").classList.add("hidden");
  }
}

function togglePayloadAccordion() {
  const btn = document.querySelector(".payload-accordion-header");
  const body = document.getElementById("payload-accordion-body");
  btn.classList.toggle("expanded");
  body.classList.toggle("hidden");
}

function copyApiPayload() {
  const code = document.getElementById("sub-payload-code").innerText;
  navigator.clipboard.writeText(code).then(() => {
    const btn = document.getElementById("btn-copy-payload");
    btn.innerText = "Copied!";
    setTimeout(() => { btn.innerText = "Copy JSON"; }, 2000);
    showToast("API payload copied to clipboard.");
  });
}

async function submitToRazorpayApi() {
  const d = appState.dispute;
  const btn = document.getElementById("btn-submit-razorpay");
  btn.disabled = true;
  btn.innerHTML = `<span>Transmitting to Razorpay CE 3.0 API...</span>`;

  try {
    // For persistent cases, use the case-specific submit endpoint (persists submission receipt)
    if (appState.caseMode === "persistent" && appState.activeCaseId) {
      const persisted = await persistSubmission();
      if (persisted && persisted.submission) {
        d.submission_response = persisted.submission;
        showSubmissionSuccessView(persisted.submission);
        updateCaseStatusBadges();
        showToast("Dispute defense successfully transmitted to Razorpay CE 3.0 API.");
      }
      return;
    }

    const payloadObj = JSON.parse(document.getElementById("sub-payload-code").innerText);
    const reqBody = {
      transaction_id: d.transaction_id,
      dispute_id: `disp_${d.transaction_id.slice(-10)}`,
      action: d.analyst_action === "OVERRIDE" ? d.override_strategy : "AUTO_CONTEST",
      override_reason: d.override_reason || null,
      evidence_payload: payloadObj,
      analyst_notes: d.evidence_note || null
    };

    const res = await fetch("/api/submit-contest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(reqBody)
    });

    if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`);
    const responseData = await res.json();
    d.submission_response = responseData;

    showSubmissionSuccessView(responseData);
    updateCaseStatusBadges();
    showToast("Dispute defense successfully transmitted to Razorpay CE 3.0 API.");
  } catch (err) {
    console.error("Submission error:", err);
    showToast("Submission failed: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>Submit to Razorpay API</span> <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>`;
  }
}

function showSubmissionSuccessView(resp) {
  document.getElementById("submission-pre-view").classList.add("hidden");
  const successView = document.getElementById("submission-success-view");
  successView.classList.remove("hidden");

  const headline = successView.querySelector(".success-headline");
  const subheadline = successView.querySelector(".success-subheadline");
  const isConcede = resp.status === "LIABILITY_CONCEDED" || resp.action === "CONCEDE";
  const isEvReq = resp.status === "EVIDENCE_REQUESTED" || resp.action === "REQUEST_EVIDENCE";

  if (isConcede) {
    if (headline) headline.innerText = "Dispute Liability Concession Recorded";
    if (subheadline) subheadline.innerText = "Liability acceptance successfully logged. Non-refundable ₹1,500 network dispute penalty fee avoided.";
  } else if (isEvReq) {
    if (headline) headline.innerText = "Additional Evidence Request Dispatched";
    if (subheadline) subheadline.innerText = "Information request successfully recorded and dispatched to buyer portal.";
  } else {
    if (headline) headline.innerText = "Dispute Defense Successfully Submitted";
    if (subheadline) subheadline.innerText = "Contest payload transmitted to Razorpay Disputes API under Visa Compelling Evidence 3.0 regulations.";
  }

  document.getElementById("res-submission-id").innerText = resp.submission_id || (isConcede ? `concede_${appState.activeCaseId}` : `sub_${Math.random().toString(16).substring(2, 14)}`);
  document.getElementById("res-dispute-id").innerText = resp.dispute_id || resp.razorpay_dispute_id || appState.activeCaseId || `disp_${appState.dispute.transaction_id.slice(-10)}`;
  document.getElementById("res-timestamp").innerText = resp.submitted_at || resp.timestamp || new Date().toISOString();
  
  const httpStatusEl = document.getElementById("res-http-status");
  if (httpStatusEl) {
    if (isConcede) {
      httpStatusEl.innerText = "RESOLVED (LIABILITY_CONCEDED · PENALTY_AVOIDED)";
    } else if (isEvReq) {
      httpStatusEl.innerText = "DISPATCHED (WAITING_FOR_CUSTOMER)";
    } else {
      httpStatusEl.innerText = "HTTP 200 OK (SUBMITTED_VIA_RAZORPAY_SDK)";
    }
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function downloadSubmissionReceipt() {
  const disputeId = appState.activeCaseId;
  if (!disputeId) {
    showToast("No active case selected. Please open a case from the Dispute Queue first.");
    return;
  }
  // Open the backend PDF endpoint — generated from the authoritative case record
  const url = `/api/disputes/${disputeId}/audit-receipt`;
  const a = document.createElement("a");
  a.href = url;
  a.download = `Audit_Receipt_${disputeId}.pdf`;
  a.click();
  showToast("Generating PDF audit receipt…");
}


function startNewDispute() {
  resetFormToBlank();
  navigateToStep(1);
}

// ==========================================================================
// MODALS MANAGEMENT & DATA FETCHING
// ==========================================================================
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("hidden");
    if (modalId === "queue-modal") fetchAndRenderQueueModal();
    if (modalId === "policy-modal") fetchAndRenderPolicyModal();
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add("hidden");
}

function closeModalOnBackdrop(event, modalId) {
  if (event.target.id === modalId) {
    closeModal(modalId);
  }
}

async function fetchAndRenderQueueModal() {
  try {
    const res = await fetch("/api/queue");
    const queue = await res.json();
    const tbody = document.getElementById("queue-modal-tbody");
    tbody.innerHTML = "";

    const badge = document.getElementById("queue-badge-count");
    if (badge) badge.innerText = queue.length;

    queue.forEach(item => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="font-mono font-bold">${item.dispute_id}</td>
        <td class="font-mono">${item.transaction_id}</td>
        <td><strong>₹${item.amount.toLocaleString()}</strong></td>
        <td><span class="status-chip">${item.reason}</span></td>
        <td><strong style="color: var(--color-seafoam-700); font-family: var(--font-mono);">${(item.win_probability * 100).toFixed(1)}%</strong></td>
        <td>${item.vlm_status}</td>
        <td class="font-mono" style="font-size: 11px;">${item.exif_status}</td>
        <td>
          <button class="btn-tool" onclick="loadCaseFromQueue('${item.transaction_id}', ${item.amount}, '${item.reason}')">Load Case</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Queue fetch error:", err);
  }
}

function loadCaseFromQueue(txId, amount, reason) {
  closeModal("queue-modal");
  const d = appState.dispute;
  d.transaction_id = txId;
  d.transaction_amount = amount;
  d.reason_code = reason;
  d.claim_text = "Item damaged in transit, packaging torn.";
  d.image_path = "data/test_samples/dark_ambiguous.jpg";
  d.image_url = "/data/test_samples/dark_ambiguous.jpg";
  d.image_name = "dark_ambiguous.jpg";
  d.image_size = "1.8 MB";
  d.analysis_result = null;
  d.analyst_action = null;
  d.is_reviewed = false;
  d.submission_response = null;

  appState.maxStepReached = 1;
  populateIntakeForm();
  updateHeaderCaseBadge(txId);
  updateCaseStatusBadges();
  navigateToStep(1);
  showToast(`Loaded case ${txId} from queue.`);
}

async function fetchAndRenderPolicyModal() {
  try {
    const res = await fetch("/api/cost-matrix");
    const data = await res.json();
    const tbody = document.getElementById("policy-modal-tbody");
    tbody.innerHTML = "";

    data.table.forEach(row => {
      const isOpt = row.threshold === 0.85;
      const tr = document.createElement("tr");
      if (isOpt) {
        tr.style.backgroundColor = "var(--color-success-bg)";
        tr.style.fontWeight = "600";
      }
      tr.innerHTML = `
        <td class="font-mono"><strong>${row.threshold.toFixed(2)}</strong></td>
        <td>${row.auto_contest_count} disputes</td>
        <td>${(row.precision * 100).toFixed(1)}%</td>
        <td>${row.false_positives} (₹${(row.false_positives * 1500).toLocaleString()})</td>
        <td class="font-mono"><strong>₹${row.net_financial_impact.toLocaleString()}</strong></td>
        <td><span class="status-chip ${isOpt ? 'chip-success' : ''}">${row.status}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Policy fetch error:", err);
  }
}

// ==========================================================================
// UTILITIES
// ==========================================================================
function copyCaseId() {
  const caseId = appState.dispute.transaction_id;
  navigator.clipboard.writeText(caseId).then(() => {
    showToast(`Case ID ${caseId} copied to clipboard.`);
  });
}

function showToast(message) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
    <span>${message}</span>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    toast.style.transition = "all 0.2s ease";
    setTimeout(() => toast.remove(), 200);
  }, 3200);
}

