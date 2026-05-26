import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from django.conf import settings
from rest_framework.exceptions import ValidationError


def dummy_mode():
    return bool(getattr(settings, "CASHFREE_DUMMY_MODE", True))


def mode_name():
    return "dummy" if dummy_mode() else getattr(settings, "CASHFREE_ENVIRONMENT", "sandbox")


def _dummy_response(service, verification_id, extra=None):
    return {
        "mode": "dummy",
        "service": service,
        "verification_id": verification_id,
        "ref_id": f"CFD-{uuid4().hex[:12].upper()}",
        "status": "VALID",
        "message": f"{service} verification approved in dummy mode.",
        **(extra or {}),
    }


def _request_json(method, path, payload, timeout=30):
    client_id = getattr(settings, "CASHFREE_CLIENT_ID", "")
    client_secret = getattr(settings, "CASHFREE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValidationError({"cashfree": "Cashfree credentials are required when CASHFREE_DUMMY_MODE is false."})

    url = urljoin(f"{settings.CASHFREE_BASE_URL.rstrip('/')}/", path.lstrip("/"))
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-client-id": client_id,
            "x-client-secret": client_secret,
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        raise ValidationError({"cashfree": raw or str(exc)}) from exc
    except URLError as exc:
        raise ValidationError({"cashfree": str(exc.reason)}) from exc
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_response": raw}


def verify_pan(application):
    verification_id = f"PAN-{application.id or uuid4().hex[:8]}"
    if dummy_mode():
        return _dummy_response(
            "PAN",
            verification_id,
            {
                "pan": application.pan_number,
                "name": application.full_name,
                "name_match": True,
                "dob_match": True,
                "pan_status": "VALID",
            },
        )
    return _request_json(
        "POST",
        "/pan-lite",
        {
            "verification_id": verification_id,
            "pan": application.pan_number,
            "name": application.full_name,
            "dob": application.dob.isoformat(),
        },
    )


# --- DigiLocker multi-step flow ---

def digilocker_create_url(verification_id, redirect_url=None):
    """Step 1: Create DigiLocker consent URL. Returns {url, verification_id, status, ...}"""
    if dummy_mode():
        return {
            "mode": "dummy",
            "verification_id": verification_id,
            "status": "PENDING",
            "url": f"https://digilocker.quickzaps.local/dummy/{verification_id}",
            "document_requested": ["AADHAAR"],
        }
    payload = {
        "verification_id": verification_id,
        "document_requested": ["AADHAAR"],
    }
    if redirect_url and redirect_url.startswith("https://"):
        # Append digilocker_vid param so the frontend useEffect can read it on return.
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
        parsed = urlparse(redirect_url)
        qs = parse_qs(parsed.query)
        qs["digilocker_vid"] = [verification_id]
        new_query = urlencode({k: v[0] for k, v in qs.items()})
        redirect_with_vid = urlunparse(parsed._replace(query=new_query))
        payload["redirect_url"] = redirect_with_vid
    # Non-https URLs (e.g. localhost dev) are rejected by Cashfree — omit redirect_url
    # and rely on the frontend polling mechanism instead.
    return _request_json("POST", "/digilocker", payload)


def digilocker_get_status(verification_id):
    """Step 2: Poll verification status. Returns {status: PENDING|AUTHENTICATED|EXPIRED|CONSENT_DENIED, ...}"""
    if dummy_mode():
        return {
            "mode": "dummy",
            "verification_id": verification_id,
            "status": "AUTHENTICATED",
            "document_consent": ["AADHAAR"],
        }
    client_id = getattr(settings, "CASHFREE_CLIENT_ID", "")
    client_secret = getattr(settings, "CASHFREE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValidationError({"cashfree": "Cashfree credentials are required."})
    from urllib.parse import urlencode
    url = f"{settings.CASHFREE_BASE_URL.rstrip('/')}/digilocker?{urlencode({'verification_id': verification_id})}"
    request = Request(
        url,
        headers={"x-client-id": client_id, "x-client-secret": client_secret},
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        raise ValidationError({"cashfree": raw or str(exc)}) from exc
    except URLError as exc:
        raise ValidationError({"cashfree": str(exc.reason)}) from exc
    return json.loads(raw) if raw else {}


def digilocker_get_document(verification_id, document_type="AADHAAR"):
    """Step 3: Fetch the document after consent granted. Returns aadhaar details."""
    if dummy_mode():
        return {
            "mode": "dummy",
            "verification_id": verification_id,
            "status": "SUCCESS",
            "name": "Demo User",
            "dob": "01-01-2001",
            "uid": "xxxxxxxx5678",
            "message": "Aadhaar Card Exists",
        }
    client_id = getattr(settings, "CASHFREE_CLIENT_ID", "")
    client_secret = getattr(settings, "CASHFREE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValidationError({"cashfree": "Cashfree credentials are required."})
    from urllib.parse import urlencode
    url = f"{settings.CASHFREE_BASE_URL.rstrip('/')}/digilocker/document/{document_type}?{urlencode({'verification_id': verification_id})}"
    request = Request(
        url,
        headers={"x-client-id": client_id, "x-client-secret": client_secret},
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        raise ValidationError({"cashfree": raw or str(exc)}) from exc
    except URLError as exc:
        raise ValidationError({"cashfree": str(exc.reason)}) from exc
    return json.loads(raw) if raw else {}


# Keep old name as alias used by verify-identity (PAN-only now)
def create_digilocker_session(application):
    """Deprecated: used only for dummy mode in verify-identity. Real flow uses digilocker_* functions."""
    verification_id = f"DIGI-{application.id or uuid4().hex[:8]}"
    return _dummy_response(
        "DIGILOCKER",
        verification_id,
        {
            "aadhaar_number": application.aadhaar_number,
            "digilocker_status": "AUTHENTICATED",
            "document_type": "AADHAAR",
            "document_verified": True,
        },
    )


def create_reverse_penny_drop(application):
    verification_id = f"RPD-{application.id or uuid4().hex[:8]}"
    if dummy_mode():
        reference = f"RPD-{uuid4().hex[:12].upper()}"
        return _dummy_response(
            "REVERSE_PENNY_DROP",
            verification_id,
            {
                "ref_id": reference,
                "account_holder_name": application.account_holder_name,
                "account_number": application.account_number[-4:].rjust(len(application.account_number), "X"),
                "ifsc": application.ifsc,
                "rpd_status": "PAID",
                "payment_link": f"https://payments.quickzaps.local/rpd/{reference}",
            },
        )
    return _request_json(
        "POST",
        "/reverse-penny-drop",
        {
            "verification_id": verification_id,
            "name": application.account_holder_name,
            "bank_account": application.account_number,
            "ifsc": application.ifsc,
            "phone": application.mobile,
        },
    )


def verify_gstin(application):
    if not application.gst_number:
        return {}
    verification_id = f"GST-{application.id or uuid4().hex[:8]}"
    if dummy_mode():
        return _dummy_response(
            "GSTIN",
            verification_id,
            {
                "gstin": application.gst_number,
                "business_name": application.business_name,
                "taxpayer_status": "ACTIVE",
            },
        )
    return _request_json("POST", "/gstin", {"verification_id": verification_id, "GSTIN": application.gst_number})


def verify_udyam(application):
    if not application.udyam_number:
        return {}
    verification_id = f"UDYAM-{application.id or uuid4().hex[:8]}"
    if dummy_mode():
        return _dummy_response(
            "UDYAM",
            verification_id,
            {
                "udyam_number": application.udyam_number,
                "business_name": application.business_name,
                "status": "VALID",
            },
        )
    return {"mode": mode_name(), "status": "PENDING_MANUAL_REVIEW", "udyam_number": application.udyam_number}
