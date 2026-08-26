import base64
import json
import logging
import mimetypes
import os
import re
import httpx
from google import genai
from google.genai import types
from PIL import Image

try:
    from src.schemas import VisionAssessment
except ImportError:
    from pydantic import BaseModel, Field

    class VisionAssessment(BaseModel):
        contradiction_found: bool = Field(
            description="Whether the image contradicts the customer's text claim"
        )
        vision_confidence_score: float = Field(
            description="Confidence score between 0.0 and 1.0"
        )
        insufficient_evidence: bool = Field(
            description="True if image is blurry, ambiguous, or irrelevant"
        )
        rationale: str = Field(
            description="Concise 1-2 sentence forensic reasoning"
        )


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VLM_Analyzer")


class VisionSpecialist:
    def __init__(self):
        """
        Multimodal Perception Specialist (Cloud Dual-Tier):
        - Tier 1: Google Gemini 2.5 Flash (Primary VLM)
        - Tier 2: Groq Llama 3.2 Vision (Fast Cloud Fallback)
        - Tier 3: Safe Inconclusive Default
        """
        # Tier 1: Gemini
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        # Tier 2: Groq Vision
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_vision_model = os.getenv(
            "GROQ_VISION_MODEL", "llama-3.2-11b-vision-preview"
        )

        self._gemini_client = None

    @property
    def gemini_client(self) -> genai.Client:
        if self._gemini_client is None:
            if not self.gemini_api_key:
                self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is not set.")
            self._gemini_client = genai.Client(api_key=self.gemini_api_key)
        return self._gemini_client

    def _extract_json(self, raw_str: str) -> dict:
        cleaned = raw_str.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        return json.loads(cleaned)

    def analyze_claim(self, image_path: str, claim_text: str) -> dict:
        logger.info(f"Analyzing visual evidence: {image_path} against claim: '{claim_text}'")

        # Tier 1: Google Gemini 2.5 Flash
        if self.gemini_api_key:
            try:
                res = self._analyze_with_gemini(image_path, claim_text)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Tier 1 (Gemini) failed: {e}. Falling over to Tier 2 (Groq)...")

        # Tier 2: Groq Cloud Vision
        if self.groq_api_key:
            try:
                res = self._analyze_with_groq(image_path, claim_text)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Tier 2 (Groq Vision) failed: {e}. Returning safe default...")

        # Tier 3: Safe Fallback
        logger.error("All cloud VLM endpoints failed. Returning safe default.")
        return {
            "vlm_contradiction_found": False,
            "vision_confidence_score": 0.0,
            "insufficient_evidence": True,
            "rationale": "Visual evidence inconclusive: Cloud VLM endpoints unreachable.",
        }

    def _analyze_with_gemini(self, image_path: str, claim_text: str) -> dict:
        img = Image.open(image_path)
        prompt = f"""
        You are an expert defense-only risk analyst evaluating a chargeback dispute.
        Customer Claim: '{claim_text}'

        Examine the provided image evidence:
        1. Does the physical image contradict the claim (e.g., claimed damaged but intact, box empty vs full)?
        2. If the image is blurry, dark, ambiguous, or cropped such that no judgment can be made, flag 'insufficient_evidence' as true.
        3. Quantify confidence (0.0 to 1.0) and give a 1-2 sentence rationale.
        """

        response = self.gemini_client.models.generate_content(
            model=self.gemini_model,
            contents=[img, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VisionAssessment,
                temperature=0.1,
            ),
        )

        vlm_result: VisionAssessment = response.parsed
        logger.info(f"Gemini VLM Rationale: {vlm_result.rationale}")

        return {
            "vlm_contradiction_found": vlm_result.contradiction_found,
            "vision_confidence_score": vlm_result.vision_confidence_score,
            "insufficient_evidence": vlm_result.insufficient_evidence,
            "rationale": vlm_result.rationale,
        }

    def _analyze_with_groq(self, image_path: str, claim_text: str) -> dict:
        mime_type, _ = mimetypes.guess_type(image_path)
        mime_type = mime_type or "image/jpeg"

        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        prompt = f"""
        You are an expert dispute risk analyst.
        Customer Claim: '{claim_text}'

        Evaluate the image evidence against the claim.
        Respond ONLY with a JSON object matching this schema:
        {{
            "vlm_contradiction_found": bool,
            "vision_confidence_score": float,
            "insufficient_evidence": bool,
            "rationale": string
        }}
        """

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.groq_vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{img_b64}"},
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers, json=body)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                parsed = self._extract_json(content)
                logger.info(f"Groq Vision ({self.groq_vision_model}) succeeded.")
                return {
                    "vlm_contradiction_found": bool(parsed.get("vlm_contradiction_found", False)),
                    "vision_confidence_score": float(parsed.get("vision_confidence_score", 0.80)),
                    "insufficient_evidence": bool(parsed.get("insufficient_evidence", False)),
                    "rationale": str(parsed.get("rationale", "Evaluated via Groq Vision.")),
                }
            else:
                logger.warning(f"Groq Vision returned {resp.status_code}: {resp.text}")
        return None


vlm_analyzer = VisionSpecialist()