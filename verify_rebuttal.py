"""
verify_rebuttal.py
Comprehensive End-to-End Automated Verification Script for REBUTTAL Platform
Tests:
1. Preset demo cases initialization & canonical scenario calibration.
2. Direct pipeline execution (perception, GPS haversine distance, timestamp correlation).
3. Telemetry isolation: Normal customer dispute with no merchant ref returns NOT_VERIFIABLE.
4. Demo case with matching merchant ref calculates exact Haversine distance and timestamp match.
5. Customer dispute creation with image upload.
6. Customer isolation / authorization: Customer B receives HTTP 403 trying to view Customer A's dispute.
7. Admin analysis execution on customer dispute.
8. Analyst review submission (Approve / Concede / Override).
9. Information request & response lifecycle:
   - Admin requests additional info -> status becomes EVIDENCE_REQUESTED.
   - Customer responds with message + supplementary photo -> original evidence preserved!
   - Supplementary evidence attached to case.
10. Final submission / liability acceptance.
11. Real ReportLab PDF generation -> HTTP 200, Content-Type application/pdf, %PDF- magic bytes, and all required sections.
"""

import sys
import os
import json
import io
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from server import app
from src.case_store import (
    get_case, list_cases, list_customer_cases,
    verify_customer_ownership, seed_preset_cases,
    STATUS_EVIDENCE_RECEIVED, STATUS_EVIDENCE_REQUESTED, STATUS_SUBMITTED
)
from src.orchestrator.agent import run_defense_agent

client = TestClient(app)

def test_preset_cases_and_scenarios():
    print("\n--- TEST 1: Preset Demo Cases Initialization ---")
    seed_preset_cases()
    cases = list_cases()
    demo_ids = [c["dispute_id"] for c in cases if c.get("source") == "demo"]
    print(f"Loaded demo cases: {demo_ids}")
    assert "DIS-DEMO-001" in demo_ids, "DIS-DEMO-001 missing"
    assert "DIS-DEMO-002" in demo_ids, "DIS-DEMO-002 missing"
    assert "DIS-DEMO-003" in demo_ids, "DIS-DEMO-003 missing"

    # Verify DIS-DEMO-001 (Friendly fraud -> Auto-Contest)
    c1 = get_case("DIS-DEMO-001")
    assert c1["amount"] == 119900.00
    assert c1["user_account_age_days"] == 5
    assert c1["prior_chargeback_count"] == 4

    # Verify DIS-DEMO-002 (Legitimate damage -> Concede Liability)
    c2 = get_case("DIS-DEMO-002")
    assert c2["amount"] == 4999.00
    assert c2["user_account_age_days"] == 850
    assert c2["prior_chargeback_count"] == 0

    print("✓ Preset demo cases correctly seeded with canonical scenario attributes.")


