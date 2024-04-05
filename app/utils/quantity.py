from typing import Union


def is_quantity_valid(quantity: Union[int, float]) -> bool:
    if isinstance(quantity, (int, float)):
        return quantity.is_integer() and quantity > 0
