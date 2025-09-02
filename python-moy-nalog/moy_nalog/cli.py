from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from datetime import datetime
from pathlib import Path
import logging
import os
from typing import Optional
from moy_nalog.logging_utils import JsonFormatter
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from .client import ApiClient
from .models import IncomeItem
from .token_store import TokenStore
from .constants import (
    PAYMENT_TYPE_CASH,
    CANCEL_COMMENT_CANCEL,
    CANCEL_COMMENT_REFUND,
)


def _get_client(args) -> ApiClient:
    return ApiClient(timeout=args.timeout)


def _load_token(args) -> str | None:
    store = TokenStore(path=args.token_file) if args.token_file else TokenStore()
    return store.load()


def _save_token(args, token_json: str) -> None:
    store = TokenStore(path=args.token_file) if args.token_file else TokenStore()
    store.save(token_json)


def cmd_login(args) -> int:
    client = _get_client(args)
    token_json = client.create_new_access_token(args.inn, args.password)
    _save_token(args, token_json)
    print("Token saved.")
    return 0


def cmd_user(args) -> int:
    client = _get_client(args)
    token = _load_token(args)
    if not token:
        print("No token found. Run: moy-nalog login --inn ... --password ...", file=sys.stderr)
        return 2
    client.authenticate(token)
    user = client.user_get()
    print(json.dumps({"inn": user.inn, "displayName": user.displayName, "id": user.id}, ensure_ascii=False))
    return 0


def cmd_create_income(args) -> int:
    client = _get_client(args)
    token = _load_token(args)
    if not token:
        print("No token found. Run: moy-nalog login --inn ... --password ...", file=sys.stderr)
        return 2
    client.authenticate(token)
    item = IncomeItem(name=args.name, amount=Decimal(args.amount), quantity=Decimal(args.quantity))
    op_time = _compose_operation_time(args)
    created = client.income_create([item], payment_type=PAYMENT_TYPE_CASH, operation_time=op_time)
    print(json.dumps(created, ensure_ascii=False))
    return 0


def _parse_items_from_args(args) -> list[IncomeItem]:
    items: list[IncomeItem] = []
    if args.items_file:
        data = json.loads(Path(args.items_file).read_text(encoding="utf-8"))
        for it in data:
            items.append(IncomeItem(name=it["name"], amount=Decimal(str(it["amount"])), quantity=Decimal(str(it["quantity"])) ))
    for s in (args.item or []):
        # format: name,amount,quantity
        parts = [p.strip() for p in s.split(",")]
        if len(parts) != 3:
            raise ValueError("--item must be 'name,amount,quantity'")
        items.append(IncomeItem(name=parts[0], amount=Decimal(parts[1]), quantity=Decimal(parts[2])))
    if not items:
        raise ValueError("No items provided. Use --item or --items-file")
    return items


def cmd_create_income_multi(args) -> int:
    client = _get_client(args)
    token = _load_token(args)
    if not token:
        print("No token found. Run: moy-nalog login --inn ... --password ...", file=sys.stderr)
        return 2
    client.authenticate(token)
    items = _parse_items_from_args(args)
    op_time = _compose_operation_time(args)
    created = client.income_create(items, payment_type=PAYMENT_TYPE_CASH, operation_time=op_time)
    print(json.dumps(created, ensure_ascii=False))
    return 0


def cmd_cancel_income(args) -> int:
    client = _get_client(args)
    token = _load_token(args)
    if not token:
        print("No token found. Run: moy-nalog login --inn ... --password ...", file=sys.stderr)
        return 2
    client.authenticate(token)
    comment = CANCEL_COMMENT_REFUND if args.refund else CANCEL_COMMENT_CANCEL
    op_time = _compose_operation_time(args)
    res = client.income_cancel(args.uuid, comment, operation_time_iso=op_time)
    print(json.dumps(res, ensure_ascii=False))
    return 0


def cmd_receipt_json(args) -> int:
    client = _get_client(args)
    token = _load_token(args)
    if not token:
        print("No token found. Run: moy-nalog login --inn ... --password ...", file=sys.stderr)
        return 2
    client.authenticate(token)
    res = client.receipt_json(args.uuid, args.inn)
    print(json.dumps(res, ensure_ascii=False))
    return 0


def cmd_receipt_print_url(args) -> int:
    client = _get_client(args)
    token = _load_token(args)
    if not token:
        print("No token found. Run: moy-nalog login --inn ... --password ...", file=sys.stderr)
        return 2
    client.authenticate(token)
    url = client.receipt_print_url(args.uuid, args.inn)
    print(url)
    return 0


def cmd_phone_start(args) -> int:
    client = _get_client(args)
    res = client.create_phone_challenge(args.phone)
    print(json.dumps(res, ensure_ascii=False))
    if args.challenge_file:
        Path(args.challenge_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.challenge_file).write_text(res.get("challengeToken", ""), encoding="utf-8")
    return 0


def cmd_phone_verify(args) -> int:
    client = _get_client(args)
    challenge = args.challenge_token
    if not challenge and args.challenge_file:
        try:
            challenge = Path(args.challenge_file).read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            pass
    if not challenge:
        print("challenge token required: --challenge-token or --challenge-file", file=sys.stderr)
        return 2
    token_json = client.create_new_access_token_by_phone(args.phone, challenge, args.code)
    _save_token(args, token_json)
    print("Token saved.")
    return 0


