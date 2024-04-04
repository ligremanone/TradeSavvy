from pathlib import Path
from typing import Optional

from tinkoff.invest import Client, AsyncClient
from tinkoff.invest.async_services import AsyncServices
from tinkoff.invest.caching.market_data_cache.cache import MarketDataCache
from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX, INVEST_GRPC_API
from tinkoff.invest.caching.market_data_cache.cache_settings import (
    MarketDataCacheSettings,
)
from tinkoff.invest.services import Services

from app.config import settings


class TinkoffClient:
    def __init__(self, token: str, sandbox: bool):
        self.token = token
        self.sandbox = sandbox
        self.client: Optional[AsyncServices] = None
        self.sync_client: Optional[Services] = None
        self.market_data_cache: Optional[MarketDataCache] = None
        if settings.sandbox:
            self.target = INVEST_GRPC_API_SANDBOX
        else:
            self.target = INVEST_GRPC_API

    async def init(self):
        self.client = await AsyncClient(
            token=self.token, target=self.target, app_name=settings.app_name
        ).__aenter__()
        if settings.use_candle_history_cache:
            self.sync_client = Client(token=self.token, target=self.target).__enter__()
            self.market_data_cache = MarketDataCache(
                settings=MarketDataCacheSettings(
                    base_cache_dir=Path("market_data_cache")
                ),
                services=self.sync_client,
            )

    async def get_orders(self, **kwargs):
        if self.sandbox:
            return await self.client.sandbox.get_sandbox_orders(**kwargs)
        return await self.client.orders.get_orders(**kwargs)

    async def get_portfolio(self, **kwargs):
        if self.sandbox:
            return await self.client.sandbox.get_sandbox_portfolio(**kwargs)
        return await self.client.operations.get_portfolio(**kwargs)

    async def get_accounts(self):
        if self.sandbox:
            return await self.client.sandbox.get_sandbox_accounts()
        return await self.client.users.get_accounts()

    async def get_all_candles(self, **kwargs):
        if settings.use_candle_history_cache:
            for candle in self.market_data_cache.get_all_candles(**kwargs):
                yield candle
        else:
            async for candle in self.client.get_all_candles(**kwargs):
                yield candle

    async def get_last_prices(self, **kwargs):
        return await self.client.market_data.get_last_prices(**kwargs)

    async def post_order(self, **kwargs):
        if self.sandbox:
            return await self.client.sandbox.post_sandbox_order(**kwargs)
        return await self.client.orders.post_order(**kwargs)

    async def get_order_state(self, **kwargs):
        if self.sandbox:
            return await self.client.sandbox.get_sandbox_order_state(**kwargs)
        return await self.client.orders.get_order_state(**kwargs)

    async def get_trading_status(self, **kwargs):
        return await self.client.market_data.get_trading_status(**kwargs)

    async def get_instrument(self, **kwargs):
        return await self.client.instruments.get_instrument_by(**kwargs)

    async def get_all_shares(self, **kwargs):
        return await self.client.instruments.shares(**kwargs)

    async def get_ticker(self, **kwargs):
        return (await self.client.instruments.share_by(**kwargs)).instrument.ticker

    async def sandbox_pay_in(self, **kwargs):
        return await self.client.sandbox.sandbox_pay_in(**kwargs)

    async def get_sandbox_withdraw_limits(self, **kwargs):
        return await self.client.sandbox.get_sandbox_withdraw_limits(**kwargs)


client = TinkoffClient(settings.token, settings.sandbox)
