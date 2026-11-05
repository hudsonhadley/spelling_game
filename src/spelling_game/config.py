"""Application configuration."""

from pathlib import Path
import os
from secrets import token_hex

from dotenv import dotenv_values

# Development sessions expire when this process restarts unless SECRET_KEY is set.
DEV_SECRET_KEY = token_hex(32)


def get_config() -> type:
    package_dir: Path = Path(__file__).parent.resolve()
    project_dir: Path = package_dir.parent.parent.resolve()

    appenv_path: Path = project_dir / ".appenv"
    env: dict[str, str | None] = dotenv_values(appenv_path)

    secret_key: str = os.environ.get("SECRET_KEY") or env.get("SECRET_KEY") or DEV_SECRET_KEY

    # Merriam-Webster Collegiate Dictionary API key (https://dictionaryapi.com).
    # Set MW_API_KEY in .appenv. Stays server-side; never sent to the browser.
    mw_api_key: str | None = os.environ.get("MW_API_KEY") or env.get("MW_API_KEY") or None

    class Config:
        SECRET_KEY: str = secret_key
        MW_API_KEY: str | None = mw_api_key

    return Config
