/**
 * customer/app.js — Rebuttal Customer Portal SPA logic.
 * NO admin-only fields (win probability, CatBoost, XAI, Razorpay payload) are used here.
 */

// ── State ─────────────────────────────────────────────────────────────────────
const customerState = {
  user: null,          // { email, name, initials }
  disputes: [],        // loaded from /api/disputes (filtered to customer's own)
  imageFile: null,     // File object for upload
};

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const saved = sessionStorage.getItem("cust_session");
  if (saved) {
    customerState.user = JSON.parse(saved);
    renderHeader();
    showPage("page-disputes");
    loadDisputes();
  } else {
    showPage("page-login");
  }

  // Drag-drop on dropzone
  const dz = document.getElementById("dropzone");
  if (dz) {
    ["dragenter", "dragover", "dragleave", "drop"].forEach(evt =>
      dz.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); })
    );
    ["dragenter", "dragover"].forEach(evt =>
      dz.addEventListener(evt, () => dz.classList.add("dragover"))
    );
    ["dragleave", "drop"].forEach(evt =>
      dz.addEventListener(evt, () => dz.classList.remove("dragover"))
    );
    dz.addEventListener("drop", e => {
      const files = e.dataTransfer.files;
      if (files.length > 0) setImageFile(files[0]);
    });
  }
});

// Cross-tab real-time sync when Admin requests info or updates dispute
window.addEventListener("storage", (e) => {
  if (e.key === "rebuttal_info_requested") {
    loadDisputes();
    if (customerState.activeDisputeId) {
      openCustomerDisputeDetail(customerState.activeDisputeId);
    }
  }
});

// ── Navigation ────────────────────────────────────────────────────────────────
function showPage(id) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  const page = document.getElementById(id);
  if (page) page.classList.add("active");

  const header = document.getElementById("cp-header");
  if (header) {
    header.style.display = id === "page-login" ? "none" : "";
  }

  window.scrollTo(0, 0);
}

