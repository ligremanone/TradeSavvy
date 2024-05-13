import asyncio
import glob

import pandas as pd
from backtesting import Backtest, Strategy
from pandas import DataFrame
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice

from app.strategies.scalpel.scalpel import ScalpelStrategy

pd.set_option("display.max_columns", None)
path = r"data"


def create_df(data_path: str) -> DataFrame:
    dfs = []
    filenames = glob.glob(data_path + "/*.csv")
    for filename in filenames:
        data = pd.read_csv(
            filename,
            delimiter=";",
            header=0,
            names=["UID", "Time", "Open", "Close", "High", "Low", "Volume", "NaN"],
        )
        dfs.append(data)

    big_frame = pd.concat(dfs, ignore_index=True).dropna(axis=1)
    big_frame["Time"] = big_frame["Time"].str.replace("Z", "")
    big_frame["Time"] = big_frame["Time"].str.replace("T", " ")
    big_frame["Time"] = pd.to_datetime(big_frame["Time"], format="%Y-%m-%d %H:%M:%S")
    big_frame.set_index("Time", inplace=True)
    big_frame = big_frame[big_frame.High != big_frame.Low]

    bbands = BollingerBands(close=big_frame["Close"], window=14, window_dev=2)
    big_frame = big_frame.join(
        [
            bbands.bollinger_hband(),
            bbands.bollinger_hband_indicator(),
            bbands.bollinger_lband(),
            bbands.bollinger_lband_indicator(),
            bbands.bollinger_mavg(),
            bbands.bollinger_pband(),
            bbands.bollinger_wband(),
        ]
    )
    big_frame["VWAP"] = VolumeWeightedAveragePrice(
        high=big_frame["High"],
        low=big_frame["Low"],
        close=big_frame["Close"],
        volume=big_frame["Volume"],
        window=7,
    ).volume_weighted_average_price()
    big_frame["RSI"] = RSIIndicator(close=big_frame["Close"], window=16).rsi()
    big_frame["ATR"] = AverageTrueRange(
        high=big_frame["High"],
        low=big_frame["Low"],
        close=big_frame["Close"],
        window=16,
    ).average_true_range()
    big_frame["EMA_slow"] = EMAIndicator(
        close=big_frame["Close"], window=50
    ).ema_indicator()
    big_frame["EMA_fast"] = EMAIndicator(
        close=big_frame["Close"], window=30
    ).ema_indicator()
    return big_frame


scalpel = ScalpelStrategy()
data_frame = asyncio.run(scalpel.add_signal(df=create_df(path)))


def signal():
    return data_frame.TotalSignal


class MyStrategy(Strategy):
    trade_size = 25
    slcoef = 1.0
    TPSLRatio = 1.0

    def init(self):
        super().init()
        self.signal1 = self.I(
            signal,
        )

    def next(self):
        super().next()
        slatr = self.slcoef * self.data.ATR[-1]
        TPSLRatio = self.TPSLRatio
        if self.signal1 == 2 and len(self.trades) == 0:
            sl1 = self.data.Close[-1] - slatr
            tp1 = self.data.Close[-1] + slatr * TPSLRatio
            self.buy(sl=sl1, tp=tp1)
        elif self.signal1 == 1 and len(self.trades) == 0:
            sl1 = self.data.Close[-1] + slatr
            tp1 = self.data.Close[-1] - slatr * TPSLRatio
            self.sell(sl=sl1, tp=tp1)


if __name__ == "__main__":
    bt = Backtest(data_frame, MyStrategy, cash=100_000)
    print(bt.run())
    bt.plot(resample=False)
