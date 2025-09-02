# Инструкция по использованию (текущая версия)

Эта версия ориентирована на личную автоматизацию: посмотреть профиль, создать/отменить чек, получить JSON чека. Есть CLI `moy-nalog`, сохраняющая токен аутентификации в файл.

## 1. Установка локально
```
cd python-moy-nalog
pip install -e .
```
Появится команда `moy-nalog`.

## 2. Аутентификация и хранение токена
- Выполните логин, токен сохранится в `~/.config/moy-nalog/token.json` (или путь из `--token-file`).
```
moy-nalog login --inn 7700000000 --password 'YOUR_PASSWORD'
```
- Файл хранит JSON с `token` и `refreshToken`. Для домашней автоматизации отдельная БД (Redis/Postgres) не нужна. Достаточно файла с правами доступа только для вашего пользователя (CLI выставляет ограниченные права по умолчанию). Если делаете многопользовательский сервис — тогда уже можно думать о БД/секрет‑хранилище.

## 3. Посмотреть профиль пользователя
```
moy-nalog user
```
Ответ будет в JSON, например `{ "inn": "...", "displayName": "..." }`.

## 4. Создать чек (одна позиция)
```
moy-nalog create-income \
  --name "Консультация" \
  --amount 100.50 \
  --quantity 1
```
Ответ вернёт JSON с `approvedReceiptUuid`.

## 4.1. Создать чек с несколькими позициями
Вариант A — повторяйте `--item name,amount,quantity`:
```
moy-nalog create-income-multi \
  --item "Услуга A,100.00,1" \
  --item "Услуга B,50.50,2"
```
Вариант B — из JSON‑файла:
```
cat items.json
[
  {"name": "Услуга A", "amount": 100.0, "quantity": 1},
  {"name": "Услуга B", "amount": 50.5, "quantity": 2}
]
moy-nalog create-income-multi --items-file items.json
```

Дополнительно можно задать время операции:
```
# Явная дата/время в ISO (с часовым поясом)
moy-nalog create-income-multi --items-file items.json --operation-time "2025-01-31T12:00:00+03:00"

# Или без пояса + указать таймзону (будет проставлена)
moy-nalog create-income-multi --items-file items.json --operation-time "2025-01-31T12:00:00" --timezone Europe/Moscow
```

## 5. Отменить чек
```
# По умолчанию причина: "Чек сформирован ошибочно"
moy-nalog cancel-income --uuid <RECEIPT_UUID>

# Либо как возврат средств
moy-nalog cancel-income --uuid <RECEIPT_UUID> --refund
```

## 6. Получить JSON чека
```
moy-nalog receipt-json --uuid <RECEIPT_UUID> --inn <ВАШ_ИНН>
```

## 6.1. Получить ссылку для печати чека
```
moy-nalog receipt-print-url --uuid <RECEIPT_UUID> --inn <ВАШ_ИНН>
```

## 6.2. Логин по номеру телефона
Шаг 1 — запросить SMS и получить `challengeToken`:
```
moy-nalog phone-start --phone 79000000000 --challenge-file /tmp/challenge.txt
```
Шаг 2 — подтвердить код из SMS и сохранить токен:
```
moy-nalog phone-verify --phone 79000000000 --code 123456 --challenge-file /tmp/challenge.txt
```

## 7. Запуск в Docker
Собрать образ:
```
cd python-moy-nalog
docker build -t moy-nalog:local .
```
Логин (токен сохраняется в volume каталоге):
```
docker run --rm -it \
  -v $HOME/.config/moy-nalog:/root/.config/moy-nalog \
  moy-nalog:local login --inn 7700000000 --password 'YOUR_PASSWORD'
```
Проверить пользователя:
```
docker run --rm -it \
  -v $HOME/.config/moy-nalog:/root/.config/moy-nalog \
  moy-nalog:local user
```
Создать чек:
```
docker run --rm -it \
  -v $HOME/.config/moy-nalog:/root/.config/moy-nalog \
  moy-nalog:local create-income --name "Консультация" --amount 100.50 --quantity 1
```

## 8. Замечания
- Клиент делает до 2 ретраев при 429/5xx и пытается обновить токен при 401.
- По умолчанию время операции указывается текущим моментом в UTC. Если нужно своё время/часовой пояс — можем добавить ключи для явной даты в CLI (скажите — добавлю).
- При ошибках сервис может возвращать русские сообщения, они будут выводиться в stderr.

## 9. Что дальше (рекомендации)
- Добавить команды phone‑flow (логин по номеру и коду из SMS).
- Поддержать создание чеков с несколькими позициями.
- Команду печати/ссылки на чек.
