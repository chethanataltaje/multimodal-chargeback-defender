from pydantic import BaseModel, Field

class VisionAssessment(BaseModel):
    """

    Forces the model to quantify its confidence and allows a fallback 
    if the image is too poor to evaluate (preventing false positives).
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
    Maps directly to Razorpay's CE 3.0 API specifications for dispute contestation.
    """
    shipping_proof: list[str] = Field(
        description="Array of document IDs proving shipping/location (e.g., GPS metadata logs)."
    )
    billing_proof: list[str] = Field(
        description="Array of document IDs proving billing or order confirmation."
    )
    customer_communication: list[str] = Field(
        description="Array of document IDs containing chat transcripts and VLM rationales."
    )

# Re-export data models for project-wide convenience
from .data_models import PerceptionResult, AgentState, VLMAnalysis