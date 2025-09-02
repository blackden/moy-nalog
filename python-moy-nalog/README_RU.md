# Неофициальный Python‑клиент для «Мой Налог» (lknpd.nalog.ru)

Этот пакет предоставляет удобную синхронную и асинхронную обёртку над API сервиса «Мой Налог» для самозанятых. Поддерживает аутентификацию (ИНН/пароль и по телефону), автоматическое обновление access‑token по refresh‑token, работу с чеками (создание, отмена, получение), а также базовые эндпоинты пользователя и налогов.

## Возможности
- Синхронный `ApiClient` и асинхронный `AsyncApiClient` (httpx)
- Логин по ИНН/паролю и по телефону (SMS‑challenge)
- Авто‑рефреш токена при 401
- Ретраи с экспоненциальной паузой для 429/5xx
- Эндпоинты: `/user`, `/income` (create, cancel), `/receipt/*/json`, `/taxes`

## Установка
Требуется Python 3.9+

```
cd python-moy-nalog
pip install -e .
# опционально для разработки/тестов
pip install -e .[dev]
```

Логи
- CLI поддерживает ключи `--log-level` и `--log-file`.
- По умолчанию пишет в stdout; при указании файла — в него (убедитесь, что настроен rotation).

## Быстрый старт (sync)
```python
from decimal import Decimal
from moy_nalog import ApiClient, IncomeItem, constants

with ApiClient() as client:
    token_json = client.create_new_access_token("ВАШ_ИНН", "ВАШ_ПАРОЛЬ")
    client.authenticate(token_json)

    user = client.user_get()
    print("Пользователь:", user.inn, user.displayName)

    items = [IncomeItem(name="Услуга", amount=Decimal("100.50"), quantity=1)]
    created = client.income_create(items, payment_type=constants.PAYMENT_TYPE_CASH)
    print("Чек создан:", created)
```

## Быстрый старт (async)
```python
import asyncio
from decimal import Decimal
from moy_nalog import AsyncApiClient, IncomeItem

async def main():
    async with AsyncApiClient() as client:
        token_json = await client.create_new_access_token("ИНН", "ПАРОЛЬ")
        client.authenticate(token_json)

        user = await client.user_get()
        print(user)

        items = [IncomeItem(name="Услуга", amount=Decimal("10.00"), quantity=1)]
        created = await client.income_create(items)
        print(created)

asyncio.run(main())
```

Логирование в коде
- Библиотека логирует события под именем логгера `moy_nalog` (запросы/ответы, ретраи, обновление токена).
- Секреты (Authorization, token, refreshToken, password, code) не логируются — автоматически редактируются.

## Отмена чека
```python
from moy_nalog import ApiClient, constants

client = ApiClient()
client.authenticate('{"token":"...","refreshToken":"..."}')
info = client.income_cancel(
    receipt_uuid="uuid",
    comment=constants.CANCEL_COMMENT_REFUND,
)
print(info)
```

## Ретраи и таймауты
- По умолчанию клиент делает до 2 повторов при ответах 429/5xx, с экспоненциальной задержкой.
- Поведение настраивается параметрами `retries`, `retry_statuses`, `retry_backoff_base`, `timeout` конструктора.

## Тесты
```
pip install -e .[dev]
pytest -q
```

## Docker и логротэйт
Собрать образ:
```
cd python-moy-nalog
docker build -t moy-nalog:local .
```
Запуск с сохранением токена:
```
docker run --rm -it \
  -v $HOME/.config/moy-nalog:/root/.config/moy-nalog \
  moy-nalog:local user
```
Логи в Docker:
- Рекомендуется писать в stdout (по умолчанию), Docker управляет логами.
- Если используете `--log-file /logs/app.log`, примонтируйте volume и настройте logrotate на хосте, например `/etc/logrotate.d/moy-nalog`:
```
/var/log/moy-nalog/*.log {
  daily
  rotate 7
  compress
  missingok
  copytruncate
}
```

## Что такое pyproject.toml
Файл конфигурации сборки и метаданных проекта (PEP 518/621). В нём описаны:
- имя, версия, описание пакета
- зависимости (runtime и dev через optional‑dependencies)
- поддерживаемая версия Python
- используемая система сборки (`setuptools`)
- классификаторы и ссылки

## Заметки
Сервис I/O‑bound: основная латентность в сети. Чтобы повысить надёжность и скорость интеграции:
- объединяйте запросы (несколько позиций чека — одним вызовом)
- используйте `AsyncApiClient` при множестве параллельных операций
- оставляйте клиент «живым» (keep‑alive), не создавайте на каждый запрос новый
- задавайте разумные таймауты и ретраи

Подробнее — см. `NOTES_RU.md`.