// ── Auth (mocked) ─────────────────────────────────────────────────────────────
function doLogin(event) {
  event.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  const err = document.getElementById("login-error");
  err.classList.remove("visible");

  if (!email || !password) {
    err.classList.add("visible");
    return;
  }

  // Simulate async login
  const spinner = document.getElementById("login-spinner");
  const btnText = document.getElementById("login-btn-text");
  spinner.style.display = "block";
  btnText.textContent = "Signing in…";

  setTimeout(() => {
    spinner.style.display = "none";
    btnText.textContent = "Sign in";

    const name = email.split("@")[0].replace(/[._]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    const initials = name.split(" ").map(p => p[0]).join("").slice(0, 2).toUpperCase();
    const user = { email, name, initials, customer_id: `CUST_${btoa(email).slice(0, 6).toUpperCase()}` };
    customerState.user = user;
    sessionStorage.setItem("cust_session", JSON.stringify(user));

    renderHeader();
    showPage("page-disputes");
    loadDisputes();
  }, 700);
}

function signOut() {
  sessionStorage.removeItem("cust_session");
  sessionStorage.removeItem("cust_session_dispute_ids");
  customerState.user = null;
  customerState.disputes = [];
  customerState.imageFile = null;
  showPage("page-login");
}

function renderHeader() {
  const u = customerState.user;
  if (!u) return;
  const av = document.getElementById("hdr-avatar");
  const nm = document.getElementById("hdr-user-name");
  if (av) av.textContent = u.initials;
  if (nm) nm.textContent = u.name;
}

// ── Load Disputes ─────────────────────────────────────────────────────────────
async function loadDisputes() {
  const listEl   = document.getElementById("disputes-list");
  const emptyEl  = document.getElementById("disputes-empty");
  const loadingEl = document.getElementById("disputes-loading");

  listEl.innerHTML = "";
  emptyEl.style.display = "none";
  loadingEl.style.display = "block";

  const u = customerState.user || {};
  const query = u.customer_id ? `?customer_id=${encodeURIComponent(u.customer_id)}&customer_email=${encodeURIComponent(u.email||"")}` : "";

  try {
    const res = await fetch(`/api/customer/disputes${query}`);
    const mine = await res.json();

    loadingEl.style.display = "none";
    customerState.disputes = mine;

    if (mine.length === 0) {
      emptyEl.style.display = "block";
    } else {
      mine.forEach(d => listEl.appendChild(renderDisputeRow(d)));
    }
  } catch (e) {
    loadingEl.style.display = "none";
    emptyEl.style.display = "block";
    console.error("Failed to load disputes:", e);
  }
}


function renderDisputeRow(d) {
  const el = document.createElement("div");
  el.className = "dispute-row";
  el.style.cursor = "pointer";
  el.style.transition = "transform 0.1s, box-shadow 0.15s, border-color 0.15s";
  el.addEventListener("mouseenter", () => {
    el.style.borderColor = "var(--seafoam)";
    el.style.boxShadow = "0 4px 16px rgba(17,26,74,0.12)";
  });
  el.addEventListener("mouseleave", () => {
    el.style.borderColor = "var(--border)";
    el.style.boxShadow = "var(--shadow)";
  });
  el.addEventListener("click", () => openCustomerDisputeDetail(d.dispute_id));

  const hasReq = d.has_action_required || d.status === "evidence_requested" || (d.additional_info_request && d.additional_info_request.status === "requested");
  const badge = statusBadge(d.status, hasReq);
  const date = d.created_at ? new Date(d.created_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";
  const amount = d.amount ? `₹${Number(d.amount).toLocaleString("en-IN")}` : "—";

  el.innerHTML = `
    <div class="dr-main">
      <div class="dr-id">${d.dispute_id}</div>
      <div class="dr-desc">${d.reason || "—"} · ${amount}</div>
      <div class="dr-meta">${d.transaction_id || "—"} · Submitted ${date}</div>
    </div>
    <div class="dr-right">
      <span class="status-badge ${badge.cls}">${badge.label}</span>
      <span style="color:var(--slate-light); font-size:16px; font-weight:700;">→</span>
    </div>
  `;
  return el;
}

async function openCustomerDisputeDetail(disputeId) {
  customerState.activeDisputeId = disputeId;
  const u = customerState.user || {};
  const query = u.customer_id ? `?customer_id=${encodeURIComponent(u.customer_id)}&customer_email=${encodeURIComponent(u.email||"")}` : "";
  
  try {
    const res = await fetch(`/api/customer/disputes/${disputeId}${query}`);
    if (!res.ok) throw new Error("Failed to load dispute details");
    const d = await res.json();

    const setTxt = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt || "—"; };
    setTxt("dtl-dispute-id", d.dispute_id);
    setTxt("dtl-txn-id", d.transaction_id);
    setTxt("dtl-amount", d.amount ? `₹${Number(d.amount).toLocaleString("en-IN")}` : "₹0.00");
    setTxt("dtl-reason", d.reason);
    setTxt("dtl-claim", d.claim ? `"${d.claim}"` : "—");
    
    const dateStr = d.created_at ? new Date(d.created_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour:"2-digit", minute:"2-digit" }) : "—";
    setTxt("dtl-created-at", `Submitted on ${dateStr}`);

    const reqInfo = d.additional_info_request;
    const hasReq = d.has_action_required || d.status === "evidence_requested" || (reqInfo && reqInfo.status === "requested");
    const badge = statusBadge(d.status, hasReq);
    const bEl = document.getElementById("dtl-status-badge");
    if (bEl) {
      if (d.customer_status) {
        bEl.textContent = d.customer_status;
        if (d.customer_status.includes("Action Required")) bEl.className = "status-badge badge-action-required";
        else if (d.customer_status.includes("Resolved")) bEl.className = "status-badge badge-submitted";
        else bEl.className = "status-badge badge-received";
      } else {
        bEl.textContent = badge.label;
        bEl.className = `status-badge ${badge.cls}`;
      }
    }

    const ev = d.evidence || {};
    const imgEl = document.getElementById("dtl-evidence-img");
    if (imgEl) {
      imgEl.src = ev.url || "";
      imgEl.style.display = ev.url ? "block" : "none";
    }
    setTxt("dtl-evidence-filename", ev.filename ? `Original: ${ev.filename}` : "Original Evidence Photo");
    setTxt("dtl-evidence-size", ev.size_bytes ? `${(ev.size_bytes/1024).toFixed(1)} KB` : "Uploaded Evidence");

    // Supplementary evidence section
    let suppContainer = document.getElementById("dtl-supp-evidence");
    if (d.supplementary_evidence) {
      const sEv = d.supplementary_evidence;
      if (!suppContainer) {
        suppContainer = document.createElement("div");
        suppContainer.id = "dtl-supp-evidence";
        suppContainer.style.cssText = "margin-top:16px; padding-top:16px; border-top:1px solid var(--border);";
        const evCont = document.getElementById("dtl-evidence-container");
        if (evCont) evCont.appendChild(suppContainer);
      }
      suppContainer.style.display = "block";
      suppContainer.innerHTML = `
        <div style="font-size:12px; font-weight:700; color:var(--teal); text-transform:uppercase; margin-bottom:8px;">Supplementary Evidence (Uploaded in Response)</div>
        <div style="display:flex; gap:16px; align-items:flex-start; flex-wrap:wrap;">
          <img src="${sEv.url || ''}" alt="Supplementary Evidence" style="max-width:240px; max-height:240px; border-radius:8px; border:1px solid var(--border); object-fit:cover;" />
          <div>
            <div style="font-size:13.5px; font-weight:700; color:var(--navy); margin-bottom:4px;">${sEv.filename || 'Supplementary Photo'}</div>
            <div style="font-size:12px; color:var(--slate-light);">${sEv.size_bytes ? (sEv.size_bytes/1024).toFixed(1) + ' KB' : 'Uploaded'} · Verified attached to case</div>
          </div>
        </div>
      `;
    } else if (suppContainer) {
      suppContainer.style.display = "none";
    }

    // Action Required Card logic
    const reqCard = document.getElementById("dtl-action-required-card");
    if (reqCard) {
      if (reqInfo && reqInfo.status === "requested") {
        reqCard.style.display = "block";
        setTxt("dtl-req-title", reqInfo.title || "Additional Information Required");
        setTxt("dtl-req-message", reqInfo.message || "Please provide clarifying evidence for your analyst.");
      } else {
        reqCard.style.display = "none";
      }
    }

    showPage("page-dispute-detail");
  } catch (err) {
    alert("Could not load dispute details: " + err.message);
  }
}

