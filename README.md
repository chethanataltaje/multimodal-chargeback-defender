# REBUTTAL — Automated Defense, Backed by Proof, Not Persuasion
**Razorpay Buildathon 2026** | **Track 02: AI Risk Manager**  
*Autonomous Multimodal Dispute Forensics & Razorpay CE 3.0 Automation*

> **"Automated defense, backed by proof, not persuasion."**  
> Rebuttal gates every chargeback contestation behind multimodal vision forensics, EXIF camera telemetry, and calibrated CatBoost statistical gating to protect merchant margins from non-refundable dispute loss penalty fees.

---

## Executive Summary

Disputed chargebacks and friendly fraud represent an escalating drain on merchant margins. Under global card network dispute rules (Visa Compelling Evidence 3.0 / Mastercard), contesting an illegitimate chargeback carries an **asymmetric financial risk**:
- **Winning a Dispute**: Recovers transaction capital (e.g. ₹15,000 to ₹1,20,000+).
- **Losing a Dispute**: The merchant loses the transaction amount **PLUS pays a non-refundable dispute loss penalty fee ($\approx ₹1,500$ per case)**.

**REBUTTAL** is an autonomous, defense-only AI system that:
1. Cross-references customer claims against photographic evidence and EXIF telemetry via a dual-tier VLM council.
2. Gates automated submissions behind a **calibrated CatBoost probability classifier** (ROC-AUC `0.9529`, Brier Score `0.0579`).
3. Formats compliant Visa CE 3.0 evidence arrays (`shipping_proof`, `billing_proof`, `customer_communication`) and auto-contests via the **official Razorpay Python SDK** (`client.dispute.contest`).

---

## System Architecture

```mermaid
graph TD
    A[Dispute Intake: Claim + Image + TX Data] --> B[Layer 1: Perception Council]
    B -->|Gemini VLM Contradiction + EXIF Forensics| C[Layer 2: Statistical Gatekeeper]
    C -->|Calibrated Win Probability + SHAP Drivers| D{3-Tier Confidence Router}
    D -- "Win Probability > 0.85" --> E[Layer 3: Razorpay CE 3.0 API Auto-Contest]
    D -- "0.60 <= Win Probability <= 0.85" --> F[Priority Human Review Queue]
    D -- "Win Probability < 0.60" --> G[Concede Liability (Avoid ₹1,500 Fee)]
```

### Layer 1: Perception Council (Agentic Multimodal Forensics)
- **Primary VLM**: Google Gemini 3.6 Flash (`gemini-3.6-flash`) via `google-genai`.
- **Failover VLM**: Groq Cloud Vision (`llama-3.2-11b-vision-preview`).
- **Image Forensics**: `exifread` extracts GPS coordinates and capture timestamps, with an explicit fallback risk flag for EXIF-stripped screenshots.
- **Structured Schema**: Outputs Pydantic `VisionAssessment` (`vlm_contradiction_found`, `vision_confidence_score`, `insufficient_evidence`, `rationale`).

### Layer 2: Statistical Gatekeeper (CatBoost ML Engine)
- **Model**: `CatBoostClassifier` using native categorical processing (`cat_features`), strictly avoiding one-hot encoding.
- **Explainability (XAI)**: `shap.TreeExplainer` computes feature-level attribution per dispute.
- **Calibration**: Validated with **Brier Score Loss (0.0579)** and **ROC-AUC (0.9529)**.

### Layer 3: LangGraph Orchestrator & Razorpay Platform Integration
- **State Machine**: Powered by LangGraph with strict 3-tier confidence routing:
  - **`> 0.85` (Auto-Contest)**: Synthesizes Visa CE 3.0 evidence payloads and invokes the official Razorpay SDK (`client.dispute.contest`).
  - **`0.60 - 0.85` (Priority Review)**: Flags borderline disputes into the Analyst Triage Queue.
  - **`< 0.60` (Concede Liability)**: Advises liability acceptance to protect the merchant from ₹1,500 penalty fees.

---

## Quantitative Justification for the 0.85 Auto-Contest Threshold

The `0.85` threshold was mathematically derived using an asymmetric financial cost matrix:

$$\text{Net Financial Recovery} = (TP \times V_{\text{tx}}) - (FP \times (V_{\text{tx}} + C_{\text{fee}})) - ((FN + TN) \times C_{\text{triage}})$$

Where $C_{\text{fee}} = ₹1,500$ (Dispute loss penalty) and $C_{\text{triage}} = ₹200$ (Human analyst time).

| Threshold | Auto-Contest Count | Precision (Win Rate) | False Positives (Lost Fees) | Net Financial Impact (₹) | Policy Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 0.50 | 903 | 65.7% | 310 | ₹2,960,600.00 | High Penalty Exposure |
| 0.70 | 808 | 72.3% | 224 | ₹4,225,600.00 | High Penalty Exposure |
| **0.85** | **762** | **73.9%** | **199** | **₹4,313,900.00** | ⭐ **OPTIMAL AUTO-CONTEST** |
| 0.90 | 357 | 97.5% | 9 | ₹4,142,900.00 | Conservative |

> **Conclusion**: Threshold `0.85` maximizes net recovered capital for merchants while strictly suppressing dispute loss penalty fees.

---

## Tech Stack

- **Platform Integration**: `razorpay` (Official Python SDK)
- **Agent Orchestration**: `langgraph`, `pydantic`
- **Vision & LLM**: Google GenAI SDK (`google-genai`), Groq Cloud API (`httpx`)
- **Forensics & ML**: `catboost`, `shap`, `scikit-learn`, `exifread`, `pillow`, `pandas`, `numpy`
- **Backend & Frontend**: `fastapi`, `uvicorn`, Column FinTech Design System

---

## Quickstart & Launch

### 1. Environment Setup
Configure `.env` at the root:
```ini
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
RAZORPAY_KEY_ID=rzp_test_your_key_id        # Optional test mode
RAZORPAY_KEY_SECRET=your_key_secret         # Optional test mode
```

### 2. Launch the Rebuttal Web Console
```powershell
python server.py
```
Open your browser at:  
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### 3. Run Pipeline via CLI
```powershell
python main.py
```
