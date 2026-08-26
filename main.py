import os
import sys
import json
import logging
from dotenv import load_dotenv
from PIL import Image, ImageDraw

# Ensure UTF-8 output encoding across Windows shells
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 1. Load environment variables
load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Rebuttal")

from src.orchestrator.agent import run_defense_agent

def create_sample_images():
    """
    Generates illustrative test images for the 3 demo scenarios.
    Uses PIL ImageDraw so the VLM has clear visual text/shapes to analyze.
    """
    os.makedirs("data/test_samples", exist_ok=True)
    
    # 1. Intact Phone (Contradicts 'shattered screen' claim)
    path1 = "data/test_samples/intact_phone.jpg"
    img1 = Image.new("RGB", (400, 400), color=(240, 240, 245))
    draw1 = ImageDraw.Draw(img1)
    draw1.rounded_rectangle([(80, 40), (320, 360)], radius=20, outline=(30, 30, 30), width=6, fill=(15, 23, 42))
    draw1.rounded_rectangle([(95, 65), (305, 335)], radius=10, fill=(56, 189, 248))
    draw1.text((110, 180), "SCREEN IS INTACT\nNO CRACKS OR DAMAGE", fill=(255, 255, 255))
    img1.save(path1)
        
    # 2. Genuine Damaged Item
    path2 = "data/test_samples/damaged_item.jpg"
    img2 = Image.new("RGB", (400, 400), color=(240, 240, 245))
    draw2 = ImageDraw.Draw(img2)
    draw2.rounded_rectangle([(60, 60), (340, 340)], radius=10, outline=(180, 30, 30), width=4, fill=(254, 226, 226))
    draw2.line([(100, 100), (300, 300)], fill=(220, 38, 38), width=8)
    draw2.line([(120, 280), (280, 120)], fill=(220, 38, 38), width=6)
    draw2.text((100, 210), "SEVERE PHYSICAL DAMAGE\nSNAPPED HEADBAND", fill=(153, 27, 27))
    img2.save(path2)
        
    # 3. Ambiguous / Dark / Inconclusive Image
    path3 = "data/test_samples/dark_ambiguous.jpg"
    img3 = Image.new("RGB", (400, 400), color=(10, 10, 15))
    draw3 = ImageDraw.Draw(img3)
    draw3.text((120, 190), "[EXTREMELY BLURRY / DARK]", fill=(40, 40, 50))
    img3.save(path3)

    return path1, path2, path3

def run_demonstration():
    logger.info("=" * 70)
    logger.info("REBUTTAL — Automated Defense, Backed by Proof, Not Persuasion")
    logger.info("Razorpay Buildathon 2026 (Track 02: AI Risk Manager)")
    logger.info("=" * 70)

    img_intact, img_damaged, img_dark = create_sample_images()

    scenarios = [
        {
            "name": "Scenario 1: High-Confidence Friendly Fraud (Auto-Contest)",
            "data": {
                "transaction_id": "pay_98a76b54c3210f",
                "order_id": "order_iphone_16_pro",
                "claim_text": "The phone screen arrived completely shattered in pieces and unusable.",
                "image_path": img_intact,
                "reason_code": "damaged",
                "merchant_category": "electronics",
                "user_account_age_days": 5,          # Burner account
                "transaction_amount": 119900.00,      # ₹1,19,900
                "prior_chargeback_count": 4           # Serial disputer
            }
        },
        {
            "name": "Scenario 2: Borderline / High-Yield Dispute (Priority Human Review)",
            "data": {
                "transaction_id": "pay_45e67f89d0123a",
                "order_id": "order_sneakers_airmax",
                "claim_text": "Package showed up but color was completely wrong and box was torn.",
                "image_path": img_dark,
                "reason_code": "damaged",
                "merchant_category": "apparel",
                "user_account_age_days": 180,
                "transaction_amount": 14999.00,
                "prior_chargeback_count": 1
            }
        },
        {
            "name": "Scenario 3: Legitimate Customer / Low Win Probability (Standard Queue / Concede)",
            "data": {
                "transaction_id": "pay_11b22c33d4455e",
                "order_id": "order_headphones_sony",
                "claim_text": "Headphone headband snapped immediately upon unboxing.",
                "image_path": img_damaged,
                "reason_code": "damaged",
                "merchant_category": "electronics",
                "user_account_age_days": 850,        # Established 2+ yr account
                "transaction_amount": 4999.00,
                "prior_chargeback_count": 0          # Clean record
            }
        }
    ]

    for sc in scenarios:
        print("\n" + "#" * 70)
        print(f"[SCENARIO] EXECUTING: {sc['name']}")
        print("#" * 70)
        
        result_state = run_defense_agent(sc["data"])
        
        print("\n--- FINAL PIPELINE DECISION SUMMARY ---")
        print(f"Transaction ID:      {result_state.transaction_id}")
        print(f"Dispute Reason:      {result_state.reason_code} ({result_state.merchant_category})")
        print(f"Transaction Amount:  INR {result_state.transaction_amount:,.2f}")
        print(f"Win Probability:     {result_state.win_probability:.1%}")
        print(f"Routing Tier:        {result_state.routing_tier}")
        print(f"Final Action:        {result_state.final_action}")
        
        if result_state.perception_result:
            print(f"VLM Contradiction:   {result_state.perception_result.vlm_contradiction_found}")
            print(f"VLM Confidence:      {result_state.perception_result.vision_confidence_score:.2f}")
            print(f"VLM Rationale:       {result_state.perception_result.vision_reasoning}")
        
        if result_state.top_drivers:
            print("\nTop 3 SHAP Drivers:")
            for d in result_state.top_drivers:
                print(f"  * {d['feature']}: {d['impact']:+.3f}")
                
        if result_state.action_details:
            print(f"\nAction Details:")
            print(json.dumps(result_state.action_details, indent=2))

if __name__ == "__main__":
    run_demonstration()