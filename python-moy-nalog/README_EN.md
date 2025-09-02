# Unofficial Python Client for "Moy Nalog" (lknpd.nalog.ru)

Sync and async HTTP wrapper for the Russian self‑employed tax app. Supports INN/password and phone (SMS challenge) auth, automatic token refresh, income (create/cancel), receipt JSON, user and taxes basics.

## Features
- Sync `ApiClient` and async `AsyncApiClient` (httpx)
- INN/password and phone SMS challenge flows
- Auto token refresh on 401
- Retries with exponential backoff for 429/5xx
- Endpoints: `/user`, `/income` (create, cancel), `/receipt/*/json`, `/taxes`

## Install
Requires Python 3.9+

```
cd python-moy-nalog
pip install -e .
# dev/test tools
pip install -e .[dev]
```

Logging
- CLI supports `--log-level` and `--log-file`.
- Defaults to stdout; when a file is provided, ensure proper rotation.

## Quick Start (sync)
```python
from decimal import Decimal
from moy_nalog import ApiClient, IncomeItem

with ApiClient() as client:
    token_json = client.create_new_access_token("YOUR_INN", "YOUR_PASSWORD")
    client.authenticate(token_json)
    user = client.user_get()
    print(user)
    items = [IncomeItem(name="Service", amount=Decimal("100.50"), quantity=1)]
    created = client.income_create(items)
    print(created)
```

## Quick Start (async)
```python
import asyncio
from decimal import Decimal
from moy_nalog import AsyncApiClient, IncomeItem

async def main():
    async with AsyncApiClient() as client:
        token_json = await client.create_new_access_token("INN", "PASSWORD")
        client.authenticate(token_json)
        user = await client.user_get()
        items = [IncomeItem(name="Service", amount=Decimal("10.00"), quantity=1)]
        created = await client.income_create(items)
        print(created)

asyncio.run(main())
```

Library logging
- The library logs under logger name `moy_nalog` (requests/responses, retries, token refresh).
- Secrets (Authorization, token, refreshToken, password, code) are redacted automatically.

## Retries & timeouts
- By default up to 2 retries for 429/5xx with exponential backoff.
- Tune via `retries`, `retry_statuses`, `retry_backoff_base`, `timeout`.

## Tests
```
pip install -e .[dev]
pytest -q
```

## Docker & logrotate
Build image:
```
cd python-moy-nalog
docker build -t moy-nalog:local .
```
Run with token persistence:
```
docker run --rm -it \
  -v $HOME/.config/moy-nalog:/root/.config/moy-nalog \
  moy-nalog:local user
```
Logs in Docker:
- Prefer writing to stdout (default), Docker manages logs.
- If using `--log-file /logs/app.log`, mount a volume and set up logrotate on the host, e.g. `/etc/logrotate.d/moy-nalog`:
```
/var/log/moy-nalog/*.log {
  daily
  rotate 7
  compress
  missingok
  copytruncate
}
```

## What is pyproject.toml?
PEP 518/621 configuration for project metadata and build settings:
- package name/version/description, Python requirements
- runtime and optional dev dependencies
- build backend (setuptools)
- classifiers and links
