import os
import json
import logging
from dotenv import load_dotenv

# 1. Load environment variables from .env at the root immediately
load_dotenv()

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ChargebackDefender")

# 2. Application Imports (imported AFTER load_dotenv so env vars are accessible)
from src.perception.vlm_analyzer import vlm_analyzer

def run_sample_pipeline():
    """
    Executes a test run simulating a chargeback claim evaluation.
    """
    logger.info("Initializing Multimodal Chargeback Defender Pipeline...")

    # Ensure API credentials exist
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    if not gemini_key and not groq_key:
        logger.error("No API keys found. Please set GEMINI_API_KEY or GROQ_API_KEY in .env")
        return

    # Sample test dispute scenario
    sample_claim = "The delivered package was completely empty, and the iPhone was missing."
    sample_image_path = "data/sample_dispute.jpg"

    # Fallback to creating a dummy test image if sample doesn't exist
    if not os.path.exists(sample_image_path):
        from PIL import Image
        os.makedirs("data", exist_ok=True)
        dummy_img = Image.new("RGB", (300, 300), color=(70, 130, 180))
        dummy_img.save(sample_image_path)
        logger.warning(f"Created temporary dummy image at '{sample_image_path}' for pipeline test.")

    logger.info("--- Step 1: Agentic Perception Layer (VLM) ---")
    vlm_result = vlm_analyzer.analyze_claim(
        image_path=sample_image_path,
        claim_text=sample_claim
    )

    print("\n" + "=" * 50)
    print("VLM ANALYSIS RESULT")
    print("=" * 50)
    print(json.dumps(vlm_result, indent=2))
    print("=" * 50 + "\n")

    # Clean up test artifact if generated dynamically
    if os.path.exists("data/sample_dispute.jpg"):
        pass

if __name__ == "__main__":
    run_sample_pipeline()