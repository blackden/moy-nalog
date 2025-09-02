from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal

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
    created = client.income_create([item], payment_type=PAYMENT_TYPE_CASH)
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
    res = client.income_cancel(args.uuid, comment)
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="moy-nalog", description="CLI for lknpd.nalog.ru API")
    p.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout, seconds")
    p.add_argument("--token-file", help="Path to token.json (default XDG config)")

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
    sp.set_defaults(func=cmd_create_income)

    sp = sub.add_parser("cancel-income", help="Cancel income by receipt UUID")
    sp.add_argument("--uuid", required=True)
    sp.add_argument("--refund", action="store_true", help="Use refund comment instead of mistake")
    sp.set_defaults(func=cmd_cancel_income)

    sp = sub.add_parser("receipt-json", help="Get receipt JSON by UUID and INN")
    sp.add_argument("--uuid", required=True)
    sp.add_argument("--inn", required=True)
    sp.set_defaults(func=cmd_receipt_json)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

