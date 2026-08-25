from pydantic import BaseModel
from typing import Optional

class VLMAnalysis(BaseModel):
    """Schema forcing Gemini 3.1 Pro to output strict JSON."""
    contradiction_found: bool
    vision_confidence_score: float
    reasoning: str

class PerceptionResult(BaseModel):
    """The combined output of both the EXIF extractor and the VLM."""
    vlm_contradiction_found: bool
    metadata_match: bool
    vision_reasoning: str

class AgentState(BaseModel):
    """The global state object passed between LangGraph nodes."""
    # Input Features
    transaction_id: str
    claim_text: str
    image_path: str
    reason_code: str
    merchant_category: str
    
    # Numerical / Risk Features
    user_account_age_days: int
    transaction_amount: float
    prior_chargeback_count: int
    
    # State updated dynamically during the workflow
    perception_result: Optional[PerceptionResult] = None
    win_probability: Optional[float] = None
    final_action: Optional[str] = None