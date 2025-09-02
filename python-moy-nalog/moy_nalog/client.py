from __future__ import annotations

import random
import time
from decimal import Decimal
from typing import Optional, List, Dict, Any, Iterable

import httpx

from .auth import Auth
from .errors import raise_for_status
from .models import DeviceInfo, User, IncomeItem, UA
from .constants import DEFAULT_BASE_URL
from .logging_utils import get_logger, redact_headers, http_debug_enabled
from .utils import utcnow_iso


class ApiClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        client: Optional[httpx.Client] = None,
        device_id: Optional[str] = None,
        timeout: float = 15.0,
        retries: int = 2,
        retry_statuses: Iterable[int] = (429, 500, 502, 503, 504),
        retry_backoff_base: float = 0.25,
    ) -> None:
        self.client = client or httpx.Client(
            base_url=base_url,
            headers={
                "User-Agent": UA,
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            timeout=timeout,
        )
        self.device = DeviceInfo(sourceDeviceId=device_id or "python-client")
        self.auth = Auth(self.client, self.device)
        self._profile: Optional[User] = None
        self.retries = retries
        self.retry_statuses = set(retry_statuses)
        self.retry_backoff_base = retry_backoff_base
        self._log = get_logger()

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -------- Auth --------
    def create_new_access_token(self, username: str, password: str) -> str:
        self._log.info("auth by INN/password started")
        r = self.client.post(
            "/auth/lkfl",
            json={
                "username": username,
                "password": password,
                "deviceInfo": self.device.json(),
            },
            headers={"Referrer": "https://lknpd.nalog.ru/auth/login"},
        )
        if r.status_code >= 400:
            raise_for_status(r.status_code, r.text)
        self._log.info("auth by INN/password success")
        return r.text

    def create_phone_challenge(self, phone: str) -> Dict[str, Any]:
        self._log.info("phone challenge start requested")
        r = self.client.post(
            "/auth/challenge/sms/start",
            json={"phone": phone, "requireTpToBeActive": True},
            headers={"Referrer": "https://lknpd.nalog.ru/auth/login"},
        )
        if r.status_code >= 400:
            raise_for_status(r.status_code, r.text)
        self._log.info("phone challenge issued")
        return r.json()

    def create_new_access_token_by_phone(self, phone: str, challenge_token: str, verification_code: str) -> str:
        self._log.info("phone verify requested")
        r = self.client.post(
            "/auth/challenge/sms/verify",
            json={
                "phone": phone,
                "code": verification_code,
                "challengeToken": challenge_token,
                "deviceInfo": self.device.json(),
            },
            headers={"Referrer": "https://lknpd.nalog.ru/auth/login"},
        )
        if r.status_code >= 400:
            raise_for_status(r.status_code, r.text)
        self._log.info("phone verify success")
        return r.text

    def authenticate(self, access_token_json: str) -> None:
        self.auth.set_token(access_token_json)

    def _request(self, method: str, url: str, **kw) -> httpx.Response:
        headers = kw.pop("headers", {})
        headers.update(self.auth.auth_header())
        attempts = 0
        while True:
            self._log.debug("request", extra={"method": method, "url": url})
            start_ns = time.perf_counter_ns()
            resp = self.client.request(method, url, headers=headers, **kw)
            elapsed_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)
            self._log.debug("response", extra={"method": method, "url": url, "status": resp.status_code, "elapsed_ms": elapsed_ms})
            if http_debug_enabled():
                try:
                    self._log.debug(
                        "request-headers",
                        extra={"method": method, "url": url, "headers": redact_headers({k: v for k, v in headers.items() if isinstance(v, str)})},
                    )
                    self._log.debug(
                        "response-headers",
                        extra={"method": method, "url": url, "status": resp.status_code, "headers": redact_headers(dict(resp.headers))},
                    )
                except Exception:
                    pass
            if resp.status_code == 401:
                retry = self.auth.refresh_if_401(resp.request, resp)
                if retry is not None:
                    resp = retry
            if resp.status_code < 400 or resp.status_code not in self.retry_statuses or attempts >= self.retries:
                if resp.status_code >= 400:
                    raise_for_status(resp.status_code, resp.text)
                return resp
            delay = self.retry_backoff_base * (2 ** attempts) + random.uniform(0, 0.1)
            self._log.warning("retrying request", extra={
                "method": method,
                "url": url,
                "status": resp.status_code,
                "attempt": attempts + 1,
                "delay": round(delay, 3),
            })
            time.sleep(delay)
            attempts += 1

    # -------- Endpoints --------
    def user_get(self) -> User:
        r = self._request("GET", "/user")
        data = r.json()
        return User(inn=data["inn"], displayName=data["displayName"], id=data.get("id"))

    def income_create(
        self,
        items: List[IncomeItem],
        operation_time: Optional[str] = None,
        client: Optional[Dict[str, Any]] = None,
        payment_type: str = "CASH",
        ignore_max_total: bool = False,
    ) -> Dict[str, Any]:
        assert items, "Items cannot be empty"
        total = sum((i.amount * i.quantity for i in items), Decimal(0))
        op_time = operation_time or utcnow_iso()
        payload = {
            "operationTime": op_time,
            "requestTime": utcnow_iso(),
            "services": [
                {
                    "name": i.name,
                    "amount": str(i.amount),
                    "quantity": float(i.quantity),
                }
                for i in items
            ],
            "totalAmount": str(total),
            "client": client or {"incomeType": "FROM_INDIVIDUAL"},
            "paymentType": payment_type,
            "ignoreMaxTotalIncomeRestriction": ignore_max_total,
        }
        r = self._request("POST", "/income", json=payload)
        return r.json()

    def receipt_print_url(self, receipt_uuid: str, inn: str) -> str:
        return f"{self.client.base_url}/receipt/{inn}/{receipt_uuid}/print"

    def receipt_json(self, receipt_uuid: str, inn: str) -> Dict[str, Any]:
        r = self._request("GET", f"/receipt/{inn}/{receipt_uuid}/json")
        return r.json()

    def taxes_get(self) -> Dict[str, Any]:
        r = self._request("GET", "/taxes")
        return r.json()

    def income_cancel(
        self,
        receipt_uuid: str,
        comment: str,
        operation_time_iso: Optional[str] = None,
        request_time_iso: Optional[str] = None,
        partner_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        assert receipt_uuid, "receipt_uuid required"
        payload = {
            "operationTime": operation_time_iso or utcnow_iso(),
            "requestTime": request_time_iso or utcnow_iso(),
            "comment": comment,
            "receiptUuid": receipt_uuid,
            "partnerCode": partner_code,
        }
        r = self._request("POST", "/cancel", json=payload)
        return r.json()
