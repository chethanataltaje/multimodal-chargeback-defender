"""
case_store.py — Lightweight JSON file-based case persistence for Rebuttal.

Each case is stored as a single JSON file:
  data/cases/<dispute_id>.json

The binary evidence image is NOT stored in the JSON; only the path reference.
"""

import json
import os
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("CaseStore")

CASES_DIR = Path("data/cases")

# ── Status constants ──────────────────────────────────────────────────────────
STATUS_NEW               = "new"
STATUS_EVIDENCE_RECEIVED = "evidence_received"
STATUS_ANALYZING         = "analyzing"
STATUS_ANALYSIS_COMPLETE = "analysis_complete"
STATUS_AWAITING_REVIEW   = "awaiting_review"
STATUS_APPROVED          = "approved"
STATUS_OVERRIDDEN        = "overridden"
STATUS_EVIDENCE_REQUESTED = "evidence_requested"
STATUS_SUBMITTED         = "submitted"

# ── Helpers ───────────────────────────────────────────────────────────────────
def _ensure_dir():
    CASES_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(dispute_id: str) -> str:
    """Validate dispute_id to prevent path traversal."""
    if not re.fullmatch(r"[A-Z0-9_\-]{4,40}", dispute_id):
        raise ValueError(f"Invalid dispute_id: {dispute_id!r}")
    return dispute_id


def _case_path(dispute_id: str) -> Path:
    return CASES_DIR / f"{_safe_id(dispute_id)}.json"


def _next_sequence() -> int:
    """Return the next sequential dispute counter based on existing files."""
    _ensure_dir()
    existing = list(CASES_DIR.glob("DIS_*.json"))
    return len(existing) + 1


def generate_dispute_id() -> str:
    """Generate a human-readable dispute ID: DIS_YYYYMMDD_NNNN"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    seq = _next_sequence()
    return f"DIS_{today}_{seq:04d}"


# ── Core CRUD ─────────────────────────────────────────────────────────────────
def create_case(dispute_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Write a new case JSON file.
    `payload` must conform to the case schema.
    Raises FileExistsError if the case already exists.
    """
    _ensure_dir()
    path = _case_path(dispute_id)
    if path.exists():
        raise FileExistsError(f"Case {dispute_id} already exists.")

    now = _now_iso()
    case = {
        "dispute_id": dispute_id,
        "source": payload.get("source", "customer_submitted"),
        "transaction_id": payload.get("transaction_id", ""),
        "customer_id": payload.get("customer_id", ""),
        "customer_email": payload.get("customer_email", ""),
        "amount": payload.get("amount", 0),
        "currency": payload.get("currency", "INR"),
        "reason": payload.get("reason", ""),
        "claim": payload.get("claim", ""),
        "merchant_category": payload.get("merchant_category", ""),
        "user_account_age_days": payload.get("user_account_age_days", 365),
        "prior_chargeback_count": payload.get("prior_chargeback_count", 0),
        "evidence": payload.get("evidence", None),
        "status": payload.get("status", STATUS_NEW),
        "analysis": None,
        "risk": None,
        "review": None,
        "submission": None,
        "audit_trail": payload.get("audit_trail", []),
        "created_at": now,
        "updated_at": now,
    }

    path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Case created: {dispute_id}")
    return case


