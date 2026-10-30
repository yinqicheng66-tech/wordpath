from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or the repo-root .env file."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+pg8000://wordpath:wordpath@localhost:5432/wordpath"
    jwt_secret: str = "change-me"


settings = Settings()
