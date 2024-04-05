from typing import List, Optional
from tinkoff.invest.schemas import OrderState, PortfolioPosition


def get_position(
    positions: List[PortfolioPosition], figi: str
) -> Optional[PortfolioPosition]:
    for position in positions:
        if position.figi == figi:
            return position
    return None


def get_order(orders: List[OrderState], figi: str) -> Optional[OrderState]:
    for order in orders:
        if order.figi == figi:
            return order
    return None