def get_case(dispute_id: str) -> Optional[Dict[str, Any]]:
    """Return the case dict, or None if not found."""
    path = _case_path(dispute_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def update_case(dispute_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge `fields` into the existing case and persist.
    Always updates `updated_at`.
    """
    case = get_case(dispute_id)
    if case is None:
        raise FileNotFoundError(f"Case {dispute_id} not found.")
    case.update(fields)
    case["updated_at"] = _now_iso()
    _case_path(dispute_id).write_text(
        json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return case


def append_audit_event(dispute_id: str, event: str, metadata: Optional[Dict] = None) -> None:
    """Push a timestamped audit event into the case's audit_trail list."""
    case = get_case(dispute_id)
    if case is None:
        raise FileNotFoundError(f"Case {dispute_id} not found.")
    entry: Dict[str, Any] = {"event": event, "timestamp": _now_iso()}
    if metadata:
        entry.update(metadata)
    case.setdefault("audit_trail", []).append(entry)
    case["updated_at"] = _now_iso()
    _case_path(dispute_id).write_text(
        json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def list_cases() -> List[Dict[str, Any]]:
    """Return all cases sorted by created_at descending."""
    _ensure_dir()
    cases = []
    for p in CASES_DIR.glob("*.json"):
        try:
            cases.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning(f"Could not read case file {p}: {e}")
    cases.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return cases


def case_exists(dispute_id: str) -> bool:
    return _case_path(dispute_id).exists()


def list_customer_cases(customer_id: Optional[str] = None, customer_email: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return cases filtered by customer_id or customer_email."""
    all_cases = list_cases()
    if not customer_id and not customer_email:
        return []
    filtered = []
    for c in all_cases:
        c_id = c.get("customer_id", "")
        c_email = c.get("customer_email", "")
        if (customer_id and c_id == customer_id) or (customer_email and c_email.lower() == customer_email.lower()):
            filtered.append(c)
    return filtered



# ── Seeding ───────────────────────────────────────────────────────────────────
PRESET_CASES = [
    {
        "dispute_id": "DIS-DEMO-001",
        "source": "demo",
        "transaction_id": "pay_demo_friendly_001",
        "customer_id": "CUST_DEMO_001",
        "customer_email": "rajan.mehta@example.com",
        "amount": 119900.00,
        "currency": "INR",
        "reason": "Damaged or Defective Goods",
        "claim": "The phone screen arrived completely shattered in pieces and unusable.",
        "merchant_category": "electronics",
        "user_account_age_days": 365,
        "prior_chargeback_count": 0,
        "evidence": {
            "source": "demo",
            "filename": "intact_phone.jpg",
            "path": "data/test_samples/intact_phone.jpg",
            "url": "/data/test_samples/intact_phone.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": 0,
        },
        "status": STATUS_EVIDENCE_RECEIVED,
        "audit_trail": [
            {"event": "case_created", "timestamp": "2026-08-30T05:00:00+00:00"},
            {"event": "evidence_received", "timestamp": "2026-08-30T05:01:00+00:00"},
        ],
    },
    {
        "dispute_id": "DIS-DEMO-002",
        "source": "demo",
        "transaction_id": "pay_demo_damage_002",
        "customer_id": "CUST_DEMO_002",
        "customer_email": "vikram.rao@example.com",
        "amount": 4999.00,
        "currency": "INR",
        "reason": "Damaged or Defective Goods",
        "claim": "The item arrived physically damaged and cannot be used.",
        "merchant_category": "electronics",
        "user_account_age_days": 90,
        "prior_chargeback_count": 1,
        "evidence": {
            "source": "demo",
            "filename": "damaged_item.jpg",
            "path": "data/test_samples/damaged_item.jpg",
            "url": "/data/test_samples/damaged_item.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": 0,
        },
        "status": STATUS_EVIDENCE_RECEIVED,
        "audit_trail": [
            {"event": "case_created", "timestamp": "2026-08-30T04:00:00+00:00"},
            {"event": "evidence_received", "timestamp": "2026-08-30T04:01:00+00:00"},
        ],
    },
    {
        "dispute_id": "DIS-DEMO-003",
        "source": "demo",
        "transaction_id": "pay_demo_borderline_003",
        "customer_id": "CUST_DEMO_003",
        "customer_email": "priya.nair@example.com",
        "amount": 14999.00,
        "currency": "INR",
        "reason": "Damaged or Defective Goods",
        "claim": "The sneakers arrived damaged and showed signs of wear.",
        "merchant_category": "apparel",
        "user_account_age_days": 45,
        "prior_chargeback_count": 3,
        "evidence": {
            "source": "demo",
            "filename": "dark_ambiguous.jpg",
            "path": "data/test_samples/dark_ambiguous.jpg",
            "url": "/data/test_samples/dark_ambiguous.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": 0,
        },
        "status": STATUS_EVIDENCE_RECEIVED,
        "audit_trail": [
            {"event": "case_created", "timestamp": "2026-08-29T23:00:00+00:00"},
            {"event": "evidence_received", "timestamp": "2026-08-29T23:01:00+00:00"},
        ],
    },
]


def seed_preset_cases():
    """
    Called at server startup.
    Non-destructive: only creates the 3 demo cases if they don't already exist.
    Customer-submitted disputes are NEVER deleted.
    """
    _ensure_dir()
    for preset in PRESET_CASES:
        did = preset["dispute_id"]
        if not _case_path(did).exists():
            create_case(did, dict(preset))
            logger.info(f"Seeded demo case: {did}")
        else:
            logger.info(f"Demo case already exists, skipping: {did}")


def reset_to_preset_cases():
    """
    Hard reset: remove all cases + uploads, re-seed 3 preset demo cases.
    Only called explicitly via the admin 'Reset Queue' button.
    NOT called at server startup.
    """
    _ensure_dir()

    for p in CASES_DIR.glob("*.json"):
        try:
            p.unlink()
        except Exception as e:
            logger.warning(f"Could not remove case file {p}: {e}")

    uploads_dir = Path("data/uploads")
    if uploads_dir.exists():
        for f in uploads_dir.glob("*"):
            try:
                if f.is_file():
                    f.unlink()
            except Exception as e:
                logger.warning(f"Could not remove upload file {f}: {e}")

    for preset in PRESET_CASES:
        did = preset["dispute_id"]
        create_case(did, dict(preset))
        logger.info(f"Re-seeded fresh preset case: {did}")


def cleanup_legacy_cases():
    """Reset to preset test cases (explicit admin action only)."""
    reset_to_preset_cases()

