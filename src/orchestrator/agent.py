import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END

from src.schemas.data_models import AgentState, PerceptionResult
from src.perception.vlm_analyzer import vlm_analyzer
from src.perception.metadata_extractor import forensics
from src.gatekeeper.predictor import gatekeeper
from src.orchestrator.razorpay_client import razorpay_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OrchestratorAgent")
import json
from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, atan2
import os

# Load merchant reference data (demo)
MERCHANT_REFS = {}
_refs_path = os.path.join(os.path.dirname(__file__), "..", "..", "merchant_refs.json")
if os.path.exists(_refs_path):
    try:
        MERCHANT_REFS = json.load(open(_refs_path, "r", encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to load merchant_refs.json: {e}")

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate Haversine distance in meters between two lat/lon points."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def compare_gps(state: AgentState) -> dict:
    exif = state.perception_result
    gps = exif.gps_coordinates if exif else None
    ref_key = None
    for k in MERCHANT_REFS.keys():
        if state.transaction_id in k or k in state.transaction_id:
            ref_key = k
            break
    if not ref_key:
        ref_key = next(iter(MERCHANT_REFS), None)
    merchant = MERCHANT_REFS.get(ref_key, {})
    result = {"merchant_reference": merchant, "gps_correlation": "NOT_VERIFIABLE", "gps_distance_meters": None}
    if gps and gps.get("latitude") is not None and gps.get("longitude") is not None:
        lat2 = merchant.get("delivery_latitude")
        lon2 = merchant.get("delivery_longitude")
        if lat2 is not None and lon2 is not None:
            dist = haversine_distance(gps["latitude"], gps["longitude"], lat2, lon2)
            result["gps_distance_meters"] = round(dist, 2)
            if dist <= state.gps_match_tolerance_meters:
                result["gps_correlation"] = "MATCH"
            else:
                result["gps_correlation"] = "MISMATCH"
        else:
            result["gps_correlation"] = "NOT_VERIFIABLE"
    else:
        result["gps_correlation"] = "NOT_VERIFIABLE"
    return result

def compare_timestamp(state: AgentState) -> dict:
    exif = state.perception_result
    ts = exif.capture_timestamp if exif else None
    ref_key = None
    for k in MERCHANT_REFS.keys():
        if state.transaction_id in k or k in state.transaction_id:
            ref_key = k
            break
    if not ref_key:
        ref_key = next(iter(MERCHANT_REFS), None)
    merchant = MERCHANT_REFS.get(ref_key, {})
    result = {"timestamp_correlation": "NOT_VERIFIABLE", "timestamp_difference_minutes": None}
    if ts:
        try:
            ts_clean = ts.replace(" ", "T").replace("_", "-")
            exif_dt = datetime.fromisoformat(ts_clean)
        except Exception:
            try:
                exif_dt = datetime.strptime(ts, "%Y:%m:%d %H:%M:%S")
            except Exception:
                exif_dt = None
        delivery_ts = merchant.get("delivery_timestamp")
        if exif_dt and delivery_ts:
            try:
                delivery_dt = datetime.fromisoformat(delivery_ts)
            except Exception:
                delivery_dt = None
            if delivery_dt:
                diff = abs((exif_dt - delivery_dt).total_seconds() / 60)
                result["timestamp_difference_minutes"] = int(diff)
                if diff <= state.timestamp_tolerance_minutes:
                    result["timestamp_correlation"] = "MATCH"
                else:
                    result["timestamp_correlation"] = "MISMATCH"
            else:
                result["timestamp_correlation"] = "NOT_VERIFIABLE"
        else:
            result["timestamp_correlation"] = "NOT_VERIFIABLE"
    else:
        result["timestamp_correlation"] = "NOT_VERIFIABLE"
    return result

def perception_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 1: Layer 1 Perception Council.
    Extracts EXIF metadata forensics and runs VLM multi-tier contradiction analysis.
    """
    logger.info(f"[{state.transaction_id}] Running Layer 1 Perception Council...")
    
    # 1. EXIF Metadata Extraction
    exif_data = forensics.extract_metadata(state.image_path)
    
    # 2. Multimodal VLM Analysis (Gemini + Groq Failover)
    vlm_data = vlm_analyzer.analyze_claim(
        image_path=state.image_path,
        claim_text=state.claim_text
    )
    
    perception_result = PerceptionResult(
        vlm_contradiction_found=vlm_data.get("vlm_contradiction_found", False),
        vision_confidence_score=vlm_data.get("vision_confidence_score", 0.0),
        insufficient_evidence=vlm_data.get("insufficient_evidence", False),
        metadata_match=exif_data.get("metadata_match", False),
        metadata_available=exif_data.get("metadata_available", False),
        camera_device=exif_data.get("camera_device"),
        gps_coordinates=exif_data.get("gps_coordinates"),
        capture_timestamp=exif_data.get("capture_timestamp"),
        exif_note=exif_data.get("exif_note"),
        vision_reasoning=vlm_data.get("rationale", "")
    )
    
    log_entry = (
        f"Perception complete: Contradiction={perception_result.vlm_contradiction_found}, "
        f"Confidence={perception_result.vision_confidence_score:.2f}, "
        f"EXIF Match={perception_result.metadata_match}"
    )
    # Compute telemetry comparisons
    gps_info = compare_gps(state)
    ts_info = compare_timestamp(state)
    
    return {
        "perception_result": perception_result,
        "audit_trail": state.audit_trail + [log_entry],
        # Telemetry fields
        "merchant_reference": gps_info.get("merchant_reference"),
        "gps_correlation": gps_info.get("gps_correlation"),
        "gps_distance_meters": gps_info.get("gps_distance_meters"),
        "timestamp_correlation": ts_info.get("timestamp_correlation"),
        "timestamp_difference_minutes": ts_info.get("timestamp_difference_minutes")
    }


def gatekeeper_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 2: Layer 2 Statistical Gatekeeper.
    Passes perception signals and transaction metadata to CatBoost for calibrated win probability and SHAP.
    """
    logger.info(f"[{state.transaction_id}] Running Layer 2 CatBoost Statistical Gatekeeper...")
    
    perc = state.perception_result
    vlm_flag = perc.vlm_contradiction_found if perc else False
    meta_flag = perc.metadata_match if perc else False
    
    feature_dict = {
        "user_account_age_days": state.user_account_age_days,
        "transaction_amount": state.transaction_amount,
        "prior_chargeback_count": state.prior_chargeback_count,
        "reason_code": state.reason_code,
        "merchant_category": state.merchant_category,
        "vlm_contradiction_found": vlm_flag,
        "metadata_match": meta_flag
    }
    
    prediction = gatekeeper.predict_with_explanation(feature_dict)
    win_prob = prediction["win_probability"]
    drivers = prediction["top_drivers"]
    
    log_entry = (
        f"Gatekeeper scored Win Probability: {win_prob:.1%} | "
        f"Top Driver: {drivers[0]['feature']} ({drivers[0]['impact']:+.3f})"
    )
    
    return {
        "win_probability": win_prob,
        "top_drivers": drivers,
        "audit_trail": state.audit_trail + [log_entry]
    }


def route_decision(state: AgentState) -> Literal["auto_contest_node", "priority_review_node", "standard_review_node"]:
    """
    Conditional Routing Function:
    - Probability >= 0.85: Auto-Contest (High confidence, profit-maximizing zone)
    - 0.60 <= Probability < 0.85: Priority Review (Borderline / High-ROI human triage)
    - Probability < 0.60: Standard Review / Concede (Low likelihood of recovery)
    """
    prob = state.win_probability or 0.0
    if prob >= 0.85:
        return "auto_contest_node"
    elif prob >= 0.60:
        return "priority_review_node"
    else:
        return "standard_review_node"


def auto_contest_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 3A: Auto-Contest Submission.
    Constructs Visa CE 3.0 / Razorpay payload and executes API contestation.
    """
    logger.info(f"[{state.transaction_id}] Routing: AUTO-CONTEST (Score: {state.win_probability:.1%})")
    
    perception_dict = state.perception_result.model_dump() if state.perception_result else {}
    evidence_payload = razorpay_client.build_ce3_evidence_payload(
        transaction_id=state.transaction_id,
        claim_text=state.claim_text,
        reason_code=state.reason_code,
        perception_data=perception_dict,
        order_id=state.order_id
    )
    
    api_response = razorpay_client.contest_dispute(
        dispute_id=f"disp_{state.transaction_id[-10:]}",
        evidence_payload=evidence_payload
    )
    
    log_entry = f"Auto-contested successfully via Razorpay API (Submission ID: {api_response.get('submission_id')})"
    
    return {
        "routing_tier": "AUTO_CONTEST",
        "final_action": "SUBMITTED_TO_RAZORPAY_API",
        "action_details": {
            "evidence_payload": evidence_payload,
            "api_response": api_response
        },
        "audit_trail": state.audit_trail + [log_entry]
    }


def priority_review_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 3B: Priority Human Review Queue.
    Disputes in the 0.60 - 0.85 confidence band requiring fast analyst verification.
    """
    logger.info(f"[{state.transaction_id}] Routing: PRIORITY HUMAN REVIEW (Score: {state.win_probability:.1%})")
    
    log_entry = "Routed to Priority Human Review Queue (Borderline confidence / high ROI opportunity)."
    return {
        "routing_tier": "PRIORITY_REVIEW",
        "final_action": "QUEUED_FOR_PRIORITY_ANALYST_TRIAGE",
        "action_details": {
            "recommendation": "Manual Analyst Review Recommended",
            "reason": "Win probability is in the borderline zone (60%-85%). Review VLM rationale before submitting.",
            "top_drivers": state.top_drivers
        },
        "audit_trail": state.audit_trail + [log_entry]
    }


def standard_review_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 3C: Standard Queue / Concede.
    Low-probability disputes (<0.60) where contesting risks the ₹1,500 non-refundable penalty fee.
    """
    logger.info(f"[{state.transaction_id}] Routing: STANDARD REVIEW / CONCEDE (Score: {state.win_probability:.1%})")
    
    log_entry = "Routed to Standard Review (Low win probability; recommending liability acceptance to avoid penalty)."
    return {
        "routing_tier": "STANDARD_REVIEW",
        "final_action": "RECOMMEND_LIABILITY_ACCEPTANCE",
        "action_details": {
            "recommendation": "Accept Dispute Liability",
            "reason": "Win probability < 60%. Contesting carries high risk of non-refundable ₹1,500 dispute penalty fee.",
            "top_drivers": state.top_drivers
        },
        "audit_trail": state.audit_trail + [log_entry]
    }


# Build LangGraph State Machine
builder = StateGraph(AgentState)

builder.add_node("perception", perception_node)
builder.add_node("gatekeeper", gatekeeper_node)
builder.add_node("auto_contest_node", auto_contest_node)
builder.add_node("priority_review_node", priority_review_node)
builder.add_node("standard_review_node", standard_review_node)

builder.set_entry_point("perception")
builder.add_edge("perception", "gatekeeper")

builder.add_conditional_edges(
    "gatekeeper",
    route_decision,
    {
        "auto_contest_node": "auto_contest_node",
        "priority_review_node": "priority_review_node",
        "standard_review_node": "standard_review_node"
    }
)

builder.add_edge("auto_contest_node", END)
builder.add_edge("priority_review_node", END)
builder.add_edge("standard_review_node", END)

dispute_agent = builder.compile()


def run_defense_agent(dispute_data: dict) -> AgentState:
    """
    Main invocation entrypoint for the end-to-end defense pipeline.
    """
    initial_state = AgentState(**dispute_data)
    final_state_dict = dispute_agent.invoke(initial_state)
    return AgentState(**final_state_dict)
