from pydantic import BaseModel, Field


class ScalpelStrategyConfig(BaseModel):
    days_back_to_consider: int = Field(1, g=0)
    stop_loss_percent: float = Field(0.05, ge=0.0, le=1.0)
    quantity_limit: int = Field(1, ge=0)
    check_data: int = Field(60, g=0)
