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
_refs_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "merchant_refs.json")
if os.path.exists(_refs_path):
    try:
        with open(_refs_path, "r", encoding="utf-8") as f:
            MERCHANT_REFS = json.load(f)
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

def _resolve_merchant_reference(state: AgentState) -> Optional[dict]:
    """
    Resolve merchant reference telemetry for this dispute.
    Returns None if no merchant telemetry exists (normal customer cases).
    Never fall back to an arbitrary demo record.
    """
    if state.merchant_reference:
        return state.merchant_reference

    # Check state dispute_id or transaction_id against known records
    keys_to_try = []
    if state.dispute_id:
        keys_to_try.append(state.dispute_id)
        keys_to_try.append(state.dispute_id.replace("-", "_"))
        keys_to_try.append(state.dispute_id.replace("_", "-"))
    if state.transaction_id:
        keys_to_try.append(state.transaction_id)
    if state.order_id:
        keys_to_try.append(state.order_id)

    for k in keys_to_try:
        if k in MERCHANT_REFS:
            return MERCHANT_REFS[k]
        # Partial match
        for m_key, m_val in MERCHANT_REFS.items():
            if k and (k in m_key or m_key in k):
                return m_val

    return None

def compare_gps(state: AgentState, perc: Optional[PerceptionResult] = None) -> dict:
    exif = perc or state.perception_result
    gps = exif.gps_coordinates if exif else None
    merchant = _resolve_merchant_reference(state)

    # Check if EXIF GPS coordinates exist (dict with latitude/longitude)
    exif_lat = None
    exif_lon = None
    if isinstance(gps, dict):
        exif_lat = gps.get("latitude")
        exif_lon = gps.get("longitude")

    mer_lat = merchant.get("delivery_latitude") if merchant else None
    mer_lon = merchant.get("delivery_longitude") if merchant else None

    gps_available = bool(exif_lat is not None and exif_lon is not None)
    merchant_gps_available = bool(mer_lat is not None and mer_lon is not None)

    result = {
        "merchant_reference": merchant,
        "gps_available": gps_available,
        "merchant_gps_available": merchant_gps_available,
        "gps_correlation": "NOT_VERIFIABLE",
        "gps_distance_meters": None,
        "gps_match_tolerance_meters": state.gps_match_tolerance_meters
    }

    if not merchant or not merchant_gps_available:
        # No merchant telemetry available for this case -> correlation not verifiable
        result["gps_correlation"] = "NOT_VERIFIABLE"
        return result

    if gps_available and merchant_gps_available:
        dist = haversine_distance(float(exif_lat), float(exif_lon), float(mer_lat), float(mer_lon))
        result["gps_distance_meters"] = round(dist, 1)
        if dist <= state.gps_match_tolerance_meters:
            result["gps_correlation"] = "MATCH"
        else:
            result["gps_correlation"] = "MISMATCH"
    else:
        result["gps_correlation"] = "NOT_VERIFIABLE"

    return result

