from typing import Dict

from app.strategies.base import BaseStrategy
from app.strategies.errors import UnsupportedStrategyError
from app.strategies.models import StrategyName
from app.strategies.scalpel.scalpel import ScalpelStrategy

strategies: Dict[StrategyName, BaseStrategy.__class__] = {
    StrategyName.SCALPEL.value: ScalpelStrategy,
}


def resolve_strategy(
    strategy_name: StrategyName, figi: str, *args, **kwargs
) -> BaseStrategy:
    if strategy_name not in strategies:
        raise UnsupportedStrategyError(strategy_name)
    return strategies[strategy_name](figi, *args, **kwargs)
