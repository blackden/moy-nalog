from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict, Any


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_2) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/88.0.4324.192 Safari/537.36"
)


@dataclass
class DeviceInfo:
    sourceType: str = "WEB"
    sourceDeviceId: str = "generated-device-id"
    appVersion: str = "1.0.0"
    userAgent: str = UA

    def json(self) -> Dict[str, Any]:
        return {
            "sourceType": self.sourceType,
            "sourceDeviceId": self.sourceDeviceId,
            "appVersion": self.appVersion,
            "metaDetails": {"userAgent": self.userAgent},
        }


@dataclass
class User:
    inn: str
    displayName: str
    id: Optional[int] = None


@dataclass
class IncomeItem:
    name: str
    amount: Decimal
    quantity: Decimal

    def as_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "amount": str(self.amount),
            "quantity": float(self.quantity),
        }

