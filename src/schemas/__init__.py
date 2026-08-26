from pydantic import BaseModel, Field
from typing import List, Optional

class VisionAssessment(BaseModel):
    """
    Schema for VLM contradiction reasoning.
    """
    contradiction_found: bool = Field(
        description="True if the visual evidence clearly contradicts the user's text claim."
    )
    vision_confidence_score: float = Field(
        description="Confidence score of the assessment between 0.00 and 1.00."
    )
    insufficient_evidence: bool = Field(
        description="True ONLY if the image is too blurry, dark, or cropped to make a definitive judgment."
    )
    rationale: str = Field(
        description="Internal reasoning for the decision. Maximum 2 sentences. This will be sent to the dashboard for SHAP auditability."
    )

class RazorpayEvidencePayload(BaseModel):
    """
    Maps directly to Razorpay's CE 3.0 / dispute contest API specifications.
    """
    shipping_proof: List[str] = Field(
        default_factory=list,
        description="Array of document IDs or metadata strings proving delivery/location (e.g. GPS metadata logs)."
    )
    billing_proof: List[str] = Field(
        default_factory=list,
        description="Array of document IDs proving billing or order confirmation."
    )
    customer_communication: List[str] = Field(
        default_factory=list,
        description="Array of document IDs or text logs containing chat transcripts and VLM rationales."
    )
    explanation: Optional[str] = Field(
        default="",
        description="Summary explanation for the dispute contestation submission."
    )

# Re-export data models for project-wide convenience
from .data_models import PerceptionResult, AgentState, VLMAnalysis, SHAPDriver