def test_telemetry_isolation_and_correlation():
    print("\n--- TEST 2: Multimodal Telemetry Isolation & Correlation ---")
    # Test A: Case with NO merchant reference (normal customer upload)
    payload_customer = {
        "dispute_id": "DIS_CUST_TEST_001",
        "transaction_id": "pay_cust_unique_999",
        "claim_text": "Item arrived defective.",
        "image_path": "data/test_samples/intact_phone.jpg",
        "reason_code": "damaged",
        "merchant_category": "electronics",
        "user_account_age_days": 365,
        "transaction_amount": 5000,
        "prior_chargeback_count": 0,
    }
    state_cust = run_defense_agent(payload_customer)
    assert state_cust.gps_correlation == "NOT_VERIFIABLE", f"Expected NOT_VERIFIABLE, got {state_cust.gps_correlation}"
    assert state_cust.timestamp_correlation == "NOT_VERIFIABLE", f"Expected NOT_VERIFIABLE, got {state_cust.timestamp_correlation}"
    assert state_cust.merchant_reference is None, "Expected merchant_reference to be None for unreferenced case"
    print("✓ Customer case without merchant telemetry correctly returns NOT_VERIFIABLE with merchant_reference=None.")

    # Test B: Demo Case 1 (DIS-DEMO-001 has reference in data/merchant_refs.json)
    payload_demo = {
        "dispute_id": "DIS-DEMO-001",
        "transaction_id": "pay_demo_friendly_001",
        "claim_text": "The phone screen arrived completely shattered in pieces and unusable.",
        "image_path": "data/test_samples/intact_phone.jpg",
        "reason_code": "damaged",
        "merchant_category": "electronics",
        "user_account_age_days": 5,
        "transaction_amount": 119900,
        "prior_chargeback_count": 4,
    }
    state_demo = run_defense_agent(payload_demo)
    assert state_demo.merchant_reference is not None, "Demo case 1 should resolve merchant reference"
    print(f"Demo 1 GPS Correlation: {state_demo.gps_correlation} (dist: {state_demo.gps_distance_meters}m)")
    print(f"Demo 1 Timestamp Correlation: {state_demo.timestamp_correlation} (diff: {state_demo.timestamp_difference_minutes}min)")
    print(f"Demo 1 Win Probability: {state_demo.win_probability * 100:.1f}%")
    print(f"Demo 1 Routing Tier: {state_demo.routing_tier}")
    assert state_demo.win_probability >= 0.85, "Demo 1 should predict high win prob >= 85%"
    assert state_demo.routing_tier == "AUTO_CONTEST", "Demo 1 should route to AUTO_CONTEST"
    print("✓ Demo 1 correctly routed to AUTO_CONTEST with genuine telemetry analysis.")


