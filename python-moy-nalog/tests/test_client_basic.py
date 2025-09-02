from decimal import Decimal
from unittest.mock import Mock

import httpx

from moy_nalog.client import ApiClient
from moy_nalog.models import IncomeItem
from moy_nalog.constants import CANCEL_COMMENT_CANCEL


class MockTransport(httpx.BaseTransport):
    def __init__(self, responders):
        self._responders = responders

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        key = (request.method, str(request.url))
        if key not in self._responders:
            return httpx.Response(404, text="Not Found")
        status, data, headers = self._responders[key]
        return httpx.Response(status, json=data if isinstance(data, dict) else None, text=None if isinstance(data, dict) else data, headers=headers)


def build_client(responders):
    transport = MockTransport(responders)
    client = httpx.Client(base_url="https://lknpd.nalog.ru/api/v1", transport=transport)
    return ApiClient(client=client)


def test_login_and_user():
    responders = {
        ("POST", "https://lknpd.nalog.ru/api/v1/auth/lkfl"): (200, '{"token":"t","refreshToken":"r"}', {}),
        ("GET", "https://lknpd.nalog.ru/api/v1/user"): (200, {"inn": "1234567890", "displayName": "Test", "id": 1}, {"Content-Type": "application/json"}),
    }
    api = build_client(responders)
    token = api.create_new_access_token("u", "p")
    api.authenticate(token)
    user = api.user_get()
    assert user.inn == "1234567890"


def test_income_create():
    responders = {
        ("GET", "https://lknpd.nalog.ru/api/v1/user"): (200, {"inn": "1234567890", "displayName": "Test"}, {"Content-Type": "application/json"}),
        ("POST", "https://lknpd.nalog.ru/api/v1/income"): (200, {"approvedReceiptUuid": "uuid"}, {"Content-Type": "application/json"}),
    }
    api = build_client(responders)
    api.authenticate('{"token":"t","refreshToken":"r"}')
    items = [IncomeItem(name="A", amount=Decimal("10.00"), quantity=1)]
    res = api.income_create(items)
    assert res.get("approvedReceiptUuid") == "uuid"


def test_income_cancel_with_retry():
    # First attempt 503, then 200
    class FlipTransport(httpx.BaseTransport):
        def __init__(self):
            self.count = 0

        def handle_request(self, request: httpx.Request) -> httpx.Response:
            self.count += 1
            if self.count == 1 and request.method == "POST" and request.url.path.endswith("/cancel"):
                return httpx.Response(503, text="Service Unavailable")
            if request.method == "POST" and request.url.path.endswith("/cancel"):
                return httpx.Response(200, json={"status": "OK"}, headers={"Content-Type": "application/json"})
            return httpx.Response(404, text="Not Found")

    transport = FlipTransport()
    client = httpx.Client(base_url="https://lknpd.nalog.ru/api/v1", transport=transport)
    api = ApiClient(client=client, retries=2, retry_backoff_base=0)
    api.authenticate('{"token":"t","refreshToken":"r"}')
    res = api.income_cancel("uuid", CANCEL_COMMENT_CANCEL)
    assert res.get("status") == "OK"
