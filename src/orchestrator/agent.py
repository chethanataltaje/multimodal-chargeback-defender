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
        gps_coordinates=exif_data.get("gps_coordinates"),
        capture_timestamp=exif_data.get("capture_timestamp"),
        vision_reasoning=vlm_data.get("rationale", "")
    )
    
    log_entry = (
        f"Perception complete: Contradiction={perception_result.vlm_contradiction_found}, "
        f"Confidence={perception_result.vision_confidence_score:.2f}, "
        f"EXIF Match={perception_result.metadata_match}"
    )
    
    return {
        "perception_result": perception_result,
        "audit_trail": state.audit_trail + [log_entry]
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
