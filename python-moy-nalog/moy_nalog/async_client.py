from __future__ import annotations

import asyncio
import random
import time
from decimal import Decimal
from typing import Optional, List, Dict, Any, Iterable

import httpx

from .async_auth import AsyncAuth
from .errors import raise_for_status
from .models import DeviceInfo, User, IncomeItem, UA
from .constants import DEFAULT_BASE_URL
from .utils import utcnow_iso


class AsyncApiClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        client: Optional[httpx.AsyncClient] = None,
        device_id: Optional[str] = None,
        timeout: float = 15.0,
        retries: int = 2,
        retry_statuses: Iterable[int] = (429, 500, 502, 503, 504),
        retry_backoff_base: float = 0.25,
    ) -> None:
        self.client = client or httpx.AsyncClient(
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
        self.auth = AsyncAuth(self.client, self.device)
        self._profile: Optional[User] = None
        self.retries = retries
        self.retry_statuses = set(retry_statuses)
        self.retry_backoff_base = retry_backoff_base

    async def aclose(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> "AsyncApiClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    # -------- Auth --------
    async def create_new_access_token(self, username: str, password: str) -> str:
        r = await self.client.post(
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
        return r.text

    async def create_phone_challenge(self, phone: str) -> Dict[str, Any]:
        r = await self.client.post(
            "/auth/challenge/sms/start",
            json={"phone": phone, "requireTpToBeActive": True},
            headers={"Referrer": "https://lknpd.nalog.ru/auth/login"},
        )
        if r.status_code >= 400:
            raise_for_status(r.status_code, r.text)
        return r.json()

    async def create_new_access_token_by_phone(self, phone: str, challenge_token: str, verification_code: str) -> str:
        r = await self.client.post(
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
        return r.text

    def authenticate(self, access_token_json: str) -> None:
        self.auth.set_token(access_token_json)

    async def _request(self, method: str, url: str, **kw) -> httpx.Response:
        headers = kw.pop("headers", {})
        headers.update(self.auth.auth_header())
        attempts = 0
        while True:
            resp = await self.client.request(method, url, headers=headers, **kw)
            if resp.status_code == 401:
                retry = await self.auth.refresh_if_401(resp.request, resp)
                if retry is not None:
                    resp = retry
            if resp.status_code < 400 or resp.status_code not in self.retry_statuses or attempts >= self.retries:
                if resp.status_code >= 400:
                    raise_for_status(resp.status_code, resp.text)
                return resp
            # backoff and retry
            delay = self.retry_backoff_base * (2 ** attempts) + random.uniform(0, 0.1)
            await asyncio.sleep(delay)
            attempts += 1

    # -------- Endpoints --------
    async def user_get(self) -> User:
        r = await self._request("GET", "/user")
        data = r.json()
        return User(inn=data["inn"], displayName=data["displayName"], id=data.get("id"))

    async def income_create(
        self,
        items: List[IncomeItem],
        operation_time: Optional[str] = None,
        client: Optional[Dict[str, Any]] = None,
        payment_type: str = "CASH",
        ignore_max_total: bool = False,
    ) -> Dict[str, Any]:
        assert items, "Items cannot be empty"
        total = sum((i.amount * i.quantity for i in items), Decimal(0))
        payload = {
            "operationTime": operation_time or utcnow_iso(),
            "requestTime": utcnow_iso(),
            "services": [i.as_payload() for i in items],
            "totalAmount": str(total),
            "client": client or {"incomeType": "FROM_INDIVIDUAL"},
            "paymentType": payment_type,
            "ignoreMaxTotalIncomeRestriction": ignore_max_total,
        }
        r = await self._request("POST", "/income", json=payload)
        return r.json()

    async def income_cancel(
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
        r = await self._request("POST", "/cancel", json=payload)
        return r.json()

    async def receipt_json(self, receipt_uuid: str, inn: str) -> Dict[str, Any]:
        r = await self._request("GET", f"/receipt/{inn}/{receipt_uuid}/json")
        return r.json()

