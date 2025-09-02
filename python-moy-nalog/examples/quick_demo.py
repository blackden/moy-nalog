from decimal import Decimal
import os

from moy_nalog.client import ApiClient
from moy_nalog.models import IncomeItem


def main():
    inn = os.getenv("NALOG_INN")
    pwd = os.getenv("NALOG_PASSWORD")
    if not inn or not pwd:
        print("Set NALOG_INN and NALOG_PASSWORD env vars to run this demo")
        return

    client = ApiClient()

    token_json = client.create_new_access_token(inn, pwd)
    client.authenticate(token_json)

    user = client.user_get()
    print("User:", user)

    items = [IncomeItem(name="Service A", amount=Decimal("100.50"), quantity=1)]
    created = client.income_create(items)
    print("Income created:", created)


if __name__ == "__main__":
    main()

