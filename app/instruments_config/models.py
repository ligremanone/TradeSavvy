from typing import Any, Dict, List

from pydantic import BaseModel


class StrategyConfig(BaseModel):
    name: str
    parameters: Dict[str, Any]


class InstrumentConfig(BaseModel):
    figi: str
    strategy: StrategyConfig


class InstrumentsConfig(BaseModel):
    instruments: List = List[InstrumentConfig]