def compare_timestamp(state: AgentState, perc: Optional[PerceptionResult] = None) -> dict:
    exif = perc or state.perception_result
    ts = exif.capture_timestamp if exif else None
    merchant = _resolve_merchant_reference(state)

    delivery_ts = merchant.get("delivery_timestamp") if merchant else None
    ts_available = bool(ts and str(ts).strip())
    merchant_ts_available = bool(delivery_ts and str(delivery_ts).strip())

    result = {
        "timestamp_available": ts_available,
        "merchant_timestamp_available": merchant_ts_available,
        "timestamp_correlation": "NOT_VERIFIABLE",
        "timestamp_difference_minutes": None,
        "timestamp_tolerance_minutes": state.timestamp_tolerance_minutes
    }

    if not merchant or not merchant_ts_available or not ts_available:
        result["timestamp_correlation"] = "NOT_VERIFIABLE"
        return result

    exif_dt = None
    try:
        ts_clean = str(ts).replace(" ", "T").replace("_", "-")
        exif_dt = datetime.fromisoformat(ts_clean)
    except Exception:
        try:
            exif_dt = datetime.strptime(str(ts), "%Y:%m:%d %H:%M:%S")
        except Exception:
            exif_dt = None

    delivery_dt = None
    try:
        delivery_dt = datetime.fromisoformat(str(delivery_ts))
    except Exception:
        try:
            delivery_dt = datetime.strptime(str(delivery_ts), "%Y:%m:%d %H:%M:%S")
        except Exception:
            delivery_dt = None

    if exif_dt and delivery_dt:
        # Ensure timezone-naive comparison for local timestamps
        if exif_dt.tzinfo is not None:
            exif_dt = exif_dt.replace(tzinfo=None)
        if delivery_dt.tzinfo is not None:
            delivery_dt = delivery_dt.replace(tzinfo=None)

        diff_minutes = abs((exif_dt - delivery_dt).total_seconds() / 60.0)
        result["timestamp_difference_minutes"] = int(round(diff_minutes))
        if diff_minutes <= state.timestamp_tolerance_minutes:
            result["timestamp_correlation"] = "MATCH"
        else:
            result["timestamp_correlation"] = "MISMATCH"
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
        analysis_status=vlm_data.get("analysis_status", "ANALYZED"),
        vlm_available=vlm_data.get("vlm_available", True),
        vlm_contradiction_found=vlm_data.get("vlm_contradiction_found", False),
        claim_supported=vlm_data.get("claim_supported", False),
        physical_damage_visible=vlm_data.get("physical_damage_visible", False),
        vision_confidence_score=vlm_data.get("vision_confidence_score"),
        insufficient_evidence=vlm_data.get("insufficient_evidence", False),
        metadata_match=exif_data.get("metadata_available", False),
        metadata_available=exif_data.get("metadata_available", False),
        gps_available=exif_data.get("gps_available", False),
        timestamp_available=exif_data.get("timestamp_available", False),
        camera_device=exif_data.get("camera_device"),
        gps_coordinates=exif_data.get("gps_coordinates"),
        capture_timestamp=exif_data.get("capture_timestamp"),
        vision_reasoning=vlm_data.get("rationale", ""),
        operational_error=vlm_data.get("operational_error"),
        provider=vlm_data.get("provider"),
        model=vlm_data.get("model"),
        fallback_used=vlm_data.get("fallback_used", False)
    )
    
    # Compute telemetry comparisons with actual perception_result
    gps_info = compare_gps(state, perception_result)
    ts_info = compare_timestamp(state, perception_result)

    conf_display = f"{perception_result.vision_confidence_score:.2f}" if perception_result.vision_confidence_score is not None else "UNAVAILABLE"
    log_entry = (
        f"Perception complete: Status={perception_result.analysis_status}, "
        f"Contradiction={perception_result.vlm_contradiction_found}, "
        f"Confidence={conf_display}, "
        f"EXIF Available={perception_result.metadata_available}, "
        f"GPS Correl={gps_info.get('gps_correlation')}, "
        f"TS Correl={ts_info.get('timestamp_correlation')}"
    )
    
    return {
        "perception_result": perception_result,
        "audit_trail": state.audit_trail + [log_entry],
        # Telemetry fields
        "merchant_reference": gps_info.get("merchant_reference"),
        "metadata_available": perception_result.metadata_available,
        "gps_available": gps_info.get("gps_available", False),
        "merchant_gps_available": gps_info.get("merchant_gps_available", False),
        "gps_correlation": gps_info.get("gps_correlation", "NOT_VERIFIABLE"),
        "gps_distance_meters": gps_info.get("gps_distance_meters"),
        "timestamp_available": ts_info.get("timestamp_available", False),
        "merchant_timestamp_available": ts_info.get("merchant_timestamp_available", False),
        "timestamp_correlation": ts_info.get("timestamp_correlation", "NOT_VERIFIABLE"),
        "timestamp_difference_minutes": ts_info.get("timestamp_difference_minutes")
    }


def gatekeeper_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 2: Layer 2 Statistical Gatekeeper.
    Passes perception signals and transaction metadata to CatBoost for calibrated win probability and SHAP.
    """
    logger.info(f"[{state.transaction_id}] Running Layer 2 CatBoost Statistical Gatekeeper...")
    
    perc = state.perception_result
    # If visual analysis failed, do not pretend VLM contradiction was found
    vlm_flag = perc.vlm_contradiction_found if (perc and perc.vlm_available) else False
    meta_flag = perc.metadata_available if perc else False
    
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
    - Probability < 0.85: Concede Liability (Score below threshold; avoid ₹1,500 penalty fee)
    """
    prob = state.win_probability or 0.0
    if prob >= 0.85:
        return "auto_contest_node"
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
    
    is_sim = api_response.get("is_simulated", True)
    mode_badge = api_response.get("mode_badge", "DEMO SIMULATION — NOT SENT TO RAZORPAY")
    final_action = f"SUBMITTED_TO_{api_response.get('mode', 'DEMO_SIMULATION')}" if not is_sim else "DEMO_SIMULATION_COMPLETED"
    log_entry = f"Contestation processed in [{mode_badge}] mode (Submission ID: {api_response.get('submission_id')})"
    
    return {
        "routing_tier": "AUTO_CONTEST",
        "final_action": final_action,
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
    Node 3C: Standard Queue / Concede Liability.
    Disputes below 85% policy threshold (<0.85) where contesting risks the ₹1,500 non-refundable penalty fee.
    """
    logger.info(f"[{state.transaction_id}] Routing: CONCEDE LIABILITY (Score: {state.win_probability:.1%})")
    
    log_entry = "Routed to Concede Liability (Score below 85% policy threshold; recommending liability acceptance to avoid ₹1,500 penalty)."
    return {
        "routing_tier": "STANDARD_REVIEW",
        "final_action": "RECOMMEND_LIABILITY_ACCEPTANCE",
        "action_details": {
            "recommendation": "Accept Dispute Liability",
            "reason": "Win probability < 85%. Contesting carries high risk of non-refundable ₹1,500 dispute penalty fee.",
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
