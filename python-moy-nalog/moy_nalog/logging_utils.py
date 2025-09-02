import json
import logging
import os
from typing import Any, Dict, Mapping


LOGGER_NAME = "moy_nalog"


def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    # Library code should not configure handlers; leave to application/CLI.
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


SENSITIVE_KEYS = {"authorization", "token", "refreshtoken", "password", "code"}


def redact_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    def _redact(key: str, value: Any) -> Any:
        if key.lower() in SENSITIVE_KEYS:
            return "***REDACTED***"
        return value

    return {k: _redact(k, v) for k, v in mapping.items()}


def redact_headers(headers: Mapping[str, str]) -> Dict[str, str]:
    return {k: ("***REDACTED***" if k.lower() in SENSITIVE_KEYS else v) for k, v in headers.items()}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }
        if hasattr(record, "method"):
            payload["method"] = getattr(record, "method")
        if hasattr(record, "url"):
            payload["url"] = getattr(record, "url")
        if hasattr(record, "status"):
            payload["status"] = getattr(record, "status")
        if hasattr(record, "attempt"):
            payload["attempt"] = getattr(record, "attempt")
        if hasattr(record, "delay"):
            payload["delay"] = getattr(record, "delay")
        if hasattr(record, "elapsed_ms"):
            payload["elapsed_ms"] = getattr(record, "elapsed_ms")
        return json.dumps(payload, ensure_ascii=False)


def http_debug_enabled() -> bool:
    return os.getenv("MOYNALOG_HTTP_DEBUG", "").lower() in ("1", "true", "yes")
