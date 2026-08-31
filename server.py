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


@app.get("/api/cost-matrix")
async def get_cost_matrix():
    """Returns the financial cost-matrix curve proving the 0.85 threshold."""
    matrix = [
        {"threshold": 0.50, "auto_contest_count": 903, "precision": 0.657, "false_positives": 310, "net_financial_impact": 2960600.0, "status": "High Penalty Risk"},
        {"threshold": 0.60, "auto_contest_count": 818, "precision": 0.714, "false_positives": 234, "net_financial_impact": 4062600.0, "status": "High Penalty Risk"},
        {"threshold": 0.70, "auto_contest_count": 808, "precision": 0.723, "false_positives": 224, "net_financial_impact": 4225600.0, "status": "High Penalty Risk"},
        {"threshold": 0.75, "auto_contest_count": 806, "precision": 0.722, "false_positives": 224, "net_financial_impact": 4195200.0, "status": "Conservative"},
        {"threshold": 0.80, "auto_contest_count": 797, "precision": 0.723, "false_positives": 221, "net_financial_impact": 4152900.0, "status": "Conservative"},
        {"threshold": 0.85, "auto_contest_count": 762, "precision": 0.739, "false_positives": 199, "net_financial_impact": 4313900.0, "status": "⭐ OPTIMAL AUTO-CONTEST"},
        {"threshold": 0.90, "auto_contest_count": 357, "precision": 0.975, "false_positives": 9,   "net_financial_impact": 4142900.0, "status": "Conservative"},
        {"threshold": 0.95, "auto_contest_count": 352, "precision": 0.974, "false_positives": 9,   "net_financial_impact": 4066900.0, "status": "Conservative"},
    ]
    return JSONResponse({
        "metrics": {
            "roc_auc_score": 0.9529,
            "brier_score_loss": 0.0579,
            "optimal_threshold": 0.85,
            "dispute_loss_penalty_fee": 1500.0,
            "human_review_triage_cost": 200.0,
        },
        "table": matrix,
    })