async function submitCustomerResponse(event) {
  event.preventDefault();
  const disputeId = customerState.activeDisputeId;
  if (!disputeId) return;

  const msgInput = document.getElementById("inp-cust-resp-msg");
  const fileInput = document.getElementById("inp-cust-resp-file");
  const btn = document.getElementById("btn-submit-cust-resp");

  if (!msgInput || !msgInput.value.trim()) {
    alert("Please enter a response message.");
    return;
  }

  const formData = new FormData();
  formData.append("message", msgInput.value.trim());
  if (customerState.user && customerState.user.customer_id) {
    formData.append("customer_id", customerState.user.customer_id);
  }
  if (fileInput && fileInput.files.length > 0) {
    formData.append("file", fileInput.files[0]);
  }

  btn.disabled = true;
  btn.textContent = "Submitting…";

  try {
    const res = await fetch(`/api/customer/disputes/${disputeId}/respond-info`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error("Failed to submit response.");

    msgInput.value = "";
    if (fileInput) fileInput.value = "";
    try {
      localStorage.setItem("rebuttal_customer_responded", JSON.stringify({
        dispute_id: disputeId,
        time: Date.now()
      }));
    } catch (_) {}
    alert("Response submitted successfully! Your analyst will review the updated information.");
    await openCustomerDisputeDetail(disputeId);
    await loadDisputes();
  } catch (err) {
    alert("Error submitting response: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Submit Information →";
  }
}

function statusBadge(status, hasActionRequired = false) {
  if (hasActionRequired || status === "evidence_requested") {
    return { cls: "badge-action-required", label: "Action Required" };
  }
  const map = {
    new:                { cls: "badge-new",             label: "Submitted" },
    evidence_received:  { cls: "badge-received",        label: "Under Review" },
    analyzing:          { cls: "badge-analyzing",       label: "Under Review" },
    analysis_complete:  { cls: "badge-analyzing",       label: "Under Review" },
    awaiting_review:    { cls: "badge-analyzing",       label: "Under Review" },
    approved:           { cls: "badge-analyzing",       label: "Under Review" },
    overridden:         { cls: "badge-submitted",       label: "Resolved (Refund Approved)" },
    evidence_requested: { cls: "badge-action-required", label: "Action Required" },
    submitted:          { cls: "badge-received",        label: "Under Network Review" },
  };
  return map[status] || { cls: "badge-new", label: "Submitted" };
}

// ── Image Handling ────────────────────────────────────────────────────────────
function handleFileSelected(event) {
  const file = event.target.files[0];
  if (file) setImageFile(file);
}

function setImageFile(file) {
  customerState.imageFile = file;
  const reader = new FileReader();
  reader.onload = e => {
    document.getElementById("preview-thumb").src = e.target.result;
    document.getElementById("preview-name").textContent = file.name;
    document.getElementById("preview-size").textContent = formatSize(file.size);
    document.getElementById("image-preview").classList.add("visible");
    document.getElementById("dropzone").style.display = "none";
  };
  reader.readAsDataURL(file);
}

function removeImage() {
  customerState.imageFile = null;
  document.getElementById("file-input").value = "";
  document.getElementById("preview-thumb").src = "";
  document.getElementById("image-preview").classList.remove("visible");
  document.getElementById("dropzone").style.display = "";
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// ── Submit Dispute ────────────────────────────────────────────────────────────
async function submitDispute(event) {
  event.preventDefault();

  const errBox = document.getElementById("submit-error");
  errBox.classList.remove("visible");
  errBox.style.display = "none";

  const txnId  = document.getElementById("inp-txn-id").value.trim();
  const amount = parseFloat(document.getElementById("inp-amount").value);
  const reason = document.getElementById("inp-reason").value;
  const claim  = document.getElementById("inp-claim").value.trim();

  if (!txnId || !amount || !reason || !claim) {
    showError(errBox, "Please fill in all required fields.");
    return;
  }
  if (!customerState.imageFile) {
    showError(errBox, "Please upload photographic evidence of the issue.");
    return;
  }

  const btn    = document.getElementById("btn-submit-dispute");
  const spinner = document.getElementById("submit-spinner");
  const btnText = document.getElementById("submit-btn-text");
  btn.disabled = true;
  spinner.style.display = "block";
  btnText.textContent = "Submitting…";

  try {
    const formData = new FormData();
    formData.append("image", customerState.imageFile, customerState.imageFile.name);
    formData.append("transaction_id", txnId);
    formData.append("amount", amount.toString());
    formData.append("reason", reason);
    formData.append("claim", claim);
    formData.append("customer_email", customerState.user.email);
    formData.append("customer_id", customerState.user.customer_id);

    const res = await fetch("/api/disputes", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error: ${res.status}`);
    }

    const data = await res.json();

    // Record dispute in this session's dispute list
    if (data.dispute_id) {
      const sessionIds = JSON.parse(sessionStorage.getItem("cust_session_dispute_ids") || "[]");
      if (!sessionIds.includes(data.dispute_id)) {
        sessionIds.unshift(data.dispute_id);
        sessionStorage.setItem("cust_session_dispute_ids", JSON.stringify(sessionIds));
      }
      try {
        localStorage.setItem("rebuttal_dispute_submitted", JSON.stringify({
          dispute_id: data.dispute_id,
          transaction_id: txnId,
          amount: amount,
          time: Date.now()
        }));
      } catch (_) {}
    }

    // Show confirmation
    document.getElementById("confirm-ref-id").textContent = data.dispute_id || "—";
    showPage("page-confirm");

    // Reset form
    document.getElementById("dispute-form").reset();
    removeImage();

  } catch (err) {
    showError(errBox, `Submission failed: ${err.message}`);
  } finally {
    btn.disabled = false;
    spinner.style.display = "none";
    btnText.textContent = "Submit Dispute →";
  }
}

function showError(el, msg) {
  el.textContent = msg;
  el.classList.add("visible");
  el.style.display = "block";
}