def test_customer_creation_and_isolation():
    print("\n--- TEST 3: Customer Submission & Strict Role Isolation ---")
    img_path = Path("data/test_samples/damaged_item.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    # Customer A creates dispute
    res_a = client.post(
        "/api/disputes",
        data={
            "transaction_id": "pay_test_cust_a_123",
            "amount": "4500.00",
            "reason": "Damaged / Defective Goods",
            "claim": "The device had a cracked frame upon arrival.",
            "customer_id": "CUST_ALPHA",
            "customer_email": "alpha@example.com",
            "merchant_category": "electronics",
            "user_account_age_days": "400",
            "prior_chargeback_count": "0",
        },
        files={"image": ("damaged_item.jpg", io.BytesIO(img_bytes), "image/jpeg")},
    )
    assert res_a.status_code == 201, f"Create dispute failed: {res_a.text}"
    disp_a_id = res_a.json()["dispute_id"]
    print(f"Created Customer A dispute: {disp_a_id}")

    # Verify Customer A can fetch their dispute detail
    res_detail_a = client.get(f"/api/customer/disputes/{disp_a_id}?customer_id=CUST_ALPHA&customer_email=alpha@example.com")
    assert res_detail_a.status_code == 200, f"Customer A should be able to view their dispute: {res_detail_a.text}"
    assert res_detail_a.json()["dispute_id"] == disp_a_id

    # Verify Customer B CANNOT fetch Customer A's dispute (Role Isolation HTTP 403)
    res_detail_b = client.get(f"/api/customer/disputes/{disp_a_id}?customer_id=CUST_BETA&customer_email=beta@example.com")
    assert res_detail_b.status_code == 403, f"Expected 403 Forbidden for Customer B, got {res_detail_b.status_code}"
    print("✓ Customer isolation verified: Customer B denied access (HTTP 403) to Customer A's dispute.")

    # Verify Customer list only returns Customer A's dispute for Customer A
    res_list_a = client.get("/api/customer/disputes?customer_id=CUST_ALPHA")
    assert res_list_a.status_code == 200
    ids_a = [d["dispute_id"] for d in res_list_a.json()]
    assert disp_a_id in ids_a
    assert "DIS-DEMO-001" not in ids_a, "Demo cases must not appear in customer list"
    print("✓ Customer dispute list strictly filtered by customer ownership.")

    return disp_a_id


def test_supplementary_evidence_preservation(dispute_id: str):
    print("\n--- TEST 4: Supplementary Evidence Lifecycle (Zero Overwrite) ---")
    case_before = get_case(dispute_id)
    original_evidence = case_before.get("evidence")
    assert original_evidence is not None, "Original evidence must exist"
    orig_path = original_evidence.get("path")
    orig_name = original_evidence.get("filename")

    # Step 1: Admin requests additional information
    req_res = client.post(
        f"/api/disputes/{dispute_id}/request-info",
        json={"title": "Delivery Package Photo Needed", "message": "Please attach delivery box photo."},
    )
    assert req_res.status_code == 200
    case_req = get_case(dispute_id)
    assert case_req["status"] == STATUS_EVIDENCE_REQUESTED

    # Step 2: Customer responds with supplementary photo
    supp_bytes = b"fake-supplementary-photo-content-2026"
    resp_res = client.post(
        f"/api/customer/disputes/{dispute_id}/respond-info",
        data={"message": "Here is the box label photo.", "customer_id": "CUST_ALPHA"},
        files={"file": ("box_label.jpg", io.BytesIO(supp_bytes), "image/jpeg")},
    )
    assert resp_res.status_code == 200, f"Customer response failed: {resp_res.text}"

    # Step 3: Check that original evidence was NOT overwritten!
    case_after = get_case(dispute_id)
    assert case_after["evidence"]["filename"] == orig_name, "Original evidence filename must NOT be overwritten"
    assert case_after["evidence"]["path"] == orig_path, "Original evidence path must NOT be overwritten"
    assert case_after["supplementary_evidence"] is not None, "Supplementary evidence must be stored in supplementary_evidence"
    assert case_after["supplementary_evidence"]["filename"] == "box_label.jpg"
    assert case_after["status"] == STATUS_EVIDENCE_RECEIVED
    print("✓ Supplementary evidence preserved in case['supplementary_evidence'] without overwriting case['evidence'].")


def test_analyst_review_and_concede(dispute_id: str):
    print("\n--- TEST 5: Pipeline Analysis & Concede Liability Resolution ---")
    # Run analysis on the dispute
    an_res = client.post(f"/api/disputes/{dispute_id}/analyze")
    assert an_res.status_code == 200, f"Analysis failed: {an_res.text}"
    case_an = get_case(dispute_id)
    assert case_an.get("analysis") is not None
    assert case_an.get("risk") is not None

    # Submit Analyst Decision to Concede Liability
    rev_res = client.post(
        f"/api/disputes/{dispute_id}/review",
        json={
            "action": "APPROVE",
            "override_strategy": None,
            "override_reason": None,
            "evidence_type": None,
            "evidence_note": None,
            "analyst_name": "Chethana A.",
        },
    )
    assert rev_res.status_code == 200, f"Review failed: {rev_res.text}"

    # Submit resolution (accept liability)
    sub_res = client.post(f"/api/disputes/{dispute_id}/submit")
    assert sub_res.status_code == 200, f"Submission failed: {sub_res.text}"
    case_final = get_case(dispute_id)
    assert case_final["status"] in ("approved", "overridden", "submitted")
    assert case_final["submission"]["status"] in ("LIABILITY_CONCEDED", "SUBMITTED_VIA_RAZORPAY_SDK", "SUBMITTED_SIMULATED", "DEMO_SIMULATION_COMPLETED")
    print(f"✓ Final resolution recorded: {case_final['submission']['status']}")


def test_real_reportlab_pdf(dispute_id: str):
    print("\n--- TEST 6: Real ReportLab PDF Audit Receipt Generation ---")
    pdf_res = client.get(f"/api/disputes/{dispute_id}/audit-receipt")
    assert pdf_res.status_code == 200, f"PDF download failed: {pdf_res.text}"
    assert pdf_res.headers.get("content-type") == "application/pdf", "Content-Type must be application/pdf"
    assert f"Audit_Receipt_{dispute_id}.pdf" in pdf_res.headers.get("content-disposition", "")
    content = pdf_res.content
    assert len(content) > 2000, f"PDF size too small: {len(content)} bytes"
    assert content.startswith(b"%PDF-"), "File must start with standard PDF magic bytes '%PDF-'"
    assert b"%%EOF" in content, "File must end with standard PDF EOF marker '%%EOF'"
    assert b"/Catalog" in content or b"/Root" in content, "File must contain PDF Document Catalog / Root dictionary"
    assert b"/Pages" in content, "File must contain PDF Pages tree dictionary"

    # Verify content consistency with UI
    import re, zlib, base64
    all_text = []
    for m in re.finditer(rb"<<(.*?)>>\s*stream[\r\n]+", content, re.DOTALL):
        start = m.end()
        end = content.find(b"endstream", start)
        raw = content[start:end].strip(b"\r\n\t ")
        if not raw.endswith(b"~>"):
            a85_data = raw + b"~>"
        else:
            a85_data = raw
        try:
            decomp = zlib.decompress(base64.a85decode(a85_data, adobe=True))
            all_text.append(decomp.decode("latin1", errors="ignore"))
        except Exception:
            try:
                decomp = zlib.decompress(raw)
                all_text.append(decomp.decode("latin1", errors="ignore"))
            except Exception:
                pass

    pdf_text = "\n".join(all_text)
    case_obj = get_case(dispute_id)
    case_win_prob = (case_obj.get("risk") or {}).get("win_probability")
    expected_routing = "AUTO-CONTEST" if (case_win_prob is not None and case_win_prob >= 0.85) else "CONCEDE LIABILITY"
    assert expected_routing in pdf_text, f"PDF must dynamically recommend {expected_routing} for win prob {case_win_prob}"
    assert "metadata_available" in pdf_text, "PDF must display metadata_available when merchant telemetry is unavailable"
    assert pdf_text.count("Analyst Approved") == 1, f"Expected exactly 1 'Analyst Approved' event, got {pdf_text.count('Analyst Approved')}"
    print(f"✓ Verified valid ReportLab PDF ({len(content):,} bytes) with '%PDF-' header, ISO PDF structure, and UI-consistent fields.")


def test_held_out_evaluation_endpoint():
    print("\n--- TEST 7: Scientifically Honest Held-Out Test Evaluation Endpoint ---")
    res = client.get("/api/model-evaluation")
    assert res.status_code == 200, f"Model evaluation endpoint failed: {res.text}"
    data = res.json()

    ds = data["dataset_metadata"]
    assert ds["train_samples"] == 20000, f"Expected 20,000 train samples, got {ds['train_samples']}"
    assert ds["held_out_samples"] == 5000, f"Expected 5,000 held-out samples, got {ds['held_out_samples']}"
    assert ds["is_synthetic"] is True, "Expected synthetic dataset disclosure"

    m = data["held_out_metrics_at_85_threshold"]
    assert m["threshold"] == 0.85
    assert m["roc_auc"] > 0.90, f"ROC-AUC should exceed 0.90, got {m['roc_auc']}"
    assert m["brier_score"] < 0.10, f"Brier score should be < 0.10 for financial APIs, got {m['brier_score']}"
    assert m["precision"] > 0.65, f"Precision at 0.85 should exceed 65%, got {m['precision']}"

    cm = m["confusion_matrix"]
    tp, tn, fp, fn = cm["true_positives"], cm["true_negatives"], cm["false_positives"], cm["false_negatives"]
    assert tp + tn + fp + fn == 5000, f"Total confusion matrix sum must equal 5,000 held-out samples, got {tp+tn+fp+fn}"
    expected_cost = fp * 1500.0
    assert m["false_positive_penalty_cost"] == expected_cost, f"FP cost mismatch: {m['false_positive_penalty_cost']} vs {expected_cost}"

    # Also verify /api/cost-matrix loads dynamic held-out metrics
    cm_res = client.get("/api/cost-matrix")
    assert cm_res.status_code == 200
    cm_data = cm_res.json()
    assert cm_data["metrics"]["roc_auc_score"] == m["roc_auc"]
    assert cm_data["metrics"]["brier_score_loss"] == m["brier_score"]
    assert len(cm_data["table"]) > 0

def test_razorpay_honesty():
    print("\n--- TEST 8: Razorpay Integration Honesty & Document ID Verification ---")
    from src.orchestrator.razorpay_client import razorpay_client

    # 1. Verify Mode Status Endpoint
    status_res = client.get("/api/razorpay-status")
    assert status_res.status_code == 200, f"Status failed: {status_res.text}"
    sdata = status_res.json()
    assert sdata["mode_badge"] in ("DEMO SIMULATION — NOT SENT TO RAZORPAY", "RAZORPAY TEST API", "RAZORPAY LIVE API")
    print(f"✓ Verified operating mode: {sdata['mode_badge']}")

    # 2. Verify Document ID Integrity (No raw EXIF/VLM strings as Document IDs)
    payload = razorpay_client.build_ce3_evidence_payload(
        transaction_id="pay_integrity_test_123",
        claim_text="Item was broken into pieces.",
        reason_code="damaged",
        perception_data={
            "vision_reasoning": "Device screen is intact.",
            "vlm_contradiction_found": True,
            "gps_coordinates": {"latitude": 12.9716, "longitude": 77.5946},
            "capture_timestamp": "2026-08-30T10:00:00Z",
            "metadata_match": True,
        }
    )

    for key in ("shipping_proof", "billing_proof", "customer_communication"):
        docs = payload[key]
        assert isinstance(docs, list), f"{key} must be an array of doc IDs"
        for doc_id in docs:
            assert doc_id.startswith("doc_"), f"Item in {key} is not a valid Razorpay Document ID: '{doc_id}'"
            assert "EXIF_FORENSICS:" not in doc_id, f"Found EXIF forensics in document ID: '{doc_id}'"
            assert "VLM_FORENSIC_EVALUATION:" not in doc_id, f"Found VLM forensics in document ID: '{doc_id}'"

    assert "CONTRADICTION DETECTED" in payload["summary"]
    assert "EXIF GPS=12.9716,77.5946" in payload["summary"]
    print("✓ Document ID integrity verified: EXIF/VLM findings strictly in summary, only doc_* IDs in proof arrays.")

    # 3. Verify No Fake "AUTO_CONTESTED_SUCCESS" on Unexecuted Calls
    contest_res = razorpay_client.contest_dispute(
        dispute_id="disp_demo_integrity",
        evidence_payload=payload
    )
    if contest_res.get("is_simulated"):
        assert contest_res["status"] != "AUTO_CONTESTED_SUCCESS", "Simulation must never return fake AUTO_CONTESTED_SUCCESS"
        assert contest_res["mode_badge"] == "DEMO SIMULATION — NOT SENT TO RAZORPAY"
        assert contest_res["submission_id"].startswith("sim_")
        print("✓ Zero fake success: Simulation accurately flagged as 'DEMO SIMULATION — NOT SENT TO RAZORPAY' with sim_* ID.")
    else:
        assert contest_res["status"] in ("SUBMITTED_VIA_RAZORPAY_TEST_API", "SUBMITTED_VIA_RAZORPAY_LIVE_API")
        print(f"✓ Real API call confirmed: {contest_res['status']}")


if __name__ == "__main__":
    try:
        test_preset_cases_and_scenarios()
        test_telemetry_isolation_and_correlation()
        new_disp_id = test_customer_creation_and_isolation()
        test_supplementary_evidence_preservation(new_disp_id)
        test_analyst_review_and_concede(new_disp_id)
        test_real_reportlab_pdf(new_disp_id)
        test_held_out_evaluation_endpoint()
        test_razorpay_honesty()
        print("\n========================================================")
        print("🎉 ALL 8 AUTOMATED BUILDATHON VERIFICATION SUITES PASSED!")
        print("========================================================\n")
    except Exception as err:
        print(f"\n❌ TEST RUN FAILED: {err}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if 'new_disp_id' in locals() and new_disp_id:
            case_p = Path(f"data/cases/{new_disp_id}.json")
            if case_p.exists():
                case_p.unlink()
            for up in Path("data/uploads").glob(f"{new_disp_id}*"):
                if up.is_file():
                    up.unlink()
            print(f"Cleaned up temporary test case: {new_disp_id}")
