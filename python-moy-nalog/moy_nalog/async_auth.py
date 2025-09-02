from __future__ import annotations

from typing import Optional, Dict, Any

import httpx

from .models import DeviceInfo


class AsyncAuth:
    def __init__(self, client: httpx.AsyncClient, device: DeviceInfo):
        self._client = client
        self._device = device
        self._token: Optional[Dict[str, Any]] = None

    def set_token(self, token_json: str) -> None:
        import json

        self._token = json.loads(token_json) if token_json else None

    def auth_header(self) -> Dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token.get('token', '')}"}

    async def refresh_if_401(self, req: httpx.Request, resp: httpx.Response) -> Optional[httpx.Response]:
        if resp.status_code != 401 or not self._token:
            return None
        refresh = self._token.get("refreshToken")
        if not refresh:
            return None

        r = await self._client.post(
            "/auth/token",
            json={
                "deviceInfo": self._device.json(),
                "refreshToken": refresh,
            },
            headers={"Referrer": "https://lknpd.nalog.ru/auth/login"},
        )
        if r.status_code != 200:
            return None

        self.set_token(r.text)
        headers = dict(req.headers)
        headers.update(self.auth_header())
        return await self._client.request(req.method, req.url, headers=headers, content=req.content)

