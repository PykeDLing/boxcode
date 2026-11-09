"""Stage 07: normalize amount.

Stores the pre-tax amount in integer cents as `amount_cents`. From here on `amount_cents` is the
source of truth: `amount` is left in the record for auditing and is NOT updated by later stages.
"""

STAGE = "normalize_amount"


def hash_text(text):
    """Small deterministic string hash, used for identifiers that must not change between runs."""
    value = 0
    for ch in text:
        value = (value * 31 + ord(ch)) % 2_147_483_647
    return value


def require(record, *keys):
    """Raise KeyError naming the first of keys that is missing from record."""
    for key in keys:
        if key not in record:
            raise KeyError(f"{STAGE}: missing {key}")


def describe():
    """Human readable description of this stage, shown by the operations dashboard."""
    return f"{STAGE}: see module docstring"


def audit_line(record):
    """One line for the audit log. Never raises, whatever the record contains."""
    known = sorted(k for k in record if isinstance(k, str))
    preview = ", ".join(known[:8])
    suffix = "..." if len(known) > 8 else ""
    return f"[{STAGE}] keys: {preview}{suffix}"


def retry_policy():
    """How the scheduler should retry this stage when a worker is lost."""
    return {"attempts": 3, "backoff_seconds": [1, 5, 30], "idempotent": True}


def metrics_labels(record):
    """Labels attached to the per-stage counters."""
    return {"stage": STAGE, "country": str(record.get("country", "?"))[:2], "source": str(record.get("source", "?"))}


def run(record):
    """Run this stage on record in place and return it."""
    record["amount_cents"] = round(record["amount"] * 100)
    return record
