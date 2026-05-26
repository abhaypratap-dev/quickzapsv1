import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import APIRequestLog, Operator, PartnerAPISetting, PaymentGatewayOrder, Service, ServiceTransaction
from .serializers import PaymentGatewayOrderSerializer, ServiceTransactionSerializer
from .services import PaymentGatewayService, TransactionExecutionService, get_client_ip, new_reference


@dataclass
class PartnerContext:
    setting: PartnerAPISetting
    request_id: str
    timestamp: str
    api_key: str

    @property
    def user(self):
        return self.setting.user


def partner_success(message, data=None, http_status=200):
    return Response({"StatusCode": "200", "Message": message, "data": data or {}}, status=http_status)


def partner_error(message, http_status=401, code="401"):
    return Response({"StatusCode": code, "Message": message}, status=http_status)


def _plain_data(value):
    if hasattr(value, "dict"):
        value = value.dict()
    if isinstance(value, dict):
        return {key: _plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_data(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def canonical_payload(data):
    return json.dumps(_plain_data(data), separators=(",", ":"), ensure_ascii=False)


def compute_signature(api_key, timestamp, payload):
    raw_data = f"{api_key}|{timestamp}|{payload}"
    return hashlib.sha256(raw_data.encode("utf-8")).hexdigest()


def validate_partner_request(request):
    if getattr(settings, "PARTNER_API_DUMMY_MODE", False):
        User = get_user_model()
        user = (
            User.objects.select_related("role", "scheme")
            .filter(mobile=getattr(settings, "PARTNER_API_DUMMY_USER_MOBILE", "9000000004"), status="active", is_active=True)
            .first()
        )
        if not user:
            user = User.objects.select_related("role", "scheme").filter(role__code="API_USER", status="active", is_active=True).first()
        if not user:
            user = User.objects.select_related("role", "scheme").filter(status="active", is_active=True).first()
        if not user:
            raise ValidationError("No active dummy API user is available.")
        api_key = request.headers.get("x-api-key", getattr(settings, "PARTNER_API_DUMMY_KEY", "quickzaps-dummy-key"))
        timestamp = request.headers.get("x-timestamp", str(int(timezone.now().timestamp())))
        request_id = request.headers.get("x-request-id", new_reference("REQ"))
        setting = SimpleNamespace(user=user, api_key=api_key, active=True, allowed_ip=None, allowed_ip2=None, webhook_url="")
        return PartnerContext(setting=setting, request_id=request_id, timestamp=timestamp, api_key=api_key)

    api_key = request.headers.get("x-api-key", "").strip()
    timestamp = request.headers.get("x-timestamp", "").strip()
    signature = request.headers.get("x-signature", "").strip().lower()
    request_id = request.headers.get("x-request-id", "").strip()

    missing = [
        name
        for name, value in {
            "x-api-key": api_key,
            "x-timestamp": timestamp,
            "x-signature": signature,
            "x-request-id": request_id,
        }.items()
        if not value
    ]
    if missing:
        raise ValidationError(f"Missing required headers: {', '.join(missing)}")

    try:
        setting = PartnerAPISetting.objects.select_related("user", "user__role", "user__scheme").get(api_key=api_key, active=True)
    except PartnerAPISetting.DoesNotExist as exc:
        raise ValidationError("Invalid or inactive API key.") from exc

    if setting.user.status != "active" or not setting.user.is_active:
        raise ValidationError("API user is inactive or blocked.")

    client_ip = get_client_ip(request)
    allowed_ips = {str(value) for value in [setting.allowed_ip, setting.allowed_ip2] if value}
    if allowed_ips and client_ip not in allowed_ips:
        raise ValidationError("Client IP is not whitelisted for this API key.")

    tolerance = int(getattr(settings, "PARTNER_API_TIMESTAMP_TOLERANCE_SECONDS", 0))
    if tolerance:
        try:
            drift = abs(int(timezone.now().timestamp()) - int(timestamp))
        except ValueError as exc:
            raise ValidationError("x-timestamp must be a Unix timestamp.") from exc
        if drift > tolerance:
            raise ValidationError("x-timestamp is outside the allowed request window.")

    payloads = [canonical_payload(request.data)]
    raw_body = request.body.decode("utf-8").strip() if request.body else ""
    if raw_body and raw_body not in payloads:
        payloads.append(raw_body)

    expected_values = [compute_signature(api_key, timestamp, payload).lower() for payload in payloads]
    if not any(constant_time_compare(signature, expected) for expected in expected_values):
        raise ValidationError("Invalid request signature.")

    return PartnerContext(setting=setting, request_id=request_id, timestamp=timestamp, api_key=api_key)


def log_partner_request(request, context=None, response_payload=None, status_code=200):
    api_key = request.headers.get("x-api-key", "")
    APIRequestLog.objects.create(
        user=context.user if context else None,
        request_id=request.headers.get("x-request-id", ""),
        api_key_prefix=api_key[:12],
        path=request.path[:240],
        method=request.method,
        ip_address=get_client_ip(request),
        request_payload=_plain_data(request.data) if hasattr(request, "data") else {},
        response_payload=_plain_data(response_payload or {}),
        status_code=status_code,
    )


def find_service(code):
    try:
        return Service.objects.get(code=code, active=True)
    except Service.DoesNotExist as exc:
        raise ValidationError(f"{code} service is not configured or inactive.") from exc


def find_operator(service, preferred_code="", preferred_name=""):
    query = Operator.objects.filter(service=service, active=True)
    preferred_code = (preferred_code or "").upper()
    if preferred_code:
        operator = query.filter(code__iexact=preferred_code).first()
        if operator:
            return operator
    if preferred_name:
        operator = query.filter(name__iexact=preferred_name).first()
        if operator:
            return operator
    operator = query.first()
    if not operator:
        raise ValidationError(f"No active operator configured for {service.name}.")
    return operator


@transaction.atomic
def execute_partner_transaction(context, service, operator, amount, customer_mobile, order_id, description="", payload=None):
    if not order_id:
        raise ValidationError("OrderId is required.")
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Amount must be a valid decimal value.") from exc
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    payload = payload or {}
    payload.setdefault("description", description)
    payload.setdefault("legacy_order_id", order_id)
    tx = TransactionExecutionService.execute(
        context.user,
        service,
        operator,
        amount,
        customer_mobile,
        tpin="",
        idempotency_key=order_id,
        payload=payload,
        skip_tpin=True,
    )
    return tx


def settlement_payload(tx):
    return {
        "OrderID": tx.idempotency_key or tx.reference,
        "Tid": tx.provider_reference or tx.reference,
        "Amount": tx.amount,
        "TxStatus": tx.status.upper(),
        "AccounNumber": tx.request_payload.get("account_number", ""),
        "AccountHolderName": tx.request_payload.get("beneficiary_name", ""),
        "IfscCode": tx.request_payload.get("ifsc", ""),
        "TransactionaDate": tx.created_at,
        "Utr": tx.provider_reference or "N/A",
    }


def transaction_payload(tx):
    return ServiceTransactionSerializer(tx).data


def create_payment_link(user, amount, order_id, payload):
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Amount must be a valid decimal value.") from exc
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    order = PaymentGatewayService.create_order(user, amount, payload=_plain_data(payload), reference=order_id or new_reference("PG"))
    return PaymentGatewayOrderSerializer(order).data
