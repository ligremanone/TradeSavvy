import asyncio

from pandas import DataFrame

from app.client import client


async def get_figi_by_ticker(ticker: str) -> str:
    await client.init()
    x = DataFrame(
        (await client.get_all_shares()).instruments,
        columns=["figi", "ticker", "name", "class_code"],
    )
    return x[x["ticker"] == ticker].figi


if __name__ == "__main__":
    tkr = input("Введите тикер: ")
    print(asyncio.run(get_figi_by_ticker(tkr)))