def _compose_operation_time(args) -> str | None:
    if not getattr(args, "operation_time", None):
        return None
    ts = args.operation_time
    # if timezone provided and ts has no offset, attach
    if getattr(args, "timezone", None) and ZoneInfo is not None:
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            print("Invalid --operation-time format, expected ISO-8601", file=sys.stderr)
            return ts
        if dt.tzinfo is None:
            try:
                dt = dt.replace(tzinfo=ZoneInfo(args.timezone))
            except Exception:
                print("Invalid --timezone name", file=sys.stderr)
                return dt.isoformat()
        return dt.isoformat()
    return ts


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="moy-nalog", description="CLI for lknpd.nalog.ru API")
    p.add_argument("--timeout", type=float, default=float(os.getenv("MOYNALOG_TIMEOUT", 15)), help="HTTP timeout, seconds")
    p.add_argument("--token-file", default=os.getenv("MOYNALOG_TOKEN_FILE"), help="Path to token.json (default XDG config)")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("login", help="Login with INN and password and save token")
    sp.add_argument("--inn", required=True, help="INN (username)")
    sp.add_argument("--password", required=True, help="Password")
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("user", help="Show current user info")
    sp.set_defaults(func=cmd_user)

    sp = sub.add_parser("create-income", help="Create a single-item income")
    sp.add_argument("--name", required=True)
    sp.add_argument("--amount", required=True, help="Amount, e.g. 100.50")
    sp.add_argument("--quantity", default="1", help="Quantity, default 1")
    sp.add_argument("--operation-time", help="ISO datetime (attach --timezone if naive)")
    sp.add_argument("--timezone", help="IANA timezone, e.g. Europe/Moscow")
    sp.set_defaults(func=cmd_create_income)

    sp = sub.add_parser("create-income-multi", help="Create an income with multiple items")
    sp.add_argument("--item", action="append", help="Item as 'name,amount,quantity' (repeatable)")
    sp.add_argument("--items-file", help="JSON file with [{name,amount,quantity}, ...]")
    sp.add_argument("--operation-time", help="ISO datetime (attach --timezone if naive)")
    sp.add_argument("--timezone", help="IANA timezone, e.g. Europe/Moscow")
    sp.set_defaults(func=cmd_create_income_multi)

    sp = sub.add_parser("cancel-income", help="Cancel income by receipt UUID")
    sp.add_argument("--uuid", required=True)
    sp.add_argument("--refund", action="store_true", help="Use refund comment instead of mistake")
    sp.add_argument("--operation-time", help="ISO datetime (attach --timezone if naive)")
    sp.add_argument("--timezone", help="IANA timezone, e.g. Europe/Moscow")
    sp.set_defaults(func=cmd_cancel_income)

    sp = sub.add_parser("receipt-json", help="Get receipt JSON by UUID and INN")
    sp.add_argument("--uuid", required=True)
    sp.add_argument("--inn", required=True)
    sp.set_defaults(func=cmd_receipt_json)

    sp = sub.add_parser("receipt-print-url", help="Get receipt print URL by UUID and INN")
    sp.add_argument("--uuid", required=True)
    sp.add_argument("--inn", required=True)
    sp.set_defaults(func=cmd_receipt_print_url)

    sp = sub.add_parser("phone-start", help="Start phone challenge (request SMS)")
    sp.add_argument("--phone", required=True)
    sp.add_argument("--challenge-file", help="Path to save challengeToken")
    sp.set_defaults(func=cmd_phone_start)

    sp = sub.add_parser("phone-verify", help="Verify SMS code and save access token")
    sp.add_argument("--phone", required=True)
    sp.add_argument("--code", required=True)
    sp.add_argument("--challenge-token", help="Challenge token string")
    sp.add_argument("--challenge-file", help="Read challenge token from file")
    sp.set_defaults(func=cmd_phone_verify)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    # Global logging options for CLI
    parser.add_argument("--log-level", default=os.getenv("MOYNALOG_LOG_LEVEL", "INFO"), help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--log-file", default=os.getenv("MOYNALOG_LOG_FILE"), help="Log file path (stdout if omitted)")
    parser.add_argument("--log-format", choices=["text", "json"], default=os.getenv("MOYNALOG_LOG_FORMAT", "text"), help="Log format")
    parser.add_argument("--log-http-debug", action="store_true", default=os.getenv("MOYNALOG_HTTP_DEBUG", "").lower() in ("1","true","yes"), help="Log HTTP headers (redacted)")
    args = parser.parse_args(argv)
    level = getattr(logging, str(args.log_level).upper(), logging.INFO)
    handlers: list[logging.Handler] = []
    if args.log_file:
        h: logging.Handler = logging.FileHandler(args.log_file)
    else:
        h = logging.StreamHandler()
    if args.log_format == "json":
        h.setFormatter(JsonFormatter())
    else:
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [h]

    # Propagate HTTP debug preference to library via env
    if args.log_http_debug:
        os.environ["MOYNALOG_HTTP_DEBUG"] = "1"
    try:
        return args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
