from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class VLMAnalysis(BaseModel):
    """Schema for VLM multimodal contradiction reasoning."""
    physical_damage_visible: bool = Field(
        default=False,
        description="Whether physical damage or defects are visible"
    )
    claim_supported: bool = Field(
        default=False,
        description="Whether the photographic evidence corroborates the customer claim"
    )
    contradiction_found: bool = Field(
        default=False,
        description="True if the visual evidence contradicts the customer's claim"
    )
    vision_confidence_score: float = Field(
        default=0.8,
        description="Confidence score between 0.00 and 1.00"
    )
    insufficient_evidence: bool = Field(
        default=False,
        description="True if image is blurry, ambiguous, or irrelevant"
    )
    rationale: str = Field(
        default="",
        description="Forensic reasoning explaining the visual findings"
    )


class PerceptionResult(BaseModel):
    """The combined output of both EXIF forensics and VLM visual analysis."""
    analysis_status: str = "ANALYZED"  # "ANALYZED" or "ANALYSIS_FAILED"
    vlm_available: bool = True
    vlm_contradiction_found: bool = False
    claim_supported: bool = False
    physical_damage_visible: bool = False
    vision_confidence_score: Optional[float] = None
    insufficient_evidence: bool = False
    metadata_match: bool = False
    metadata_available: bool = False
    gps_available: bool = False
    timestamp_available: bool = False
    camera_device: Optional[str] = None
    gps_coordinates: Optional[Any] = None
    capture_timestamp: Optional[str] = None
    exif_note: Optional[str] = None
    vision_reasoning: str = ""
    operational_error: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    fallback_used: bool = False


class SHAPDriver(BaseModel):
    """Explains a single feature's contribution to the win probability."""
    feature: str
    impact: float



class AgentState(BaseModel):
    """The complete state object passed between LangGraph nodes."""
    # Transaction & Customer Inputs
    dispute_id: Optional[str] = None
    transaction_id: str
    claim_text: str
    image_path: str
    reason_code: str
    merchant_category: str
    
    # Numerical / Behavioral Risk Features
    user_account_age_days: int
    transaction_amount: float
    prior_chargeback_count: int
    
    # Optional metadata
    order_id: Optional[str] = "order_default"
    customer_email: Optional[str] = "dispute_user@example.com"
    
    # Dynamically updated state fields
    perception_result: Optional[PerceptionResult] = None
    win_probability: Optional[float] = None
    top_drivers: Optional[List[Dict[str, Any]]] = None
    routing_tier: Optional[str] = None  # 'AUTO_CONTEST', 'PRIORITY_REVIEW', 'STANDARD_REVIEW'
    final_action: Optional[str] = None
    action_details: Optional[Dict[str, Any]] = None
    # Telemetry fields
    exif: Optional[Dict[str, Any]] = None
    merchant_reference: Optional[Dict[str, Any]] = None
    metadata_available: bool = False
    gps_available: bool = False
    merchant_gps_available: bool = False
    gps_correlation: Optional[str] = "NOT_VERIFIABLE"
    gps_distance_meters: Optional[float] = None
    gps_match_tolerance_meters: int = 500
    timestamp_available: bool = False
    merchant_timestamp_available: bool = False
    timestamp_correlation: Optional[str] = "NOT_VERIFIABLE"
    timestamp_difference_minutes: Optional[int] = None
    timestamp_tolerance_minutes: int = 120
    audit_trail: List[str] = Field(default_factory=list)