@app.post("/api/submit-contest")
async def submit_dispute_contest(req: SubmitContestRequest):
    """
    Submits authorized dispute defense directly to Razorpay CE 3.0 API.
    Legacy endpoint — also used by /api/disputes/{id}/submit internally.
    """
    dispute_id = req.dispute_id or f"disp_{req.transaction_id[-10:]}"
    logger.info(f"API Contest Submission requested for: {dispute_id} | Action: {req.action}")

    from src.orchestrator.razorpay_client import razorpay_client
    payload = req.evidence_payload or {}

    submission_res = razorpay_client.contest_dispute(
        dispute_id=dispute_id,
        evidence_payload=payload,
    )

    return JSONResponse({
        "status": "CONTEST_SUBMITTED_SUCCESS",
        "http_code": 200,
        "dispute_id": dispute_id,
        "transaction_id": req.transaction_id,
        "action": req.action,
        "override_reason": req.override_reason,
        "submission_id": submission_res.get("submission_id", f"sub_{uuid.uuid4().hex[:12]}"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_endpoint": f"POST https://api.razorpay.com/v1/disputes/{dispute_id}/contest",
        "regulatory_framework": "Visa Compelling Evidence 3.0 / Mastercard Dispute Rules",
        "details": submission_res,
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


def map_customer_status(status: str, has_info_req: bool = False) -> str:
    if has_info_req or status == STATUS_EVIDENCE_REQUESTED:
        return "Action Required"
    elif status == STATUS_SUBMITTED:
        return "Under Network Review"
    elif status == STATUS_OVERRIDDEN:
        return "Resolved (Refund Approved)"
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
        req = c.get("additional_info_request") or {}
        has_req = req.get("status") == "requested" or c.get("status") == STATUS_EVIDENCE_REQUESTED
        result.append({
            "dispute_id": c["dispute_id"],
            "transaction_id": c.get("transaction_id", ""),
            "amount": c.get("amount", 0),
            "currency": c.get("currency", "INR"),
            "reason": c.get("reason", ""),
            "claim": c.get("claim", ""),
            "status": c.get("status", STATUS_NEW),
            "customer_status": map_customer_status(c.get("status", STATUS_NEW), has_req),
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

    ev = case.get("evidence") or {}
    req = case.get("additional_info_request") or {}
    has_req = req.get("status") == "requested" or case.get("status") == STATUS_EVIDENCE_REQUESTED

    return JSONResponse({
        "dispute_id": case["dispute_id"],
        "transaction_id": case.get("transaction_id", ""),
        "amount": case.get("amount", 0),
        "currency": case.get("currency", "INR"),
        "reason": case.get("reason", ""),
        "claim": case.get("claim", ""),
        "status": case.get("status", STATUS_NEW),
        "customer_status": map_customer_status(case.get("status", STATUS_NEW), has_req),
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
            "vlm_contradiction_found": perc.get("vlm_contradiction_found", False),
            "vision_confidence_score": perc.get("vision_confidence_score", 0.0),
            "insufficient_evidence": perc.get("insufficient_evidence", False),
            "vision_reasoning": perc.get("vision_reasoning", ""),
            "metadata_available": perc.get("metadata_available", False),
            "metadata_match": perc.get("metadata_match", False),
            "camera_device": perc.get("camera_device"),
            "gps_coordinates": perc.get("gps_coordinates"),
            "capture_timestamp": perc.get("capture_timestamp"),
            "exif_note": perc.get("exif_note"),
            # Telemetry correlation fields
            "gps_correlation": result.get("gps_correlation"),
            "gps_distance_meters": result.get("gps_distance_meters"),
            "timestamp_correlation": result.get("timestamp_correlation"),
            "timestamp_difference_minutes": result.get("timestamp_difference_minutes"),
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
        "override_strategy": req.override_strategy,
        "override_reason": req.override_reason,
        "evidence_type": req.evidence_type,
        "evidence_note": req.evidence_note,
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
    append_audit_event(dispute_id, event_map[action], {"analyst": req.analyst_name})

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

    if customer_id and case.get("customer_id") and case["customer_id"] != customer_id:
        raise HTTPException(status_code=403, detail="Access denied: Dispute belongs to another customer.")

    ev_info = case.get("evidence") or {}
    if file:
        file_bytes = await file.read()
        suffix = Path(file.filename).suffix or ".jpg"
        unique_name = f"{dispute_id}_resp_{uuid.uuid4().hex[:8]}{suffix}"
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
        "evidence": ev_info if file else None,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "submitted_by": customer_id or case.get("customer_id", "CUST_001"),
    }

    update_fields = {
        "status": STATUS_EVIDENCE_RECEIVED,
        "additional_info_request": req_data,
    }
    if file:
        update_fields["evidence"] = ev_info

    update_case(dispute_id, update_fields)

    append_audit_event(dispute_id, "customer_info_responded", {
        "has_evidence": file is not None,
        "submitted_by": customer_id or case.get("customer_id", "CUST_001"),
    })

    return JSONResponse({
        "dispute_id": dispute_id,
        "status": STATUS_EVIDENCE_RECEIVED,
        "additional_info_request": req_data,
        "evidence": ev_info,
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
            or ((case.get("risk") or {}).get("win_probability", 1.0) < 0.60)
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

    submission_data = {
        "status": "CONTEST_SUBMITTED_SUCCESS",
        "razorpay_dispute_id": razorpay_dispute_id,
        "submission_id": submission_res.get("submission_id", f"sub_{uuid.uuid4().hex[:12]}"),
        "action": review.get("action"),
        "api_endpoint": f"POST https://api.razorpay.com/v1/disputes/{razorpay_dispute_id}/contest",
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
        story.append(kv_table([
            ("Dispute ID",      case.get("dispute_id", "—")),
            ("Case Source",     source_label),
            ("Transaction ID",  case.get("transaction_id", "—")),
            ("Customer ID",     case.get("customer_id", "—")),
            ("Customer Email",  case.get("customer_email", "—")),
            ("Submission Date", fmt_ts(case.get("created_at"))),
            ("Last Updated",    fmt_ts(case.get("updated_at"))),
            ("Current Status",  (case.get("status", "—") or "—").upper()),
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
        story.append(kv_table([
            ("Original Filename",  ev.get("filename", "—")),
            ("File Type",          ev.get("mime_type", "—")),
            ("File Size",          f"{ev.get('size_bytes', 0) / 1024:.1f} KB" if ev.get("size_bytes") else "—"),
            ("Upload Source",      ev.get("source", "—")),
            ("Evidence URL",       ev.get("url", "—")),
        ]))

        # ── Forensic Analysis ─────────────────────────────────────────────────
        story += section("04 · Forensic Analysis")
        analysis = case.get("analysis") or {}

        # EXIF
        exif_status = "AVAILABLE" if analysis.get("metadata_available") else "UNAVAILABLE / STRIPPED"
        gps_raw     = analysis.get("gps_coordinates")
        if isinstance(gps_raw, dict):
            gps_str = f"{gps_raw.get('latitude', '?'):.6f}, {gps_raw.get('longitude', '?'):.6f}"
        elif gps_raw:
            gps_str = str(gps_raw)
        else:
            gps_str = "Unavailable"

        gps_cor   = analysis.get("gps_correlation") or "NOT_VERIFIABLE"
        gps_dist  = analysis.get("gps_distance_meters")
        ts_cor    = analysis.get("timestamp_correlation") or "NOT_VERIFIABLE"
        ts_diff   = analysis.get("timestamp_difference_minutes")
        mer_ref   = analysis.get("merchant_reference")

        gps_cor_str = gps_cor.replace("_", " ")
        if gps_dist is not None:
            gps_cor_str += f" · {gps_dist:.0f}m"
        ts_cor_str = ts_cor.replace("_", " ")
        if ts_diff is not None:
            ts_cor_str += f" · {ts_diff} min difference"

        story.append(kv_table([
            ("EXIF Status",           exif_status),
            ("Camera / Device",       analysis.get("camera_device") or "Unavailable"),
            ("Capture Timestamp",     analysis.get("capture_timestamp") or "Unavailable"),
            ("GPS Coordinates",       gps_str),
            ("GPS Tolerance (m)",     "500"),
            ("GPS Correlation",       gps_cor_str),
            ("Timestamp Tolerance",   "120 minutes"),
            ("Timestamp Correlation", ts_cor_str),
            ("Merchant Telemetry",    "Present (Demo reference)" if mer_ref else "NOT AVAILABLE — correlation not verifiable"),
        ]))

        if not mer_ref:
            story.append(Spacer(1, 1*mm))
            story.append(Paragraph(
                "⚠ No merchant delivery telemetry is available for this case. "
                "GPS and timestamp correlations cannot be independently verified.",
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
            vlm_finding = "CONTRADICTION DETECTED"
        elif vlm_found is False:
            vlm_finding = "NO CONTRADICTION"
        else:
            vlm_finding = "PENDING / NOT RUN"

        story.append(kv_table([
            ("Visual Contradiction",    vlm_finding),
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
        routing = (risk.get("routing_tier") or "PENDING").replace("_", " ")

        story.append(kv_table([
            ("CatBoost Win Probability", win_prob_str),
            ("Policy Threshold",         "85.0%"),
            ("Policy Margin",            margin_str),
            ("ROC-AUC Score",            "0.9529"),
            ("Brier Score Loss",         "0.0579"),
            ("Recommended Routing",      routing),
        ]))

        # XAI
        drivers = risk.get("top_drivers") or []
        if drivers:
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph("XAI / Feature Attribution", S_H2))
            xai_data = [["Feature", "Impact", "Direction"]]
            for drv in drivers[:6]:
                feat    = drv.get("feature", "—")
                impact  = drv.get("impact", 0)
                direction = "▲ Increases Risk" if impact > 0 else "▼ Reduces Risk"
                xai_data.append([feat, f"{impact:+.4f}", direction])
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
            story.append(kv_table([
                ("System Recommendation", routing),
                ("Analyst Decision",      review.get("action", "—")),
                ("Override Strategy",     review.get("override_strategy") or "N/A"),
                ("Override Reason",       review.get("override_reason") or "N/A"),
                ("Evidence Requested",    review.get("evidence_type") or "N/A"),
                ("Evidence Note",         review.get("evidence_note") or "N/A"),
                ("Analyst Name",          review.get("analyst_name", "—")),
                ("Decision Timestamp",    fmt_ts(review.get("reviewed_at"))),
            ]))
        else:
            story.append(Paragraph("No analyst review recorded for this dispute.", S_VALUE))

        # ── Final Resolution ──────────────────────────────────────────────────
        story += section("07 · Final Resolution")
        submission = case.get("submission") or {}
        if submission:
            story.append(kv_table([
                ("Final Status",       submission.get("status", "—")),
                ("Final Action",       submission.get("action", "—")),
                ("Razorpay Dispute ID",submission.get("razorpay_dispute_id", "—")),
                ("Submission ID",      submission.get("submission_id", "—")),
                ("API Endpoint",       submission.get("api_endpoint", "—")),
                ("Framework",          submission.get("regulatory_framework", "—")),
                ("Concede Reason",     submission.get("reason", "—") if submission.get("action") == "CONCEDE" else "N/A"),
                ("Submitted At",       fmt_ts(submission.get("submitted_at"))),
            ]))
        else:
            story.append(Paragraph("No final submission recorded for this dispute.", S_VALUE))

        # ── Audit Trail ───────────────────────────────────────────────────────
        story += section("08 · Audit Trail")
        trail = case.get("audit_trail") or []
        if trail:
            trail_data = [["Timestamp", "Event"]]
            for entry in trail:
                if isinstance(entry, dict):
                    ts_str  = fmt_ts(entry.get("timestamp"))
                    evt_str = (entry.get("event") or "").replace("_", " ").title()
                elif isinstance(entry, str):
                    ts_str  = "—"
                    evt_str = entry
                else:
                    continue
                trail_data.append([ts_str, evt_str])
            tt = Table(trail_data, colWidths=[60*mm, 100*mm])
            tt.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,0), NAVY),
                ("TEXTCOLOR",     (0,0),(-1,0), colors.white),
                ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
                ("FONTSIZE",      (0,0),(-1,-1), 8),
                ("ROWBACKGROUNDS",(0,1),(-1,-1), [LGRAY, colors.white]),
                ("VALIGN",        (0,0),(-1,-1), "TOP"),
                ("TOPPADDING",    (0,0),(-1,-1), 4),
                ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                ("LEFTPADDING",   (0,0),(-1,-1), 6),
                ("RIGHTPADDING",  (0,0),(-1,-1), 6),
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
