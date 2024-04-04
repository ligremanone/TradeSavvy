from app.instruments_config.models import InstrumentsConfig


def get_instruments(
    filename: str = "../../instruments_config_scalpel.json",
) -> InstrumentsConfig:
    with open(filename, "r") as f:
        data = f.read()
        return InstrumentsConfig.model_validate_json(data)


instruments_config = get_instruments()
