from pathlib import Path

from app.instruments_config.models import InstrumentsConfig

project_dir = Path(__file__).resolve().parent.parent.parent


def get_instruments(
    filename: str = Path(project_dir, "instruments_config_scalpel.json"),
) -> InstrumentsConfig:
    with open(filename, "r") as f:
        data = f.read()
        return InstrumentsConfig.model_validate_json(data)


instruments_config = get_instruments()
