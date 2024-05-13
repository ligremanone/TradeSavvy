import logging

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "TradeSavvy"
    token: str
    account_id: str
    sandbox: bool
    use_candle_history_cache: bool = True
    log_level: int = logging.DEBUG
    tinkoff_library_log_level: int = logging.INFO

    class Config:
        env_file = "../.env"


settings = Settings()
