from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class VLMAnalysis(BaseModel):
    """Schema for VLM multimodal contradiction reasoning."""
    contradiction_found: bool = Field(
        description="True if the visual evidence contradicts the customer's claim"
    )
    vision_confidence_score: float = Field(
        description="Confidence score between 0.00 and 1.00"
    )
    insufficient_evidence: bool = Field(
        description="True if image is blurry, ambiguous, or irrelevant"
    )
    rationale: str = Field(
        description="Forensic reasoning explaining the visual findings"
    )


class PerceptionResult(BaseModel):
    """The combined output of both EXIF forensics and VLM visual analysis."""
    vlm_contradiction_found: bool
    vision_confidence_score: float = 0.0
    insufficient_evidence: bool = False
    metadata_match: bool
    metadata_available: bool = False
    camera_device: Optional[str] = None
    gps_coordinates: Optional[str] = None
    capture_timestamp: Optional[str] = None
    exif_note: Optional[str] = None
    vision_reasoning: str


class SHAPDriver(BaseModel):
    """Explains a single feature's contribution to the win probability."""
    feature: str
    impact: float
    
    



class AgentState(BaseModel):
    """The complete state object passed between LangGraph nodes."""
    # Transaction & Customer Inputs
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
    gps_correlation: Optional[str] = None
    gps_distance_meters: Optional[float] = None
    gps_match_tolerance_meters: int = 500
    timestamp_correlation: Optional[str] = None
    timestamp_difference_minutes: Optional[int] = None
    timestamp_tolerance_minutes: int = 120
    audit_trail: List[str] = Field(default_factory=list)