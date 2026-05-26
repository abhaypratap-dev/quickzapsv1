import base64
import binascii
import hashlib
import json
import os
from datetime import datetime
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from django.conf import settings
from rest_framework.exceptions import ValidationError


try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, padding as sym_padding, serialization
    from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError:  # pragma: no cover - guarded by runtime configuration errors.
    x509 = None
    default_backend = None
    hashes = None
    sym_padding = None
    serialization = None
    asym_padding = None
    Cipher = None
    algorithms = None
    modes = None


SENSITIVE_KEY_PARTS = {
    "aadhaar",
    "aadhar",
    "adhaar",
    "pid",
    "biometric",
    "capture",
    "hmac",
    "sessionkey",
    "merchantpin",
    "merchantloginpin",
    "password",
    "supermerchantpassword",
    "accountnumber",
    "companybankaccountnumber",
    "pannumber",
    "userpan",
    "companyorshoppan",
    "merchantpanimage",
    "maskedaadharimage",
    "backgroundimageofshop",
}


VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def md5_hex(value):
    return hashlib.md5(str(value or "").encode("utf-8")).hexdigest()


def sha256_base64(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return base64.b64encode(hashlib.sha256(value).digest()).decode("ascii")


def canonical_json(data):
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def trn_timestamp():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def only_digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def mask_aadhaar(value):
    digits = only_digits(value)
    if len(digits) < 4:
        return ""
    return f"XXXXXXXX{digits[-4:]}"


def mask_account(value):
    digits = only_digits(value)
    if len(digits) < 4:
        return ""
    return f"XXXX{digits[-4:]}"


def mask_pan(value):
    value = str(value or "").strip().upper()
    if len(value) < 5:
        return ""
    return f"{value[:2]}***{value[-2:]}"


def is_valid_aadhaar(value):
    digits = only_digits(value)
    if len(digits) != 12 or digits[0] in {"0", "1"}:
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        checksum = VERHOEFF_D[checksum][VERHOEFF_P[index % 8][int(digit)]]
    return checksum == 0


def sanitize_payload(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                if "aadhaar" in normalized or "aadhar" in normalized or "adhaar" in normalized:
                    sanitized[key] = mask_aadhaar(item)
                elif "accountnumber" in normalized or "companybankaccountnumber" in normalized:
                    sanitized[key] = mask_account(item)
                elif "pan" in normalized:
                    sanitized[key] = mask_pan(item)
                elif "capture" in normalized or "pid" in normalized or "biometric" in normalized:
                    sanitized[key] = "[redacted biometric payload]"
                else:
                    sanitized[key] = "[redacted]"
            else:
                sanitized[key] = sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def compact_provider_response(response):
    if not isinstance(response, dict):
        return {}
    return sanitize_payload(response)


class FingpayAepsClient:
    ONBOARDING_PATH = "/fpaepsweb/api/onboarding/merchant/creation/v2"
    EKYC_SEND_OTP_PATH = "/fpekyc/api/ekyc/merchant/sendotp"
    EKYC_VALIDATE_OTP_PATH = "/fpekyc/api/ekyc/merchant/validateotp"
    EKYC_RESEND_OTP_PATH = "/fpekyc/api/ekyc/merchant/resendotp"
    EKYC_BIOMETRIC_PATH = "/fpekyc/api/ekyc/merchant/biometric"
    EKYC_STATUS_PATH = "/fpekyc/api/ekyc/status/check"
    BANK_DETAILS_PATH = "/fpaepsservice/api/bankdata/bank/details"
    PRODUCT_PATHS = {
        "CW": "/fpaepsservice/api/cashWithdrawal/merchant/withdrawal",
        "BE": "/fpaepsservice/api/balanceInquiry/merchant/getBalance",
        "MS": "/fpaepsservice/api/miniStatement/merchant/statement",
        "M": "/fpaepsservice/api/aadhaarPay/merchant/pay",
        "CD": "/fpaepsservice/api/CashDeposit/merchant/deposit",
    }

    def __init__(self):
        self.dummy_mode = bool(getattr(settings, "FINGPAY_AEPS_DUMMY_MODE", True))
        self.base_url = getattr(settings, "FINGPAY_AEPS_BASE_URL", "https://fingpayap.tapits.in").rstrip("/")
        self.onboarding_url = getattr(settings, "FINGPAY_AEPS_ONBOARDING_URL", "").strip()
        self.ekyc_base_url = getattr(settings, "FINGPAY_AEPS_EKYC_BASE_URL", "https://fpekyc.tapits.in").rstrip("/")
        self.super_login_id = getattr(settings, "FINGPAY_AEPS_SUPER_MERCHANT_LOGIN_ID", "")
        self.super_password = getattr(settings, "FINGPAY_AEPS_SUPER_MERCHANT_PASSWORD", "")
        self.super_merchant_id = int(getattr(settings, "FINGPAY_AEPS_SUPER_MERCHANT_ID", 0) or 0)
        self.secret_key = getattr(settings, "FINGPAY_AEPS_SECRET_KEY", "")
        self.default_device_imei = getattr(settings, "FINGPAY_AEPS_DEFAULT_DEVICE_IMEI", "")
        self.timeout = int(getattr(settings, "FINGPAY_AEPS_TIMEOUT_SECONDS", 45) or 45)

    def _url(self, base_url, path):
        return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))

    def _require_credentials(self, secure=False, super_credentials=False, secret_key=False):
        if self.dummy_mode:
            return
        missing = []
        if super_credentials and not self.super_login_id:
            missing.append("FINGPAY_AEPS_SUPER_MERCHANT_LOGIN_ID")
        if super_credentials and not self.super_password:
            missing.append("FINGPAY_AEPS_SUPER_MERCHANT_PASSWORD")
        if not self.super_merchant_id:
            missing.append("FINGPAY_AEPS_SUPER_MERCHANT_ID")
        if secure and not self._public_key_configured():
            missing.append("FINGPAY_AEPS_PUBLIC_KEY_PEM or FINGPAY_AEPS_PUBLIC_CERT_PATH")
        if secret_key and not self.secret_key:
            missing.append("FINGPAY_AEPS_SECRET_KEY")
        if missing:
            raise ValidationError(
                {
                    "code": "FINGPAY_AEPS_CONFIG_REQUIRED",
                    "message": f"Missing Fingpay AEPS configuration: {', '.join(missing)}.",
                }
            )

    def _public_key_configured(self):
        return bool(getattr(settings, "FINGPAY_AEPS_PUBLIC_KEY_PEM", "") or getattr(settings, "FINGPAY_AEPS_PUBLIC_CERT_PATH", ""))

    def _public_key_candidates(self, raw):
        candidates = [raw]
        text = raw.decode("utf-8", errors="ignore").strip()
        if text:
            unescaped = text.replace("\\r\\n", "\n").replace("\\n", "\n")
            if unescaped != text:
                candidates.append(unescaped.encode("utf-8"))
            if "-----BEGIN" not in unescaped:
                compact = "".join(unescaped.split())
                if compact:
                    try:
                        candidates.append(base64.b64decode(compact, validate=True))
                    except (binascii.Error, ValueError):
                        pass
        return candidates

    def _load_public_key(self, raw):
        for candidate in self._public_key_candidates(raw):
            loaders = (
                lambda value: serialization.load_pem_public_key(value, backend=default_backend()),
                lambda value: x509.load_pem_x509_certificate(value, default_backend()).public_key(),
                lambda value: serialization.load_der_public_key(value, backend=default_backend()),
                lambda value: x509.load_der_x509_certificate(value, default_backend()).public_key(),
            )
            for loader in loaders:
                try:
                    return loader(candidate)
                except (TypeError, ValueError):
                    continue
        raise ValidationError(
            {
                "code": "FINGPAY_AEPS_PUBLIC_KEY_INVALID",
                "message": "Fingpay public certificate/key could not be parsed. Provide PEM certificate text, PEM public key text, DER bytes, or base64 DER text.",
            }
        )

    def _public_key(self):
        if serialization is None or x509 is None:
            raise ValidationError({"code": "CRYPTOGRAPHY_REQUIRED", "message": "Install cryptography to use Fingpay encrypted AEPS APIs."})
        pem = getattr(settings, "FINGPAY_AEPS_PUBLIC_KEY_PEM", "")
        cert_path = getattr(settings, "FINGPAY_AEPS_PUBLIC_CERT_PATH", "")
        if pem:
            return self._load_public_key(pem.encode("utf-8"))
        if cert_path:
            with open(cert_path, "rb") as cert_file:
                return self._load_public_key(cert_file.read())
        raise ValidationError({"code": "FINGPAY_AEPS_PUBLIC_KEY_REQUIRED", "message": "Fingpay public certificate/key is required."})

    def _encrypt_payload(self, payload, use_secret_hash=False):
        self._require_credentials(secure=True, secret_key=use_secret_hash)
        session_key = os.urandom(16)
        raw_json = canonical_json(payload).encode("utf-8")
        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(raw_json) + padder.finalize()
        cipher = Cipher(algorithms.AES(session_key), modes.ECB(), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_body = encryptor.update(padded) + encryptor.finalize()
        encrypted_key = self._public_key().encrypt(session_key, asym_padding.PKCS1v15())
        hash_input = raw_json + (self.secret_key.encode("utf-8") if use_secret_hash else b"")
        return {
            "body": base64.b64encode(encrypted_body).decode("ascii"),
            "eskey": base64.b64encode(encrypted_key).decode("ascii"),
            "hash": sha256_base64(hash_input),
        }

    def _post_json(self, url, payload, headers=None):
        request = Request(
            url,
            data=canonical_json(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        return self._open_json(request)

    def _post_text(self, url, text_body, headers=None):
        request = Request(
            url,
            data=str(text_body).encode("utf-8"),
            headers={"Content-Type": "text/plain", **(headers or {})},
            method="POST",
        )
        return self._open_json(request)

    def _get_json(self, url, headers=None):
        request = Request(url, headers=headers or {}, method="GET")
        return self._open_json(request)

    def _open_json(self, request):
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8") if exc.fp else ""
            raise ValidationError({"code": "FINGPAY_AEPS_REQUEST_FAILED", "message": (raw or str(exc))[:240]}) from exc
        except URLError as exc:
            raise ValidationError({"code": "FINGPAY_AEPS_UNREACHABLE", "message": str(exc.reason)[:240]}) from exc
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw_response": raw}

    def _encrypted_post(self, base_url, path, payload, device_imei="", use_secret_hash=False, require_device_imei=True):
        if self.dummy_mode:
            return self._dummy_response(path, payload)
        device_header = device_imei or self.default_device_imei
        if require_device_imei and not device_header:
            raise ValidationError(
                {
                    "code": "FINGPAY_AEPS_DEVICE_IMEI_REQUIRED",
                    "message": "Fingpay requires the biometric scanner IMEI/serial in the deviceIMEI header for web EKYC/AEPS calls.",
                }
            )
        encrypted = self._encrypt_payload(payload, use_secret_hash=use_secret_hash)
        headers = {
            "trnTimestamp": trn_timestamp(),
            "hash": encrypted["hash"],
            "eskey": encrypted["eskey"],
        }
        if device_header:
            headers["deviceIMEI"] = device_header
        return self._post_text(self._url(base_url, path), encrypted["body"], headers=headers)

    def onboard_merchant(self, payload):
        if self.dummy_mode:
            return self._dummy_onboarding(payload)
        self._require_credentials(secure=True, super_credentials=True)
        timestamp = payload.get("timestamp") or trn_timestamp()
        encrypted_payload = {**payload, "timestamp": timestamp}
        encrypted = self._encrypt_payload(encrypted_payload)
        headers = {
            "trnTimestamp": timestamp,
            "hash": encrypted["hash"],
            "eskey": encrypted["eskey"],
        }
        url = self.onboarding_url or self._url(self.base_url, self.ONBOARDING_PATH)
        return self._post_text(url, encrypted["body"], headers=headers)

    def send_ekyc_otp(self, payload, device_imei=""):
        return self._encrypted_post(self.ekyc_base_url, self.EKYC_SEND_OTP_PATH, payload, device_imei=device_imei)

    def validate_ekyc_otp(self, payload, device_imei=""):
        return self._encrypted_post(self.ekyc_base_url, self.EKYC_VALIDATE_OTP_PATH, payload, device_imei=device_imei)

    def resend_ekyc_otp(self, payload, device_imei=""):
        return self._encrypted_post(self.ekyc_base_url, self.EKYC_RESEND_OTP_PATH, payload, device_imei=device_imei)

    def biometric_ekyc(self, payload, device_imei=""):
        return self._encrypted_post(self.ekyc_base_url, self.EKYC_BIOMETRIC_PATH, payload, device_imei=device_imei)

    def ekyc_status(self, payload):
        if self.dummy_mode:
            return {"status": True, "message": "Ekyc Done Successfully", "data": None, "statusCode": 10000}
        self._require_credentials(secret_key=True)
        timestamp = trn_timestamp()
        raw_json = canonical_json(payload)
        hash_value = sha256_base64(f"{raw_json}{self.secret_key}{timestamp}".encode("utf-8"))
        headers = {"trnTimestamp": timestamp, "hash": hash_value}
        return self._post_json(self._url(self.ekyc_base_url, self.EKYC_STATUS_PATH), payload, headers=headers)

    def bank_details(self):
        if self.dummy_mode:
            return {
                "status": True,
                "message": "Request Completed",
                "data": [
                    {"bankName": "State Bank of India", "iinno": "607094"},
                    {"bankName": "Punjab National Bank", "iinno": "607027"},
                    {"bankName": "Bank of Baroda", "iinno": "606985"},
                ],
                "statusCode": 10000,
            }
        return self._get_json(self._url(self.base_url, self.BANK_DETAILS_PATH))

    def execute_product(self, transaction_type, payload, device_imei=""):
        path = self.PRODUCT_PATHS.get(transaction_type)
        if not path:
            raise ValidationError({"transaction_type": "Unsupported AEPS transaction type."})
        return self._encrypted_post(self.base_url, path, payload, device_imei=device_imei, use_secret_hash=transaction_type == "CD")

    def _dummy_onboarding(self, payload):
        merchant = payload.get("merchant") or {}
        return {
            "status": True,
            "message": "successful",
            "data": {
                "merchantStatus": True,
                "remarks": "Successfully recorded in AEPS dummy mode",
                "superMerchantId": payload.get("supermerchantId") or payload.get("superMerchantId") or self.super_merchant_id,
                "merchantLoginId": merchant.get("merchantLoginId", ""),
                "errorCodes": None,
            },
            "statusCode": 10000,
        }

    def _dummy_response(self, path, payload):
        if path == self.EKYC_SEND_OTP_PATH:
            return {
                "status": True,
                "message": "Request Completed",
                "data": {"primaryKeyId": 12123, "encodeFPTxnId": "EKYCDUMMY123"},
                "statusCode": 10000,
            }
        if path in {self.EKYC_VALIDATE_OTP_PATH, self.EKYC_RESEND_OTP_PATH}:
            return {
                "status": True,
                "message": "Request Completed",
                "data": {"primaryKeyId": payload.get("primaryKeyId", 12123), "encodeFPTxnId": payload.get("encodeFPTxnId", "EKYCDUMMY123")},
                "statusCode": 10000,
            }
        if path == self.EKYC_BIOMETRIC_PATH:
            return {"status": True, "message": "EKYC Completed Successfully", "data": None, "statusCode": 10000}

        transaction_type = payload.get("transactionType", "CW")
        amount = payload.get("transactionAmount", 0)
        merchant_txn = payload.get("merchantTranId") or payload.get("merchantTransactionId") or "AEPSDUMMY"
        return {
            "status": True,
            "message": "Request Completed",
            "data": {
                "terminalId": "FPDUMMY001",
                "requestTransactionTime": trn_timestamp(),
                "transactionAmount": amount,
                "transactionStatus": "SUCCESS",
                "balanceAmount": 25000.0 if transaction_type in {"BE", "MS"} else 0.0,
                "bankRRN": f"RRN{only_digits(merchant_txn)[-9:] or '000000001'}",
                "transactionType": transaction_type,
                "fpTransactionId": f"{transaction_type}DUMMY{only_digits(merchant_txn)[-8:] or '00000001'}",
                "merchantTxnId": merchant_txn,
                "responseCode": "00",
            },
            "statusCode": 10000,
        }


def fingpay_success(response):
    if not isinstance(response, dict):
        return False
    status_code = str(response.get("statusCode", ""))
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    response_code = str(data.get("responseCode", ""))
    if response_code:
        return response_code == "00" and bool(response.get("status", False))
    return bool(response.get("status", False)) and status_code in {"10000", "200", "201", ""}
