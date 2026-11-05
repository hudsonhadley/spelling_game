"""Application configuration."""

from pathlib import Path

from dotenv import dotenv_values

# TODO: Before deploying, remove this placeholder. Put a long random SECRET_KEY
# in .appenv (generate one with: python -c "import secrets; print(secrets.token_hex(32))")
# and have get_config() raise ValueError when it is missing instead of falling
# back to this publicly visible key.
DEV_SECRET_KEY = "dev-only-placeholder-key-change-me"


def get_config() -> type:
    package_dir: Path = Path(__file__).parent.resolve()
    project_dir: Path = package_dir.parent.parent.resolve()

    appenv_path: Path = project_dir / ".appenv"
    env: dict[str, str | None] = dotenv_values(appenv_path)

    secret_key: str = env.get("SECRET_KEY") or DEV_SECRET_KEY

    class Config:
        SECRET_KEY: str = secret_key

    return Config
