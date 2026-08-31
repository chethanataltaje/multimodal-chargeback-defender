<div align="center">

# REBUTTAL

### Automated Defense, Backed by Proof — Not Persuasion

**Razorpay Buildathon 2026 · Track 02: AI Risk Manager**

*Autonomous Multimodal Dispute Forensics & Razorpay CE 3.0 Automation*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CatBoost](https://img.shields.io/badge/ML-CatBoost-FFCC00)](https://catboost.ai/)
[![Gemini](https://img.shields.io/badge/VLM-Google%20Gemini-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-1C3C3C)](https://www.langchain.com/langgraph)
[![Razorpay](https://img.shields.io/badge/API-Razorpay%20CE%203.0-0C2340?logo=razorpay&logoColor=white)](https://razorpay.com/)
[![License](https://img.shields.io/badge/License-MIT-blue)](#license)

</div>

---

> **"Rebuttal doesn't talk your customer out of a dispute. It proves them wrong."**
>
> Rebuttal gates every chargeback contestation behind multimodal visual forensics, real EXIF/GPS telemetry validation against merchant delivery logs, and a calibrated CatBoost statistical gate — protecting merchant margins from non-refundable dispute-loss penalty fees without a single user-facing persuasion tactic.

---

## Table of Contents

- [The Problem](#the-problem)
- [The Solution](#the-solution)
- [System Architecture](#system-architecture)
- [Two-Role Platform Architecture](#two-role-platform-architecture)
- [Forensic & Telemetry Honesty](#forensic--telemetry-honesty)
- [Quantitative 0.85 Threshold Justification](#quantitative-justification-for-the-085-auto-contest-threshold)
- [Tech Stack](#tech-stack)
- [Quickstart & Setup](#quickstart--setup)
- [Key API Endpoints](#key-api-endpoints)
- [Project Structure](#project-structure)
- [Limitations & Disclosures](#limitations--disclosures)

---

## The Problem

Friendly fraud — customers falsely claiming an item was never received, or arrived damaged — costs merchants billions annually. Under card network rules (Visa Compelling Evidence 3.0, Mastercard), contesting a chargeback carries **asymmetric financial risk**:

| Outcome | Financial Impact |
|---|---|
| **Win the dispute** | Recovers transaction capital (₹15,000 – ₹1,20,000+) |
| **Lose the dispute** | Loses transaction amount **+ a non-refundable dispute penalty fee (₹1,500/case)** |

Most approaches either build user-facing chatbots that try to talk customers out of disputes (a major compliance violation) or rely on a single LLM to guess fraud, which hallucinates and cannot be trusted with financial APIs.

**Rebuttal takes an evidence-first, back-office approach.** It is an enterprise dispute operations platform that acts strictly on verifiable data and calibrated statistical confidence.

---

## The Solution

1. **Multimodal Perception Council**: Cross-references customer claim statements against uploaded photos via **Google Gemini 3.6 Flash / 2.5 Flash** to detect visual contradictions, and extracts real camera EXIF metadata (capture timestamp, GPS coordinates, camera model).
2. **Telemetry Correlation**: Compares evidence coordinates and capture time against authoritative merchant logistics records (`merchant_refs.json`) to detect geofence/temporal mismatches.
3. **Statistical Gatekeeper**: Gates automated actions behind a calibrated `CatBoostClassifier` (ROC-AUC `0.9529`, Brier Score `0.0579`) with SHAP TreeExplainer feature attributions.
4. **Dynamic Operational Resolution**:
   - **Win Probability ≥ 85% (`AUTO_CONTEST`)**: Compiles rigid Visa CE 3.0 evidence arrays and transmits to Razorpay Disputes API (`POST /v1/disputes/{id}/contest`).
   - **Win Probability < 60% (`CONCEDE LIABILITY`)**: Formally records liability acceptance to protect merchant capital from the non-refundable ₹1,500 penalty fee.
   - **60% ≤ Win Probability < 85% (`PRIORITY TRIAGE`)**: Routes case to senior risk specialists for manual review.
5. **Analyst Decision Station with Confirmation Modal**: Human-in-the-loop review station with a formal audit modal before committing determinations to the case ledger.
6. **Forensically Honest PDF Audit Receipt**: Generates downloadable, court-ready PDF audit reports on demand via `ReportLab` directly from backend case records.

---

## System Architecture

```mermaid
graph TD
    A["Customer Dispute Submission: Claim + Evidence Image + Transaction ID"] --> B["Case Store: JSON File Persistence (data/cases/)"]
    B --> C["Layer 1: Perception Council"]
    C -->|"Gemini VLM Contradiction Check"| D["Forensic Features"]
    C -->|"Real EXIF GPS & Timestamp Extraction"| E["Telemetry Engine"]
    E -->|"Haversine Distance vs Merchant Reference"| D
    D --> F["Layer 2: CatBoost Statistical Gatekeeper"]
    F -->|"Calibrated Win Probability + SHAP Attribution"| G{"3-Tier Confidence Router"}
    G -- "Win Probability ≥ 0.85" --> H["AUTO-CONTEST: Razorpay CE 3.0 API"]
    G -- "0.60 ≤ Win Probability < 0.85" --> I["PRIORITY TRIAGE: Specialist Queue"]
    G -- "Win Probability < 0.60" --> J["CONCEDE LIABILITY: Avoid ₹1,500 Penalty Fee"]
    H & I & J --> K["Analyst Review Station + Confirmation Modal"]
    K --> L["Final Action & Resolution + PDF Audit Receipt"]
```

---

## Two-Role Platform Architecture

### 1. Risk Operations Console (`/admin` or `/`)
- **Dispute Queue**: Central operations hub displaying all active cases, status filters (New, Evidence Received, Awaiting Review, Submitted, Conceded), and real-time cross-tab sync.
- **5-Stage Defense Workflow**:
  - `01 Intake`: Transaction data, dispute claims, customer KYC profile, and customer evidence responses.
  - `02 Evidence Analysis`: Dual-viewport pixel examination, VLM contradiction detection, and EXIF/GPS telemetry validation.
  - `03 Risk Assessment`: Calibrated win probability gauge, 0.85 policy threshold margin, and human-readable SHAP drivers.
  - `04 Analyst Review`: Recommendation review (`Approve (Auto-Contest)`, `Approve (Concede Liability)`, `Override Strategy`, or `Request Additional Evidence`) with **Decision Confirmation Modal**.
  - `05 Final Action & Resolution`: Dynamic display for CE 3.0 submission vs Liability Acceptance, live API transmission, and PDF Audit Receipt download.

### 2. Customer Dispute Portal (`/customer`)
- **Strict Role Isolation**: Completely separated from admin routes and controls.
- **My Disputes**: Cardholders view submitted disputes, active status badges, and action-required banners.
- **Submit Dispute**: Intake form with real-time transaction ID validation, amount, reason code, claim narrative, and evidence image upload.
- **Additional Evidence Response**: Direct interface for customers to fulfill evidence requests issued by risk operations.

---

## Forensic & Telemetry Honesty

Rebuttal enforces strict truth-in-evidence standards:
- **No Fabricated Telemetry**: If an image lacks EXIF data (common in chat apps or screenshots), it is explicitly marked `Unavailable / Stripped`.
- **GPS Honesty**: If EXIF exists without GPS tags, coordinates are flagged `Unavailable` and delivery correlation is marked `NOT VERIFIABLE`.
- **Telemetry Verification**: Delivery `MATCH` is asserted **only** when real coordinate data exists in both the image EXIF and merchant logistics delivery records, and falls within acceptable distance/time tolerance limits. If merchant records are missing, the system explicitly reports:
  > *"Merchant delivery telemetry unavailable — correlation not verifiable."*

---

## Quantitative Justification for the 0.85 Auto-Contest Threshold

The 0.85 threshold is mathematically derived from the asymmetric cost matrix:

$$\text{Net Recovery} = (TP \times V_{tx}) - (FP \times (V_{tx} + C_{fee})) - ((FN + TN) \times C_{triage})$$

where $C_{fee} = \text{₹1,500}$ (network dispute-loss penalty) and $C_{triage} = \text{₹200}$ (analyst triage overhead).

| Threshold | Auto-Contest Volume | Precision (Win Rate) | False Positives | Net Financial Impact | Status |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 0.50 | 903 | 65.7% | 310 | ₹29,60,600 | High penalty exposure |
| 0.70 | 808 | 72.3% | 224 | ₹42,25,600 | High penalty exposure |
| **0.85** | **762** | **73.9%** | **199** | **₹43,13,900** | ⭐ **Optimal Recovery** |
| 0.90 | 357 | 97.5% | 9 | ₹41,42,900 | Overly conservative |

---

## Tech Stack

| Component | Technologies |
|---|---|
| **Backend** | FastAPI, Uvicorn, Pydantic, Python 3.10+ |
| **ML & Explainability** | CatBoostClassifier, SHAP (TreeExplainer), Scikit-Learn |
| **Multimodal Vision** | Google Gemini 3.6 Flash / 2.5 Flash (`google-genai`), Pillow |
| **Forensics** | ExifRead, Haversine Coordinate Distance Math |
| **Audit Generation** | ReportLab 5.x (In-memory PDF generation) |
| **Agent Orchestration** | LangGraph, Razorpay Python SDK |
| **Persistence** | File-backed atomic JSON Case Store (`data/cases/`) |
| **Frontend** | Vanilla JS, CSS Custom Properties, FinTech Operations Design System |

---

## Quickstart & Setup

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/chethanataltaje/multimodal-chargeback-defender.git
cd multimodal-chargeback-defender
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file at the project root:

```ini
# Required for VLM perception
GEMINI_API_KEY=your_gemini_api_key

# Optional (Failover VLM)
GROQ_API_KEY=your_groq_api_key

# Optional: Razorpay Live/Testnet Credentials (defaults to Sandbox simulation if omitted)
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
```

### 3. Start the Server

```bash
uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

- **Portal Landing**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Admin Risk Console**: [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) *(Demo login: `admin@razorpay.com` / `admin123`)*
- **Customer Portal**: [http://127.0.0.1:8000/customer](http://127.0.0.1:8000/customer) *(Demo login: any email/password)*

---

## Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/disputes` | List all disputes in the operations queue |
| `GET` | `/api/disputes/{id}` | Fetch authoritative dispute record |
| `POST` | `/api/disputes` | Customer submits new dispute with evidence image |
| `POST` | `/api/disputes/{id}/analyze` | Run VLM + EXIF + CatBoost defense pipeline |
| `POST` | `/api/disputes/{id}/review` | Persist analyst determination to audit trail |
| `POST` | `/api/disputes/{id}/submit` | Execute Razorpay CE 3.0 submission or Liability Concession |
| `GET` | `/api/disputes/{id}/audit-receipt` | Stream Court-Ready PDF Audit Receipt (ReportLab) |
| `POST` | `/api/customer/disputes/{id}/respond-info` | Customer submits requested supplemental evidence |

---

## Project Structure

```
multimodal-chargeback-defender/
├── server.py                       # FastAPI application & REST/PDF endpoints
├── main.py                         # CLI multi-scenario runner
├── requirements.txt                # Full Python dependencies
├── src/
│   ├── case_store.py               # Authoritative JSON case store & audit trail
│   ├── orchestrator/
│   │   ├── agent.py                # LangGraph defense workflow orchestrator
│   │   └── razorpay_client.py      # Razorpay SDK CE 3.0 client & sandbox
│   ├── perception/
│   │   ├── vlm_analyzer.py         # Google Gemini multimodal contradiction analyzer
│   │   └── metadata_extractor.py   # EXIF GPS/timestamp extraction engine
│   ├── gatekeeper/
│   │   ├── predictor.py            # CatBoost win probability & SHAP explainer
│   │   ├── train_model.py          # Model training pipeline
│   │   └── gatekeeper_model.cbm    # Serialized CatBoost binary model
│   └── schemas/
│       └── data_models.py          # Pydantic data schemas & state models
├── frontend/
│   ├── index.html                  # Risk Operations Console SPA
│   ├── app.js                      # Admin controller & multi-stage state engine
│   ├── style.css                   # Enterprise design tokens & layouts
│   ├── landing.html                # Role selection portal
│   └── customer/
│       ├── index.html              # Customer Dispute Portal SPA
│       └── app.js                  # Customer intake & dispute tracking logic
└── data/
    ├── merchant_refs.json          # Merchant logistics & delivery telemetry references
    ├── test_samples/               # Illustrative test evidence imagery
    └── cases/                      # Authoritative dispute JSON storage records
```

---

## Limitations & Disclosures

- **Synthetic Baseline Distribution**: The CatBoost model is trained on a synthetic dataset of 25,000 mathematically correlated dispute transactions due to the confidentiality of proprietary cardholder data.
- **EXIF Stripping by Social Platforms**: Images uploaded through social channels (WhatsApp, screenshots) frequently lack EXIF metadata. The system flags this explicitly as an unverified signal rather than assuming tampering.
- **Defense-Only Scope**: The system never communicates unprompted messages or applies persuasive pressure to the cardholder; it operates strictly as an internal decision engine and API integration layer.

---

<div align="center">

Built for **Razorpay Buildathon 2026** · Track 02: AI Risk Manager

</div>
