from app.strategies.models import StrategyName


class UnsupportedStrategyError(Exception):
    def __init__(self, strategy_name: StrategyName):
        self.strategy_name = strategy_name

    def __str__(self):
        return f"Strategy {self.strategy_name} is not supported"
