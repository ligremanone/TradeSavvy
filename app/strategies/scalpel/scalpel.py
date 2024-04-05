import asyncio
import logging
from datetime import timedelta
from typing import Optional
from uuid import uuid4
import datetime
from pandas import DataFrame
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice
from tinkoff.invest import CandleInterval, Instrument, AioRequestError
from tinkoff.invest.grpc.instruments_pb2 import INSTRUMENT_ID_TYPE_FIGI
from tinkoff.invest.grpc.orders_pb2 import (
    ORDER_DIRECTION_SELL,
    ORDER_TYPE_MARKET,
    ORDER_DIRECTION_BUY,
)
from tinkoff.invest.utils import now

from app.client import client
from app.config import settings
from app.stats.handler import StatsHandler
from app.strategies.base import BaseStrategy
from app.strategies.models import StrategyName
from app.strategies.scalpel.models import ScalpelStrategyConfig
from app.utils.portfolio import get_position, get_order
from app.utils.quantity import is_quantity_valid
from app.utils.quotation import quotation_to_float

logger = logging.getLogger(__name__)


class ScalpelStrategy(BaseStrategy):
    def __init__(self, figi: str = None, backcandles: int = 15, *args, **kwargs):
        self.account_id = settings.account_id
        self.figi = figi
        self.stats_handler = StatsHandler(StrategyName.SCALPEL, client)
        self.config: ScalpelStrategyConfig = ScalpelStrategyConfig(**kwargs)
        self.backcandles = backcandles
        self.instrument_info: Optional[Instrument, None] = None

    async def get_historical_data(self):
        candles = []
        logger.info(
            f"Start getting historical data for {self.config.days_back_to_consider} days back from now. "
            f"figi={self.figi}"
        )
        async for candle in client.get_all_candles(
            figi=self.figi,
            from_=now() - timedelta(days=self.config.days_back_to_consider),
            to=now(),
            interval=CandleInterval.CANDLE_INTERVAL_5_MIN,
        ):
            candles.append(candle)
        logger.info(f"Found {len(candles)} candles. figi={self.figi}")
        return candles

    async def create_df(self):
        candles = await self.get_historical_data()
        if len(candles) == 0:
            logger.debug(f"No candles found for {self.figi}")
            return
        df = DataFrame(
            [
                {
                    "Time": i.time,
                    "Open": quotation_to_float(i.open),
                    "High": quotation_to_float(i.high),
                    "Low": quotation_to_float(i.low),
                    "Close": quotation_to_float(i.close),
                    "Volume": i.volume,
                }
                for i in candles
            ]
        )
        df = df[df.High != df.Low]
        logger.info(f"DataFrame created for {self.figi}")
        return df

    async def add_indicators(self):
        df = await self.create_df()
        bbands = BollingerBands(close=df["Close"], window=14, window_dev=2)
        df = df.join(
            [
                bbands.bollinger_hband_indicator(),
                bbands.bollinger_lband_indicator(),
            ]
        )
        df["VWAP"] = VolumeWeightedAveragePrice(
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            volume=df["Volume"],
            window=7,
        ).volume_weighted_average_price()
        df["RSI"] = RSIIndicator(close=df["Close"], window=16).rsi()
        df["ATR"] = AverageTrueRange(
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            window=16,
        ).average_true_range()
        df["EMA_slow"] = EMAIndicator(close=df["Close"], window=50).ema_indicator()
        df["EMA_fast"] = EMAIndicator(close=df["Close"], window=30).ema_indicator()
        return df

    async def add_signal(self, df: DataFrame):
        above = df["EMA_fast"] > df["EMA_slow"]
        below = df["EMA_fast"] < df["EMA_slow"]
        above_all = (
            above.rolling(window=self.backcandles)
            .apply(lambda x: x.all(), raw=True)
            .fillna(0)
            .astype(bool)
        )
        below_all = (
            below.rolling(window=self.backcandles)
            .apply(lambda x: x.all(), raw=True)
            .fillna(0)
            .astype(bool)
        )
        df["EMASignal"] = 0
        df.loc[above_all, "EMASignal"] = 2
        df.loc[below_all, "EMASignal"] = 1
        # df.reset_index(inplace=True, drop=True)
        condition_buy = (df["EMASignal"] == 2) & (df["bbilband"])
        condition_sell = (df["EMASignal"] == 1) & (df["bbihband"])
        df["TotalSignal"] = 0
        df.loc[condition_buy, "TotalSignal"] = 2
        df.loc[condition_sell, "TotalSignal"] = 1
        return df

    async def get_position_quantity(self):
        positions = (await client.get_portfolio(account_id=self.account_id)).positions
        position = get_position(positions, self.figi)
        if position is None:
            return 0
        return int(quotation_to_float(position.quantity))

    async def sell_order(self, last_price: float):
        position_quantity = await self.get_position_quantity()
        if position_quantity > 0:
            logger.info(
                f"Selling {position_quantity} shares. Last price={last_price} figi={self.figi}"
            )
            try:
                quantity = position_quantity / self.instrument_info.lot
                if not is_quantity_valid(quantity):
                    raise ValueError(
                        f"Invalid quantity for posting an order. quantity={quantity}"
                    )
                posted_order = await client.post_order(
                    order_id=str(uuid4()),
                    direction=ORDER_DIRECTION_SELL,
                    quantity=int(quantity),
                    order_type=ORDER_TYPE_MARKET,
                    account_id=self.account_id,
                    instrument_id=self.figi,
                )
            except Exception as e:
                logger.error(f"Failed to post sell order. figi={self.figi}. error={e}")
                return
            await asyncio.create_task(
                self.stats_handler.handle_new_order(
                    order_id=posted_order.order_id, account_id=self.account_id
                )
            )

    async def buy_order(self, last_price: float):
        position_quantity = await self.get_position_quantity()
        if position_quantity < self.config.quantity_limit:
            quantity_to_by = self.config.quantity_limit - position_quantity
            logger.info(
                f"Buying {quantity_to_by} shares. Last price={last_price} figi={self.figi}"
            )
            try:
                quantity = quantity_to_by / self.instrument_info.lot
                if not is_quantity_valid(quantity):
                    raise ValueError(
                        f"Invalid quantity for posting an order. quantity={quantity}"
                    )
                posted_order = await client.post_order(
                    order_id=str(uuid4()),
                    direction=ORDER_DIRECTION_BUY,
                    quantity=int(quantity),
                    order_type=ORDER_TYPE_MARKET,
                    account_id=self.account_id,
                    instrument_id=self.figi,
                )
            except Exception as e:
                logger.error(f"Failed to post buy order. figi={self.figi}. error={e}")
                return
            await asyncio.create_task(
                self.stats_handler.handle_new_order(
                    order_id=posted_order.order_id, account_id=self.account_id
                )
            )

    async def get_last_price(self):
        last_prices_response = await client.get_last_prices(instrument_id=[self.figi])
        last_prices = last_prices_response.last_prices
        return quotation_to_float(last_prices.pop().price)

    async def validate_stop_loss(self, last_price: float):
        positions = (await client.get_portfolio(account_id=self.account_id)).positions
        position = get_position(positions, self.figi)
        if position is None or quotation_to_float(position.quantity) == 0:
            return
        position_price = quotation_to_float(position.average_position_price)
        if (
            last_price
            <= position_price - position_price * self.config.stop_loss_percent
        ):
            logger.info(
                f"Stop loss triggered. Last price={last_price} figi={self.figi}"
            )
            try:
                quantity = (
                    int(quotation_to_float(position.quantity))
                    / self.instrument_info.lot
                )
                if not is_quantity_valid(quantity):
                    raise ValueError(
                        f"Invalid quantity for posting an order. quantity={quantity}"
                    )
                posted_order = await client.post_order(
                    order_id=str(uuid4()),
                    direction=ORDER_DIRECTION_SELL,
                    quantity=int(quantity),
                    order_type=ORDER_TYPE_MARKET,
                    account_id=self.account_id,
                )
            except Exception as e:
                logger.error(f"Failed to post sell order. figi={self.figi}. error={e}")
                return
            await asyncio.create_task(
                self.stats_handler.handle_new_order(
                    order_id=posted_order.order_id, account_id=self.account_id
                )
            )
        return

    async def ensure_market_open(self):
        trading_status = await client.get_trading_status(instrument_id=self.figi)
        while not (
            trading_status.market_order_available_flag
            and trading_status.limit_order_available_flag
        ):
            logger.debug(
                f"Waiting for market to open. figi={self.figi}. time={datetime.datetime.now()}"
            )
            await asyncio.sleep(60)
            trading_status = await client.get_trading_status(instrument_id=self.figi)

    async def prepare_data(self):
        self.instrument_info = (
            await client.get_instrument(id_type=INSTRUMENT_ID_TYPE_FIGI, id=self.figi)
        ).instrument

    async def main_cycle(self):
        await self.prepare_data()
        logger.info(
            f"Starting scalpel strategy for figi={self.figi}"
            f"({self.instrument_info.name} {self.instrument_info.currency}) lot size is {self.instrument_info.lot}."
            f"Configuration is : {self.config}"
        )
        while True:
            try:
                await self.ensure_market_open()
                df = await self.add_signal(await self.add_indicators())
                orders = await client.get_orders(account_id=self.account_id)
                if get_order(orders=orders.orders, figi=self.figi):
                    logger.info(
                        f"There are orders in progress. Waiting. figi={self.figi}"
                    )
                    continue
                last_price = await self.get_last_price()
                logger.debug(f"Last price: {last_price}, figi={self.figi}")
                await self.validate_stop_loss(last_price)
                if df.TotalSignal.iloc[-1] == 2:
                    logger.info(
                        f"Triggered buy order for figi={self.figi}. Last price={last_price}"
                    )
                    await self.buy_order(last_price)
                elif df.TotalSignal.iloc[-1] == 1:
                    logger.info(
                        f"Triggered sell order for figi={self.figi}. Last price={last_price}"
                    )
                    await self.sell_order(last_price)
                else:
                    logger.info(f"No signal. figi={self.figi}")
            except AioRequestError as er:
                logger.error(f"Error in main cycle. Stopping strategy. {er}")
            await asyncio.sleep(self.config.check_data)

    async def start(self):
        if self.account_id is None:
            try:
                self.account_id = (await client.get_accounts()).accounts.pop().id
            except AioRequestError as er:
                logger.error(f"Error taking account id. Stopping strategy. {er}")
                return
        await self.main_cycle()
