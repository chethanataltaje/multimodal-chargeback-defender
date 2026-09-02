import os
import json
import uuid
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# 1. Load Environment Variables
load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("DefenderServer")

from src.orchestrator.agent import run_defense_agent
from src.gatekeeper.train_model import evaluate_cost_matrix
from src.case_store import (
    create_case, get_case, update_case, list_cases,
    append_audit_event, generate_dispute_id, seed_preset_cases,
    verify_customer_ownership,
    STATUS_NEW, STATUS_EVIDENCE_RECEIVED, STATUS_ANALYZING,
    STATUS_ANALYSIS_COMPLETE, STATUS_AWAITING_REVIEW,
    STATUS_APPROVED, STATUS_OVERRIDDEN, STATUS_SUBMITTED,
    STATUS_EVIDENCE_REQUESTED,
)

app = FastAPI(
    title="Rebuttal — Dispute Defense Platform API",
    description="Razorpay Buildathon 2026 (Track 02) — Two-Role Architecture",
    version="2.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure required directories exist
os.makedirs("data/test_samples", exist_ok=True)
os.makedirs("data/uploads", exist_ok=True)
os.makedirs("data/cases", exist_ok=True)

from main import create_sample_images
create_sample_images()

# Seed preset demo cases
seed_preset_cases()

# ── Static File Mounts ────────────────────────────────────────────────────────
app.mount("/data/test_samples", StaticFiles(directory="data/test_samples"), name="samples")
app.mount("/data/uploads",      StaticFiles(directory="data/uploads"),      name="uploads")
app.mount("/uploads",           StaticFiles(directory="data/uploads"),      name="uploads_alias")
app.mount("/static",            StaticFiles(directory="frontend"),          name="frontend")

# ── Pydantic Models ───────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    transaction_id: str
    order_id: Optional[str] = "order_default"
    claim_text: str
    image_path: str
    reason_code: str
    merchant_category: str
    user_account_age_days: int
    transaction_amount: float
    prior_chargeback_count: int


class SubmitContestRequest(BaseModel):
    transaction_id: str
    dispute_id: Optional[str] = None
    action: str = "AUTO_CONTEST"
    override_reason: Optional[str] = None
    evidence_payload: Optional[Dict[str, Any]] = None
    analyst_notes: Optional[str] = None


class ReviewRequest(BaseModel):
    action: str  # APPROVE | OVERRIDE | REQUEST_EVIDENCE
    override_strategy: Optional[str] = None
    override_reason: Optional[str] = None
    evidence_type: Optional[str] = None
    evidence_note: Optional[str] = None
    analyst_name: Optional[str] = "Chethana A."


# ── SPA Routes ────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_landing():
    landing = Path(__file__).parent / "frontend" / "landing.html"
    if landing.exists():
        return FileResponse(str(landing))
    return RedirectResponse("/admin")


@app.get("/admin")
@app.get("/admin/")
@app.get("/admin/{path:path}")
async def serve_admin(path: Optional[str] = None):
    index = Path(__file__).parent / "frontend" / "index.html"
    if not index.exists():
        return JSONResponse({"error": "frontend/index.html not found"}, status_code=404)
    return FileResponse(str(index))


@app.get("/customer")
@app.get("/customer/")
@app.get("/customer/{path:path}")
async def serve_customer(path: Optional[str] = None):
    index = Path(__file__).parent / "frontend" / "customer" / "index.html"
    if not index.exists():
        return JSONResponse({"error": "frontend/customer/index.html not found"}, status_code=404)
    return FileResponse(str(index))


# Keep legacy root routes for backward compatibility
@app.get("/dispute/{path:path}")
@app.get("/disputes")
@app.get("/queue")
@app.get("/policy")
@app.get("/analytics")
@app.get("/settings")
async def serve_legacy(path: Optional[str] = None):
    return RedirectResponse("/admin")


# ── Existing Endpoints (UNCHANGED) ────────────────────────────────────────────

@app.get("/api/scenarios")
async def get_scenarios():
    """Returns pre-configured demonstration scenarios matching DESIGN.md standards."""
    scenarios = [
        {
            "id": "scenario-1",
            "tag": "FRIENDLY FRAUD",
            "title": "High-Ticket Electronics Claim",
            "transaction_id": "pay_98a76b54c3210f",
            "order_id": "order_iphone_16_pro",
            "claim_text": "The phone screen arrived completely shattered in pieces and unusable.",
            "image_path": "data/test_samples/intact_phone.jpg",
            "image_url": "/data/test_samples/intact_phone.jpg",
            "reason_code": "damaged",
            "merchant_category": "electronics",
            "user_account_age_days": 5,
            "transaction_amount": 119900.00,
            "prior_chargeback_count": 4,
            "expected_outcome": "AUTO_CONTEST (Win Probability > 85%)",
            "dispute_id": "DIS_DEMO_FRAUD001",
        },
        {
            "id": "scenario-2",
            "tag": "BORDERLINE DISPUTE",
            "title": "Apparel Color & Damage Mismatch",
            "transaction_id": "pay_45e67f89d0123a",
            "order_id": "order_sneakers_airmax",
            "claim_text": "Package showed up but color was completely wrong and box was torn.",
            "image_path": "data/test_samples/dark_ambiguous.jpg",
            "image_url": "/data/test_samples/dark_ambiguous.jpg",
            "reason_code": "damaged",
            "merchant_category": "apparel",
            "user_account_age_days": 180,
            "transaction_amount": 14999.00,
            "prior_chargeback_count": 1,
            "expected_outcome": "PRIORITY HUMAN REVIEW (Score 60% - 85%)",
            "dispute_id": "DIS_DEMO_BORDER002",
        },
        {
            "id": "scenario-3",
            "tag": "LEGITIMATE CUSTOMER",
            "title": "Physical Hardware Defect",
            "transaction_id": "pay_11b22c33d4455e",
            "order_id": "order_headphones_sony",
            "claim_text": "Headphone headband snapped immediately upon unboxing.",
            "image_path": "data/test_samples/damaged_item.jpg",
            "image_url": "/data/test_samples/damaged_item.jpg",
            "reason_code": "damaged",
            "merchant_category": "electronics",
            "user_account_age_days": 850,
            "transaction_amount": 4999.00,
            "prior_chargeback_count": 0,
            "expected_outcome": "STANDARD REVIEW / CONCEDE (Score < 60%)",
            "dispute_id": "DIS_DEMO_LEGIT003",
        }
    ]
    return JSONResponse(scenarios)


@app.post("/api/analyze")
async def analyze_dispute(req: AnalyzeRequest):
    """Executes the pipeline on structured JSON inputs (legacy / demo path)."""
    logger.info(f"API Analyze request received for transaction: {req.transaction_id}")
    try:
        result_state = run_defense_agent(req.model_dump())
        return JSONResponse(result_state.model_dump())
    except Exception as e:
        logger.error(f"Error running defense agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-upload")
async def analyze_custom_upload(
    image: UploadFile = File(...),
    transaction_id: str = Form(...),
    order_id: str = Form("order_custom"),
    claim_text: str = Form(...),
    reason_code: str = Form(...),
    merchant_category: str = Form(...),
    user_account_age_days: int = Form(...),
    transaction_amount: float = Form(...),
    prior_chargeback_count: int = Form(...),
):
    """
    Accepts real user-uploaded photos (with real EXIF metadata) + custom form data
    and runs the live multimodal forensic defense pipeline (legacy / Custom Live Test path).
    """
    logger.info(f"Analyzing custom user upload: {image.filename} for TX: {transaction_id}")

    file_ext = Path(image.filename).suffix or ".jpg"
    saved_filename = f"upload_{uuid.uuid4().hex[:10]}{file_ext}"
    saved_path = Path("data/uploads") / saved_filename

    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    dispute_payload = {
        "transaction_id": transaction_id,
        "order_id": order_id,
        "claim_text": claim_text,
        "image_path": str(saved_path),
        "reason_code": reason_code,
        "merchant_category": merchant_category,
        "user_account_age_days": user_account_age_days,
        "transaction_amount": transaction_amount,
        "prior_chargeback_count": prior_chargeback_count,
    }

    try:
        result_state = run_defense_agent(dispute_payload)
        response_data = result_state.model_dump()
        response_data["uploaded_image_url"] = f"/data/uploads/{saved_filename}"
        return JSONResponse(response_data)
    except Exception as e:
        logger.error(f"Error running custom upload analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def get_model_evaluation_data() -> Dict[str, Any]:
    """Loads the authoritative held-out test set evaluation artifact."""
    eval_path = Path(__file__).parent / "data" / "model_evaluation.json"
    if eval_path.exists():
        try:
            return json.loads(eval_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Could not parse {eval_path}: {e}")
    return {
        "business_decision_threshold": 0.85,
        "penalty_fee_per_lost_contest": 1500.0,
        "held_out_metrics_at_85_threshold": {
            "threshold": 0.85,
            "precision": 0.7116,
            "recall": 0.8302,
            "accuracy": 0.9356,
            "roc_auc": 0.9433,
            "brier_score": 0.0641,
            "confusion_matrix": {"true_positives": 528, "true_negatives": 4150, "false_positives": 214, "false_negatives": 108},
            "contested_count": 742,
            "cost_per_false_positive": 1500.0,
            "false_positive_penalty_cost": 321000.0
        },
        "dataset_metadata": {
            "total_samples": 25000,
            "train_samples": 20000,
            "held_out_samples": 5000,
            "held_out_positives": 636,
            "held_out_negatives": 4364
        },
        "validation_cost_matrix": []
    }


@app.get("/api/model-evaluation")
async def get_model_evaluation():
    """
    Returns the scientifically honest held-out test set evaluation artifact.
    Contains strictly quarantined held-out metrics, confusion matrix, and sample sizes.
    """
    data = get_model_evaluation_data()
    return JSONResponse(data)


@app.get("/api/cost-matrix")
async def get_cost_matrix():
    """Returns the validation-derived financial cost-matrix curve proving the 0.85 threshold."""
    eval_data = get_model_evaluation_data()
    held_out = eval_data.get("held_out_metrics_at_85_threshold", {})
    matrix = eval_data.get("validation_cost_matrix", [])

    return JSONResponse({
        "metrics": {
            "roc_auc_score": held_out.get("roc_auc", 0.9433),
            "brier_score_loss": held_out.get("brier_score", 0.0641),
            "optimal_threshold": 0.85,
            "precision": held_out.get("precision", 0.7116),
            "recall": held_out.get("recall", 0.8302),
            "false_positives": held_out.get("confusion_matrix", {}).get("false_positives", 214),
            "false_positive_penalty_cost": held_out.get("false_positive_penalty_cost", 321000.0),
            "dispute_loss_penalty_fee": 1500.0,
            "human_review_triage_cost": 200.0,
        },
        "table": matrix,
    })


@app.get("/api/razorpay-status")
async def get_razorpay_status():
    """Returns current Razorpay API connectivity mode: DEMO_SIMULATION, RAZORPAY_TEST_API, or RAZORPAY_LIVE_API."""
    from src.orchestrator.razorpay_client import razorpay_client
    mode = razorpay_client.get_api_mode()
    mode_badge = razorpay_client.get_mode_badge()
    header_label = razorpay_client.get_header_label()
    return JSONResponse({
        "mode": mode,
        "mode_badge": mode_badge,
        "header_label": header_label,
        "is_live": mode == "RAZORPAY_LIVE_API",
        "is_test": mode == "RAZORPAY_TEST_API",
        "is_simulated": mode == "DEMO_SIMULATION",
        "has_credentials": bool(razorpay_client.key_id and razorpay_client.key_secret),
        "sdk_installed": bool(razorpay_client.sdk_client is not None),
    })


@app.get("/api/vlm-config")
async def get_vlm_config():
    """Returns dynamically configured VLM providers and model names from environment."""
    load_dotenv(override=True)
    has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    primary_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite") if has_gemini else None
    fallback_model = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b") if has_groq else None

    # Format dynamic label
    parts = []
    if primary_model:
        # e.g. "gemini-3.5-flash-lite" -> "Gemini 3.5 Flash Lite"
        name = primary_model.replace("-", " ").title().replace("Gemini", "Gemini")
        parts.append(name)
    if fallback_model:
        # e.g. "qwen/qwen3.6-27b" -> "Groq Qwen 3.6 27B Fallback"
        clean_fb = fallback_model.split("/")[-1].replace("-", " ").title()
        parts.append(f"Groq {clean_fb} Fallback")
    council_label = " + ".join(parts) if parts else "Deterministic Rules"

    return JSONResponse({
        "primary_provider": "gemini" if has_gemini else None,
        "primary_model": primary_model,
        "fallback_provider": "groq" if has_groq else None,
        "fallback_model": fallback_model,
        "council_label": council_label,
    })


@app.post("/api/submit-contest")
async def submit_dispute_contest(req: SubmitContestRequest):
    """
    Submits authorized dispute defense. Uses official Razorpay SDK if configured,
    or transparent Demo Simulation mode if credentials are absent.
    """
    dispute_id = req.dispute_id or f"disp_{req.transaction_id[-10:]}"
    logger.info(f"Contest Submission requested for: {dispute_id} | Action: {req.action}")

    from src.orchestrator.razorpay_client import razorpay_client
    payload = req.evidence_payload or {}

    submission_res = razorpay_client.contest_dispute(
        dispute_id=dispute_id,
        evidence_payload=payload,
    )

    is_sim = submission_res.get("is_simulated", True)
    mode_badge = submission_res.get("mode_badge", "DEMO SIMULATION — NOT SENT TO RAZORPAY")
    final_status = submission_res.get("status", "DEMO_SIMULATION_COMPLETED")

    return JSONResponse({
        "status": final_status,
        "is_simulated": is_sim,
        "mode": submission_res.get("mode", "DEMO_SIMULATION"),
        "mode_badge": mode_badge,
        "http_code": 200,
        "dispute_id": dispute_id,
        "transaction_id": req.transaction_id,
        "action": req.action,
        "override_reason": req.override_reason,
        "submission_id": submission_res.get("submission_id", f"sim_{uuid.uuid4().hex[:12]}"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_endpoint": f"POST https://api.razorpay.com/v1/disputes/{dispute_id}/contest" if not is_sim else "LOCAL_SIMULATION_ONLY",
        "regulatory_framework": "Visa Compelling Evidence 3.0 / Mastercard Dispute Rules",
        "details": submission_res,
        "message": submission_res.get("message", f"Contestation processed in {mode_badge} mode.")
    })


@app.get("/api/queue")
async def get_analyst_queue():
    """Legacy analyst queue endpoint."""
    queue = [
        {
            "dispute_id": "DIS_DEMO_FRAUD001",
            "transaction_id": "pay_98a76b54c3210f",
            "amount": 119900,
            "status": "Awaiting Review",
            "win_probability": 0.991,
            "vlm_status": "CONTRADICTION FLAG",
            "exif_status": "INTACT",
            "risk_signal": "5-day-old account + 4 prior chargebacks",
        },
        {
            "dispute_id": "DIS_DEMO_BORDER002",
            "transaction_id": "pay_45e67f89d0123a",
            "amount": 14999,
            "status": "Priority Review",
            "win_probability": 0.79,
            "vlm_status": "CONTRADICTION FLAG",
            "exif_status": "INTACT",
            "risk_signal": "User accessed service from 2 IPs",
        },
    ]
    return JSONResponse(queue)


# ── NEW: Case Management Endpoints ────────────────────────────────────────────

@app.post("/api/disputes")
async def create_dispute(
    image: UploadFile = File(...),
    transaction_id: str = Form(...),
    amount: float = Form(...),
    reason: str = Form(...),
    claim: str = Form(...),
    merchant_category: str = Form("general"),
    user_account_age_days: int = Form(365),
    prior_chargeback_count: int = Form(0),
    customer_email: str = Form(""),
    customer_id: str = Form(""),
):
    """
    CUSTOMER endpoint: Create a new dispute with uploaded evidence.
    Returns only safe, customer-facing fields.
    Does NOT run ML analysis.
    """
    dispute_id = generate_dispute_id()
    logger.info(f"Creating dispute {dispute_id} for TX: {transaction_id}")

    # Save uploaded evidence to data/uploads/
    file_ext = Path(image.filename).suffix.lower() or ".jpg"
    safe_filename = f"{dispute_id}_{uuid.uuid4().hex[:8]}{file_ext}"
    saved_path = Path("data/uploads") / safe_filename

    content = await image.read()
    saved_path.write_bytes(content)
    size_bytes = len(content)

    # Build case payload
    payload = {
        "source": "customer_submitted",
        "transaction_id": transaction_id,
        "customer_id": customer_id or f"CUST_{uuid.uuid4().hex[:6].upper()}",
        "customer_email": customer_email,
        "amount": amount,
        "currency": "INR",
        "reason": reason,
        "claim": claim,
        "merchant_category": merchant_category,
        "user_account_age_days": user_account_age_days,
        "prior_chargeback_count": prior_chargeback_count,
        "evidence": {
            "source": "customer_submitted",
            "filename": image.filename,
            "path": str(saved_path),
            "url": f"/data/uploads/{safe_filename}",
            "mime_type": image.content_type or "image/jpeg",
            "size_bytes": size_bytes,
        },
        "status": STATUS_EVIDENCE_RECEIVED,
        "audit_trail": [
            {"event": "case_created", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"event": "evidence_received", "timestamp": datetime.now(timezone.utc).isoformat(),
             "metadata": {"filename": image.filename, "size_bytes": size_bytes}},
        ],
    }

    case = create_case(dispute_id, payload)

    # Return ONLY customer-safe fields
    return JSONResponse({
        "dispute_id": case["dispute_id"],
        "status": case["status"],
        "transaction_id": case["transaction_id"],
        "amount": case["amount"],
        "currency": case["currency"],
        "reason": case["reason"],
        "created_at": case["created_at"],
        "message": "Your dispute has been received. Our team will review the evidence.",
    }, status_code=201)


def map_customer_status(status: str, has_info_req: bool = False, submission_status: Optional[str] = None) -> str:
    if has_info_req or status == STATUS_EVIDENCE_REQUESTED:
        return "Action Required"
    elif status == STATUS_SUBMITTED:
        return "Contest Submission Prepared / Under Network Review"
    elif submission_status == "LIABILITY_CONCEDED":
        return "Resolved — Liability Accepted"
    elif status == STATUS_OVERRIDDEN:
        return "Resolved — Liability Accepted"
    elif status in (STATUS_EVIDENCE_RECEIVED, STATUS_ANALYZING, STATUS_ANALYSIS_COMPLETE, STATUS_AWAITING_REVIEW, STATUS_APPROVED):
        return "Under Review"
    return "Submitted"


@app.get("/api/customer/disputes")
async def list_customer_disputes_api(
    customer_id: Optional[str] = None,
    customer_email: Optional[str] = None,
):
    """
    CUSTOMER endpoint: Return only disputes belonging to the requesting customer.
    Sanitizes internal ML and model scores.
    """
    from src.case_store import list_customer_cases
    cases = list_customer_cases(customer_id=customer_id, customer_email=customer_email)

    # Customer portal MUST only show cases the customer themselves submitted.
    # Demo cases (source="demo") and legacy test cases (no source field) are Admin-only.
    cases = [c for c in cases if c.get("source") == "customer_submitted"]

    result = []
    for c in cases:
        ev = c.get("evidence") or {}
        supp_ev = c.get("supplementary_evidence")
        req = c.get("additional_info_request") or {}
        has_req = req.get("status") == "requested" or c.get("status") == STATUS_EVIDENCE_REQUESTED
        sub_status = (c.get("submission") or {}).get("status")
        result.append({
            "dispute_id": c["dispute_id"],
            "transaction_id": c.get("transaction_id", ""),
            "amount": c.get("amount", 0),
            "currency": c.get("currency", "INR"),
            "reason": c.get("reason", ""),
            "claim": c.get("claim", ""),
            "status": c.get("status", STATUS_NEW),
            "customer_status": map_customer_status(c.get("status", STATUS_NEW), has_req, sub_status),
            "has_action_required": has_req,
            "created_at": c.get("created_at", ""),
            "updated_at": c.get("updated_at", ""),
            "customer_id": c.get("customer_id", ""),
            "customer_email": c.get("customer_email", ""),
            "evidence": {
                "filename": ev.get("filename", ""),
                "url": ev.get("url", ""),
                "size_bytes": ev.get("size_bytes", 0),
            },
            "supplementary_evidence": supp_ev,
            "additional_info_request": c.get("additional_info_request"),
        })
    return JSONResponse(result)


@app.get("/api/customer/disputes/{dispute_id}")
async def get_customer_dispute_detail_api(
    dispute_id: str,
    customer_id: Optional[str] = None,
    customer_email: Optional[str] = None,
):
    """
    CUSTOMER endpoint: Return exact details of a single dispute owned by the customer.
    Enforces customer ownership verification.
    """
    case = get_case(dispute_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Dispute {dispute_id} not found.")

    # Block customer access to demo or backend internal files
    if case.get("source") != "customer_submitted":
        raise HTTPException(status_code=403, detail="This case is not accessible via the customer portal.")

    # Enforce customer ownership verification
    if not verify_customer_ownership(case, customer_id=customer_id, customer_email=customer_email):
        raise HTTPException(status_code=403, detail="Access denied: You do not have permission to view this dispute.")

    ev = case.get("evidence") or {}
    supp_ev = case.get("supplementary_evidence")
    req = case.get("additional_info_request") or {}
    has_req = req.get("status") == "requested" or case.get("status") == STATUS_EVIDENCE_REQUESTED
    sub_status = (case.get("submission") or {}).get("status")

    return JSONResponse({
        "dispute_id": case["dispute_id"],
        "transaction_id": case.get("transaction_id", ""),
        "amount": case.get("amount", 0),
        "currency": case.get("currency", "INR"),
        "reason": case.get("reason", ""),
        "claim": case.get("claim", ""),
        "status": case.get("status", STATUS_NEW),
        "customer_status": map_customer_status(case.get("status", STATUS_NEW), has_req, sub_status),
        "has_action_required": has_req,
        "created_at": case.get("created_at", ""),
        "updated_at": case.get("updated_at", ""),
        "customer_id": case.get("customer_id", ""),
        "customer_email": case.get("customer_email", ""),
        "evidence": {
            "filename": ev.get("filename", ""),
            "url": ev.get("url", ""),
            "size_bytes": ev.get("size_bytes", 0),
        },
        "supplementary_evidence": supp_ev,
        "additional_info_request": case.get("additional_info_request"),
    })


@app.get("/api/disputes")
async def list_disputes():

    """
    ADMIN endpoint: Return all dispute cases (full data).
    """
    cases = list_cases()
    # Return a summary view for the queue table
    summary = []
    for c in cases:
        ev = c.get("evidence") or {}
        summary.append({
            "dispute_id": c["dispute_id"],
            "source": c.get("source", "customer_submitted"),
            "transaction_id": c.get("transaction_id", ""),
            "customer_id": c.get("customer_id", ""),
            "customer_email": c.get("customer_email", ""),
            "amount": c.get("amount", 0),
            "currency": c.get("currency", "INR"),
            "reason": c.get("reason", ""),
            "claim": c.get("claim", ""),
            "status": c.get("status", STATUS_NEW),
            "evidence_received": ev.get("path") is not None,
            "evidence_url": ev.get("url"),
            "evidence_filename": ev.get("filename", ""),
            "routing_tier": (c.get("risk") or {}).get("routing_tier"),
            "win_probability": (c.get("risk") or {}).get("win_probability"),
            "created_at": c.get("created_at", ""),
            "updated_at": c.get("updated_at", ""),
        })
    return JSONResponse(summary)


@app.post("/api/admin/clear-old-disputes")
async def clear_old_disputes_api():
    """Clear legacy test disputes and re-seed fresh demo cases."""
    from src.case_store import cleanup_legacy_cases, seed_preset_cases
    cleanup_legacy_cases()
    seed_preset_cases()
    return JSONResponse({"status": "ok", "message": "Cleared legacy disputes"})


@app.get("/api/disputes/{dispute_id}")
async def get_dispute(dispute_id: str):
    """
    ADMIN endpoint: Return full case data for a specific dispute.
    """
    case = get_case(dispute_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Dispute {dispute_id} not found.")
    return JSONResponse(case)


@app.get("/api/disputes/{dispute_id}/evidence")
async def get_dispute_evidence(dispute_id: str):
    """
    Redirect to the static evidence file URL for a dispute.
    Never exposes arbitrary filesystem paths.
    """
    case = get_case(dispute_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Dispute {dispute_id} not found.")
    ev = case.get("evidence")
    if not ev or not ev.get("url"):
        raise HTTPException(status_code=404, detail="No evidence file found for this dispute.")
    return RedirectResponse(ev["url"])


@app.post("/api/disputes/{dispute_id}/analyze")
async def analyze_dispute_case(dispute_id: str):
    """
    ADMIN endpoint: Run the existing ML pipeline against the stored evidence.
    Reuses run_defense_agent() — zero duplicate ML logic.
    Persists analysis + risk results to the case JSON.
    """
    case = get_case(dispute_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Dispute {dispute_id} not found.")

    ev = case.get("evidence")
    if not ev or not ev.get("path"):
        raise HTTPException(status_code=400, detail="No evidence file found for this dispute.")

    image_path = ev["path"]
    if not Path(image_path).exists():
        raise HTTPException(status_code=400, detail=f"Evidence file not found on disk: {image_path}")

    # Update status
    update_case(dispute_id, {"status": STATUS_ANALYZING})
    append_audit_event(dispute_id, "analysis_started")

    try:
        dispute_payload = {
            "dispute_id": dispute_id,
            "transaction_id": case["transaction_id"],
            "order_id": f"order_{case['transaction_id'][-8:]}",
            "claim_text": case["claim"],
            "image_path": image_path,
            "reason_code": case.get("reason", "damaged").lower().replace(" ", "_").replace("/", "_"),
            "merchant_category": case.get("merchant_category", "general"),
            "user_account_age_days": case.get("user_account_age_days", 365),
            "transaction_amount": case.get("amount", 0),
            "prior_chargeback_count": case.get("prior_chargeback_count", 0),
        }

        result_state = run_defense_agent(dispute_payload)
        result = result_state.model_dump()

        # Extract perception/analysis fields
        perc = result.get("perception_result") or {}
        analysis_data = {
            "analysis_status": perc.get("analysis_status", "ANALYZED"),
            "vlm_available": perc.get("vlm_available", True),
            "vlm_contradiction_found": perc.get("vlm_contradiction_found", False),
            "claim_supported": perc.get("claim_supported", False),
            "physical_damage_visible": perc.get("physical_damage_visible", False),
            "vision_confidence_score": perc.get("vision_confidence_score"),
            "insufficient_evidence": perc.get("insufficient_evidence", False),
            "vision_reasoning": perc.get("vision_reasoning", ""),
            "operational_error": perc.get("operational_error"),
            "provider": perc.get("provider"),
            "model": perc.get("model"),
            "fallback_used": perc.get("fallback_used", False),
            "metadata_available": perc.get("metadata_available", False),
            "metadata_match": perc.get("metadata_match", False),
            "gps_available": perc.get("gps_available", False) or result.get("gps_available", False),
            "merchant_gps_available": result.get("merchant_gps_available", False),
            "timestamp_available": perc.get("timestamp_available", False) or result.get("timestamp_available", False),
            "merchant_timestamp_available": result.get("merchant_timestamp_available", False),
            "camera_device": perc.get("camera_device"),
            "gps_coordinates": perc.get("gps_coordinates"),
            "capture_timestamp": perc.get("capture_timestamp"),
            "exif_note": perc.get("exif_note") or "EXIF metadata presence alone does not establish image originality or authenticity.",
            # Telemetry correlation fields
            "gps_correlation": result.get("gps_correlation") or "NOT_VERIFIABLE",
            "gps_distance_meters": result.get("gps_distance_meters"),
            "gps_match_tolerance_meters": result.get("gps_match_tolerance_meters", 500),
            "timestamp_correlation": result.get("timestamp_correlation") or "NOT_VERIFIABLE",
            "timestamp_difference_minutes": result.get("timestamp_difference_minutes"),
            "timestamp_tolerance_minutes": result.get("timestamp_tolerance_minutes", 120),
            "merchant_reference": result.get("merchant_reference"),
        }

        risk_data = {
            "win_probability": result.get("win_probability"),
            "top_drivers": result.get("top_drivers", []),
            "routing_tier": result.get("routing_tier"),
            "final_action": result.get("final_action"),
            "action_details": result.get("action_details"),
        }

        update_case(dispute_id, {
            "status": STATUS_ANALYSIS_COMPLETE,
            "analysis": analysis_data,
            "risk": risk_data,
        })
        append_audit_event(dispute_id, "analysis_completed", {
            "routing_tier": risk_data.get("routing_tier"),
            "win_probability": risk_data.get("win_probability"),
        })

        return JSONResponse({
            "dispute_id": dispute_id,
            "status": STATUS_ANALYSIS_COMPLETE,
            "analysis": analysis_data,
            "risk": risk_data,
        })

    except Exception as e:
        update_case(dispute_id, {"status": STATUS_EVIDENCE_RECEIVED})
        logger.error(f"Analysis failed for {dispute_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/disputes/{dispute_id}/review")
async def review_dispute(dispute_id: str, req: ReviewRequest):
    """
    ADMIN endpoint: Persist analyst review determination to the case.
    """
    case = get_case(dispute_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Dispute {dispute_id} not found.")

    action = req.action.upper()
    if action not in ("APPROVE", "OVERRIDE", "REQUEST_EVIDENCE"):
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    review_data = {
        "action": action,
        "override_strategy": req.override_strategy if action == "OVERRIDE" else None,
        "override_reason": req.override_reason if action == "OVERRIDE" else None,
        "evidence_type": req.evidence_type if action == "REQUEST_EVIDENCE" else None,
        "evidence_note": req.evidence_note if action == "REQUEST_EVIDENCE" else None,
        "analyst_name": req.analyst_name,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }

    status_map = {
        "APPROVE": STATUS_APPROVED,
        "OVERRIDE": STATUS_OVERRIDDEN,
        "REQUEST_EVIDENCE": STATUS_EVIDENCE_REQUESTED,
    }
    new_status = status_map[action]

    update_case(dispute_id, {"status": new_status, "review": review_data})

    event_map = {
        "APPROVE": "analyst_approved",
        "OVERRIDE": "analyst_overrode",
        "REQUEST_EVIDENCE": "analyst_requested_evidence",
    }
    target_event = event_map[action]
    existing_trail = case.get("audit_trail") or []
    # Avoid appending duplicate review event only if the immediately preceding event is already this action
    is_immediate_duplicate = bool(existing_trail and isinstance(existing_trail[-1], dict) and existing_trail[-1].get("event") == target_event)
    if not is_immediate_duplicate:
        append_audit_event(dispute_id, target_event, {"analyst": req.analyst_name})

    return JSONResponse({
        "dispute_id": dispute_id,
        "status": new_status,
        "review": review_data,
    })


class RequestInfoPayload(BaseModel):
    title: str = "Original Delivery Evidence Required"
    message: str = "Please upload the original delivery photograph and provide the delivery date."
    requested_by: Optional[str] = "Chethana A."


@app.post("/api/disputes/{dispute_id}/request-info")
async def request_additional_info(dispute_id: str, req: RequestInfoPayload):
    """
    ADMIN endpoint: Request additional information from the customer.
    Persists the request and sets status to WAITING FOR CUSTOMER (evidence_requested).
    """
    case = get_case(dispute_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Dispute {dispute_id} not found.")

    req_data = {
        "status": "requested",
        "title": req.title,
        "message": req.message,
        "requested_by": req.requested_by or "Chethana A.",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "response": None,
    }

    update_case(dispute_id, {
        "status": STATUS_EVIDENCE_REQUESTED,
        "additional_info_request": req_data,
    })

    append_audit_event(dispute_id, "additional_info_requested", {
        "title": req.title,
        "requested_by": req.requested_by or "Chethana A.",
    })

    return JSONResponse({
        "dispute_id": dispute_id,
        "status": STATUS_EVIDENCE_REQUESTED,
        "additional_info_request": req_data,
    })


@app.post("/api/disputes/{dispute_id}/respond-info")
@app.post("/api/customer/disputes/{dispute_id}/respond-info")
async def respond_additional_info(
    dispute_id: str,
    message: str = Form(""),
    customer_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """
    CUSTOMER endpoint: Respond to an additional information request with text and/or file.
    Updates request status to responded, attaches evidence, and updates case status to evidence_received.
    """
    case = get_case(dispute_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Dispute {dispute_id} not found.")

    if customer_id and case.get("customer_id") and not verify_customer_ownership(case, customer_id=customer_id):
        raise HTTPException(status_code=403, detail="Access denied: Dispute belongs to another customer.")

    ev_info = None
    if file:
        file_bytes = await file.read()
        suffix = Path(file.filename).suffix or ".jpg"
        unique_name = f"{dispute_id}_supp_{uuid.uuid4().hex[:8]}{suffix}"
        save_path = Path("data/uploads") / unique_name

        with open(save_path, "wb") as f:
            f.write(file_bytes)

        ev_info = {
            "source": "customer_requested_response",
            "filename": file.filename,
            "path": str(save_path),
            "url": f"/data/uploads/{unique_name}",
            "mime_type": file.content_type or "image/jpeg",
            "size_bytes": len(file_bytes),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

    req_data = case.get("additional_info_request") or {}
    req_data["status"] = "responded"
    req_data["response"] = {
        "message": message,
        "evidence": ev_info,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "submitted_by": customer_id or case.get("customer_id", "CUST_001"),
    }

    update_fields = {
        "status": STATUS_EVIDENCE_RECEIVED,
        "additional_info_request": req_data,
    }
    if file and ev_info:
        # Save separately as supplementary_evidence to NEVER overwrite original customer evidence
        update_fields["supplementary_evidence"] = ev_info

    update_case(dispute_id, update_fields)

    append_audit_event(dispute_id, "customer_info_responded", {
        "has_supplementary_evidence": file is not None,
        "submitted_by": customer_id or case.get("customer_id", "CUST_001"),
    })

    return JSONResponse({
        "dispute_id": dispute_id,
        "status": STATUS_EVIDENCE_RECEIVED,
        "additional_info_request": req_data,
        "evidence": case.get("evidence"),
        "supplementary_evidence": ev_info or case.get("supplementary_evidence"),
    })


@app.post("/api/disputes/{dispute_id}/submit")
async def submit_dispute(dispute_id: str):
    """
    ADMIN endpoint: Execute the Razorpay contestation and persist the result.
    Reuses the existing razorpay_client — zero duplicate logic.
    """
    case = get_case(dispute_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Dispute {dispute_id} not found.")

    review = case.get("review")
    if not review:
        raise HTTPException(status_code=400, detail="Dispute must be reviewed before submission.")

    action = review.get("action")
    if action == "REQUEST_EVIDENCE":
        req_data = {
            "status": "requested",
            "title": f"Information Required: {review.get('evidence_type', 'Supporting Documentation')}",
            "message": review.get("evidence_note") or "Please provide clarifying evidence for your dispute.",
            "requested_by": review.get("analyst_name", "Chethana A."),
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "response": None,
        }
        update_case(dispute_id, {
            "status": STATUS_EVIDENCE_REQUESTED,
            "additional_info_request": req_data,
        })
        append_audit_event(dispute_id, "evidence_requested_dispatched", {
            "type": review.get("evidence_type"),
            "note": review.get("evidence_note")
        })
        return JSONResponse({
            "dispute_id": dispute_id,
            "status": STATUS_EVIDENCE_REQUESTED,
            "message": "Information request dispatched to customer.",
            "additional_info_request": req_data,
        })

    is_concede = (action == "OVERRIDE" and review.get("override_strategy") == "CONCEDE") or (
        action == "APPROVE" and (
            (case.get("risk") or {}).get("routing_tier") in ("STANDARD_REVIEW", "CONCEDE")
            or ((case.get("risk") or {}).get("win_probability", 1.0) < 0.85)
        )
    )

    if is_concede:
        concede_reason = review.get("override_reason") or "Analyst approved Concede Liability recommendation to avoid penalty fee."
        submission_data = {
            "status": "LIABILITY_CONCEDED",
            "action": "CONCEDE",
            "reason": concede_reason,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        final_status = STATUS_APPROVED if action == "APPROVE" else STATUS_OVERRIDDEN
        update_case(dispute_id, {
            "status": final_status,
            "submission": submission_data,
        })
        append_audit_event(dispute_id, "liability_conceded", {
            "reason": concede_reason,
            "analyst": review.get("analyst_name", "Chethana A.")
        })
        append_audit_event(dispute_id, "final_resolution_recorded")
        return JSONResponse({
            "dispute_id": dispute_id,
            "status": final_status,
            "submission": submission_data,
        })

    risk = case.get("risk") or {}
    analysis = case.get("analysis") or {}

    append_audit_event(dispute_id, "submission_started")

    from src.orchestrator.razorpay_client import razorpay_client

    razorpay_dispute_id = f"disp_{case['transaction_id'][-10:]}"

    evidence_payload = razorpay_client.build_ce3_evidence_payload(
        transaction_id=case["transaction_id"],
        claim_text=case["claim"],
        reason_code=case.get("reason", "damaged"),
        perception_data=analysis,
        order_id=f"order_{case['transaction_id'][-8:]}",
    )

    submission_res = razorpay_client.contest_dispute(
        dispute_id=razorpay_dispute_id,
        evidence_payload=evidence_payload,
    )

    is_sim = submission_res.get("is_simulated", True)
    mode_badge = submission_res.get("mode_badge", "DEMO SIMULATION — NOT SENT TO RAZORPAY")
    final_sub_status = submission_res.get("status", "DEMO_SIMULATION_COMPLETED")

    submission_data = {
        "status": final_sub_status,
        "is_simulated": is_sim,
        "mode": submission_res.get("mode", "DEMO_SIMULATION"),
        "mode_badge": mode_badge,
        "razorpay_dispute_id": razorpay_dispute_id,
        "submission_id": submission_res.get("submission_id", f"sim_{uuid.uuid4().hex[:12]}"),
        "action": review.get("action"),
        "api_endpoint": f"POST https://api.razorpay.com/v1/disputes/{razorpay_dispute_id}/contest" if not is_sim else "LOCAL_SIMULATION_ONLY",
        "regulatory_framework": "Visa Compelling Evidence 3.0 / Mastercard Dispute Rules",
        "evidence_payload": evidence_payload,
        "razorpay_response": submission_res,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    update_case(dispute_id, {
        "status": STATUS_SUBMITTED,
        "submission": submission_data,
    })
    append_audit_event(dispute_id, "submission_completed", {
        "submission_id": submission_data["submission_id"],
    })

    return JSONResponse({
        "dispute_id": dispute_id,
        "status": STATUS_SUBMITTED,
        "submission": submission_data,
    })


@app.get("/api/disputes/{dispute_id}/audit-receipt")
async def download_audit_receipt(dispute_id: str):
    """
    ADMIN endpoint: Generate and return a professional PDF audit receipt for a dispute.
    Uses ReportLab. All data comes from the authoritative case store record.
    """
    case = get_case(dispute_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Dispute {dispute_id} not found.")

    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=18*mm, rightMargin=18*mm,
            topMargin=16*mm, bottomMargin=16*mm
        )

        W, H = A4
        styles = getSampleStyleSheet()

        # ── Custom Styles ──────────────────────────────────────────────────────
        NAVY   = colors.HexColor("#111a4a")
        TEAL   = colors.HexColor("#167e6c")
        SLATE  = colors.HexColor("#4a5568")
        RED    = colors.HexColor("#dc2626")
        GREEN  = colors.HexColor("#059669")
        AMBER  = colors.HexColor("#b45309")
        LGRAY  = colors.HexColor("#f1f5f9")
        BORDER = colors.HexColor("#cbd5e1")

        def style(name, **kw):
            s = ParagraphStyle(name, parent=styles["Normal"], **kw)
            return s

        S_TITLE    = style("title",    fontSize=20, textColor=NAVY,  leading=24, spaceAfter=2, fontName="Helvetica-Bold", alignment=TA_LEFT)
        S_SUBTITLE = style("subtitle", fontSize=10, textColor=TEAL,  leading=14, spaceAfter=0, fontName="Helvetica")
        S_H2       = style("h2",       fontSize=11, textColor=NAVY,  leading=14, spaceAfter=4, spaceBefore=10, fontName="Helvetica-Bold")
        S_LABEL    = style("label",    fontSize=8,  textColor=SLATE, leading=11, fontName="Helvetica-Bold")
        S_VALUE    = style("value",    fontSize=9,  textColor=NAVY,  leading=13, fontName="Helvetica")
        S_SMALL    = style("small",    fontSize=7.5,textColor=SLATE, leading=10, fontName="Helvetica")
        S_NOTE     = style("note",     fontSize=8,  textColor=AMBER, leading=11, fontName="Helvetica-Oblique")

        def section(title):
            return [
                Spacer(1, 4*mm),
                HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=2),
                Paragraph(title.upper(), S_H2),
            ]

        def kv_table(rows, col_widths=None):
            """Render a two-column key-value table."""
            if not col_widths:
                col_widths = [55*mm, 105*mm]
            data = [[Paragraph(k, S_LABEL), Paragraph(str(v) if v is not None else "—", S_VALUE)] for k, v in rows]
            t = Table(data, colWidths=col_widths)
            t.setStyle(TableStyle([
                ("VALIGN",   (0,0),(-1,-1), "TOP"),
                ("ROWBACKGROUNDS", (0,0),(-1,-1), [LGRAY, colors.white]),
                ("TOPPADDING",    (0,0),(-1,-1), 4),
                ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                ("LEFTPADDING",   (0,0),(-1,-1), 5),
                ("RIGHTPADDING",  (0,0),(-1,-1), 5),
            ]))
            return t

        def fmt_ts(ts):
            if not ts:
                return "—"
            try:
                return datetime.fromisoformat(ts).strftime("%d %b %Y, %H:%M UTC")
            except Exception:
                return str(ts)

        def fmt_inr(amt):
            if amt is None:
                return "—"
            return f"\u20b9{float(amt):,.2f}"

        story = []

        # ── Header ────────────────────────────────────────────────────────────
        story.append(Paragraph("REBUTTAL", S_TITLE))
        story.append(Paragraph("Automated Dispute Defense Platform — Audit Receipt", S_SUBTITLE))
        story.append(Paragraph("Razorpay Buildathon 2026 · Visa Compelling Evidence 3.0", S_SMALL))
        story.append(Spacer(1, 3*mm))
        story.append(HRFlowable(width="100%", thickness=1.5, color=TEAL, spaceAfter=2))

        # ── Case Information ──────────────────────────────────────────────────
        story += section("01 · Case Information")
        source_label = "DEMO CASE" if case.get("source") == "demo" else "CUSTOMER SUBMITTED"
        sub_data = case.get("submission") or {}
        if sub_data.get("status") == "LIABILITY_CONCEDED" or sub_data.get("action") == "CONCEDE":
            status_display = "LIABILITY_CONCEDED"
        elif sub_data.get("status"):
            status_display = sub_data.get("status").upper()
        else:
            status_display = (case.get("status", "—") or "—").upper()

        story.append(kv_table([
            ("Dispute ID",      case.get("dispute_id", "—")),
            ("Case Source",     source_label),
            ("Transaction ID",  case.get("transaction_id", "—")),
            ("Customer ID",     case.get("customer_id", "—")),
            ("Customer Email",  case.get("customer_email", "—")),
            ("Submission Date", fmt_ts(case.get("created_at"))),
            ("Last Updated",    fmt_ts(case.get("updated_at"))),
            ("Current Status",  status_display),
        ]))

        # ── Transaction & Claim ───────────────────────────────────────────────
        story += section("02 · Transaction & Claim")
        story.append(kv_table([
            ("Dispute Amount",     fmt_inr(case.get("amount"))),
            ("Currency",           case.get("currency", "INR")),
            ("Dispute Reason",     case.get("reason", "—")),
            ("Merchant Category",  case.get("merchant_category", "—")),
            ("Account Age (days)", str(case.get("user_account_age_days", "—"))),
            ("Prior Chargebacks",  str(case.get("prior_chargeback_count", "—"))),
        ]))
        claim = case.get("claim", "")
        if claim:
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph("Customer Claim Statement:", S_LABEL))
            story.append(Paragraph(f'"{claim}"', S_VALUE))

        # ── Evidence ──────────────────────────────────────────────────────────
        story += section("03 · Submitted Evidence")
        ev = case.get("evidence") or {}
        ev_rows = [
            ("Original Filename",      ev.get("filename", "—")),
            ("File Type",              ev.get("mime_type", "—")),
            ("File Size",              f"{ev.get('size_bytes', 0) / 1024:.1f} KB" if ev.get("size_bytes") else "—"),
            ("Upload Source",          ev.get("source", "customer_submitted")),
            ("Evidence URL",           ev.get("url", "—")),
        ]
        supp_ev = case.get("supplementary_evidence")
        if supp_ev:
            ev_rows.extend([
                ("Supplementary Evidence", supp_ev.get("filename", "—")),
                ("Supp. File Type",        supp_ev.get("mime_type", "—")),
                ("Supp. File Size",        f"{supp_ev.get('size_bytes', 0) / 1024:.1f} KB" if supp_ev.get("size_bytes") else "—"),
                ("Supp. Uploaded At",      fmt_ts(supp_ev.get("uploaded_at"))),
            ])
        story.append(kv_table(ev_rows))

        # ── Forensic Analysis ─────────────────────────────────────────────────
        story += section("04 · Forensic Analysis")
        analysis = case.get("analysis") or {}

        # EXIF & Telemetry
        exif_avail  = bool(analysis.get("metadata_available"))
        exif_status = "EXIF METADATA PRESENT" if exif_avail else "EXIF METADATA UNAVAILABLE / STRIPPED"
        gps_raw     = analysis.get("gps_coordinates")
        if isinstance(gps_raw, dict) and gps_raw.get("latitude") is not None:
            gps_str = f"{gps_raw.get('latitude'):.6f}, {gps_raw.get('longitude'):.6f}"
        elif gps_raw and str(gps_raw).strip() not in ("Unavailable", "GPS unavailable"):
            gps_str = str(gps_raw)
        else:
            gps_str = "EXIF metadata available — GPS unavailable" if exif_avail else "EXIF metadata unavailable / stripped"

        ts_raw = analysis.get("capture_timestamp")
        ts_str = str(ts_raw) if ts_raw else "Unavailable"

        gps_cor   = analysis.get("gps_correlation") or "NOT_VERIFIABLE"
        gps_dist  = analysis.get("gps_distance_meters")
        ts_cor    = analysis.get("timestamp_correlation") or "NOT_VERIFIABLE"
        ts_diff   = analysis.get("timestamp_difference_minutes")
        mer_ref   = analysis.get("merchant_reference")

        if gps_cor == "MATCH":
            gps_cor_str = f"MATCH ({gps_dist:.1f} m distance, tolerance: 500 m)"
        elif gps_cor == "MISMATCH":
            gps_cor_str = f"MISMATCH ({gps_dist:.1f} m distance, tolerance: 500 m)"
        else:
            gps_cor_str = "NOT VERIFIABLE (correlation could not be performed)"

        if ts_cor == "MATCH":
            ts_cor_str = f"MATCH (Δ{ts_diff} min, tolerance: 120 min)"
        elif ts_cor == "MISMATCH":
            ts_cor_str = f"MISMATCH (Δ{ts_diff} min, tolerance: 120 min)"
        else:
            ts_cor_str = "NOT VERIFIABLE (correlation could not be performed)"

        mer_label = "DEMO MERCHANT RECORD (Synthetic)" if mer_ref else "UNAVAILABLE — correlation not verifiable"

        story.append(kv_table([
            ("EXIF Metadata",         exif_status),
            ("Camera / Device",       analysis.get("camera_device") or "Unavailable"),
            ("Capture Timestamp",     ts_str),
            ("GPS Coordinates",       gps_str),
            ("GPS Correlation",       gps_cor_str),
            ("Timestamp Correlation", ts_cor_str),
            ("Merchant Telemetry",    mer_label),
        ]))

        story.append(Spacer(1, 1.5*mm))
        story.append(Paragraph(
            "Note: EXIF metadata presence alone does not establish image originality or authenticity. "
            "Telemetry correlation is only marked MATCH when verified against independent merchant delivery records.",
            S_NOTE
        ))

        # VLM
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("VLM Visual Assessment", S_H2))
        vlm_found = analysis.get("vlm_contradiction_found")
        vlm_insuf = analysis.get("insufficient_evidence")
        if vlm_insuf:
            vlm_finding = "EVIDENCE INCONCLUSIVE"
        elif vlm_found:
            vlm_finding = "CLAIM CONTRADICTED BY SUBMITTED EVIDENCE"
        elif vlm_found is False:
            vlm_finding = "CLAIM CONSISTENT WITH SUBMITTED EVIDENCE"
        else:
            vlm_finding = "PENDING / NOT RUN"

        story.append(kv_table([
            ("Visual Assessment",       vlm_finding),
            ("Visual Confidence",       f"{(analysis.get('vision_confidence_score', 0) * 100):.1f}%" if analysis.get('vision_confidence_score') is not None else "—"),
            ("Insufficient Evidence",   "Yes" if vlm_insuf else ("No" if vlm_insuf is False else "—")),
            ("Vision Reasoning",        (analysis.get("vision_reasoning") or "—")[:280]),
        ]))

        # ── Risk Assessment ───────────────────────────────────────────────────
        story += section("05 · Risk Assessment")
        risk = case.get("risk") or {}
        win_prob = risk.get("win_probability")
        win_prob_str = f"{win_prob * 100:.1f}%" if win_prob is not None else "PENDING"
        margin = (win_prob - 0.85) * 100 if win_prob is not None else None
        margin_str = (f"+{margin:.1f}%" if margin >= 0 else f"{margin:.1f}%") if margin is not None else "—"

        # Derive routing dynamically from application decision logic (Threshold = 85.0%)
        if win_prob is not None:
            routing = "AUTO-CONTEST" if win_prob >= 0.85 else "CONCEDE LIABILITY"
        elif risk.get("routing_tier"):
            tier = risk.get("routing_tier")
            if tier == "AUTO_CONTEST":
                routing = "AUTO-CONTEST"
            elif tier in ("STANDARD_REVIEW", "CONCEDE"):
                routing = "CONCEDE LIABILITY"
            else:
                routing = tier.replace("_", " ")
        else:
            routing = "PENDING"

        eval_data = get_model_evaluation_data()
        held_out = eval_data.get("held_out_metrics_at_85_threshold", {})
        roc_auc_val = held_out.get("roc_auc", 0.9433)
        brier_val = held_out.get("brier_score", 0.0641)

        story.append(kv_table([
            ("CatBoost Win Probability", win_prob_str),
            ("Policy Threshold",         "85.0% (Calibrated Operational Decision Boundary)"),
            ("Policy Margin",            margin_str),
            ("ROC-AUC Benchmark",        f"{roc_auc_val:.4f} (Evaluated on held-out test set, n=5,000)"),
            ("Brier Calibration Score",  f"{brier_val:.4f} (Evaluated on held-out test set, n=5,000)"),
            ("Recommended Routing",      routing),
        ]))

        # XAI
        drivers = risk.get("top_drivers") or []
        if drivers:
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph("XAI / Feature Attribution", S_H2))
            xai_data = [["Feature", "Impact", "Direction"]]

            # Check telemetry and VLM status from analysis to match UI behavior
            analysis_dict = case.get("analysis") or {}
            exif_avail = bool(analysis_dict.get("metadata_available"))
            gps_cor = analysis_dict.get("gps_correlation") or "NOT_VERIFIABLE"
            ts_cor = analysis_dict.get("timestamp_correlation") or "NOT_VERIFIABLE"
            vlm_insuf = bool(analysis_dict.get("insufficient_evidence"))
            vlm_failed = analysis_dict.get("analysis_status") == "ANALYSIS_FAILED" or analysis_dict.get("vlm_available") is False

            for drv in drivers[:6]:
                feat_raw = drv.get("feature", "—")
                impact   = drv.get("impact", 0)

                if feat_raw == "metadata_match":
                    is_correlated = (gps_cor in ("MATCH", "MISMATCH") or ts_cor in ("MATCH", "MISMATCH"))
                    if not is_correlated:
                        feat_display = "metadata_available"
                        dir_display  = "— Not Verifiable"
                    else:
                        feat_display = "metadata_match"
                        dir_display  = "▲ Increases Win Prob" if impact > 0 else "▼ Reduces Win Prob"
                elif feat_raw == "vlm_contradiction_found":
                    feat_display = "vlm_contradiction_found"
                    if vlm_failed:
                        dir_display = "— Not Applicable"
                    elif vlm_insuf:
                        dir_display = "— Not Verifiable"
                    else:
                        dir_display = "▲ Increases Win Prob" if impact > 0 else "▼ Reduces Win Prob"
                else:
                    feat_display = feat_raw
                    dir_display  = "▲ Increases Win Prob" if impact > 0 else "▼ Reduces Win Prob"

                xai_data.append([feat_display, f"{impact:+.4f}", dir_display])

            xt = Table(xai_data, colWidths=[75*mm, 35*mm, 50*mm])
            xt.setStyle(TableStyle([
                ("BACKGROUND",   (0,0),(-1,0), NAVY),
                ("TEXTCOLOR",    (0,0),(-1,0), colors.white),
                ("FONTNAME",     (0,0),(-1,0), "Helvetica-Bold"),
                ("FONTSIZE",     (0,0),(-1,-1), 8),
                ("ROWBACKGROUNDS",(0,1),(-1,-1), [LGRAY, colors.white]),
                ("ALIGN",        (1,0),(-1,-1), "CENTER"),
                ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
                ("TOPPADDING",   (0,0),(-1,-1), 4),
                ("BOTTOMPADDING",(0,0),(-1,-1), 4),
                ("LEFTPADDING",  (0,0),(-1,-1), 6),
                ("RIGHTPADDING", (0,0),(-1,-1), 6),
                ("GRID",         (0,0),(-1,-1), 0.3, BORDER),
            ]))
            story.append(xt)

        # ── Analyst Review ────────────────────────────────────────────────────
        story += section("06 · Analyst Review")
        review = case.get("review") or {}
        if review:
            analyst_action = review.get("action", "—")
            analyst_decision_str = f"APPROVE ({routing})" if analyst_action == "APPROVE" else analyst_action
            is_ev_req = (analyst_action == "REQUEST_EVIDENCE") or bool(case.get("additional_info_request"))
            ev_req = review.get("evidence_type") if is_ev_req else None
            ev_note = review.get("evidence_note") if is_ev_req else None
            story.append(kv_table([
                ("System Recommendation", routing),
                ("Analyst Decision",      analyst_decision_str),
                ("Override Strategy",     review.get("override_strategy") or "N/A"),
                ("Override Reason",       review.get("override_reason") or "N/A"),
                ("Evidence Requested",    ev_req or "N/A"),
                ("Evidence Note",         ev_note or "N/A"),
                ("Analyst Name",          review.get("analyst_name", "—")),
                ("Decision Timestamp",    fmt_ts(review.get("reviewed_at"))),
            ]))
        else:
            story.append(Paragraph("No analyst review recorded for this dispute.", S_VALUE))

        # ── Final Resolution ──────────────────────────────────────────────────
        story += section("07 · Final Resolution")
        submission = case.get("submission") or {}
        if submission:
            is_concede = submission.get("action") == "CONCEDE" or submission.get("status") == "LIABILITY_CONCEDED"
            op_mode = submission.get("mode_badge") or ("INTERNAL RESOLUTION (LIABILITY CONCEDED)" if is_concede else "DEMO SIMULATION — NOT SENT TO RAZORPAY")
            rzp_id = submission.get("razorpay_dispute_id") or ("N/A (Internal Concession)" if is_concede else "—")
            sub_id = submission.get("submission_id") or (f"concede_{dispute_id}" if is_concede else "—")
            api_ep = submission.get("api_endpoint") or ("N/A (Internal Settlement — No Network Transmission)" if is_concede else "—")
            framework = submission.get("regulatory_framework") or ("Visa CE 3.0 / Network Dispute Rules (Liability Conceded)" if is_concede else "—")

            # Canonical resolution timestamp aligns with active decision, not stale predecessor
            submitted_ts = submission.get("submitted_at")
            rev_ts = review.get("reviewed_at") if review else None
            if rev_ts and submitted_ts and submitted_ts < rev_ts:
                submitted_ts = rev_ts

            story.append(kv_table([
                ("Final Status",       submission.get("status", "—")),
                ("Operating Mode",     op_mode),
                ("Final Action",       submission.get("action", "—")),
                ("Razorpay Dispute ID",rzp_id),
                ("Submission ID",      sub_id),
                ("API Endpoint",       api_ep),
                ("Framework",          framework),
                ("Concede Reason",     submission.get("reason", "—") if is_concede else "N/A"),
                ("Submitted At",       fmt_ts(submitted_ts)),
            ]))
        else:
            story.append(Paragraph("No final submission recorded for this dispute.", S_VALUE))

        # ── Audit Trail ───────────────────────────────────────────────────────
        story += section("08 · Audit Trail")
        trail = case.get("audit_trail") or []
        if trail:
            trail_data = [["Timestamp (UTC)", "Event Description", "Event Category"]]

            # Find index of the final analyst_approved and liability_conceded events
            last_approval_idx = -1
            last_concede_idx = -1
            for idx, entry in enumerate(trail):
                if isinstance(entry, dict):
                    if entry.get("event") == "analyst_approved":
                        last_approval_idx = idx
                    elif entry.get("event") == "liability_conceded":
                        last_concede_idx = idx

            start_idx = 0
            comp_idx = 0
            seen_entries = set()
            for idx, entry in enumerate(trail):
                if isinstance(entry, dict):
                    ts_str  = fmt_ts(entry.get("timestamp"))
                    evt_raw = entry.get("event") or ""

                    if evt_raw == "analysis_started":
                        start_idx += 1
                        if start_idx == 1:
                            evt_str = "Initial Analysis Started"
                            evt_type = "Automated Analysis"
                        else:
                            evt_str = f"Re-Analysis Started (Run #{start_idx})"
                            evt_type = "Diagnostic Re-Run"
                    elif evt_raw == "analysis_completed":
                        comp_idx += 1
                        if comp_idx == 1:
                            evt_str = "Initial Analysis Completed"
                            evt_type = "Automated Analysis"
                        else:
                            evt_str = f"Re-Analysis Completed (Run #{comp_idx})"
                            evt_type = "Diagnostic Re-Run"
                    elif evt_raw == "analyst_approved":
                        if idx == last_approval_idx:
                            evt_str = "Analyst Approved"
                            evt_type = "Business Decision"
                        else:
                            evt_str = "Prior Decision (Superseded by Re-Analysis)"
                            evt_type = "Superseded History"
                    elif evt_raw == "liability_conceded":
                        if idx == last_concede_idx and idx >= last_approval_idx:
                            evt_str = "Liability Conceded"
                            evt_type = "Business Decision"
                        else:
                            evt_str = "Prior Resolution (Superseded by Re-Analysis)"
                            evt_type = "Superseded History"
                    elif evt_raw in ("prior_determination_superseded", "prior_analyst_decision_superseded", "prior_decision_superseded"):
                        evt_str = "Prior Decision (Superseded by Re-Analysis)"
                        evt_type = "Superseded History"
                    elif evt_raw in ("prior_concession_reopened", "prior_liability_conceded", "prior_concession_superseded", "prior_resolution_superseded"):
                        evt_str = "Prior Resolution (Superseded by Re-Analysis)"
                        evt_type = "Superseded History"
                    elif evt_raw == "final_resolution_recorded":
                        if idx >= last_approval_idx:
                            evt_str = "Final Resolution Recorded"
                            evt_type = "Business Decision"
                        else:
                            evt_str = "Prior Resolution (Superseded by Re-Analysis)"
                            evt_type = "Superseded History"
                    elif evt_raw == "case_created":
                        evt_str = "Case Created"
                        evt_type = "Case Lifecycle"
                    elif evt_raw == "evidence_received":
                        evt_str = "Evidence Received"
                        evt_type = "Case Lifecycle"
                    else:
                        evt_str = evt_raw.replace("_", " ").title()
                        evt_type = "Operational Log"
                elif isinstance(entry, str):
                    ts_str  = "—"
                    evt_str = entry
                    evt_type = "Log Entry"
                else:
                    continue

                # Deduplicate identical superseded events for the same timestamp
                dedup_key = (ts_str, evt_str)
                if dedup_key in seen_entries:
                    continue
                seen_entries.add(dedup_key)

                trail_data.append([ts_str, evt_str, evt_type])

            tt = Table(trail_data, colWidths=[42*mm, 78*mm, 40*mm])
            tt.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,0), NAVY),
                ("TEXTCOLOR",     (0,0),(-1,0), colors.white),
                ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
                ("FONTSIZE",      (0,0),(-1,-1), 8),
                ("ROWBACKGROUNDS",(0,1),(-1,-1), [LGRAY, colors.white]),
                ("VALIGN",        (0,0),(-1,-1), "TOP"),
                ("TOPPADDING",    (0,0),(-1,-1), 4),
                ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                ("LEFTPADDING",   (0,0),(-1,-1), 5),
                ("RIGHTPADDING",  (0,0),(-1,-1), 5),
                ("GRID",          (0,0),(-1,-1), 0.3, BORDER),
            ]))
            story.append(tt)
        else:
            story.append(Paragraph("No audit trail events recorded.", S_VALUE))

        # ── Footer ────────────────────────────────────────────────────────────
        story.append(Spacer(1, 6*mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 2*mm))
        generated_at = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
        story.append(Paragraph(
            f"Generated by Rebuttal Dispute Defense Platform · {generated_at} · "
            f"For internal compliance and audit purposes only.",
            S_SMALL
        ))

        doc.build(story)
        buf.seek(0)

        filename = f"Audit_Receipt_{dispute_id}.pdf"
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    except Exception as e:
        logger.error(f"PDF generation failed for {dispute_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Rebuttal Dispute Defense Platform on http://127.0.0.1:8000...")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
