from __future__ import annotations

import httpx
from typing import Optional, Dict, Any

from .models import DeviceInfo
from .logging_utils import get_logger


class Auth:
    def __init__(self, client: httpx.Client, device: DeviceInfo):
        self._client = client
        self._device = device
        self._token: Optional[Dict[str, Any]] = None
        self._log = get_logger()

    def set_token(self, token_json: str) -> None:
        import json

        self._token = json.loads(token_json) if token_json else None
        self._log.debug("token set (redacted)")

    def auth_header(self) -> Dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token.get('token', '')}"}

    def refresh_if_401(self, req: httpx.Request, resp: httpx.Response) -> Optional[httpx.Response]:
        if resp.status_code != 401 or not self._token:
            return None
        refresh = self._token.get("refreshToken")
        if not refresh:
            return None

        self._log.info("401 received, attempting token refresh")
        r = self._client.post(
            "/auth/token",
            json={
                "deviceInfo": self._device.json(),
                "refreshToken": refresh,
            },
            headers={"Referrer": "https://lknpd.nalog.ru/auth/login"},
        )
        if r.status_code != 200:
            self._log.warning("token refresh failed: status=%s", r.status_code)
            return None

        self.set_token(r.text)
        self._log.info("token refreshed successfully, retrying request")
        # retry original request
        headers = dict(req.headers)
        headers.update(self.auth_header())
        return self._client.request(req.method, req.url, headers=headers, content=req.content)
