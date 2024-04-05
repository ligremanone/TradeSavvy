import math
from typing import Union
from tinkoff.invest import Quotation, MoneyValue


def quotation_to_float(quotation: Union[Quotation, MoneyValue]) -> float:
    return float(quotation.units + quotation.nano / 1e9)


def float_to_quotation(value: float) -> Quotation:
    return Quotation(*math.modf(value))
