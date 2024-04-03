from tinkoff.invest import Client
from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX

from app.config import settings


def get_all_accounts():
    with Client(settings.token, target=INVEST_GRPC_API_SANDBOX) as client:
        return client.users.get_accounts().accounts


def get_account_id():
    with Client(settings.token, target=INVEST_GRPC_API_SANDBOX) as client:
        if not client.users.get_accounts().accounts:
            return client.sandbox.open_sandbox_account()


if __name__ == "__main__":
    get_account_id()
    accounts = get_all_accounts()
    for account in accounts:
        print(f'id: {account.id} {account.name if account.name else ""}')
